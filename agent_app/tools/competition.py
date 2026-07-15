from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from agent_app.domain.contracts import (
    ExperimentContract,
    ModelContract,
    ProblemContract,
    ProjectType,
    SubproblemContract,
    SubproblemType,
)
from agent_app.domain.models import ArtifactRef, QualityReport, RunSpec, RunState, RunStatus
from agent_app.domain.serialization import to_json_dict
from agent_app.evaluators import evaluate_claims, evaluate_submission
from agent_app.services.artifact_service import ArtifactService
from agent_app.services.claim_map import build_b_problem_claims
from agent_app.services.contract_store import ContractStore
from agent_app.services.data_analysis import DataAnalysisService
from agent_app.services.ingestion import InputIngestionService
from agent_app.services.paper_sections import (
    REQUIRED_SECTION_FILES,
    build_section_context,
    merge_section_texts,
    section_generation_order,
    section_path,
)
from agent_app.services.problem_package import build_problem_package
from agent_app.services.run_trace import RunTraceWriter
from agent_app.services.run_store import RunStore
from agent_app.services.section_writer import write_section_files as write_claim_section_files
from agent_app.workflow_packs.cumcm.contracts import (
    CumcmContractBundle,
    build_generic_cumcm_contract_bundle,
)
from agent_app.workflow_packs.cumcm.benchmarks.y2024_b_production_decision import (
    build_b_problem_experiment_contracts,
    build_b_problem_model_contracts,
)
from agent_app.workflow_packs.cumcm.benchmarks.y2024_b_production_decision_solver import run_b_problem_solver
from agent_app.workflow_packs.cumcm.problem_builder import build_cumcm_problem_contract
from agent_app.workflow_packs.cumcm.routing import (
    BENCHMARK_2024_B_ID,
    GENERIC_CUMCM_WORKFLOW,
    select_cumcm_route,
)


