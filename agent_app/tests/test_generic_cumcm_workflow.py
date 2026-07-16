from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_app.domain.models import RunOptions, RunSpec
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools
from agent_app.workflow_packs.cumcm.routing import (
    BENCHMARK_2024_B_ID,
    GENERIC_CUMCM_WORKFLOW,
)


B_LOOKING_TEXT = (
    "2024 年 B 题 生产过程中的决策问题。\n"
    "企业购买零配件 1 和零配件 2 装配成成品，需要决定是否检测零配件、"
    "是否检测成品、是否拆解不合格成品，并结合抽样检测结果完成建模。\n"
    "问题1：根据标称次品率设计抽样检测方案。\n"
    "问题2：对表 1 六种情形确定检测和拆解决策。\n"
    "问题3：推广到多零配件、多半成品装配过程。\n"
    "问题4：分析抽样不确定性对决策结果的影响。"
)


def _tools_for(store: RunStore) -> dict[str, object]:
    return {tool.name: tool for tool in make_competition_tools(run_store=store)}


class FailingGenerationService:
    def __init__(self):
        self.calls = []

    def generate_markdown(self, role, messages):
        self.calls.append((role, messages))
        raise AssertionError("generic CUMCM run_experiment must not call generation_service")


def test_production_b_looking_text_uses_generic_cumcm_contract_workflow(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question=B_LOOKING_TEXT))
    tools = _tools_for(store)

    problem = tools["analyze_problem"].invoke(
        {"run_id": state.run_id, "question": B_LOOKING_TEXT}
    )
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )
    experiment = tools["run_experiment"].invoke(
        {
            "run_id": state.run_id,
            "modeling_plan": plan["modeling_plan"],
            "data_files": [],
        }
    )

    run_dir = store.run_dir(state.run_id)
    routing = json.loads((run_dir / "trace" / "routing_decision.json").read_text(encoding="utf-8"))
    problem_contract = json.loads((run_dir / "contracts" / "problem_contract.json").read_text(encoding="utf-8"))
    b_fixture_result_files = [
        "results/q1_sampling_plan.csv",
        "results/q2_table1_decisions.csv",
        "results/q3_table2_tree_decisions.csv",
        "results/q4_uncertainty_re_solve.csv",
        "results/parameter_audit.json",
    ]

    assert problem["problem_brief"]["workflow_type"] == GENERIC_CUMCM_WORKFLOW
    assert routing["workflow_type"] == GENERIC_CUMCM_WORKFLOW
    assert routing["is_benchmark"] is False
    assert routing["rejected_routes"] == [BENCHMARK_2024_B_ID]
    assert plan["modeling_plan"]["selected_model"] == "CUMCM dynamic contract workflow"
    assert plan["modeling_plan"]["workflow_type"] == GENERIC_CUMCM_WORKFLOW
    assert (run_dir / "contracts" / "solver_strategies.json").exists()
    assert "solver_strategy_path" in plan["modeling_plan"]
    assert "cumcm_b_problem" not in plan["modeling_plan"]["workflow_type"]
    assert [item["subproblem_id"] for item in problem_contract["subproblems"]] == [
        "q1",
        "q2",
        "q3",
        "q4",
    ]
    assert experiment["experiment_result"]["execution_status"] == "success"
    assert (run_dir / "results" / "q1_result.csv").exists()
    assert (run_dir / "results" / "subproblem_summary.csv").exists()
    for relative_path in b_fixture_result_files:
        assert not (run_dir / relative_path).exists()


