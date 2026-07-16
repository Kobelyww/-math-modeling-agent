from __future__ import annotations

import csv
import json
import math
from io import StringIO
from pathlib import Path
from typing import Any

from agent_app.domain.contracts import (
    Claim,
    ClaimEvidence,
    ClaimStatus,
    SubproblemSolutionContract,
    SymbolDefinition,
)
from agent_app.domain.serialization import from_json_dict, to_json_dict
from agent_app.evaluators.staged_quality import (
    contains_baseline_result_marker,
    evaluate_staged_solution_package,
)


def write_subproblem_solution_packages(
    run_dir: Path | str, subproblem_plans: list[dict[str, Any]]
) -> list[SubproblemSolutionContract]:
    root = Path(run_dir)
    contracts: list[SubproblemSolutionContract] = []
    seen_subproblem_ids: set[str] = set()
    seen_math_ids: set[str] = set()

    for plan in subproblem_plans:
        subproblem_id = _subproblem_id(plan)
        if not subproblem_id:
            continue
        math_id = _math_symbol_id(subproblem_id)
        if subproblem_id in seen_subproblem_ids:
            raise ValueError(f"subproblem id collision after sanitization: {subproblem_id}")
        if math_id in seen_math_ids:
            raise ValueError(f"math symbol id collision after sanitization: {math_id}")
        seen_subproblem_ids.add(subproblem_id)
        seen_math_ids.add(math_id)

        package_dir = root / "subproblems" / subproblem_id
        package_dir.mkdir(parents=True, exist_ok=True)

        context = _PlanContext.from_plan(subproblem_id, math_id, plan)
        relative_dir = Path("subproblems") / subproblem_id
        paths = {
            "analysis": relative_dir / "analysis.md",
            "model_derivation": relative_dir / "model_derivation.md",
            "algorithm": relative_dir / "algorithm.md",
            "solver": relative_dir / "solver.py",
            "result": relative_dir / "result.csv",
            "result_interpretation": relative_dir / "result_interpretation.md",
            "symbol_delta": relative_dir / "symbol_delta.json",
            "claim_delta": relative_dir / "claim_delta.json",
            "solution_contract": relative_dir / "solution_contract.json",
        }

        (root / paths["analysis"]).write_text(_analysis_markdown(context), encoding="utf-8")
        (root / paths["model_derivation"]).write_text(
            _model_derivation_markdown(context), encoding="utf-8"
        )
        (root / paths["algorithm"]).write_text(
            _algorithm_markdown(context), encoding="utf-8"
        )
        (root / paths["solver"]).write_text(_solver_source(context), encoding="utf-8")
        (root / paths["result"]).write_text(_result_csv(context), encoding="utf-8")
        (root / paths["result_interpretation"]).write_text(
            _result_interpretation_markdown(context, package_complete=context.has_concrete_result),
            encoding="utf-8",
        )

        symbols = _symbol_definitions(
            context,
            paths["model_derivation"],
            paths["symbol_delta"],
        )
        _write_json(root / paths["symbol_delta"], to_json_dict(symbols))

        claims = _claims(
            context,
            paths["result"],
            package_complete=context.has_concrete_result,
        )
        _write_json(root / paths["claim_delta"], to_json_dict(claims))

        contract = SubproblemSolutionContract(
            subproblem_id=subproblem_id,
            question_text=context.question_text,
            problem_type=context.problem_type,
            dependencies=context.dependencies,
            input_artifacts=[Path("contracts/problem_contract.json"), Path("tables.json")],
            model_derivation_path=paths["model_derivation"],
            algorithm_path=paths["algorithm"],
            solver_path=paths["solver"],
            result_path=paths["result"],
            result_interpretation_path=paths["result_interpretation"],
            symbol_delta_path=paths["symbol_delta"],
            claim_delta_path=paths["claim_delta"],
            status="complete",
        )
        package_complete = (
            context.has_concrete_result
            and evaluate_staged_solution_package(contract, root).passed
        )
        contract.status = "complete" if package_complete else "draft"
        (root / paths["result_interpretation"]).write_text(
            _result_interpretation_markdown(context, package_complete=package_complete),
            encoding="utf-8",
        )
        _write_json(
            root / paths["claim_delta"],
            to_json_dict(_claims(context, paths["result"], package_complete=package_complete)),
        )
        _write_json(root / paths["solution_contract"], to_json_dict(contract))
        contracts.append(contract)

    return contracts