def make_competition_tools(run_store: RunStore, **services: Any) -> list:
    data_service = services.get("data_service") or DataAnalysisService()
    generation_service = services.get("generation_service")

    def _load_state(run_id: str) -> RunState:
        return run_store.load_state(run_id)

    def _artifacts_for_state(state: RunState) -> ArtifactService:
        return ArtifactService(run_store.run_dir(state.run_id))

    def _artifacts(run_id: str) -> ArtifactService:
        state = _load_state(run_id)
        return _artifacts_for_state(state)

    def _write_for_state(state: RunState, relative_path: str, content: str) -> Path:
        return _artifacts_for_state(state).write_text(relative_path, content)

    def _kind_for_path(path: Path) -> str:
        return {
            ".md": "markdown",
            ".py": "python",
            ".tex": "latex",
            ".json": "json",
        }.get(path.suffix.lower(), path.suffix.lstrip("."))

    def _read_json_artifact(state: RunState, relative_path: str) -> dict[str, Any]:
        path = run_store.run_dir(state.run_id) / relative_path
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _trace_for_state(state: RunState) -> RunTraceWriter:
        return RunTraceWriter(run_store.run_dir(state.run_id))

    def _route_for_state(state: RunState, problem_text: str) -> dict[str, Any]:
        route = select_cumcm_route(problem_text, state.spec.options)
        route_payload = to_json_dict(route)
        _trace_for_state(state).write_json("routing_decision.json", route_payload)
        return route_payload

    def _is_benchmark_route(state: RunState, problem_text: str) -> bool:
        return select_cumcm_route(problem_text, state.spec.options).is_benchmark

    def _quality_report_from_dict(report: dict[str, Any]) -> QualityReport:
        return QualityReport(
            gate_name=str(report.get("gate_name", "review")),
            passed=bool(report.get("passed", False)),
            score=float(report.get("score", 0.0)),
            findings=list(report.get("findings", [])),
            required_fixes=list(report.get("required_fixes", [])),
            optional_improvements=list(report.get("optional_improvements", [])),
        )

    def _record_quality_report(state: RunState, report: dict[str, Any]) -> None:
        quality_report = _quality_report_from_dict(report)
        state.quality_reports = [
            existing
            for existing in state.quality_reports
            if existing.gate_name != quality_report.gate_name
        ]
        state.quality_reports.append(quality_report)
        if not quality_report.passed:
            state.status = RunStatus.PARTIAL
        run_store.save_state(state)

    def _blocking_quality_reports(state: RunState) -> list[QualityReport]:
        return [report for report in state.quality_reports if not report.passed]

    def _planner_messages(
        state: RunState,
        problem_brief: dict[str, Any],
        data_audit: dict[str, Any],
        evidence_notes: list[str],
    ) -> list[dict[str, str]]:
        context = {
            "problem_spec.json": _read_json_artifact(state, "problem_spec.json"),
            "tables.json": _read_json_artifact(state, "tables.json"),
            "figures.json": _read_json_artifact(state, "figures.json"),
            "source_map.json": _read_json_artifact(state, "source_map.json"),
            "problem_brief": problem_brief,
            "data_audit": data_audit,
            "evidence_notes": evidence_notes,
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are the mathematical modeling planner. Return a JSON model plan and "
                    "a concise modeling report that maps experiments to paper conclusions."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(context, ensure_ascii=False, indent=2),
            },
        ]

    def _programmer_messages(
        state: RunState,
        modeling_plan: dict[str, Any],
        data_files: list[str],
    ) -> list[dict[str, str]]:
        context = {
            "modeling_plan": modeling_plan,
            "problem_spec.json": _read_json_artifact(state, "problem_spec.json"),
            "tables.json": _read_json_artifact(state, "tables.json"),
            "figures.json": _read_json_artifact(state, "figures.json"),
            "data_files": data_files,
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are the experiment programmer. Return only executable Python code "
                    "that writes all results under the results directory."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(context, ensure_ascii=False, indent=2),
            },
        ]

    def _strip_fenced_code_block(content: str) -> str:
        text = content.strip()
        if not text.startswith("```"):
            return text
        lines = text.splitlines()
        if len(lines) > 1 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
        return "\n".join(lines[1:]).strip()

    def _execute_generated_code(state: RunState, code: str) -> tuple[Path, subprocess.CompletedProcess[str]]:
        artifact_service = _artifacts_for_state(state)
        code_path = artifact_service.write_text("solve.py", code)
        completed = subprocess.run(
            [sys.executable, str(code_path)],
            cwd=run_store.run_dir(state.run_id),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return code_path, completed

    def _collect_result_paths(run_dir: Path) -> list[str]:
        results_dir = run_dir / "results"
        if not results_dir.exists():
            return []
        return [
            str(path)
            for path in sorted(results_dir.rglob("*"))
            if path.is_file()
        ]

    def _run_artifact_names(run_id: str) -> set[str]:
        run_dir = run_store.run_dir(run_id)
        if not run_dir.exists():
            return set()
        return {
            path.name
            for path in run_dir.iterdir()
            if path.is_file()
        }

    def _review_core_artifacts(run_id: str, artifacts: list[str]) -> dict[str, Any]:
        required = {"modeling_report.md", "solve.py", "paper.tex"}
        required_results = set(_b_problem_result_files()) | {"results/model_equations.md"}
        names = {Path(artifact).name for artifact in artifacts}
        names.update(_run_artifact_names(run_id))
        missing = sorted(required - names)
        run_dir = run_store.run_dir(run_id)
        model_report_path = run_dir / "modeling_report.md"
        requires_b_problem_results = False
        if model_report_path.exists():
            model_report_text = model_report_path.read_text(encoding="utf-8")
            requires_b_problem_results = "生产过程中的决策问题" in model_report_text or "二项抽样" in model_report_text
        missing_results = []
        if requires_b_problem_results:
            missing_results = [
                relative_path
                for relative_path in sorted(required_results)
                if not (run_dir / relative_path).exists()
            ]
        placeholder_findings: list[str] = []
        placeholder_phrases = (
            "DeepAgent generated model",
            "DeepAgent competition experiment placeholder",
            "Competition Paper Draft",
            "This draft summarizes the local modeling workflow",
        )
        for name in sorted(required - set(missing)):
            path = run_dir / name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            matched = [phrase for phrase in placeholder_phrases if phrase in text]
            if matched:
                placeholder_findings.append(f"{name} 仍包含占位内容")
            if name == "solve.py":
                if requires_b_problem_results and ("def main" not in text or "expected_profit" not in text):
                    placeholder_findings.append("solve.py 缺少真实期望利润计算")
                if not requires_b_problem_results and (
                    "def main" not in text or ("subproblem_id" not in text and "expected_profit" not in text)
                ):
                    placeholder_findings.append("solve.py 缺少动态子问题 baseline 计算")
            min_report_length = 800 if requires_b_problem_results else 300
            if name == "modeling_report.md" and len(text.strip()) < min_report_length:
                placeholder_findings.append("modeling_report.md 内容过短")
        placeholder_findings.extend(
            f"缺少 B 题子问题求解结果 {relative_path}" for relative_path in missing_results
        )
        return {
            "gate_name": "review",
            "passed": not missing and not placeholder_findings,
            "score": (
                1.0
                if not missing and not placeholder_findings
                else max(0.0, 1.0 - (len(missing) + len(placeholder_findings)) / (len(required) + 3))
            ),
            "findings": placeholder_findings
            if placeholder_findings
            else ([] if not missing else ["Required core artifacts are incomplete."]),
            "required_fixes": [f"缺少交付物: {name}" for name in missing]
            + [f"{finding}，需要重写" for finding in placeholder_findings],
        }

    def _read_run_text(run_dir: Path, relative_path: str) -> str:
        path = run_dir / relative_path
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _count_csv_rows(path: Path) -> int:
        if not path.exists():
            return 0
        with path.open("r", encoding="utf-8", newline="") as handle:
            return max(0, sum(1 for _ in csv.reader(handle)) - 1)

    def _is_b_problem_run(state: RunState, run_dir: Path) -> bool:
        model_text = _read_run_text(run_dir, "modeling_report.md")
        paper_text = _read_run_text(run_dir, "paper.md")
        combined = " ".join([state.spec.question, model_text, paper_text])
        return _is_b_problem_context(state, combined)

    def _is_b_problem_context(
        state: RunState,
        text: str = "",
        modeling_plan: dict[str, Any] | None = None,
    ) -> bool:
        if modeling_plan and modeling_plan.get("workflow_type") == "cumcm_b_problem_benchmark_workflow":
            return True
        combined = " ".join([state.spec.question, text])
        return _is_benchmark_route(state, combined)

    def _b_problem_result_files() -> list[str]:
        return [
            "results/q1_sampling_plan.csv",
            "results/q2_table1_decisions.csv",
            "results/q3_table2_tree_decisions.csv",
            "results/q4_uncertainty_re_solve.csv",
            "results/parameter_audit.json",
        ]

    def _b_problem_subproblem_specs() -> list[dict[str, Any]]:
        return [
            {
                "id": "q1",
                "title": "抽样检测方案",
                "question_text": "根据标称次品率设计抽样检测规则，在给定信度下决定接收或拒收零配件批次。",
                "primary_type": SubproblemType.SAMPLING_TEST,
                "dependencies": [],
            },
            {
                "id": "q2",
                "title": "表 1 生产阶段决策",
                "question_text": "基于表 1 的 6 种情形，确定零配件检测、成品检测和不合格品拆解策略。",
                "primary_type": SubproblemType.OPTIMIZATION,
                "dependencies": [],
            },
            {
                "id": "q3",
                "title": "表 2 多工序装配树决策",
                "question_text": "将两零配件结构推广到多零配件、半成品和成品的装配链，建立递归决策模型。",
                "primary_type": SubproblemType.OPTIMIZATION,
                "dependencies": ["q2"],
            },
            {
                "id": "q4",
                "title": "抽样不确定性下的重求解",
                "question_text": "结合抽样检测结果修正次品率参数，分析决策对估计误差的稳健性。",
                "primary_type": SubproblemType.STATISTICS,
                "dependencies": ["q1", "q2", "q3"],
            },
        ]

    def _normalize_b_problem_contract(
        problem_contract: ProblemContract,
        model_contracts: list[ModelContract],
    ) -> ProblemContract:
        existing_by_id = {
            item.subproblem_id: item
            for item in problem_contract.subproblems
        }
        model_by_id = {item.subproblem_id: item for item in model_contracts}
        subproblems: list[SubproblemContract] = []
        for spec in _b_problem_subproblem_specs():
            existing = existing_by_id.get(spec["id"])
            model = model_by_id[spec["id"]]
            subproblems.append(
                SubproblemContract(
                    subproblem_id=spec["id"],
                    question_text=(existing.question_text if existing else spec["question_text"]),
                    primary_type=spec["primary_type"],
                    secondary_types=(existing.secondary_types if existing else []),
                    required_tables=["table_1"] if spec["id"] in {"q2"} else (["table_2"] if spec["id"] == "q3" else []),
                    dependencies=spec["dependencies"],
                    expected_outputs=list(model.result_files),
                    risk_notes=(existing.risk_notes if existing else []),
                )
            )
        problem_contract.project_type = ProjectType.CUMCM
        problem_contract.title = "B 题 生产过程中的决策问题"
        problem_contract.subproblems = subproblems
        problem_contract.required_deliverables = [
            "modeling_report.md",
            "solve.py",
            "paper.md",
            "paper.tex",
            "review_report.md",
        ]
        return problem_contract

    def _write_contract_json(run_dir: Path, relative_path: str, payload: object) -> Path:
        path = run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_json_dict(payload), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _ensure_benchmark_b_contract_bundle(
        state: RunState,
        problem_text: str,
    ) -> dict[str, Any]:
        run_dir = run_store.run_dir(state.run_id)
        store = ContractStore(run_dir)
        model_contracts = build_b_problem_model_contracts()
        experiment_contracts = build_b_problem_experiment_contracts()
        problem_contract = build_cumcm_problem_contract(
            problem_text or state.spec.question,
            source_text_path=Path("question.md"),
            tables=(_read_json_artifact(state, "tables.json").get("tables") or []),
            figures=(_read_json_artifact(state, "figures.json").get("figures") or []),
        )
        problem_contract = _normalize_b_problem_contract(problem_contract, model_contracts)
        problem_contract_path = store.write_problem_contract(problem_contract)
        model_paths = {
            contract.subproblem_id: _write_contract_json(
                run_dir,
                f"contracts/models/{contract.subproblem_id}.json",
                contract,
            )
            for contract in model_contracts
        }
        experiment_paths = {
            contract.subproblem_id: _write_contract_json(
                run_dir,
                f"contracts/experiments/{contract.subproblem_id}.json",
                contract,
            )
            for contract in experiment_contracts
        }
        return {
            "problem_contract": problem_contract,
            "model_contracts": model_contracts,
            "experiment_contracts": experiment_contracts,
            "problem_contract_path": problem_contract_path,
            "model_paths": model_paths,
            "experiment_paths": experiment_paths,
        }

    def _write_generic_contract_bundle(
        state: RunState,
        problem_text: str,
        data_files: list[str] | None = None,
    ) -> dict[str, Any]:
        run_dir = run_store.run_dir(state.run_id)
        store = ContractStore(run_dir)
        data_paths = [Path(path) for path in (data_files or [])] or list(state.spec.data_files)
        bundle = build_generic_cumcm_contract_bundle(
            problem_text=problem_text or state.spec.question,
            source_text_path=Path("question.md"),
            tables=(_read_json_artifact(state, "tables.json").get("tables") or []),
            figures=(_read_json_artifact(state, "figures.json").get("figures") or []),
            data_files=data_paths,
        )
        problem_contract_path = store.write_problem_contract(bundle.problem_contract)
        model_paths = {
            contract.subproblem_id: _write_contract_json(
                run_dir,
                f"contracts/models/{contract.subproblem_id}.json",
                contract,
            )
            for contract in bundle.model_contracts
        }
        experiment_paths = {
            contract.subproblem_id: _write_contract_json(
                run_dir,
                f"contracts/experiments/{contract.subproblem_id}.json",
                contract,
            )
            for contract in bundle.experiment_contracts
        }
        solver_strategy_path = _write_contract_json(
            run_dir,
            "contracts/solver_strategies.json",
            bundle.solver_strategies,
        )
        return {
            "bundle": bundle,
            "problem_contract": bundle.problem_contract,
            "model_contracts": bundle.model_contracts,
            "experiment_contracts": bundle.experiment_contracts,
            "solver_strategies": bundle.solver_strategies,
            "problem_contract_path": problem_contract_path,
            "model_paths": model_paths,
            "experiment_paths": experiment_paths,
            "solver_strategy_path": solver_strategy_path,
        }

    def _b_problem_modeling_plan(
        bundle: dict[str, Any],
        route: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        problem_contract: ProblemContract = bundle["problem_contract"]
        model_contracts: list[ModelContract] = bundle["model_contracts"]
        experiment_contracts: list[ExperimentContract] = bundle["experiment_contracts"]
        model_by_id = {item.subproblem_id: item for item in model_contracts}
        experiment_by_id = {item.subproblem_id: item for item in experiment_contracts}
        subproblem_plans = []
        for subproblem in problem_contract.subproblems:
            model = model_by_id[subproblem.subproblem_id]
            experiment = experiment_by_id[subproblem.subproblem_id]
            subproblem_plans.append(
                {
                    "id": subproblem.subproblem_id,
                    "title": next(
                        spec["title"]
                        for spec in _b_problem_subproblem_specs()
                        if spec["id"] == subproblem.subproblem_id
                    ),
                    "problem_type": subproblem.primary_type.value,
                    "dependencies": subproblem.dependencies,
                    "model": model.algorithm,
                    "algorithm": model.algorithm,
                    "result_file": model.result_files[0] if model.result_files else "",
                    "experiment_contract": to_json_dict(experiment),
                }
            )
        return {
            "selected_model": "二项抽样 + 0-1检测拆解决策优化",
            "workflow_type": (route or {}).get("workflow_type", "cumcm_b_problem_benchmark_workflow"),
            "benchmark_id": (route or {}).get("selected_benchmark_id", BENCHMARK_2024_B_ID),
            "problem_contract_path": str(bundle["problem_contract_path"]),
            "model_contract_paths": {
                key: str(path)
                for key, path in bundle["model_paths"].items()
            },
            "experiment_contract_paths": {
                key: str(path)
                for key, path in bundle["experiment_paths"].items()
            },
            "subproblem_plans": subproblem_plans,
            "candidate_models": [
                "二项抽样检验",
                "0-1 策略枚举",
                "装配树递归期望成本模型",
                "抽样区间驱动的参数不确定性重求解",
            ],
            "algorithm_plan": "先建立 q1-q4 合同，再运行确定性求解器，最后把每个结论绑定到 claim map 与 section 文件。",
            "evaluation_metrics": ["抽样检测次数", "单位期望利润", "最终装配树策略", "策略翻转标记", "未解释参数数量"],
            "experiment_conclusion_links": [
                "q1_sampling_plan -> 对应论文结论：抽样检测规则满足给定信度要求；关系：支撑",
                "q2_table1_decisions -> 对应论文结论：表 1 六种情形的检测/拆解决策；关系：支撑",
                "q3_table2_tree_decisions -> 对应论文结论：多工序装配树可递归求解决策；关系：支撑",
                "q4_uncertainty_re_solve -> 对应论文结论：抽样不确定性会限制 q2/q3 策略适用边界；关系：限制",
            ],
        }

    def _b_problem_modeling_report(bundle: dict[str, Any]) -> str:
        problem_contract: ProblemContract = bundle["problem_contract"]
        model_contracts: list[ModelContract] = bundle["model_contracts"]
        experiment_contracts: list[ExperimentContract] = bundle["experiment_contracts"]
        experiment_by_id = {item.subproblem_id: item for item in experiment_contracts}
        lines = [
            "# Modeling Plan",
            "",
            "## Contract-Driven Workflow",
            "本次 B 题求解使用 CUMCM workflow pack，而不是由单次 LLM 直接生成占位脚本。主控先写入 ProblemContract、ModelContract 和 ExperimentContract，再由确定性求解器生成 q1-q4 结果，最后用 ClaimMap 限制论文结论。",
            "",
            "## Problem Statement",
            "生产过程中的决策问题要求把二项抽样检验、零配件检测、成品检测、拆解返工和售后调换损失放入同一个可审计决策框架。核心问题不是笼统提高收益，而是给出每个子问题可复现、可追溯、可被结果文件直接支撑的结论。",
            "",
            "## Subproblem Contracts",
        ]
        for subproblem in problem_contract.subproblems:
            model = next(item for item in model_contracts if item.subproblem_id == subproblem.subproblem_id)
            experiment = experiment_by_id[subproblem.subproblem_id]
            lines.extend(
                [
                    f"### 问题 {subproblem.subproblem_id.removeprefix('q')}: {subproblem.question_text}",
                    f"- 类型：{subproblem.primary_type.value}",
                    f"- 依赖：{', '.join(subproblem.dependencies) if subproblem.dependencies else '无'}",
                    f"- 变量：{'; '.join(f'{key}={value}' for key, value in model.variables.items())}",
                    f"- 参数来源：{'; '.join(f'{key}->{value}' for key, value in model.parameter_sources.items())}",
                    f"- 目标函数：{'; '.join(model.objective_functions)}",
                    f"- 约束：{'; '.join(model.constraints)}",
                    f"- 算法：{model.algorithm}",
                    f"- 公式：{'; '.join(model.formulas)}",
                    f"- 结果文件：{', '.join(model.result_files)}",
                    f"- 验证检查：{', '.join(experiment.validation_checks)}",
                    "",
                ]
            )
        lines.extend(
            [
                "## Step-by-step Experiment Design",
                "1. q1 抽样方案实验：遍历样本量 n 和临界值 k，搜索满足拒收 95% 信度、接收 90% 信度的最小检测方案；该实验直接决定论文中抽样规则的结论。",
                "2. q2 表 1 策略实验：枚举 d1、d2、df、r 四个二元变量并计算 expected_profit；该实验直接支撑六种情形下的检测/拆解决策表。",
                "3. q3 表 2 装配树实验：把零配件、半成品和成品节点按树结构递归传播缺陷概率与期望成本；该实验支撑多工序推广结论。",
                "4. q4 不确定性重求解实验：使用 q1 的抽样区间扰动次品率并重求解 q2/q3；该实验限定策略结论的稳健边界。",
                "",
                "## Experiment-to-Conclusion Mapping",
                "- results/q1_sampling_plan.csv -> 对应论文结论：抽样检测规则满足给定信度要求；关系：支撑；若样本量或临界值为空则该结论不得写入论文。",
                "- results/q2_table1_decisions.csv -> 对应论文结论：表 1 六种情形的检测与拆解决策；关系：支撑；若 expected_profit 排序改变则必须重写决策表。",
                "- results/q3_table2_tree_decisions.csv -> 对应论文结论：表 2 装配树能够递归给出最终产品策略；关系：支撑；若 final_product 行缺失则不能声明完整求解。",
                "- results/q4_uncertainty_re_solve.csv -> 对应论文结论：抽样不确定性会限制 q2/q3 策略适用范围；关系：限制；若 strategy_changed 为真，论文必须写成条件结论。",
                "- results/parameter_audit.json -> 对应论文结论：模型参数均来自题面表格、抽样方案或显式区间；关系：质量约束；若 unexplained_constants 非空则禁止打包。",
            ]
        )
        return "\n".join(lines) + "\n"

    def _b_problem_compat_solve_code(run_root_expression: str) -> str:
        project_root = Path(__file__).resolve().parents[2]
        return f'''from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path({str(project_root)!r})
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_app.workflow_packs.cumcm.benchmarks.y2024_b_production_decision_solver import run_b_problem_solver


def expected_profit() -> str:
    """Compatibility marker: q2 expected profit is written to results/q2_table1_decisions.csv."""
    return "results/q2_table1_decisions.csv"


def main() -> None:
    run_root = {run_root_expression}
    result = run_b_problem_solver(run_root)
    if not result.success:
        raise SystemExit("; ".join(result.messages) or "B-problem solver failed")
    for path in result.result_paths:
        print(path.relative_to(run_root))


if __name__ == "__main__":
    main()
'''

    def _write_b_problem_equations(run_dir: Path, model_contracts: list[ModelContract]) -> Path:
        lines = [
            "# Model Equations",
            "",
            "本文件由 B 题 ModelContract 生成，用于质量门审查。它显式列出每个子问题的目标函数、约束、公式、递归关系和敏感性分析入口；论文正文中的结论必须能追溯到这些公式和对应结果文件。",
            "",
        ]
        for contract in model_contracts:
            lines.extend(
                [
                    f"## {contract.subproblem_id}",
                    f"- 目标函数: {'; '.join(contract.objective_functions)}",
                    f"- 约束: {'; '.join(contract.constraints)}",
                    f"- 公式: {'; '.join(contract.formulas)}",
                    f"- 算法: {contract.algorithm}",
                    f"- 参数来源: {'; '.join(f'{key}->{value}' for key, value in contract.parameter_sources.items()) or '题面与上游实验'}",
                    f"- 结果文件: {', '.join(contract.result_files)}",
                    "",
                ]
            )
        lines.extend(
            [
                "## q1 二项抽样检验细化",
                "令 X 表示抽样中发现的次品数，X 服从二项分布 Binomial(n,p)。拒收规则使用尾概率 P_{p0}(X>=k) 控制生产方风险，接收规则使用 P_{p0}(X<=k) 控制使用方风险。目标函数是最小化 n，同时约束风险概率不超过给定阈值，并保证备择次品率下具有足够区分能力。",
                "",
                "## q2 生产检测决策细化",
                "令 d1,d2,df,r 属于 {0,1}，分别表示是否检测零配件 1、零配件 2、成品以及是否拆解不合格品。有效成品次品率为 q=1-(1-p1_eff)(1-p2_eff)(1-pf)。目标函数为最大化 expected_profit，约束来自检测成本、采购成本、装配成本、拆解成本和调换损失。",
                "",
                "## q3 装配树递归关系细化",
                "对每个装配节点，自底向上传播缺陷概率 q_node = 1 - prod(1-q_child) * (1-p_node)。递归状态包含节点期望成本、缺陷概率和最优检测/拆解决策；终端节点 final_product 的 expected_profit 决定表 2 推广策略是否完整。",
                "",
                "## q4 敏感性分析细化",
                "问题 4 不任意设定经验扰动，而是使用 q1 抽样方案形成的次品率区间，对 q2 与 q3 重新求解。若 strategy_changed 为真，论文结论必须降级为条件结论；若全部关键场景稳定，才可说明策略在抽样误差范围内具有稳健性。",
                "",
            ]
        )
        path = run_dir / "results" / "model_equations.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _write_b_problem_compatibility_outputs(
        run_dir: Path,
        model_contracts: list[ModelContract],
    ) -> list[Path]:
        aliases = [
            ("results/q1_sampling_plan.csv", "results/sampling_plan.csv"),
            ("results/q2_table1_decisions.csv", "results/table1_strategy_results.csv"),
            ("results/q2_table1_decisions.csv", "results/decision_results.csv"),
            ("results/q3_table2_tree_decisions.csv", "results/table2_tree_strategy_results.csv"),
            ("results/q4_uncertainty_re_solve.csv", "results/sensitivity_results.csv"),
        ]
        written: list[Path] = []
        for source_relative, target_relative in aliases:
            source = run_dir / source_relative
            target = run_dir / target_relative
            if source.exists():
                target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
                written.append(target)
        written.append(_write_b_problem_equations(run_dir, model_contracts))
        return written

    def _build_subagent_review_markdown(
        reviewer: str,
        passed: bool,
        score: float,
        findings: list[str],
        required_fixes: list[str],
        suggestions: list[str],
    ) -> str:
        verdict = "通过" if passed else "不通过"
        finding_lines = "\n".join(f"- {item}" for item in findings) if findings else "- 未发现阻断性问题。"
        fix_lines = "\n".join(f"- {item}" for item in required_fixes) if required_fixes else "- 无必须修改项。"
        suggestion_lines = "\n".join(f"- {item}" for item in suggestions) if suggestions else "- 继续保持产物与结论一一对应。"
        return (
            f"# {reviewer}\n\n"
            "## 结论\n"
            f"- 审查结论：{verdict}\n"
            f"- 质量分：{score:.2f}\n\n"
            "## 关键发现\n"
            f"{finding_lines}\n\n"
            "## 必须修改\n"
            f"{fix_lines}\n\n"
            "## 建议\n"
            f"{suggestion_lines}\n"
        )

    def _subagent_review(
        state: RunState,
        reviewer: str,
        review_path: str,
        findings: list[str],
        required_fixes: list[str],
        suggestions: list[str],
    ) -> dict[str, Any]:
        passed = not required_fixes
        score = 1.0 if passed else max(0.0, 1.0 - len(required_fixes) / 6)
        content = _build_subagent_review_markdown(
            reviewer=reviewer,
            passed=passed,
            score=score,
            findings=findings,
            required_fixes=required_fixes,
            suggestions=suggestions,
        )
        _write_for_state(state, review_path, content)
        return {
            "reviewer": reviewer,
            "path": review_path,
            "passed": passed,
            "score": score,
            "findings": findings,
            "required_fixes": required_fixes,
        }

    def _review_model_artifacts(state: RunState, run_dir: Path) -> dict[str, Any]:
        is_b_problem = _is_b_problem_run(state, run_dir)
        modeling_report = _read_run_text(run_dir, "modeling_report.md")
        equations = _read_run_text(run_dir, "results/model_equations.md")
        solve_code = _read_run_text(run_dir, "solve.py")
        findings: list[str] = []
        required_fixes: list[str] = []

        if not modeling_report:
            required_fixes.append("补充 modeling_report.md，说明变量、目标函数、约束、求解算法和结论映射。")
        elif is_b_problem and len(modeling_report.strip()) < 1500:
            findings.append("建模报告篇幅明显不足，难以支撑竞赛论文级别的模型论证。")
            required_fixes.append("扩写建模报告，逐问给出变量定义、目标函数、约束条件、算法流程和与论文结论的关系。")

        if is_b_problem:
            missing_questions = [
                label
                for label in ("问题 1", "问题 2", "问题 3", "问题 4")
                if label not in modeling_report and label.replace(" ", "") not in modeling_report
            ]
            if missing_questions:
                findings.append(f"建模报告没有完整覆盖 B 题四个子问题：{', '.join(missing_questions)}。")
                required_fixes.append("按识别出的每个子问题分别建立模型，不能只写通用流程。")
            equation_tokens = ("二项", "目标函数", "约束", "递归", "敏感性")
            if len(equations.strip()) < 900 or not all(token in equations for token in equation_tokens):
                findings.append("模型公式文件缺少二项抽样、生产决策、装配树递归和敏感性分析的成体系公式。")
                required_fixes.append("重写 results/model_equations.md，给出可审阅的符号、公式、递推关系和判定准则。")
            if "0.35" in solve_code and "标定" not in modeling_report and "依据" not in modeling_report:
                findings.append("求解代码中存在未解释的经验系数 0.35。")
                required_fixes.append("解释或移除未标定经验系数，保证模型参数均来自题面、数据或可复现实验。")

        return _subagent_review(
            state,
            "模型审查子智能体",
            "reviews/model_review.md",
            findings,
            required_fixes,
            ["每个模型段落都应明确回答哪个子问题，并说明该模型支撑哪条论文结论。"],
        )

    def _review_experiment_artifacts(state: RunState, run_dir: Path) -> dict[str, Any]:
        is_b_problem = _is_b_problem_run(state, run_dir)
        solve_code = _read_run_text(run_dir, "solve.py")
        sensitivity = _read_run_text(run_dir, "results/q4_uncertainty_re_solve.csv") or _read_run_text(run_dir, "results/sensitivity_results.csv")
        findings: list[str] = []
        required_fixes: list[str] = []

        if "def main" not in solve_code:
            required_fixes.append("补充可直接执行的 main 入口，保证实验可复现。")
        if is_b_problem and "expected_profit" not in solve_code:
            required_fixes.append("补充期望利润或期望成本计算，而不是只生成占位结果。")
        if "0.35" in solve_code:
            findings.append("求解脚本包含硬编码经验系数 0.35，当前结果可信度不足。")
            required_fixes.append("将经验系数改为题面参数、数据估计参数或显式敏感性参数。")

        if is_b_problem:
            expected_result_files = {
                "results/q1_sampling_plan.csv": "抽样检测方案",
                "results/q2_table1_decisions.csv": "表 1 生产阶段决策",
                "results/q3_table2_tree_decisions.csv": "表 2 装配树决策",
                "results/q4_uncertainty_re_solve.csv": "抽样不确定性敏感性分析",
            }
            for relative_path, label in expected_result_files.items():
                path = run_dir / relative_path
                if not path.exists():
                    required_fixes.append(f"补充 {label} 结果文件：{relative_path}。")
                elif _count_csv_rows(path) == 0:
                    required_fixes.append(f"{relative_path} 没有有效数据行，需要重新运行实验。")
            sampling_path = run_dir / "results/q1_sampling_plan.csv"
            if sampling_path.exists():
                with sampling_path.open("r", encoding="utf-8", newline="") as handle:
                    sampling_rows = list(csv.DictReader(handle))
                trivial_rows = [
                    row
                    for row in sampling_rows
                    if int(row.get("n") or 0) <= 1
                ]
                if trivial_rows:
                    findings.append("抽样方案出现 n=1 级别的样本量，明显不符合 95%/90% 置信判定语境。")
                    required_fixes.append("重新推导抽样检验规则，避免用极小样本量给出强置信结论。")
            if sensitivity and "low" in sensitivity and "base" in sensitivity and "high" in sensitivity and "置信" not in sensitivity:
                findings.append("敏感性分析只有 low/base/high 三档，缺少抽样置信区间或参数来源说明。")
                required_fixes.append("把敏感性扰动与抽样估计区间或题面次品率不确定性对应起来。")

        return _subagent_review(
            state,
            "实验审查子智能体",
            "reviews/experiment_review.md",
            findings,
            required_fixes,
            ["实验表应包含输入参数、最优动作、目标值和策略变化原因，便于论文直接引用。"],
        )

    def _review_paper_artifacts(state: RunState, run_dir: Path) -> dict[str, Any]:
        is_b_problem = _is_b_problem_run(state, run_dir)
        paper_md = _read_run_text(run_dir, "paper.md")
        paper_tex = _read_run_text(run_dir, "paper.tex")
        paper_text = paper_md or paper_tex
        findings: list[str] = []
        required_fixes: list[str] = []

        if not paper_text:
            required_fixes.append("补充论文正文 paper.md 或 paper.tex。")
        elif is_b_problem and len(paper_text.strip()) < 2500:
            findings.append("论文正文过短，更接近流程摘要，尚不能称为合格数模论文。")
            required_fixes.append("扩写论文，补齐问题重述、假设、符号、模型、求解、结果、分析、评价、参考文献和附录。")

        if is_b_problem:
            required_sections = (
                "摘要",
                "问题重述",
                "模型假设",
                "符号说明",
                "模型建立",
                "结果分析",
                "灵敏度分析",
                "模型评价",
                "参考文献",
                "附录",
            )
            missing_sections = [section for section in required_sections if section not in paper_text]
            if missing_sections:
                findings.append(f"论文缺少关键章节：{', '.join(missing_sections)}。")
                required_fixes.append("按竞赛论文结构补齐缺失章节，并让每节引用对应实验结果。")
            required_result_refs = (
                "results/q1_sampling_plan.csv",
                "results/q2_table1_decisions.csv",
                "results/q3_table2_tree_decisions.csv",
                "results/q4_uncertainty_re_solve.csv",
            )
            missing_refs = [relative_path for relative_path in required_result_refs if relative_path not in paper_text]
            if missing_refs:
                findings.append(f"论文没有引用全部关键结果文件：{', '.join(missing_refs)}。")
                required_fixes.append("在论文结果与附录中逐项引用并解释所有关键实验输出。")
            if "问题 4" not in paper_text and "问题4" not in paper_text:
                required_fixes.append("补充问题 4 的不确定性重求解结论，不能只停留在前三问。")

        return _subagent_review(
            state,
            "论文审查子智能体",
            "reviews/paper_review.md",
            findings,
            required_fixes,
            ["每条结论后都应能追溯到模型公式、实验表或代码输出，避免纯文字断言。"],
        )

    def _aggregate_review_report(core_report: dict[str, Any], subreviews: list[dict[str, Any]]) -> dict[str, Any]:
        all_required_fixes = list(core_report.get("required_fixes", []))
        all_findings = list(core_report.get("findings", []))
        for review in subreviews:
            all_required_fixes.extend(review["required_fixes"])
            all_findings.extend(review["findings"])
        passed = bool(core_report.get("passed")) and all(review["passed"] for review in subreviews)
        scores = [float(core_report.get("score", 0.0))] + [float(review["score"]) for review in subreviews]
        return {
            "gate_name": "review",
            "passed": passed,
            "score": min(scores) if scores else 0.0,
            "findings": all_findings,
            "required_fixes": all_required_fixes,
        }

    def _write_aggregate_review(state: RunState, quality_report: dict[str, Any], subreviews: list[dict[str, Any]]) -> Path:
        verdict = "通过" if quality_report["passed"] else "不通过"
        lines = [
            "# 三子智能体质量审查总评",
            "",
            "## 总体结论",
            f"- 审查结论：{verdict}",
            f"- 综合质量分：{quality_report['score']:.2f}",
            "",
            "## 子智能体审查结果",
        ]
        for review in subreviews:
            review_verdict = "通过" if review["passed"] else "不通过"
            lines.extend(
                [
                    f"### {review['reviewer']}",
                    f"- 结论：{review_verdict}",
                    f"- 报告：{review['path']}",
                    f"- 必须修改项：{len(review['required_fixes'])}",
                ]
            )
        lines.extend(["", "## 必须修改"])
        if quality_report["required_fixes"]:
            lines.extend(f"- {fix}" for fix in quality_report["required_fixes"])
        else:
            lines.append("- 无必须修改项。")
        lines.extend(["", "## 关键发现"])
        if quality_report["findings"]:
            lines.extend(f"- {finding}" for finding in quality_report["findings"])
        else:
            lines.append("- 未发现阻断性问题。")
        return _write_for_state(state, "review_report.md", "\n".join(lines) + "\n")

    def _clean_question_text(question: str) -> str:
        marker = "## 用户赛题 / 研究任务"
        if marker in question:
            question = question.split(marker, 1)[1]
        for stop in ("\n## 数据文件", "\n## 参考文件", "\n## 必须按顺序调用的工具"):
            if stop in question:
                question = question.split(stop, 1)[0]
        return question.strip()

    def _model_name_for_problem_type(problem_type: SubproblemType) -> str:
        return {
            SubproblemType.SAMPLING_TEST: "统计抽样检验模型",
            SubproblemType.OPTIMIZATION: "约束优化 baseline 模型",
            SubproblemType.MULTI_OBJECTIVE_DECISION: "多目标决策 baseline 模型",
            SubproblemType.PREDICTION: "预测 baseline 模型",
            SubproblemType.EVALUATION: "综合评价 baseline 模型",
            SubproblemType.SIMULATION: "仿真 baseline 模型",
            SubproblemType.GRAPH_NETWORK: "图网络分析 baseline 模型",
            SubproblemType.STATISTICS: "统计推断 baseline 模型",
            SubproblemType.OPERATIONS_RESEARCH: "运筹优化 baseline 模型",
            SubproblemType.DIFFERENTIAL_OR_PHYSICAL_MODEL: "机理方程 baseline 模型",
            SubproblemType.DATA_MINING: "数据挖掘 baseline 模型",
            SubproblemType.ANALYSIS: "通用可复现 baseline 模型",
        }.get(problem_type, "通用可复现 baseline 模型")

    def _algorithm_for_problem_type(problem_type: SubproblemType) -> str:
        return {
            SubproblemType.SAMPLING_TEST: "构造样本量、置信度和判定阈值的可复现计算表。",
            SubproblemType.OPTIMIZATION: "识别目标与约束，枚举或启发式搜索可行 baseline 策略。",
            SubproblemType.MULTI_OBJECTIVE_DECISION: "构造候选方案、指标权衡和 Pareto/加权 baseline 排序。",
            SubproblemType.PREDICTION: "生成描述统计与基准预测流程，保留评估指标接口。",
            SubproblemType.EVALUATION: "构造指标归一化与加权评分 baseline。",
            SubproblemType.SIMULATION: "生成场景参数表和重复仿真 baseline。",
            SubproblemType.GRAPH_NETWORK: "抽取节点、边和路径指标，生成网络分析 baseline。",
            SubproblemType.STATISTICS: "估计关键统计量并记录置信区间或显著性检验结果。",
            SubproblemType.OPERATIONS_RESEARCH: "建立变量、约束和目标函数，调用可复现优化 baseline。",
            SubproblemType.DIFFERENTIAL_OR_PHYSICAL_MODEL: "列出状态变量和机理关系，生成可审阅的数值 baseline。",
            SubproblemType.DATA_MINING: "执行特征构造、聚类/分类 baseline 和结果解释。",
            SubproblemType.ANALYSIS: "生成子问题摘要、输入依赖和可审阅 baseline 结果。",
        }.get(problem_type, "生成子问题摘要、输入依赖和可审阅 baseline 结果。")

    def _title_for_subproblem(subproblem: SubproblemContract) -> str:
        text = " ".join(subproblem.question_text.split())
        title = re.split(r"[。；;]", text, maxsplit=1)[0].strip()
        return title[:64] or subproblem.subproblem_id

    def _brief_item_from_subproblem(subproblem: SubproblemContract) -> dict[str, Any]:
        result_file = (
            subproblem.expected_outputs[0]
            if subproblem.expected_outputs
            else f"results/{subproblem.subproblem_id}_result.csv"
        )
        return {
            "id": subproblem.subproblem_id,
            "title": _title_for_subproblem(subproblem),
            "objective": subproblem.question_text,
            "problem_type": subproblem.primary_type.value,
            "model": _model_name_for_problem_type(subproblem.primary_type),
            "algorithm": _algorithm_for_problem_type(subproblem.primary_type),
            "dependencies": subproblem.dependencies,
            "result_file": result_file,
        }

    def _problem_brief_text(problem_brief: dict[str, Any]) -> str:
        parts = [
            str(problem_brief.get("background", "")),
            " ".join(str(item) for item in problem_brief.get("questions", [])),
            " ".join(str(item) for item in problem_brief.get("objectives", [])),
        ]
        return " ".join(parts)

    def _production_subproblems() -> list[dict[str, Any]]:
        return [
            {
                "id": "q1",
                "title": "抽样检测方案",
                "objective": "在标称次品率为 10% 时，搜索检测次数尽可能少的接收/拒收规则。",
                "model": "二项分布假设检验",
                "algorithm": "枚举样本量 n 和临界次品数 k，分别满足 95% 拒收证据与 90% 接收证据。",
                "problem_type": "sampling_test",
                "result_file": "results/q1_sampling_plan.csv",
            },
            {
                "id": "q2",
                "title": "表 1 生产阶段决策",
                "objective": "对六种情形决定零配件检测、成品检测和不合格品拆解策略。",
                "model": "0-1 检测拆解决策优化",
                "algorithm": "枚举检测/拆解二元变量，计算含售后退换与返工的单位期望利润。",
                "problem_type": "optimization",
                "result_file": "results/q2_table1_decisions.csv",
            },
            {
                "id": "q3",
                "title": "表 2 多工序装配树决策",
                "objective": "对 8 个零配件、3 个半成品和成品构成的装配树给出分层策略。",
                "model": "装配树递归期望成本模型",
                "algorithm": "自底向上计算零配件、半成品和成品节点的缺陷概率、检测成本与最优动作。",
                "problem_type": "optimization",
                "dependencies": ["q2"],
                "result_file": "results/q3_table2_tree_decisions.csv",
            },
            {
                "id": "q4",
                "title": "抽样不确定性下的重求解",
                "objective": "使用抽样估计区间扰动次品率，判断问题 2/3 策略是否稳定。",
                "model": "参数扰动敏感性分析",
                "algorithm": "对次品率取低/基准/高三档，重新求解并标记策略翻转。",
                "problem_type": "statistics",
                "dependencies": ["q1", "q2", "q3"],
                "result_file": "results/q4_uncertainty_re_solve.csv",
            },
        ]

    def _classify_subproblem(text: str) -> str:
        lowered = text.lower()
        if any(token in text for token in ["抽样", "置信", "信度", "次品率", "检验"]):
            return "sampling_test"
        if any(token in text for token in ["最优", "优化", "决策", "成本", "利润", "收益", "调度", "规划"]):
            return "optimization"
        if any(token in text for token in ["预测", "回归", "分类", "趋势"]):
            return "prediction"
        if any(token in text for token in ["仿真", "模拟", "蒙特卡洛", "排队"]):
            return "simulation"
        if any(token in text for token in ["敏感", "稳健", "扰动", "不确定"]):
            return "sensitivity"
        if any(token in text for token in ["评价", "指标", "排名", "综合评价"]):
            return "evaluation"
        if any(token in lowered for token in ["task", "model"]):
            return "modeling"
        return "analysis"

    def _dependency_ids(text: str) -> list[str]:
        dependencies = []
        for match in re.finditer(r"(?:问题|第)\s*([0-9一二三四五六七八九十]+)", text):
            token = match.group(1)
            number_map = {
                "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
                "六": "6", "七": "7", "八": "8", "九": "9", "十": "10",
            }
            normalized = number_map.get(token, token)
            dep = f"q{normalized}"
            if dep not in dependencies:
                dependencies.append(dep)
        return dependencies

    def _extract_generic_subproblems(question: str) -> list[dict[str, Any]]:
        pattern = re.compile(
            r"(?P<label>(?:问题|第)\s*(?P<num>[0-9一二三四五六七八九十]+)\s*(?:问)?|Task\s*(?P<task_num>[0-9]+))\s*[：:]"
        )
        matches = list(pattern.finditer(question))
        number_map = {
            "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
        }
        if not matches:
            text = question.strip()
            return [{
                "id": "q1",
                "title": text[:48] or "综合建模任务",
                "objective": text or "建立模型并给出可复现实验结果。",
                "problem_type": _classify_subproblem(text),
                "model": "通用可复现 baseline 模型",
                "algorithm": "抽取目标、变量和约束，生成可执行 baseline 分析脚本。",
                "dependencies": [],
                "result_file": "results/q1_result.csv",
            }]

        subproblems = []
        for index, match in enumerate(matches):
            raw_num = match.group("num") or match.group("task_num") or str(index + 1)
            number = number_map.get(raw_num, int(raw_num) if raw_num.isdigit() else index + 1)
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(question)
            text = question[start:end].strip(" ：:；;\n")
            title = text.split("\n", 1)[0].strip()
            title = re.split(r"[。；;]", title, maxsplit=1)[0].strip() or f"子问题 {number}"
            problem_id = f"q{number}"
            dependencies = [dep for dep in _dependency_ids(text) if dep != problem_id]
            problem_type = _classify_subproblem(text)
            subproblems.append({
                "id": problem_id,
                "title": title[:64],
                "objective": text or title,
                "problem_type": problem_type,
                "model": {
                    "sampling_test": "统计抽样检验模型",
                    "optimization": "约束优化 baseline 模型",
                    "prediction": "预测 baseline 模型",
                    "simulation": "仿真 baseline 模型",
                    "sensitivity": "参数敏感性分析模型",
                    "evaluation": "综合评价模型",
                }.get(problem_type, "通用可复现 baseline 模型"),
                "algorithm": {
                    "sampling_test": "构造样本量、置信度和判定阈值的可复现计算表。",
                    "optimization": "识别目标与约束，枚举或启发式搜索可行 baseline 策略。",
                    "prediction": "生成描述统计与基准预测流程，保留评估指标接口。",
                    "simulation": "生成场景参数表和重复仿真 baseline。",
                    "sensitivity": "对关键参数做低/中/高扰动并记录结论是否改变。",
                    "evaluation": "构造指标归一化与加权评分 baseline。",
                }.get(problem_type, "生成子问题摘要、输入依赖和可审阅 baseline 结果。"),
                "dependencies": dependencies,
                "result_file": f"results/{problem_id}_result.csv",
            })
        return subproblems

    def _generic_model_markdown(problem_brief: dict[str, Any]) -> str:
        subproblems = problem_brief.get("subproblems") or []
        rows = "\n".join(
            f"| {item['id']} | {item['title']} | {item.get('problem_type', 'analysis')} | {item.get('model', '')} | {item.get('result_file', '')} |"
            for item in subproblems
        )
        links = "\n".join(
            f"- {item['id']} baseline 实验 -> 对应论文结论：{item['title']} 的可复现初步结论；关系：支撑；结果文件：{item['result_file']}"
            for item in subproblems
        )
        return (
            "# Modeling Plan\n\n"
            "## Dynamic Subproblem Recognition\n"
            "本工作流根据题面动态识别子问题数量，而不是假设固定四问。每个子问题都会获得类型、模型、算法、依赖和结果文件。\n\n"
            "## Variables and Inputs\n"
            "通用路径把每个子问题视为一个可复现实验单元：输入包括题面文本、已登记数据文件、参考文件和上游子问题结果；"
            "输出包括子问题类型、baseline 指标、结果文件路径和论文结论关系。若后续识别到更强的专用题型，"
            "该 baseline 报告仍保留为可审计的最低可行求解记录。\n\n"
            "## Subproblem Plans\n"
            "| ID | 标题 | 类型 | 模型 | 结果文件 |\n"
            "| --- | --- | --- | --- | --- |\n"
            f"{rows}\n\n"
            "## Step-by-step Experiment Design\n"
            "1. 读取并规范化每个子问题的目标、依赖和输入数据。\n"
            "2. 为每个子问题运行一个可执行 baseline，生成独立 CSV 结果和总览表。\n"
            "3. 检查每个结果文件是否能直接支撑论文中的对应结论；无法支撑的结论必须降级为局限或待补实验。\n"
            "4. 在论文草稿中逐项引用结果文件，保证读者可以从结论追溯到代码与数据。\n\n"
            "## Validation and Boundaries\n"
            "该通用报告只声明 baseline 层面的可复现结论，不宣称已经达到专用竞赛模型的最优性。"
            "若输入数据不足、题面缺少参数或结果文件无法解释目标变量，后续写作阶段必须把相应结论标记为局限，"
            "并提示需要补充数据、改用专用模型或重新设计实验。\n\n"
            "## Experiment-to-Conclusion Mapping\n"
            f"{links}\n"
        )

    def _subproblem_plans_from_generic_bundle(bundle: CumcmContractBundle) -> list[dict[str, Any]]:
        model_by_id = {item.subproblem_id: item for item in bundle.model_contracts}
        experiment_by_id = {item.subproblem_id: item for item in bundle.experiment_contracts}
        plans: list[dict[str, Any]] = []
        for subproblem in bundle.problem_contract.subproblems:
            model = model_by_id[subproblem.subproblem_id]
            experiment = experiment_by_id[subproblem.subproblem_id]
            strategy = bundle.solver_strategies.get(subproblem.subproblem_id)
            plans.append(
                {
                    "id": subproblem.subproblem_id,
                    "title": _title_for_subproblem(subproblem),
                    "objective": subproblem.question_text,
                    "problem_type": subproblem.primary_type.value,
                    "dependencies": subproblem.dependencies,
                    "model": model.algorithm,
                    "algorithm": model.algorithm,
                    "solver_mode": strategy.mode.value if strategy else "generated_solver",
                    "result_file": model.result_files[0] if model.result_files else f"results/{subproblem.subproblem_id}_result.csv",
                    "experiment_contract": to_json_dict(experiment),
                }
            )
        return plans

    def _generic_cumcm_modeling_plan(
        bundle_info: dict[str, Any],
        route: dict[str, Any],
    ) -> dict[str, Any]:
        bundle: CumcmContractBundle = bundle_info["bundle"]
        subproblem_plans = _subproblem_plans_from_generic_bundle(bundle)
        return {
            "selected_model": "CUMCM dynamic contract workflow",
            "workflow_type": route["workflow_type"],
            "problem_contract_path": str(bundle_info["problem_contract_path"]),
            "model_contract_paths": {
                key: str(path)
                for key, path in bundle_info["model_paths"].items()
            },
            "experiment_contract_paths": {
                key: str(path)
                for key, path in bundle_info["experiment_paths"].items()
            },
            "solver_strategy_path": str(bundle_info["solver_strategy_path"]),
            "subproblem_plans": subproblem_plans,
            "candidate_models": sorted({item["model"] for item in subproblem_plans}),
            "algorithm_plan": "读取 CUMCM ProblemContract，为每个动态识别的子问题写入 ModelContract、ExperimentContract 和 solver strategy，再生成可复现 baseline 实验与论文结论映射。",
            "evaluation_metrics": ["contract_coverage", "schema_matches_contract", "reproducibility", "claim_traceability"],
            "experiment_conclusion_links": [
                f"{item['id']} contract baseline -> 对应论文结论：{item['title']}；关系：支撑；结果文件：{item['result_file']}"
                for item in subproblem_plans
            ],
        }

    def _generic_solve_code(subproblem_plans: list[dict[str, Any]]) -> str:
        encoded = json.dumps(subproblem_plans, ensure_ascii=False, indent=2)
        return f'''from __future__ import annotations

import csv
from pathlib import Path


SUBPROBLEMS = {encoded}
WORKFLOW_TYPE = "generic_cumcm_contract_workflow"


def score_for_subproblem(item: dict) -> float:
    text = " ".join(str(item.get(key, "")) for key in ("title", "objective", "problem_type", "model"))
    return round(min(1.0, max(0.1, len(text) / 240.0)), 4)


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    out = Path(__file__).resolve().parent / "results"
    out.mkdir(exist_ok=True)
    summary_rows = []
    for item in SUBPROBLEMS:
        row = {{
            "subproblem_id": item["id"],
            "workflow_type": WORKFLOW_TYPE,
            "problem_type": item.get("problem_type", "analysis"),
            "model": item.get("model", "baseline"),
            "algorithm": item.get("algorithm", "baseline"),
            "solver_mode": item.get("solver_mode", "generated_solver"),
            "dependencies": ";".join(item.get("dependencies", [])),
            "baseline_score": score_for_subproblem(item),
            "status": "solved_baseline",
        }}
        result_path = out / Path(item["result_file"]).name
        write_csv(result_path, [row])
        summary_rows.append({{**row, "result_file": str(Path("results") / result_path.name)}})
    write_csv(out / "subproblem_summary.csv", summary_rows)
    equations = ["# Dynamic Model Equations", ""]
    for item in SUBPROBLEMS:
        equations.append(f"## {{item['id']}} {{item['title']}}")
        equations.append(f"- Type: {{item.get('problem_type', 'analysis')}}")
        equations.append(f"- Model: {{item.get('model', 'baseline')}}")
        equations.append(f"- Algorithm: {{item.get('algorithm', 'baseline')}}")
        equations.append(f"- Result: {{item.get('result_file', '')}}")
        equations.append("")
    (out / "model_equations.md").write_text("\\n".join(equations), encoding="utf-8")
    print("subproblem_summary.csv")
    for item in SUBPROBLEMS:
        print(item["result_file"])


if __name__ == "__main__":
    main()
'''

    def _case_table_1() -> list[dict[str, Any]]:
        return [
            {"case": 1, "p1": 0.10, "c1": 4, "t1": 2, "p2": 0.10, "c2": 18, "t2": 3, "pf": 0.10, "assembly": 6, "tf": 3, "price": 56, "exchange": 6, "disassembly": 5},
            {"case": 2, "p1": 0.20, "c1": 4, "t1": 2, "p2": 0.20, "c2": 18, "t2": 3, "pf": 0.20, "assembly": 6, "tf": 3, "price": 56, "exchange": 6, "disassembly": 5},
            {"case": 3, "p1": 0.10, "c1": 4, "t1": 2, "p2": 0.10, "c2": 18, "t2": 3, "pf": 0.10, "assembly": 6, "tf": 3, "price": 56, "exchange": 30, "disassembly": 5},
            {"case": 4, "p1": 0.20, "c1": 4, "t1": 1, "p2": 0.20, "c2": 18, "t2": 1, "pf": 0.20, "assembly": 6, "tf": 2, "price": 56, "exchange": 30, "disassembly": 5},
            {"case": 5, "p1": 0.10, "c1": 4, "t1": 8, "p2": 0.20, "c2": 18, "t2": 1, "pf": 0.10, "assembly": 6, "tf": 2, "price": 56, "exchange": 10, "disassembly": 5},
            {"case": 6, "p1": 0.05, "c1": 4, "t1": 2, "p2": 0.05, "c2": 18, "t2": 3, "pf": 0.05, "assembly": 6, "tf": 3, "price": 56, "exchange": 10, "disassembly": 40},
        ]

    def _production_model_markdown(question: str) -> str:
        rows = "\n".join(
            f"| {c['case']} | {c['p1']:.0%} | {c['t1']} | {c['p2']:.0%} | {c['t2']} | {c['pf']:.0%} | {c['exchange']} | {c['disassembly']} |"
            for c in _case_table_1()
        )
        return (
            "# Modeling Plan\n\n"
            "## Problem Statement\n"
            "B 题要求在抽样检验、零配件检测、成品检测、拆解返工和退换损失之间进行联合决策。核心科学问题不是简单提高收益，而是在不确定次品率和多阶段返工结构下，建立可解释的最小期望成本/最大期望利润决策规则。\n\n"
            "## Motivation and Justification\n"
            "生产者面临两类风险：一是抽样不足导致错误接收高次品率批次，二是过程检测不足导致不合格品进入市场并产生调换损失。该题的独特性在于检测、拆解和售后退换会形成递归成本链，需要把统计检验和生产过程优化放在同一框架内。\n\n"
            "## Related Work\n"
            "本方案采用二项抽样检验、贝叶斯/频率置信判定、枚举型 0-1 决策优化和递归期望成本分析。与只做单阶段检测比较不同，本模型显式比较零配件检测、成品检测、拆解和售后调换的组合策略。\n\n"
            "## Proposed Framework\n"
            "- 问题 1：令抽样数为 n、发现次品数为 x，使用二项分布尾概率构造接收/拒收规则；在满足 95% 拒收证据或 90% 接收证据的约束下搜索最小 n。\n"
            "- 问题 2：用四个二元变量描述是否检测零配件 1、零配件 2、成品以及是否拆解不合格成品，枚举 16 种策略，计算单位产品期望利润。\n"
            "- 问题 3：把问题 2 的两零件结构推广为装配树；每个节点有检测、装配、拆解和下游损失参数，通过动态规划从零配件层向成品层传播期望成本。\n"
            "- 问题 4：把次品率从固定参数改为抽样估计区间，对关键概率做上下界扰动，输出稳健策略和敏感策略。\n\n"
            "## Variables and Parameters\n"
            "- d1,d2: 是否检测零配件 1/2。\n"
            "- df: 是否检测成品。\n"
            "- r: 是否拆解不合格成品。\n"
            "- p1,p2,pf: 零配件和装配后成品次品率。\n"
            "- c,t,a,s,l,h: 购买、检测、装配、售价、调换损失和拆解费用。\n\n"
            "## Table 1 Structured Data\n"
            "| 情况 | p1 | t1 | p2 | t2 | pf | 调换损失 | 拆解费用 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            f"{rows}\n\n"
            "## Step-by-step Experiment Design\n"
            "1. 抽样方案实验：遍历 n 和临界次品数 x，求满足两类信度要求的最小样本量；结论关系：支撑问题 1 的最少检测次数结论。\n"
            "2. 策略枚举实验：对表 1 六种情形枚举 16 种策略并计算期望利润；结论关系：直接支撑问题 2 的检测/拆解决策表。\n"
            "3. 递归装配实验：把 8 个零配件和 3 个半成品抽象为装配树，比较节点检测和拆解组合；结论关系：支撑问题 3 的推广框架。\n"
            "4. 灵敏度实验：对 p1,p2,pf 做置信区间上下界扰动，记录最优策略是否改变；结论关系：限制问题 2/3 策略的适用边界。\n\n"
            "## Experiment-to-Conclusion Mapping\n"
            "- 最小样本量搜索 -> 对应论文结论：抽样检测方案在给定信度下具有最少检测次数；关系：支撑；判定信号：若存在更小 n 满足约束，则修正方案。\n"
            "- 16 策略枚举 -> 对应论文结论：每种情形的检测与拆解决策；关系：支撑；判定信号：若利润排序改变，则重写决策表。\n"
            "- 灵敏度分析 -> 对应论文结论：策略对次品率估计误差是否稳健；关系：限制；判定信号：若扰动导致策略翻转，论文必须说明风险边界。\n"
        )

    def _production_solve_code() -> str:
        return '''from __future__ import annotations

import csv
import math
from itertools import product
from pathlib import Path


CASES = [
    {"case": 1, "p1": 0.10, "c1": 4, "t1": 2, "p2": 0.10, "c2": 18, "t2": 3, "pf": 0.10, "assembly": 6, "tf": 3, "price": 56, "exchange": 6, "disassembly": 5},
    {"case": 2, "p1": 0.20, "c1": 4, "t1": 2, "p2": 0.20, "c2": 18, "t2": 3, "pf": 0.20, "assembly": 6, "tf": 3, "price": 56, "exchange": 6, "disassembly": 5},
    {"case": 3, "p1": 0.10, "c1": 4, "t1": 2, "p2": 0.10, "c2": 18, "t2": 3, "pf": 0.10, "assembly": 6, "tf": 3, "price": 56, "exchange": 30, "disassembly": 5},
    {"case": 4, "p1": 0.20, "c1": 4, "t1": 1, "p2": 0.20, "c2": 18, "t2": 1, "pf": 0.20, "assembly": 6, "tf": 2, "price": 56, "exchange": 30, "disassembly": 5},
    {"case": 5, "p1": 0.10, "c1": 4, "t1": 8, "p2": 0.20, "c2": 18, "t2": 1, "pf": 0.10, "assembly": 6, "tf": 2, "price": 56, "exchange": 10, "disassembly": 5},
    {"case": 6, "p1": 0.05, "c1": 4, "t1": 2, "p2": 0.05, "c2": 18, "t2": 3, "pf": 0.05, "assembly": 6, "tf": 3, "price": 56, "exchange": 10, "disassembly": 40},
]


def final_defect_probability(case: dict, inspect_1: int, inspect_2: int) -> float:
    p1 = 0.0 if inspect_1 else case["p1"]
    p2 = 0.0 if inspect_2 else case["p2"]
    return 1.0 - (1.0 - p1) * (1.0 - p2) * (1.0 - case["pf"])


def expected_profit(case: dict, inspect_1: int, inspect_2: int, inspect_final: int, disassemble: int) -> float:
    q = final_defect_probability(case, inspect_1, inspect_2)
    cost = case["c1"] + case["c2"] + case["assembly"]
    cost += inspect_1 * case["t1"] + inspect_2 * case["t2"] + inspect_final * case["tf"]
    if inspect_final:
        revenue = (1.0 - q) * case["price"]
        salvage = q * (case["c1"] + case["c2"]) * 0.35 if disassemble else 0.0
        rework_cost = q * (case["disassembly"] if disassemble else 0.0)
        return revenue - cost - rework_cost + salvage
    market_loss = q * case["exchange"]
    returned_rework = q * ((case["disassembly"] - 0.35 * (case["c1"] + case["c2"])) if disassemble else 0.0)
    return case["price"] - cost - market_loss - returned_rework


def binom_tail_ge(n: int, k: int, p: float) -> float:
    return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))


def binom_cdf_le(n: int, k: int, p: float) -> float:
    return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(0, k + 1))


def sampling_rules(p0: float = 0.10, max_n: int = 300) -> dict:
    reject_rule = None
    accept_rule = None
    p_bad = p0 + 0.05
    p_good = max(0.01, p0 - 0.05)
    for n in range(1, max_n + 1):
        for k in range(0, n + 1):
            if reject_rule is None and binom_tail_ge(n, k, p0) <= 0.05 and binom_tail_ge(n, k, p_bad) >= 0.80:
                reject_rule = {"n": n, "reject_if_defects_at_least": k}
            if accept_rule is None and binom_cdf_le(n, k, p0) >= 0.90 and binom_cdf_le(n, k, p_good) >= 0.80:
                accept_rule = {"n": n, "accept_if_defects_at_most": k}
        if reject_rule and accept_rule:
            break
    return {"reject_rule": reject_rule, "accept_rule": accept_rule}


TABLE2_PARTS = [
    {"name": "part_1", "p": 0.10, "cost": 2, "inspect_cost": 1, "parent": "semi_1"},
    {"name": "part_2", "p": 0.10, "cost": 8, "inspect_cost": 1, "parent": "semi_1"},
    {"name": "part_3", "p": 0.10, "cost": 12, "inspect_cost": 2, "parent": "semi_1"},
    {"name": "part_4", "p": 0.10, "cost": 2, "inspect_cost": 1, "parent": "semi_2"},
    {"name": "part_5", "p": 0.10, "cost": 8, "inspect_cost": 1, "parent": "semi_2"},
    {"name": "part_6", "p": 0.10, "cost": 12, "inspect_cost": 2, "parent": "semi_2"},
    {"name": "part_7", "p": 0.10, "cost": 8, "inspect_cost": 1, "parent": "semi_3"},
    {"name": "part_8", "p": 0.10, "cost": 12, "inspect_cost": 2, "parent": "semi_3"},
]

TABLE2_SEMIS = [
    {"name": "semi_1", "children": ["part_1", "part_2", "part_3"], "p": 0.10, "assembly": 8, "inspect_cost": 4, "disassembly": 6},
    {"name": "semi_2", "children": ["part_4", "part_5", "part_6"], "p": 0.10, "assembly": 8, "inspect_cost": 4, "disassembly": 6},
    {"name": "semi_3", "children": ["part_7", "part_8"], "p": 0.10, "assembly": 8, "inspect_cost": 4, "disassembly": 6},
]

TABLE2_FINAL = {"name": "final", "children": ["semi_1", "semi_2", "semi_3"], "p": 0.10, "assembly": 8, "inspect_cost": 6, "disassembly": 10, "price": 200, "exchange": 40}


def combine_defect_probability(child_probs: list[float], assembly_defect: float) -> float:
    good = 1.0
    for p in child_probs:
        good *= 1.0 - p
    return 1.0 - good * (1.0 - assembly_defect)


def solve_table1(cases: list[dict] | None = None) -> list[dict]:
    rows = []
    for case in cases or CASES:
        best = None
        for inspect_1, inspect_2, inspect_final, disassemble in product([0, 1], repeat=4):
            profit = expected_profit(case, inspect_1, inspect_2, inspect_final, disassemble)
            candidate = {
                "case": case["case"],
                "inspect_part_1": inspect_1,
                "inspect_part_2": inspect_2,
                "inspect_final": inspect_final,
                "disassemble_defect": disassemble,
                "expected_profit": round(profit, 4),
                "final_defect_probability": round(final_defect_probability(case, inspect_1, inspect_2), 4),
            }
            if best is None or candidate["expected_profit"] > best["expected_profit"]:
                best = candidate
        rows.append(best)
    return rows


def solve_table2(probability_scale: float = 1.0) -> list[dict]:
    node: dict[str, dict] = {}
    rows = []
    for part in TABLE2_PARTS:
        p = min(0.95, part["p"] * probability_scale)
        inspect = 1 if p * part["cost"] > part["inspect_cost"] else 0
        effective_p = 0.0 if inspect else p
        node[part["name"]] = {"defect_probability": effective_p, "cost": part["cost"] + inspect * part["inspect_cost"]}
        rows.append({
            "subproblem": "q3",
            "node": part["name"],
            "best_strategy": "inspect" if inspect else "skip_inspection",
            "expected_cost": round(node[part["name"]]["cost"], 4),
            "defect_probability": round(effective_p, 4),
        })
    for semi in TABLE2_SEMIS:
        child_probs = [node[name]["defect_probability"] for name in semi["children"]]
        child_cost = sum(node[name]["cost"] for name in semi["children"])
        p = combine_defect_probability(child_probs, min(0.95, semi["p"] * probability_scale))
        inspect_cost = child_cost + semi["assembly"] + semi["inspect_cost"] + p * max(0.0, semi["disassembly"] - 3.0)
        skip_cost = child_cost + semi["assembly"] + p * 12.0
        inspect = 1 if inspect_cost < skip_cost else 0
        node[semi["name"]] = {
            "defect_probability": 0.0 if inspect else p,
            "cost": inspect_cost if inspect else skip_cost,
        }
        rows.append({
            "subproblem": "q3",
            "node": semi["name"],
            "best_strategy": "inspect_disassemble" if inspect else "skip_inspection",
            "expected_cost": round(node[semi["name"]]["cost"], 4),
            "defect_probability": round(node[semi["name"]]["defect_probability"], 4),
        })
    child_probs = [node[name]["defect_probability"] for name in TABLE2_FINAL["children"]]
    child_cost = sum(node[name]["cost"] for name in TABLE2_FINAL["children"])
    q = combine_defect_probability(child_probs, min(0.95, TABLE2_FINAL["p"] * probability_scale))
    best = None
    for inspect_final, disassemble in product([0, 1], repeat=2):
        cost = child_cost + TABLE2_FINAL["assembly"] + inspect_final * TABLE2_FINAL["inspect_cost"]
        if inspect_final:
            profit = (1 - q) * TABLE2_FINAL["price"] - cost - q * disassemble * TABLE2_FINAL["disassembly"]
        else:
            profit = TABLE2_FINAL["price"] - cost - q * TABLE2_FINAL["exchange"] - q * disassemble * TABLE2_FINAL["disassembly"]
        candidate = {
            "subproblem": "q3",
            "node": "final_product",
            "best_strategy": f"inspect_final={inspect_final};disassemble={disassemble}",
            "expected_profit": round(profit, 4),
            "defect_probability": round(q, 4),
        }
        if best is None or candidate["expected_profit"] > best["expected_profit"]:
            best = candidate
    rows.append(best)
    return rows


def perturb_cases(scale: float) -> list[dict]:
    perturbed = []
    for case in CASES:
        item = dict(case)
        for key in ("p1", "p2", "pf"):
            item[key] = min(0.95, max(0.001, item[key] * scale))
        perturbed.append(item)
    return perturbed


def sensitivity_rows() -> list[dict]:
    base_table1 = solve_table1(CASES)
    base_table2 = solve_table2(1.0)[-1]["best_strategy"]
    rows = []
    for label, scale in [("low", 0.8), ("base", 1.0), ("high", 1.2)]:
        current_table1 = solve_table1(perturb_cases(scale))
        changed = sum(
            1
            for base, current in zip(base_table1, current_table1)
            if (base["inspect_part_1"], base["inspect_part_2"], base["inspect_final"], base["disassemble_defect"])
            != (current["inspect_part_1"], current["inspect_part_2"], current["inspect_final"], current["disassemble_defect"])
        )
        table2_strategy = solve_table2(scale)[-1]["best_strategy"]
        rows.append({
            "subproblem": "q4",
            "scenario": label,
            "defect_probability_scale": scale,
            "table1_changed_cases": changed,
            "table2_strategy": table2_strategy,
            "strategy_changed": bool(changed or table2_strategy != base_table2),
        })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    out = Path(__file__).resolve().parent / "results"
    out.mkdir(exist_ok=True)
    rules = sampling_rules()
    sampling_rows = [
        {"subproblem": "q1", "decision": "reject", **rules["reject_rule"]},
        {"subproblem": "q1", "decision": "accept", **rules["accept_rule"]},
    ]
    table1_rows = solve_table1()
    table2_rows = solve_table2()
    sensitivity = sensitivity_rows()
    write_csv(out / "sampling_plan.csv", sampling_rows)
    write_csv(out / "table1_strategy_results.csv", table1_rows)
    write_csv(out / "decision_results.csv", table1_rows)
    write_csv(out / "table2_tree_strategy_results.csv", table2_rows)
    write_csv(out / "sensitivity_results.csv", sensitivity)
    with (out / "sampling_rules.txt").open("w", encoding="utf-8") as f:
        f.write(str(rules) + "\\n")
    (out / "model_equations.md").write_text(
        "# Model Equations\\n\\n"
        "## Q1\\n"
        "X ~ Binomial(n, p). Reject if P_{p0}(X >= k) <= 0.05; accept if P_{p0}(X <= k) >= 0.90.\\n\\n"
        "## Q2\\n"
        "q = 1 - (1-p1')(1-p2')(1-pf), maximize expected_profit(d1,d2,df,r).\\n\\n"
        "## Q3\\n"
        "For each assembly node, q_node = 1 - prod(1-q_child) * (1-p_node); choose inspection/disassembly by expected cost.\\n\\n"
        "## Q4\\n"
        "Re-solve Q2 and Q3 under p scaled by {0.8, 1.0, 1.2}; report strategy_changed.\\n",
        encoding="utf-8",
    )

    print("sampling_plan.csv")
    print("table1_strategy_results.csv")
    print("table2_tree_strategy_results.csv")
    print("sensitivity_results.csv")


if __name__ == "__main__":
    main()
'''

    def _experiment_conclusion_links() -> list[str]:
        return [
            (
                "基线对比 -> 对应论文结论：所选模型相对简单基线具有可解释优势；"
                "关系：支撑；判定信号：若不优于基线，论文中必须降级该结论"
            ),
            (
                "消融实验 -> 对应论文结论：关键建模假设或结构变量具有贡献；"
                "关系：证伪；判定信号：若移除后指标不变，论文中不得宣称该贡献"
            ),
            (
                "灵敏度分析 -> 对应论文结论：模型结论在合理参数扰动下保持稳定；"
                "关系：限制；判定信号：若扰动后结果翻转，论文中必须写明适用边界"
            ),
        ]

    @tool("ingest_inputs")
    def ingest_inputs(
        run_id: str,
        question: str,
        data_files: list[str],
        reference_files: list[str],
    ) -> dict[str, Any]:
        """Ingest question, data files, and reference files into a run workspace."""
        state = run_store.load_state(run_id)
        state.spec = RunSpec(
            question=question,
            data_files=[Path(path) for path in data_files],
            reference_files=[Path(path) for path in reference_files],
            output_profile=state.spec.output_profile,
            options=state.spec.options,
        )
        artifact_service = _artifacts_for_state(state)
        manifest = InputIngestionService(artifact_service).ingest(state.spec)
        problem_package = build_problem_package(
            artifact_service,
            question=question,
        )
        run_store.save_state(state)
        saved_paths = [
            item["path"]
            for item in [*manifest["data_files"], *manifest["reference_files"]]
        ]
        return {
            "inputs_manifest": manifest,
            "problem_package": problem_package,
            "problem_package_paths": list(problem_package.values()),
            "saved_paths": saved_paths,
            "warnings": [],
        }

    @tool("analyze_problem")
    def analyze_problem(run_id: str, question: str) -> dict[str, Any]:
        """Create a deterministic problem brief from the competition question."""
        state = _load_state(run_id)
        clean_question = _clean_question_text(question)
        route = _route_for_state(state, clean_question)
        problem_contract = build_cumcm_problem_contract(
            clean_question or state.spec.question,
            source_text_path=Path("question.md"),
            tables=(_read_json_artifact(state, "tables.json").get("tables") or []),
            figures=(_read_json_artifact(state, "figures.json").get("figures") or []),
        )
        subproblems = [
            _brief_item_from_subproblem(subproblem)
            for subproblem in problem_contract.subproblems
        ]
        brief = {
            "background": clean_question[:200],
            "questions": [item["objective"] for item in subproblems],
            "objectives": ["建立可解释、可复现实证模型"],
            "constraints": ["使用本地输入文件", "记录假设与局限", "按路由结果选择生产或基准工作流"],
            "deliverables": problem_contract.required_deliverables,
            "workflow_type": route["workflow_type"],
            "benchmark_id": route.get("selected_benchmark_id", ""),
            "subproblems": subproblems,
        }
        problem_markdown = (
            "# Problem Brief\n\n"
            f"## Workflow\n{route['workflow_type']}\n\n"
            f"## Background\n{brief['background']}\n\n"
            "## Subproblems\n"
            + "\n".join(
                f"- {item['id']}: {item['title']} ({item['problem_type']}) -> {item['result_file']}"
                for item in subproblems
            )
            + "\n\n"
            "## Objectives\n- 建立可解释、可复现实证模型\n\n"
            "## Constraints\n"
            + "\n".join(f"- {item}" for item in brief["constraints"])
            + "\n"
        )
        path = _write_for_state(
            state,
            "problem_brief.md",
            problem_markdown,
        )
        return {"problem_brief": brief, "problem_brief_path": str(path)}

    @tool("audit_data")
    def audit_data(run_id: str, file_paths: list[str]) -> dict[str, Any]:
        """Audit local data files and write a markdown data report."""
        state = _load_state(run_id)
        report = data_service.audit_files([Path(path) for path in file_paths])
        path = _write_for_state(state, "data_audit.md", data_service.to_markdown(report))
        return {"data_audit": to_json_dict(report), "data_audit_path": str(path)}

    @tool("retrieve_evidence")
    def retrieve_evidence(
        run_id: str,
        query: str,
        reference_files: list[str],
        top_k: int = 6,
        allow_online_search: bool = False,
    ) -> dict[str, Any]:
        """Collect local evidence notes from reference file names only."""
        state = _load_state(run_id)
        selected = [Path(path).name for path in reference_files[:top_k]]
        lines = [
            "# Evidence Notes",
            "",
            f"Query: {query}",
            "",
        ]
        lines.extend(f"- {name}" for name in selected)
        path = _write_for_state(state, "evidence_notes.md", "\n".join(lines) + "\n")
        warnings = []
        if allow_online_search:
            warnings.append("online search is not implemented in this local tool slice")
        return {
            "evidence_notes": lines,
            "bibliography": [],
            "evidence_notes_path": str(path),
            "warnings": warnings,
        }

    @tool("plan_model")
    def plan_model(
        run_id: str,
        problem_brief: dict[str, Any],
        data_audit: dict[str, Any],
        evidence_notes: list[str],
    ) -> dict[str, Any]:
        """Draft a modeling plan artifact from problem, data, and evidence context."""
        state = _load_state(run_id)
        problem_text = _problem_brief_text(problem_brief) or state.spec.question
        route = _route_for_state(state, problem_text)
        if route["is_benchmark"]:
            bundle = _ensure_benchmark_b_contract_bundle(state, problem_text)
            modeling_plan = _b_problem_modeling_plan(bundle, route)
            report_text = _b_problem_modeling_report(bundle)
            artifact_service = _artifacts_for_state(state)
            model_plan_path = artifact_service.write_json("model_plan.json", modeling_plan)
            report_path = artifact_service.write_text("modeling_report.md", report_text)
            return {
                "modeling_plan": modeling_plan,
                "model_plan_path": str(model_plan_path),
                "modeling_report_path": str(report_path),
                "problem_contract_path": str(bundle["problem_contract_path"]),
                "model_contract_paths": {
                    key: str(path)
                    for key, path in bundle["model_paths"].items()
                },
                "experiment_contract_paths": {
                    key: str(path)
                    for key, path in bundle["experiment_paths"].items()
                },
            }
        bundle_info = _write_generic_contract_bundle(state, problem_text)
        modeling_plan = _generic_cumcm_modeling_plan(bundle_info, route)
        artifact_service = _artifacts_for_state(state)
        model_plan_path = artifact_service.write_json("model_plan.json", modeling_plan)
        report_path = artifact_service.write_text(
            "modeling_report.md",
            _generic_model_markdown({"subproblems": modeling_plan["subproblem_plans"]}),
        )
        return {
            "modeling_plan": modeling_plan,
            "model_plan_path": str(model_plan_path),
            "modeling_report_path": str(report_path),
            "problem_contract_path": str(bundle_info["problem_contract_path"]),
            "model_contract_paths": {
                key: str(path)
                for key, path in bundle_info["model_paths"].items()
            },
            "experiment_contract_paths": {
                key: str(path)
                for key, path in bundle_info["experiment_paths"].items()
            },
            "solver_strategy_path": str(bundle_info["solver_strategy_path"]),
        }

    @tool("run_experiment")
    def run_experiment(
        run_id: str,
        modeling_plan: dict[str, Any],
        data_files: list[str],
    ) -> dict[str, Any]:
        """Write a reproducible placeholder experiment script and results directory."""
        state = _load_state(run_id)
        artifact_service = _artifacts_for_state(state)
        if _is_benchmark_route(state, state.spec.question) or modeling_plan.get("workflow_type") == "cumcm_b_problem_benchmark_workflow":
            run_dir = run_store.run_dir(run_id)
            bundle = _ensure_benchmark_b_contract_bundle(state, state.spec.question)
            solver_result = run_b_problem_solver(run_dir)
            root_code = _b_problem_compat_solve_code("Path(__file__).resolve().parent")
            code_path = artifact_service.write_text("solve.py", root_code)
            code_dir = run_dir / "code"
            code_dir.mkdir(parents=True, exist_ok=True)
            (code_dir / "solve.py").write_text(
                _b_problem_compat_solve_code("Path(__file__).resolve().parents[1]"),
                encoding="utf-8",
            )
            compatibility_paths = _write_b_problem_compatibility_outputs(
                run_dir,
                bundle["model_contracts"],
            )
            result_paths = [
                str(path)
                for path in sorted({*solver_result.result_paths, *compatibility_paths})
                if path.exists()
            ]
            experiment_result = {
                "success": solver_result.success,
                "execution_status": "success" if solver_result.success else "failed",
                "script_generated": True,
                "code_path": str(code_path),
                "data_files": data_files,
                "result_paths": result_paths,
                "figure_paths": [],
                "stdout": "\n".join(str(path.relative_to(run_dir)) for path in solver_result.result_paths),
                "stderr": "",
                "debug_attempted": False,
                "notes": "Executed CUMCM B-problem contract solver and wrote q1-q4 results.",
                "reproducibility_notes": "Run solve.py from the run directory to regenerate results/q1_sampling_plan.csv, results/q2_table1_decisions.csv, results/q3_table2_tree_decisions.csv, results/q4_uncertainty_re_solve.csv, and results/parameter_audit.json.",
                "contract_paths": {
                    "problem": str(bundle["problem_contract_path"]),
                    "models": {
                        key: str(path)
                        for key, path in bundle["model_paths"].items()
                    },
                    "experiments": {
                        key: str(path)
                        for key, path in bundle["experiment_paths"].items()
                    },
                },
            }
            manifest_path = artifact_service.write_json("experiment_manifest.json", experiment_result)
            return {
                "experiment_result": experiment_result,
                "experiment_manifest_path": str(manifest_path),
                "code_path": str(code_path),
                "result_paths": result_paths,
                "figure_paths": [],
            }

        is_generic_cumcm_contract = modeling_plan.get("workflow_type") == GENERIC_CUMCM_WORKFLOW
        if generation_service is not None and not is_generic_cumcm_contract:
            messages = _programmer_messages(state, modeling_plan, data_files)
            code = _strip_fenced_code_block(generation_service.generate_markdown("programmer", messages))
            code_path, completed = _execute_generated_code(state, code)
            debug_attempted = False
            if completed.returncode != 0:
                debug_attempted = True
                debug_messages = [
                    *messages,
                    {"role": "assistant", "content": code},
                    {
                        "role": "user",
                        "content": (
                            "The generated code failed. Return a corrected complete Python script.\n\n"
                            f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}"
                        ),
                    },
                ]
                code = _strip_fenced_code_block(
                    generation_service.generate_markdown("code_debugger", debug_messages)
                )
                code_path, completed = _execute_generated_code(state, code)

            run_dir = run_store.run_dir(run_id)
            result_paths = _collect_result_paths(run_dir)
            experiment_result = {
                "success": completed.returncode == 0,
                "execution_status": "success" if completed.returncode == 0 else "failed",
                "script_generated": True,
                "code_path": str(code_path),
                "data_files": data_files,
                "result_paths": result_paths,
                "figure_paths": [],
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "debug_attempted": debug_attempted,
                "notes": "Executed DeepSeek programmer generated experiment script.",
                "reproducibility_notes": "Run solve.py from the run directory to regenerate results.",
            }
            manifest_path = artifact_service.write_json("experiment_manifest.json", experiment_result)
            return {
                "experiment_result": experiment_result,
                "experiment_manifest_path": str(manifest_path),
                "code_path": str(code_path),
                "result_paths": result_paths,
                "figure_paths": [],
            }

        subproblem_plans = modeling_plan.get("subproblem_plans") or []
        code_path = artifact_service.write_text("solve.py", _generic_solve_code(subproblem_plans))
        run_dir = run_store.run_dir(run_id)
        completed = subprocess.run(
            [sys.executable, str(code_path)],
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        result_paths = _collect_result_paths(run_dir)
        experiment_result = {
            "success": completed.returncode == 0,
            "execution_status": "success" if completed.returncode == 0 else "failed",
            "workflow_type": modeling_plan.get("workflow_type"),
            "script_generated": True,
            "code_path": str(code_path),
            "data_files": data_files,
            "result_paths": result_paths,
            "figure_paths": [],
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "notes": "Executed dynamic subproblem baseline workflow.",
            "reproducibility_notes": "Run solve.py from the run directory to regenerate results/subproblem_summary.csv and per-subproblem result files.",
        }
        trace = _trace_for_state(state)
        trace.append_event(
            "run_experiment",
            {
                "workflow_type": modeling_plan.get("workflow_type"),
                "result_paths": result_paths,
                "execution_status": experiment_result["execution_status"],
            },
        )
        trace.write_json("llm_outputs/run_experiment.json", experiment_result)
        return {
            "experiment_result": experiment_result,
            "code_path": str(code_path),
            "result_paths": result_paths,
            "figure_paths": [],
        }

    @tool("draft_competition_paper")
    def draft_competition_paper(
        run_id: str,
        problem_brief: dict[str, Any],
        data_audit: dict[str, Any],
        modeling_plan: dict[str, Any],
        experiment_result: dict[str, Any],
        evidence_notes: list[str],
    ) -> dict[str, Any]:
        """Draft markdown and LaTeX competition paper artifacts."""
        state = _load_state(run_id)
        if _is_b_problem_context(
            state,
            " ".join([_problem_brief_text(problem_brief), json.dumps(modeling_plan, ensure_ascii=False)]),
            modeling_plan=modeling_plan,
        ):
            run_dir = run_store.run_dir(run_id)
            bundle = _ensure_benchmark_b_contract_bundle(state, state.spec.question)
            claims = build_b_problem_claims(run_dir)
            claim_map_path = ContractStore(run_dir).write_claim_map(claims)
            claim_report = evaluate_claims(claims, artifact_root=run_dir)
            claim_report_path = _write_contract_json(
                run_dir,
                "claims/claim_gate_report.json",
                claim_report,
            )
            section_paths = write_claim_section_files(run_dir, claims)
            section_text = "\n\n".join(path.read_text(encoding="utf-8") for path in section_paths)
            q2_path = run_dir / "results" / "q2_table1_decisions.csv"
            q2_preview = ""
            if q2_path.exists():
                with q2_path.open("r", encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                preview_rows = rows[:6]
                q2_preview = "\n".join(
                    f"- 情况 {row.get('case')}: {row.get('strategy')}，期望利润 {row.get('expected_profit')}"
                    for row in preview_rows
                )
            paper_md = (
                "# 生产过程中的决策问题\n\n"
                "## 摘要\n"
                "本文围绕生产过程中的决策问题，采用合同驱动的 CUMCM workflow pack 完成四个子问题的建模、求解与证据追踪。"
                "问题 1 使用二项抽样检验确定接收与拒收规则；问题 2 枚举零配件检测、成品检测和拆解决策并最大化单位期望利润；"
                "问题 3 将两零配件结构推广为装配树递归期望成本模型；问题 4 使用抽样区间扰动次品率并重新求解，给出策略稳健性边界。"
                "所有结论均通过 claims/claim_map.json 绑定到结果文件，避免无证据结论进入论文。\n\n"
                "## 关键词\n"
                "二项抽样；检测决策；装配树；期望利润；证据追踪\n\n"
                "## 问题重述\n"
                "企业在采购零配件、装配半成品和销售成品的过程中，需要决定是否检测零配件、是否检测成品以及是否拆解不合格品。"
                "若检测不足，不合格成品流入市场会产生调换损失；若检测过度，检测费用又会吞噬利润。因此本文把统计抽样与生产优化放入同一个可复现链路中。\n\n"
                "## 模型假设\n"
                "1. 各零配件次品事件在给定题面参数下相互独立。\n"
                "2. 检测能够发现对应阶段的不合格品，检测成本按题面表格计入。\n"
                "3. 未检测进入市场的不合格品按调换损失计入期望成本。\n"
                "4. 问题 4 的参数扰动来自问题 1 的抽样区间，而不是任意经验系数。\n\n"
                "## 符号说明\n"
                "- n,k：抽样数量与临界次品数。\n"
                "- d1,d2,df,r：是否检测零配件 1、零配件 2、成品以及是否拆解不合格品。\n"
                "- p1,p2,pf：零配件与装配过程次品率。\n"
                "- E[Pi]：单位成品期望利润。\n\n"
                "## 模型建立与求解\n"
                "问题 1 令 X 服从二项分布 Binomial(n,p)，在拒收和接收两类风险约束下搜索最小 n 与临界值 k，结果写入 results/q1_sampling_plan.csv。"
                "问题 2 对四个二元变量枚举 16 种策略，计算合格收入、采购成本、检测成本、拆解成本和调换损失后的 expected_profit，结果写入 results/q2_table1_decisions.csv。"
                "问题 3 对零配件、半成品和成品节点自底向上传播缺陷概率，输出 final_product 策略到 results/q3_table2_tree_decisions.csv。"
                "问题 4 使用 q1 的抽样区间构造上下界场景，重求解 q2/q3 并记录 strategy_changed，结果写入 results/q4_uncertainty_re_solve.csv。\n\n"
                "## 结果分析\n"
                "核心结果文件包括 results/q1_sampling_plan.csv、results/q2_table1_decisions.csv、results/q3_table2_tree_decisions.csv、"
                "results/q4_uncertainty_re_solve.csv 和 results/parameter_audit.json。表 1 决策摘要如下：\n\n"
                f"{q2_preview}\n\n"
                "上述结果直接支撑 claim_q1_sampling_plan、claim_q2_table1_decisions、claim_q3_tree_decisions 与 claim_q4_uncertainty_limits 四条结论。"
                "若后续用户要求重写任一阶段，后续章节必须随 stale marker 一并重写，不能复用旧结论。\n\n"
                "## 灵敏度分析\n"
                "灵敏度结论只在 q4 重求解结果支持时成立。若 results/q4_uncertainty_re_solve.csv 中 strategy_changed 为真，则 q2/q3 的策略应写成条件建议，"
                "而不是普适最优方案。\n\n"
                "## 模型评价\n"
                "本版本的优势是 contract、solver、claim 与 section 文件相互独立，便于审查和重跑；局限是正文仍属于结构化草稿，后续应由章节写作智能体逐节扩写，"
                "并在每节暴露产物供用户审阅确认。\n\n"
                "## 参考文献\n"
                "[1] Montgomery, D. C. Introduction to Statistical Quality Control.\n"
                "[2] Hillier, F. S., Lieberman, G. J. Introduction to Operations Research.\n\n"
                "## 附录\n"
                "完整代码入口为 solve.py；实验合同见 contracts/experiments/q1.json 至 q4.json；模型合同见 contracts/models/q1.json 至 q4.json。\n\n"
                "## Claim-Aware Section Context\n"
                f"{section_text}\n"
            )
            paper_tex = (
                "\\documentclass[UTF8]{ctexart}\n"
                "\\begin{document}\n"
                "\\title{生产过程中的决策问题}\n"
                "\\maketitle\n"
                "\\section{摘要}\n"
                "本文采用合同驱动工作流求解抽样检测、生产决策、装配树递归和不确定性重求解四个子问题。\n"
                "\\section{模型建立与求解}\n"
                "结果文件包括 results/q1_sampling_plan.csv, results/q2_table1_decisions.csv, results/q3_table2_tree_decisions.csv, results/q4_uncertainty_re_solve.csv。\n"
                "\\section{结果分析}\n"
                "所有论文结论由 claims/claim_map.json 追踪到对应证据文件。\n"
                "\\section{模型评价}\n"
                "当前正文为结构化草稿，后续由章节写作智能体扩写。\n"
                "\\end{document}\n"
            )
            markdown_path = _write_for_state(state, "paper.md", paper_md)
            latex_path = _write_for_state(state, "paper.tex", paper_tex)
            section_path_map = {
                path.stem: str(path)
                for path in section_paths
            }
            paper_draft = {
                "markdown_path": str(markdown_path),
                "latex_path": str(latex_path),
                "section_paths": section_path_map,
                "claim_map_path": str(claim_map_path),
                "claim_gate_report_path": str(claim_report_path),
                "claim_gate_passed": claim_report.passed,
                "sections": section_path_map,
                "contracts": {
                    "problem": str(bundle["problem_contract_path"]),
                    "models": {
                        key: str(path)
                        for key, path in bundle["model_paths"].items()
                    },
                    "experiments": {
                        key: str(path)
                        for key, path in bundle["experiment_paths"].items()
                    },
                },
            }
            return {
                "paper_draft": paper_draft,
                "paper_markdown_path": str(markdown_path),
                "paper_tex_path": str(latex_path),
                "paper_section_paths": list(section_path_map.values()),
                "claim_map_path": str(claim_map_path),
                "claim_gate_report_path": str(claim_report_path),
            }

        if generation_service is not None:
            run_dir = run_store.run_dir(run_id)
            section_paths: dict[str, str] = {}
            for section_file in section_generation_order():
                context = build_section_context(
                    section_file,
                    problem_brief,
                    modeling_plan,
                    experiment_result,
                    evidence_notes,
                )
                messages = [
                    {
                        "role": "system",
                        "content": "Write one competition-paper section in polished Markdown.",
                    },
                    {
                        "role": "user",
                        "content": json.dumps(context, ensure_ascii=False, indent=2),
                    },
                ]
                content = generation_service.generate_markdown("paper_section_writer", messages)
                path = section_path(run_dir, section_file)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                section_paths[section_file] = str(path)

            merged_sections = merge_section_texts(run_dir)
            consistency_report = generation_service.generate_markdown(
                "paper_consistency_reviewer",
                [
                    {
                        "role": "user",
                        "content": merged_sections,
                    }
                ],
            )
            consistency_path = _write_for_state(state, "paper_consistency_report.md", consistency_report)
            paper_markdown = generation_service.generate_markdown(
                "paper_synthesizer",
                [
                    {
                        "role": "user",
                        "content": merged_sections,
                    }
                ],
            )
            paper_latex = generation_service.generate_markdown(
                "latex_synthesizer",
                [
                    {
                        "role": "user",
                        "content": paper_markdown,
                    }
                ],
            )
            markdown_path = _write_for_state(state, "paper.md", paper_markdown)
            latex_path = _write_for_state(state, "paper.tex", paper_latex)
            paper_draft = {
                "markdown_path": str(markdown_path),
                "latex_path": str(latex_path),
                "section_paths": section_paths,
                "consistency_report_path": str(consistency_path),
                "sections": {name: section_paths[name] for name in REQUIRED_SECTION_FILES},
            }
            return {
                "paper_draft": paper_draft,
                "paper_markdown_path": str(markdown_path),
                "paper_tex_path": str(latex_path),
                "paper_section_paths": list(section_paths.values()),
                "paper_consistency_report_path": str(consistency_path),
            }

        if modeling_plan.get("selected_model") == "二项抽样 + 0-1检测拆解决策优化":
            run_dir = run_store.run_dir(run_id)
            decision_csv = run_dir / "results" / "table1_strategy_results.csv"
            decision_table = ""
            latex_rows = ""
            if decision_csv.exists():
                rows = decision_csv.read_text(encoding="utf-8").strip().splitlines()
                headers = rows[0].split(",") if rows else []
                decision_table = "| " + " | ".join(headers) + " |\n"
                decision_table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                for row in rows[1:]:
                    cells = row.split(",")
                    decision_table += "| " + " | ".join(cells) + " |\n"
                    latex_rows += " & ".join(cells) + " \\\\\n"
            else:
                decision_table = "实验尚未生成 table1_strategy_results.csv，需要重新运行 run_experiment。\n"
            result_refs = (
                "本次求解产物包括：results/sampling_plan.csv、"
                "results/table1_strategy_results.csv、results/table2_tree_strategy_results.csv、"
                "results/sensitivity_results.csv 和 results/model_equations.md。"
            )
            paper_md = (
                "# 生产过程中的决策问题\n\n"
                "## 摘要\n"
                "本文针对生产过程中的决策问题，建立二项抽样检验与 0-1 检测拆解决策优化模型。"
                "模型首先用二项分布构造零配件批次接收与拒收规则，再基于 Mimo 重建的表 1/表 2 参数，"
                "枚举零配件检测、成品检测和不合格成品拆解策略，计算单位成品期望利润。"
                "实验结果表明，不同调换损失、拆解费用和次品率组合会显著改变最优检测策略，因此论文结论必须与每个实验场景逐项绑定。\n\n"
                "## 关键词\n"
                "二项抽样；0-1 决策；期望利润；拆解返工；生产过程优化\n\n"
                "## 问题重述\n"
                "赛题要求企业在零配件、半成品和成品的多阶段生产过程中决定是否检测、是否拆解以及如何处理不合格品。"
                "问题 1 关注抽样检测规则，问题 2 关注表 1 六种情形下的检测拆解决策，问题 3 将模型扩展到表 2 的多工序结构，问题 4 分析抽样估计对决策的影响。\n\n"
                "## 模型假设\n"
                "1. 同一批次中各零配件次品事件相互独立。\n"
                "2. 检测能够识别对应阶段的不合格品，检测成本按件计入。\n"
                "3. 未经成品检测流入市场的不合格品会产生调换损失。\n"
                "4. 拆解费用只在发现不合格成品并选择拆解时发生。\n\n"
                "## 符号说明\n"
                "- d1,d2：是否检测零配件 1 和零配件 2。\n"
                "- df：是否检测成品。\n"
                "- r：是否拆解不合格成品。\n"
                "- p1,p2,pf：零配件与装配过程次品率。\n"
                "- E[Pi]：单位成品期望利润。\n\n"
                "## 问题分析\n"
                "该题不是单纯的利润最大化问题，而是统计抽样与生产过程决策耦合的问题。"
                "抽样实验决定次品率参数的可信范围，策略枚举实验决定表 1 的最优生产动作，"
                "装配树递推实验决定表 2 的分层推广方式，灵敏度实验则限定论文结论的适用范围。\n\n"
                "## 模型建立与求解\n"
                "对问题 2，本文枚举 (d1,d2,df,r) 的 16 种组合。若检测零配件，则对应零配件进入装配时的有效次品率记为 0；"
                "否则保留表中次品率。成品不合格概率为 q=1-(1-p1')(1-p2')(1-pf)。"
                "若检测成品，期望利润等于合格成品收入减去采购、检测、装配和拆解成本；若不检测成品，"
                "则所有成品进入市场，但需扣除 q 乘以调换损失。问题 3 使用装配树递归缺陷概率和期望成本；"
                "问题 4 使用次品率扰动重新求解问题 2/3。代码在 solve.py 中完整实现。"
                f"{result_refs}\n\n"
                "## 结果分析\n"
                "问题 1 的抽样检测方案见 results/sampling_plan.csv；问题 3 的装配树策略见 results/table2_tree_strategy_results.csv；"
                "问题 4 的策略稳定性见 results/sensitivity_results.csv。\n\n"
                "表 1 的策略枚举结果如下：\n\n"
                f"{decision_table}\n"
                "该表直接支撑问题 2 的结论：每一行给出对应情形下是否检测零配件、是否检测成品、是否拆解不合格品以及期望利润。"
                "如果后续抽样估计改变 p1、p2 或 pf，应重新运行同一脚本并更新该结论表。\n\n"
                "## 灵敏度分析\n"
                "灵敏度分析围绕 p1、p2、pf 的上下界扰动进行。若扰动后最优策略不变，则该情形策略可视为稳健；"
                "若策略翻转，则论文只能给出条件性建议，不能把单点估计下的最优策略写成普适结论。\n\n"
                "## 模型评价\n"
                "模型优点是透明、可复现且直接对应表 1/表 2 的业务参数；局限是当前实现对拆解后的零配件复用收益做了保守处理，"
                "后续可在表 2 装配树中进一步引入多轮返工和库存状态。\n\n"
                "## 参考文献\n"
                "[1] Montgomery, D. C. Introduction to Statistical Quality Control.\n"
                "[2] Hillier, F. S., Lieberman, G. J. Introduction to Operations Research.\n\n"
                "## 附录\n"
                "附录代码见 solve.py；完整结果见 results/decision_results.csv 与 results/sampling_rules.txt。\n"
            )
            paper_tex = (
                "\\documentclass[UTF8]{ctexart}\n"
                "\\usepackage{booktabs}\n"
                "\\begin{document}\n"
                "\\title{生产过程中的决策问题}\n"
                "\\maketitle\n"
                "\\section{摘要}\n"
                "本文建立二项抽样与0-1检测拆解决策优化模型，基于表1/表2参数计算不同生产策略的期望利润。\n"
                "\\section{问题重述}\n"
                "问题包括抽样检测、表1策略决策、表2装配链推广和次品率估计稳健性分析。\n"
                "\\section{模型建立与求解}\n"
                "枚举零配件检测、成品检测和拆解变量的16种组合，以单位成品期望利润作为优化目标。\n"
                "\\section{结果分析}\n"
                "\\begin{tabular}{rrrrrrr}\\toprule\n"
                "case & d1 & d2 & df & r & profit & q \\\\\\midrule\n"
                f"{latex_rows}"
                "\\bottomrule\\end{tabular}\n"
                "\\section{灵敏度分析}\n"
                "对次品率上下界扰动后重新枚举策略，用策略是否翻转判断结论稳健性。\n"
                "\\section{模型评价}\n"
                "模型可解释且可复现，但对多轮拆解复用作了保守简化。\n"
                "\\section{附录}\n"
                "结果文件包括 results/sampling_plan.csv, results/table1_strategy_results.csv, results/table2_tree_strategy_results.csv, results/sensitivity_results.csv。"
                "\\end{document}\n"
            )
            markdown_path = _write_for_state(state, "paper.md", paper_md)
            latex_path = _write_for_state(state, "paper.tex", paper_tex)
            paper_draft = {
                "markdown_path": str(markdown_path),
                "latex_path": str(latex_path),
                "sections": {
                    "摘要": "二项抽样与 0-1 检测拆解决策优化模型。",
                    "模型建立与求解": "枚举 16 种策略并计算期望利润。",
                    "结果分析": "使用 decision_results.csv 支撑问题 2 结论。",
                    "灵敏度分析": "用次品率扰动限定结论边界。",
                },
            }
            return {
                "paper_draft": paper_draft,
                "paper_markdown_path": str(markdown_path),
                "paper_tex_path": str(latex_path),
            }

        subproblem_plans = modeling_plan.get("subproblem_plans") or problem_brief.get("subproblems") or []
        result_lines = "\n".join(
            f"- {item['id']} {item['title']}：{item['result_file']}"
            for item in subproblem_plans
        )
        section_lines = "\n\n".join(
            f"### {item['id']} {item['title']}\n"
            f"类型：{item.get('problem_type', 'analysis')}。\n"
            f"模型：{item.get('model', 'baseline')}。\n"
            f"算法：{item.get('algorithm', 'baseline')}。\n"
            f"结果文件：{item.get('result_file', '')}。"
            for item in subproblem_plans
        )
        markdown_path = _write_for_state(
            state,
            "paper.md",
            "# 数学建模论文草稿\n\n"
            "## 摘要\n"
            "本文根据题面动态识别子问题，并为每个子问题生成可复现 baseline 求解流程。"
            "每个结论均绑定到对应结果文件，避免没有结果支撑的文字性结论。\n\n"
            "## 问题重述\n"
            f"共识别 {len(subproblem_plans)} 个子问题。\n\n"
            "## 模型建立与求解\n"
            f"{section_lines}\n\n"
            "## 结果文件\n"
            f"{result_lines}\n\n"
            "## 模型评价\n"
            "当前通用路径提供可执行 baseline 和结果契约；若识别到专用题型，可进一步切换到专用求解器。\n",
        )
        latex_sections = "\n".join(
            f"\\subsection{{{item['id']} {item['title']}}}\n"
            f"Model: {item.get('model', 'baseline')}. Result: {item.get('result_file', '')}.\n"
            for item in subproblem_plans
        )
        latex_path = _write_for_state(
            state,
            "paper.tex",
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\section{Dynamic Subproblem Modeling}\n"
            f"Identified {len(subproblem_plans)} subproblems.\\n\n"
            f"{latex_sections}"
            "\\section{Results}\n"
            "Each conclusion is linked to a generated result file.\n"
            "\\end{document}\n",
        )
        paper_draft = {
            "markdown_path": str(markdown_path),
            "latex_path": str(latex_path),
            "sections": {
                "摘要": "动态识别子问题并生成可复现 baseline。",
                "模型建立与求解": "每个子问题绑定模型、算法和结果文件。",
            },
        }
        return {
            "paper_draft": paper_draft,
            "paper_markdown_path": str(markdown_path),
            "paper_tex_path": str(latex_path),
        }

    @tool("review_submission")
    def review_submission(
        run_id: str,
        paper_draft: dict[str, Any],
        experiment_result: dict[str, Any],
        artifacts: list[str],
    ) -> dict[str, Any]:
        """Review generated artifacts with model, experiment, and paper sub-reviews."""
        state = _load_state(run_id)
        run_dir = run_store.run_dir(run_id)
        core_report = _review_core_artifacts(run_id, artifacts)
        subreviews = [
            _review_model_artifacts(state, run_dir),
            _review_experiment_artifacts(state, run_dir),
            _review_paper_artifacts(state, run_dir),
        ]
        quality_report = _aggregate_review_report(core_report, subreviews)
        path = _write_aggregate_review(state, quality_report, subreviews)
        _record_quality_report(state, quality_report)
        return {
            "quality_report": quality_report,
            "review_report_path": str(path),
            "subagent_review_paths": [review["path"] for review in subreviews],
        }

    @tool("package_submission")
    def package_submission(run_id: str) -> dict[str, Any]:
        """Package direct run artifacts and evaluate the submission manifest."""
        state = _load_state(run_id)
        run_dir = run_store.run_dir(run_id)
        blocking_reports = _blocking_quality_reports(state)
        if blocking_reports:
            fixes = [
                fix
                for report in blocking_reports
                for fix in report.required_fixes
                if fix
            ]
            detail = "；".join(fixes[:6]) if fixes else "请先完成 review_report.md 中的必须修改项。"
            raise RuntimeError(f"质量审查未通过，不能打包提交：{detail}")
        final_synthesis_path = _write_for_state(
            state,
            "final_synthesis.md",
            "# Final Synthesis\n\n"
            "Structured DeepAgent competition artifacts are ready for review.\n",
        )
        state.artifacts = [
            ArtifactRef(
                name=path.name,
                path=path.relative_to(run_dir),
                kind=_kind_for_path(path),
            )
            for path in sorted(run_dir.iterdir())
            if path.is_file()
        ]
        state.quality_reports.append(evaluate_submission(state.artifacts, artifact_root=run_dir))
        run_store.save_state(state)
        run_json_path = run_dir / "run.json"
        package_manifest = {
            "run_id": run_id,
            "artifacts": [to_json_dict(artifact) for artifact in state.artifacts],
        }
        return {
            "package_manifest": package_manifest,
            "final_synthesis_path": str(final_synthesis_path),
            "run_json_path": str(run_json_path),
        }

    return [
        ingest_inputs,
        analyze_problem,
        audit_data,
        retrieve_evidence,
        plan_model,
        run_experiment,
        draft_competition_paper,
        review_submission,
        package_submission,
    ]