def test_explicit_benchmark_mode_uses_b_fixture_contracts(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(
        RunSpec(
            question=B_LOOKING_TEXT,
            options=RunOptions(
                workflow_mode="benchmark",
                benchmark_id=BENCHMARK_2024_B_ID,
            ),
        )
    )
    tools = _tools_for(store)

    problem = tools["analyze_problem"].invoke(
        {"run_id": state.run_id, "question": B_LOOKING_TEXT}
    )
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )

    run_dir = store.run_dir(state.run_id)
    routing = json.loads((run_dir / "trace" / "routing_decision.json").read_text(encoding="utf-8"))

    assert routing["workflow_type"] == "cumcm_b_problem_benchmark_workflow"
    assert routing["is_benchmark"] is True
    assert routing["selected_benchmark_id"] == BENCHMARK_2024_B_ID
    assert plan["modeling_plan"]["workflow_type"] == "cumcm_b_problem_benchmark_workflow"
    assert plan["modeling_plan"]["benchmark_id"] == BENCHMARK_2024_B_ID
    assert plan["modeling_plan"]["selected_model"] == "二项抽样 + 0-1检测拆解决策优化"
    expected_result_files = {
        "q1": "results/q1_sampling_plan.csv",
        "q2": "results/q2_table1_decisions.csv",
        "q3": "results/q3_table2_tree_decisions.csv",
        "q4": "results/q4_uncertainty_re_solve.csv",
    }
    for subproblem_id in ("q1", "q2", "q3", "q4"):
        model_contract = json.loads(
            (run_dir / "contracts" / "models" / f"{subproblem_id}.json").read_text(encoding="utf-8")
        )
        assert expected_result_files[subproblem_id] in model_contract["result_files"]


def test_non_b_problem_does_not_enter_benchmark_solver(tmp_path):
    question = (
        "C 题 河流水质评价。"
        "问题1：建立水质综合评价指标体系。"
        "问题2：预测未来三个月水质等级。"
    )
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question=question))
    tools = _tools_for(store)

    problem = tools["analyze_problem"].invoke(
        {"run_id": state.run_id, "question": question}
    )
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )
    experiment = tools["run_experiment"].invoke(
        {
            "run_id": state.run_id,
            "modeling_plan": plan["modeling_plan"],
            "data_files": [],
        }
    )

    run_dir = store.run_dir(state.run_id)
    solve_path = run_dir / "solve.py"
    q1_result_path = run_dir / "results" / "q1_result.csv"
    q2_result_path = run_dir / "results" / "q2_result.csv"
    benchmark_q2_path = run_dir / "results" / "q2_table1_decisions.csv"
    run_experiment_trace = json.loads(
        (run_dir / "trace" / "llm_outputs" / "run_experiment.json").read_text(
            encoding="utf-8"
        )
    )

    assert experiment["experiment_result"]["execution_status"] == "success"
    assert q1_result_path.exists()
    assert q2_result_path.exists()
    assert not benchmark_q2_path.exists()
    assert "generic_cumcm_contract_workflow" in solve_path.read_text(encoding="utf-8")
    assert "results/q1_result.csv" in {
        str(Path(path).relative_to(run_dir))
        for path in experiment["experiment_result"]["result_paths"]
    }
    assert run_experiment_trace["execution_status"] == "success"
    assert run_experiment_trace["workflow_type"] == GENERIC_CUMCM_WORKFLOW

    with q1_result_path.open("r", encoding="utf-8", newline="") as handle:
        q1_rows = list(csv.DictReader(handle))
    with q2_result_path.open("r", encoding="utf-8", newline="") as handle:
        q2_rows = list(csv.DictReader(handle))

    plan_by_id = {
        item["id"]: item
        for item in plan["modeling_plan"]["subproblem_plans"]
    }
    assert q1_rows[0]["workflow_type"] == GENERIC_CUMCM_WORKFLOW
    assert q1_rows[0]["solver_mode"] == plan_by_id["q1"]["solver_mode"]
    assert q2_rows[0]["workflow_type"] == GENERIC_CUMCM_WORKFLOW
    assert q2_rows[0]["solver_mode"] == plan_by_id["q2"]["solver_mode"]

    rerun = subprocess.run(
        [sys.executable, str(solve_path)],
        cwd=run_dir,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert rerun.returncode == 0, rerun.stderr


def test_generic_run_experiment_ignores_injected_generation_service(tmp_path):
    question = (
        "C 题 河流水质评价。"
        "问题1：建立水质综合评价指标体系。"
        "问题2：预测未来三个月水质等级。"
    )
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question=question))
    generation_service = FailingGenerationService()
    tools = {
        tool.name: tool
        for tool in make_competition_tools(
            run_store=store,
            generation_service=generation_service,
        )
    }

    problem = tools["analyze_problem"].invoke(
        {"run_id": state.run_id, "question": question}
    )
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )
    experiment = tools["run_experiment"].invoke(
        {
            "run_id": state.run_id,
            "modeling_plan": plan["modeling_plan"],
            "data_files": [],
        }
    )

    run_dir = store.run_dir(state.run_id)
    q1_result_path = run_dir / "results" / "q1_result.csv"
    trace_path = run_dir / "trace" / "llm_outputs" / "run_experiment.json"

    assert generation_service.calls == []
    assert experiment["experiment_result"]["execution_status"] == "success"
    assert "generic_cumcm_contract_workflow" in (run_dir / "solve.py").read_text(
        encoding="utf-8"
    )
    assert trace_path.exists()
    assert (
        json.loads(trace_path.read_text(encoding="utf-8"))["workflow_type"]
        == GENERIC_CUMCM_WORKFLOW
    )

    with q1_result_path.open("r", encoding="utf-8", newline="") as handle:
        q1_rows = list(csv.DictReader(handle))
    assert q1_rows[0]["workflow_type"] == GENERIC_CUMCM_WORKFLOW
    assert (
        q1_rows[0]["solver_mode"]
        == plan["modeling_plan"]["subproblem_plans"][0]["solver_mode"]
    )