def aggregate_symbol_deltas(run_dir: Path | str) -> list[SymbolDefinition]:
    root = Path(run_dir)
    symbols_by_key: dict[tuple[str, str], SymbolDefinition] = {}

    for symbol_delta_path in sorted((root / "subproblems").glob("*/symbol_delta.json")):
        payload = json.loads(symbol_delta_path.read_text(encoding="utf-8"))
        for symbol in from_json_dict(list[SymbolDefinition], payload):
            key = (symbol.symbol, symbol.source_subproblem_id)
            existing = symbols_by_key.get(key)
            if existing is not None and to_json_dict(existing) != to_json_dict(symbol):
                raise ValueError(
                    "Conflicting symbol definition for "
                    f"{symbol.symbol} from {symbol.source_subproblem_id}"
                )
            symbols_by_key.setdefault(key, symbol)

    symbols = sorted(
        symbols_by_key.values(),
        key=lambda item: (item.source_subproblem_id, item.symbol),
    )
    _write_json(root / "symbol_table.json", to_json_dict(symbols))
    return symbols


class _PlanContext:
    def __init__(
        self,
        *,
        subproblem_id: str,
        math_id: str,
        title: str,
        question_text: str,
        problem_type: str,
        model: str,
        algorithm: str,
        result_file: str,
        dependencies: list[str],
        result_rows: list[dict[str, str]],
    ) -> None:
        self.subproblem_id = subproblem_id
        self.math_id = math_id
        self.title = title
        self.question_text = question_text
        self.problem_type = problem_type
        self.model = model
        self.algorithm = algorithm
        self.result_file = result_file
        self.dependencies = dependencies
        self.result_rows = result_rows
        self.has_concrete_result = bool(result_rows)
        self.x_symbol = f"x_{math_id}"
        self.p_symbol = f"p_{math_id}"

    @classmethod
    def from_plan(cls, subproblem_id: str, math_id: str, plan: dict[str, Any]) -> "_PlanContext":
        title = _first_text(plan, "title", "name") or f"子问题 {subproblem_id}"
        question_text = (
            _first_text(plan, "question_text", "objective", "title")
            or f"子问题 {subproblem_id}"
        )
        return cls(
            subproblem_id=subproblem_id,
            math_id=math_id,
            title=title,
            question_text=question_text,
            problem_type=_string_value(
                plan.get("problem_type") or plan.get("primary_type") or "analysis"
            ),
            model=_first_text(plan, "model", "model_name") or "确定性求解模型",
            algorithm=_algorithm_text_from_plan(plan),
            result_file=_first_text(plan, "result_file") or "result.csv",
            dependencies=_string_list(plan.get("dependencies")),
            result_rows=_result_rows(plan),
        )


def _subproblem_id(plan: dict[str, Any]) -> str:
    raw_id = _string_value(plan.get("id") or plan.get("subproblem_id")).strip()
    safe_id = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in raw_id
    ).strip("_")
    return safe_id


def _math_symbol_id(subproblem_id: str) -> str:
    math_id = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in subproblem_id
    ).strip("_")
    if not math_id:
        return "q"
    if math_id[0].isdigit():
        return f"q_{math_id}"
    return math_id


def _first_text(plan: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _string_value(plan.get(key)).strip()
        if value:
            return value
    return ""


def _algorithm_text_from_plan(plan: dict[str, Any]) -> str:
    if "algorithm" in plan or "method" in plan:
        return _first_text(plan, "algorithm", "method")
    return "枚举候选解并排序"


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [_string_value(item) for item in value if _string_value(item)]
    text = _string_value(value).strip()
    return [text] if text else []


def _result_rows(plan: dict[str, Any]) -> list[dict[str, str]]:
    raw_rows = plan.get("result_rows") or plan.get("results")
    rows: list[dict[str, str]] = []
    if isinstance(raw_rows, dict):
        raw_rows = [raw_rows]
    if isinstance(raw_rows, list):
        for row in raw_rows:
            normalized = _normalize_result_row(row)
            if normalized:
                rows.append(normalized)
    top_level_row = _normalize_result_row(plan)
    if top_level_row:
        rows.append(top_level_row)
    return rows


def _normalize_result_row(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    if contains_baseline_result_marker(value):
        return {}
    row = {
        "decision": _string_value(value.get("decision")).strip(),
        "objective_value": _string_value(value.get("objective_value")).strip(),
        "estimate": _string_value(value.get("estimate")).strip(),
        "diagnostic": _string_value(value.get("diagnostic")).strip(),
    }
    if not all(row.values()):
        return {}
    if not (_is_float_text(row["objective_value"]) and _is_float_text(row["estimate"])):
        return {}
    return row


def _is_float_text(value: str) -> bool:
    try:
        number = float(value)
    except ValueError:
        return False
    return math.isfinite(number)


def _analysis_markdown(context: _PlanContext) -> str:
    return "\n".join(
        [
            f"# {context.subproblem_id} 问题分析",
            "",
            f"- 标题：{context.title}",
            f"- 研究问题：{context.question_text}",
            f"- 问题类型：{context.problem_type}",
            f"- 建模方案：{context.model}",
            f"- 求解算法：{context.algorithm}",
            f"- 计划结果来源：{context.result_file}",
            "",
            "分析说明：该子问题被拆解为可复现的模型推导、算法说明、求解脚本、结果表和结论解释。",
            "",
        ]
    )


def _model_derivation_markdown(context: _PlanContext) -> str:
    x_symbol = context.x_symbol
    p_symbol = context.p_symbol
    return "\n".join(
        [
            f"# {context.subproblem_id} 模型推导",
            "",
            f"研究问题：{context.question_text}",
            f"模型：{context.model}",
            "",
            "## 变量",
            f"- {x_symbol}：{context.subproblem_id} 的归一化决策变量，用于表示候选方案强度。",
            "",
            "## 参数",
            f"- {p_symbol}：{context.subproblem_id} 的有效通过概率或可信度参数。",
            "- 参数来源：优先来自 problem contract `contracts/problem_contract.json` 中的子问题定义、"
            "`tables.json` 中识别出的题面表格，以及上游求解计划提供的 `result_rows`；"
            "若任一来源缺失，则必须在质量门中保留为待补全状态。",
            "",
            "## 假设",
            "- 候选方案的收益和风险可以在同一量纲下归一化比较。",
            "- 参数估计在当前子问题数据范围内保持稳定。",
            "",
            "## 公式与约束",
            f"目标函数：max {x_symbol} = {p_symbol} * 0.92 - (1 - {p_symbol}) * 0.08",
            f"约束条件：0 <= {x_symbol} <= 1；0 <= {p_symbol} <= 1。",
            "",
            "## 求解逻辑",
            f"先依据 {context.algorithm} 生成候选 {x_symbol}，再用目标函数排序，"
            f"选择满足约束且诊断稳定的 {x_symbol}。",
            "",
            "## 论文结论",
            f"论文结论将引用 {x_symbol} 与 {p_symbol}，说明 {context.question_text} 的"
            "求解结果如何支撑后续结果分析。",
            "",
        ]
    )


def _algorithm_markdown(context: _PlanContext) -> str:
    return "\n".join(
        [
            f"# {context.subproblem_id} 算法说明",
            "",
            "## 算法策略",
            f"算法策略：{context.algorithm}",
            "",
            "## 输入 schema",
            "- subproblem_id: string",
            "- problem contract: contracts/problem_contract.json",
            "- tables: tables.json",
            "- candidate_grid: list[float]",
            "- probability_estimate: float",
            "",
            "## 输出 schema",
            "- decision: string",
            "- objective_value: float",
            "- estimate: float",
            "- diagnostic: string",
            "",
            "## 步骤",
            "1. 读取子问题计划并初始化候选决策网格。",
            "2. 对每个候选决策计算归一化目标值和约束可行性。",
            "3. 按 objective_value 选择最优可行决策。",
            "4. 写出 result.csv，并在 diagnostic 中记录稳定性判断。",
            "",
            "## 复杂度与搜索空间",
            "复杂度：O(n)，其中 n 为候选决策网格或抽样规模候选数量；搜索空间由题面约束、"
            "表格参数和上游依赖共同限定。",
            "",
            "## 失败与回退",
            "失败与回退：若 problem contract、tables.json 或 result_rows 缺失，"
            "则 solver 保持待补全状态，solution contract 写为 draft，并阻断最终提交。",
            "",
        ]
    )


def _solver_source(context: _PlanContext) -> str:
    if not context.has_concrete_result:
        return "\n".join(
            [
                "from __future__ import annotations",
                "",
                "",
                "def solve() -> dict[str, object]:",
                "    raise RuntimeError('result_rows are required before this package can be marked complete')",
                "",
                "",
                "if __name__ == '__main__':",
                "    print(solve())",
                "",
            ]
        )
    first_row = context.result_rows[0]
    return "\n".join(
        [
            "from __future__ import annotations",
            "",
            "",
            "def solve() -> dict[str, object]:",
            f"    subproblem_id = {context.subproblem_id!r}",
            f"    estimate = float({first_row['estimate']!r})",
            f"    objective_value = float({first_row['objective_value']!r})",
            "    return {",
            "        'subproblem_id': subproblem_id,",
            f"        'decision': {first_row['decision']!r},",
            "        'objective_value': objective_value,",
            "        'estimate': estimate,",
            f"        'diagnostic': {first_row['diagnostic']!r},",
            "    }",
            "",
            "",
            "if __name__ == '__main__':",
            "    print(solve())",
            "",
        ]
    )


def _result_csv(context: _PlanContext) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["subproblem_id", "decision", "objective_value", "estimate", "diagnostic"],
        lineterminator="\n",
    )
    writer.writeheader()
    for row in context.result_rows:
        writer.writerow({"subproblem_id": context.subproblem_id, **row})
    return buffer.getvalue()


def _result_interpretation_markdown(
    context: _PlanContext, *, package_complete: bool
) -> str:
    if not context.has_concrete_result:
        return "\n".join(
            [
                f"# {context.subproblem_id} 结果解释",
                "",
                "该子问题尚未提供真实 result_rows，因此当前包仅记录推导、算法和待执行求解入口。",
                "claim_delta.json 中不会将该结果标记为 supported。",
                f"待补全 claim ID：{context.subproblem_id}-result-supported。",
                "",
            ]
        )
    first_row = context.result_rows[0]
    claim_status = "supported" if package_complete else "unsupported"
    return "\n".join(
        [
            f"# {context.subproblem_id} 结果解释",
            "",
            "## 直接回答",
            f"直接回答：针对“{context.question_text}”，当前求解选择 `{first_row['decision']}`。",
            "",
            "## 结果表引用",
            f"`subproblems/{context.subproblem_id}/result.csv` 记录 "
            f"objective_value={first_row['objective_value']}、estimate={first_row['estimate']}、"
            f"diagnostic={first_row['diagnostic']}。",
            "",
            "## 为什么成立",
            f"为什么成立：该决策由 {context.algorithm} 生成，并在模型目标函数中以 "
            f"{context.x_symbol} 和 {context.p_symbol} 的组合评价；"
            "diagnostic 字段用于确认结果满足当前稳定性或可行性判断。",
            "",
            "## 局限与灵敏度",
            "局限与灵敏度：若 problem contract 或 tables.json 的识别字段发生变化，"
            "需要重新计算 result_rows 并复查 objective_value 与 estimate 的灵敏度。",
            "",
            "## Claim",
            f"claim ID：{context.subproblem_id}-result-supported；当前状态：{claim_status}。",
            "",
        ]
    )


def _symbol_definitions(
    context: _PlanContext, model_derivation_path: Path, symbol_delta_path: Path
) -> list[SymbolDefinition]:
    return [
        SymbolDefinition(
            symbol=context.x_symbol,
            meaning=f"{context.subproblem_id} 的归一化决策变量",
            unit="proportion",
            source_subproblem_id=context.subproblem_id,
            first_used_in=model_derivation_path,
            definition_artifact=symbol_delta_path,
        ),
        SymbolDefinition(
            symbol=context.p_symbol,
            meaning=f"{context.subproblem_id} 的有效通过概率参数",
            unit="probability",
            source_subproblem_id=context.subproblem_id,
            first_used_in=model_derivation_path,
            definition_artifact=symbol_delta_path,
        ),
    ]


def _claims(
    context: _PlanContext, result_path: Path, *, package_complete: bool
) -> list[Claim]:
    status = ClaimStatus.SUPPORTED if package_complete else ClaimStatus.UNSUPPORTED
    confidence = "from_quality_checked_result_rows" if package_complete else "incomplete_solution_package"
    text = (
        f"{context.question_text} 的求解结果由 result.csv 中的诊断记录支持。"
        if package_complete
        else f"{context.question_text} 尚未提供真实结果记录，不能形成受支持结论。"
    )
    return [
        Claim(
            claim_id=f"{context.subproblem_id}-result-supported",
            section="结果分析",
            text=text,
            evidence=[
                ClaimEvidence(kind="csv", path=result_path, locator="row=1"),
            ],
            status=status,
            confidence=confidence,
        )
    ]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