def test_package_blocks_when_claim_gate_failed(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="C 题 河流水质评价。问题1：评价水质。"))
    tools = _tools_for(store)

    tools["draft_competition_paper"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": {
                "workflow_type": GENERIC_CUMCM_WORKFLOW,
                "subproblems": [{"id": "q1", "title": "水质评价"}],
            },
            "data_audit": {},
            "modeling_plan": {
                "workflow_type": GENERIC_CUMCM_WORKFLOW,
                "subproblem_plans": [
                    {
                        "id": "q1",
                        "title": "水质评价",
                        "result_file": "results/q1_result.csv",
                    }
                ],
            },
            "experiment_result": {},
            "evidence_notes": [],
        }
    )

    with pytest.raises(RuntimeError, match="claim_q1_result"):
        tools["package_submission"].invoke({"run_id": state.run_id})

    saved_state = store.load_state(state.run_id)
    claim_reports = [
        report
        for report in saved_state.quality_reports
        if report.gate_name == "claim"
    ]
    assert len(claim_reports) == 1
    assert claim_reports[0].passed is False


def test_package_blocks_when_submission_gate_failed(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="C 题 河流水质评价。问题1：评价水质。"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("内容过短\n", encoding="utf-8")
    (run_dir / "solve.py").write_text(
        "def main():\n"
        "    subproblem_id = 'q1'\n"
        "    print(subproblem_id)\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )
    (run_dir / "paper.tex").write_text(
        "\\documentclass{ctexart}\n"
        "\\begin{document}\n"
        "\\section{摘要} 水质评价模型摘要。\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    (run_dir / "review_report.md").write_text("# Review\n", encoding="utf-8")
    tools = _tools_for(store)

    with pytest.raises(RuntimeError, match="modeling_report.md 内容过短"):
        tools["package_submission"].invoke({"run_id": state.run_id})


def test_package_submission_can_recover_after_submission_gate_fix(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="C 题 河流水质评价。问题1：评价水质。"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("内容过短\n", encoding="utf-8")
    (run_dir / "solve.py").write_text(
        "def main():\n"
        "    subproblem_id = 'q1'\n"
        "    print(subproblem_id)\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )
    (run_dir / "paper.tex").write_text(
        "\\documentclass{ctexart}\n"
        "\\begin{document}\n"
        "\\section{摘要} 水质评价模型摘要。\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    (run_dir / "review_report.md").write_text("# Review\n", encoding="utf-8")
    tools = _tools_for(store)

    with pytest.raises(RuntimeError, match="modeling_report.md 内容过短"):
        tools["package_submission"].invoke({"run_id": state.run_id})

    (run_dir / "modeling_report.md").write_text(
        "# Modeling Report\n\n"
        + "本报告包含变量、目标函数、约束、实验流程、结果解释和论文结论映射。\n" * 80,
        encoding="utf-8",
    )

    result = tools["package_submission"].invoke({"run_id": state.run_id})

    assert result["final_synthesis_path"].endswith("final_synthesis.md")
    submission_reports = [
        report
        for report in store.load_state(state.run_id).quality_reports
        if report.gate_name == "submission"
    ]
    assert len(submission_reports) == 1
    assert submission_reports[0].passed is True


def test_package_blocks_when_stale_marker_exists(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="C 题 河流水质评价。问题1：评价水质。"))
    run_dir = store.run_dir(state.run_id)
    stale_dir = run_dir / "stale"
    stale_dir.mkdir()
    (stale_dir / "sections.json").write_text(
        json.dumps({"reason": "claims changed"}, ensure_ascii=False),
        encoding="utf-8",
    )
    tools = _tools_for(store)

    with pytest.raises(RuntimeError, match="stale/sections.json"):
        tools["package_submission"].invoke({"run_id": state.run_id})


def test_review_submission_writes_paper_gate_report_when_markdown_is_missing(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="C 题 河流水质评价。问题1：评价水质。"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text(
        "模型报告说明水质评价问题、指标归一化、综合评分公式和结果解释。"
        * 12,
        encoding="utf-8",
    )
    (run_dir / "solve.py").write_text(
        "def main():\n"
        "    subproblem_id = 'q1'\n"
        "    print(subproblem_id)\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )
    (run_dir / "paper.tex").write_text(
        "\\section{摘要} 水质评价模型摘要。\n",
        encoding="utf-8",
    )
    tools = _tools_for(store)

    tools["review_submission"].invoke(
        {
            "run_id": state.run_id,
            "paper_draft": {},
            "experiment_result": {},
            "artifacts": ["modeling_report.md", "solve.py", "paper.tex"],
        }
    )

    paper_gate_path = run_dir / "trace" / "gate_reports" / "paper_gate.json"
    paper_review = (run_dir / "reviews" / "paper_review.md").read_text(encoding="utf-8")

    assert paper_gate_path.exists()
    assert "缺少论文章节" in paper_gate_path.read_text(encoding="utf-8")
    assert "缺少论文章节" in paper_review


def test_review_submission_records_paper_gate_when_latex_is_not_file(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="C 题 河流水质评价。问题1：评价水质。"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text(
        "模型报告说明水质评价问题、指标归一化、综合评分公式和结果解释。"
        * 12,
        encoding="utf-8",
    )
    (run_dir / "solve.py").write_text(
        "def main():\n"
        "    subproblem_id = 'q1'\n"
        "    print(subproblem_id)\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )
    (run_dir / "paper.tex").mkdir()
    tools = _tools_for(store)

    result = tools["review_submission"].invoke(
        {
            "run_id": state.run_id,
            "paper_draft": {},
            "experiment_result": {},
            "artifacts": ["modeling_report.md", "solve.py", "paper.tex"],
        }
    )

    paper_gate_path = run_dir / "trace" / "gate_reports" / "paper_gate.json"
    paper_review = (run_dir / "reviews" / "paper_review.md").read_text(encoding="utf-8")

    assert result["quality_report"]["passed"] is False
    assert paper_gate_path.exists()
    assert "缺少 paper.tex" in paper_gate_path.read_text(encoding="utf-8")
    assert "缺少 paper.tex" in paper_review


def test_review_submission_records_paper_gate_when_latex_has_invalid_encoding(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="C 题 河流水质评价。问题1：评价水质。"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text(
        "模型报告说明水质评价问题、指标归一化、综合评分公式和结果解释。"
        * 12,
        encoding="utf-8",
    )
    (run_dir / "solve.py").write_text(
        "def main():\n"
        "    subproblem_id = 'q1'\n"
        "    print(subproblem_id)\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )
    (run_dir / "paper.tex").write_bytes(b"\xff\xfe\xff")
    tools = _tools_for(store)

    result = tools["review_submission"].invoke(
        {
            "run_id": state.run_id,
            "paper_draft": {},
            "experiment_result": {},
            "artifacts": ["modeling_report.md", "solve.py", "paper.tex"],
        }
    )

    paper_gate_path = run_dir / "trace" / "gate_reports" / "paper_gate.json"

    assert result["quality_report"]["passed"] is False
    assert paper_gate_path.exists()
    assert "缺少 paper.tex" in paper_gate_path.read_text(encoding="utf-8")


def test_review_submission_does_not_infer_benchmark_from_model_text(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="C 题 通用抽样评价。问题1：建立抽样评价模型。"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text(
        "# Modeling Report\n\n"
        + "本通用问题使用二项抽样估计指标置信区间，但不属于 2024 B benchmark。\n" * 80,
        encoding="utf-8",
    )
    (run_dir / "solve.py").write_text(
        "def main():\n"
        "    subproblem_id = 'q1'\n"
        "    print(subproblem_id)\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )
    (run_dir / "paper.tex").write_text(
        "\\documentclass{ctexart}\n"
        "\\begin{document}\n"
        "\\section{摘要} 通用抽样评价模型。\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    tools = _tools_for(store)

    result = tools["review_submission"].invoke(
        {
            "run_id": state.run_id,
            "paper_draft": {},
            "experiment_result": {},
            "artifacts": ["modeling_report.md", "solve.py", "paper.tex"],
        }
    )

    required_fixes = result["quality_report"]["required_fixes"]
    assert not any("B 题子问题求解结果" in fix for fix in required_fixes)


def test_plan_model_uses_analyzed_problem_text_when_run_spec_question_is_placeholder(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="用户稍后补充题面"))
    tools = _tools_for(store)

    problem = tools["analyze_problem"].invoke(
        {"run_id": state.run_id, "question": B_LOOKING_TEXT}
    )
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )

    run_dir = store.run_dir(state.run_id)
    problem_contract = json.loads((run_dir / "contracts" / "problem_contract.json").read_text(encoding="utf-8"))
    routing_trace_path = run_dir / "trace" / "routing_decision.json"
    routing_after_plan = json.loads(routing_trace_path.read_text(encoding="utf-8"))

    experiment = tools["run_experiment"].invoke(
        {
            "run_id": state.run_id,
            "modeling_plan": plan["modeling_plan"],
            "data_files": [],
        }
    )
    routing_after_experiment = json.loads(routing_trace_path.read_text(encoding="utf-8"))

    assert [item["id"] for item in problem["problem_brief"]["subproblems"]] == ["q1", "q2", "q3", "q4"]
    assert [item["id"] for item in plan["modeling_plan"]["subproblem_plans"]] == ["q1", "q2", "q3", "q4"]
    assert [item["subproblem_id"] for item in problem_contract["subproblems"]] == ["q1", "q2", "q3", "q4"]
    assert routing_after_plan["rejected_routes"] == [BENCHMARK_2024_B_ID]
    assert routing_after_plan == routing_after_experiment
    assert routing_after_experiment["workflow_type"] == GENERIC_CUMCM_WORKFLOW
    assert routing_after_experiment["reason"] == (
        "problem text is treated as production input; benchmark routes require explicit options"
    )
    assert experiment["experiment_result"]["execution_status"] == "success"
    assert (run_dir / "results" / "q1_result.csv").exists()
    assert (run_dir / "results" / "q2_result.csv").exists()
    assert "抽样检测方案" in problem_contract["subproblems"][0]["question_text"]
    assert "检测和拆解决策" in problem_contract["subproblems"][1]["question_text"]


def test_plan_model_preserves_pdf_extracted_subproblems_after_long_preamble(tmp_path):
    pdf_extracted_text = (
        "2024 年高教社杯全国大学生数学建模竞赛题目\n"
        "（请先阅读全国大学生数学建模竞赛论文格式规范）\n"
        "B 题  生产过程中的决策问题\n"
        + "某企业生产某种畅销的电子产品，需要分别购买两种零配件。"
        * 12
        + "\n请建立数学模型，解决以下问题：\n"
        "问题1  供应商声称一批零配件的次品率不会超过某个标称值，请设计抽样检测方案。\n"
        "问题2  已知两种零配件和成品次品率，请为企业生产过程的各个阶段作出检测和拆解决策。\n"
        "问题3  对 m 道工序、n 个零配件，重复问题\n"
        "2，给出生产过程的决策方案。\n"
        "问题4  假设问题2 和问题3 中零配件、半成品和成品的次品率均是通过抽样检测方法得到的。\n"
    )
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question=pdf_extracted_text))
    tools = _tools_for(store)

    problem = tools["analyze_problem"].invoke(
        {"run_id": state.run_id, "question": pdf_extracted_text}
    )
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )

    run_dir = store.run_dir(state.run_id)
    problem_contract = json.loads((run_dir / "contracts" / "problem_contract.json").read_text(encoding="utf-8"))

    assert [item["id"] for item in problem["problem_brief"]["subproblems"]] == ["q1", "q2", "q3", "q4"]
    assert [item["id"] for item in plan["modeling_plan"]["subproblem_plans"]] == ["q1", "q2", "q3", "q4"]
    assert [item["subproblem_id"] for item in problem_contract["subproblems"]] == ["q1", "q2", "q3", "q4"]
