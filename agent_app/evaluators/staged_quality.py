from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from agent_app.domain.contracts import SubproblemSolutionContract, SymbolDefinition
from agent_app.domain.models import QualityReport

OPTIMIZATION_LIKE_TYPES = {
    "optimization",
    "multi_objective_decision",
    "operations_research",
}
FORMULA_REQUIRED_TYPES = {
    "evaluation",
    "multi_objective_decision",
    "optimization",
    "operations_research",
    "prediction",
    "sampling",
    "sampling_test",
    "statistics",
}
OBJECTIVE_MARKERS = (
    "目标函数",
    "objective",
    "minimize",
    "maximize",
    "最小化",
    "最大化",
    "min ",
    "max ",
)
CONSTRAINT_MARKERS = (
    "约束",
    "constraint",
    "subject to",
    "s.t.",
    "<=",
    ">=",
    "≤",
    "≥",
)
DERIVATION_REQUIRED_MARKERS = {
    "变量": ("变量", "decision variable", "variable"),
    "参数": ("参数", "parameter"),
    "假设": ("假设", "assumption"),
}
CONCLUSION_LINK_MARKERS = (
    "论文结论",
    "结论关系",
    "支撑结论",
    "支持结论",
    "对应结论",
)
ALGORITHM_REQUIRED_MARKERS = {
    "输入": ("输入", "input schema", "input"),
    "输出": ("输出", "output schema", "output"),
    "步骤": ("步骤", "step", "pseudocode", "伪代码"),
}
FORMULA_PATTERN = re.compile(
    r"(\$[^$]+\$|\\\(|\\\[|\\sum|\\frac|[A-Za-z]\w*\s*[=<>≤≥])"
)
BASELINE_RESULT_MARKERS = (
    "baseline_score",
    "generic_cumcm_contract_workflow",
    "solved_baseline",
    "solver strategy 选择求解方式",
    "claim map 追踪到具体文件",
    "baseline 求解流程",
    "workflow summary",
)
RESULT_COLUMN_TERMS = (
    "decision",
    "objective",
    "estimate",
    "diagnostic",
    "决策",
    "目标",
    "估计",
    "诊断",
)
REQUIRED_ARTIFACT_FIELDS = {
    "model_derivation_path": "model_derivation",
    "algorithm_path": "algorithm",
    "solver_path": "solver",
    "result_path": "result",
    "result_interpretation_path": "result_interpretation",
    "symbol_delta_path": "symbol_delta",
    "claim_delta_path": "claim_delta",
}
MATH_BLOCK_PATTERN = re.compile(r"\$([^$]+)\$|\\\((.*?)\\\)|\\\[(.*?)\\\]", re.DOTALL)
SYMBOL_TOKEN_PATTERN = re.compile(r"(?<!\\)([A-Za-z][A-Za-z0-9]*(?:_\{?[A-Za-z0-9]+\}?)?)")
PLAIN_SUBSCRIPT_SYMBOL_PATTERN = re.compile(r"\b[A-Za-z]_\{?[A-Za-z0-9]+\}?")
PLAIN_EXPECTATION_SYMBOL_PATTERN = re.compile(r"\bE\[[A-Za-z][A-Za-z0-9_]*\]")
LATEX_COMMAND_PATTERN = re.compile(r"\\([A-Za-z]+)(?:_\{?([A-Za-z0-9]+)\}?)?")
LATEX_TEXT_COMMAND_PATTERN = re.compile(
    r"\\(?:mathrm|text|operatorname|mbox)\{[^{}]*\}"
)
LATEX_SYMBOL_COMMANDS = {
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "varepsilon",
    "zeta",
    "eta",
    "theta",
    "vartheta",
    "iota",
    "kappa",
    "lambda",
    "mu",
    "nu",
    "xi",
    "pi",
    "rho",
    "sigma",
    "tau",
    "upsilon",
    "phi",
    "varphi",
    "chi",
    "psi",
    "omega",
}
COMMON_MATH_WORDS = {
    "arg",
    "cos",
    "exp",
    "for",
    "frac",
    "log",
    "max",
    "min",
    "sin",
    "sum",
    "tan",
    "text",
}


@dataclass(frozen=True)
class ResultShape:
    columns: list[str]
    has_records: bool


def evaluate_derivation_artifact(path: Path, problem_type: str) -> QualityReport:
    fixes: list[str] = []
    text = _read_required_text(Path(path), "model_derivation", fixes)
    normalized_type = str(problem_type).strip().lower()
    normalized_text = text.lower()

    if text:
        for label, markers in DERIVATION_REQUIRED_MARKERS.items():
            if not any(marker.lower() in normalized_text for marker in markers):
                fixes.append(f"模型推导缺少{label}说明")
        if not any(marker in text for marker in CONCLUSION_LINK_MARKERS):
            fixes.append("模型推导需要说明与论文结论的关系")

    if normalized_type in FORMULA_REQUIRED_TYPES and text:
        if not FORMULA_PATTERN.search(text):
            fixes.append("模型推导需要写出关键公式")

    if normalized_type in OPTIMIZATION_LIKE_TYPES and text:
        if not any(marker in normalized_text for marker in OBJECTIVE_MARKERS):
            fixes.append("优化类推导需要明确目标函数")
        if not any(marker in normalized_text for marker in CONSTRAINT_MARKERS):
            fixes.append("优化类推导需要明确约束条件")

    return _quality_report("derivation", fixes, total_checks=4)


def evaluate_algorithm_artifact(algorithm_path: Path, result_path: Path) -> QualityReport:
    fixes: list[str] = []
    algorithm_text = _read_required_text(Path(algorithm_path), "algorithm", fixes)
    result_text = _read_required_text(Path(result_path), "result", fixes)

    if algorithm_text:
        normalized_algorithm = algorithm_text.lower()
        for label, markers in ALGORITHM_REQUIRED_MARKERS.items():
            if not any(marker.lower() in normalized_algorithm for marker in markers):
                fixes.append(f"算法说明缺少{label}schema或步骤")

    if result_text:
        normalized_result = result_text.lower()
        if any(marker in normalized_result for marker in BASELINE_RESULT_MARKERS):
            fixes.append("结果文件仍包含 baseline/workflow 摘要标记，需要真实求解结果")

        result_shape = _result_shape(Path(result_path), result_text)
        if not result_shape.has_records:
            fixes.append("结果文件缺少非空数据行或结果记录")
        if not _has_required_result_column(result_shape.columns):
            fixes.append("结果文件缺少 decision/objective/estimate/diagnostic 列")

    return _quality_report("algorithm", fixes, total_checks=4)


def evaluate_symbol_table(
    symbols: list[SymbolDefinition], paper_text: str
) -> QualityReport:
    fixes: list[str] = []
    defined_symbols: set[str] = set()

    for symbol in symbols:
        raw_symbol = str(symbol.symbol).strip()
        if raw_symbol:
            defined_symbols.add(_normalize_symbol(raw_symbol))

        missing_fields: list[str] = []
        if not raw_symbol:
            missing_fields.append("symbol")
        if not str(symbol.meaning).strip():
            missing_fields.append("meaning")
        if not str(symbol.unit).strip():
            missing_fields.append("unit")
        if not str(symbol.source_subproblem_id).strip():
            missing_fields.append("source")
        if _is_unset_symbol_path(symbol.first_used_in):
            missing_fields.append("first_used_in")
        if _is_unset_symbol_path(symbol.definition_artifact):
            missing_fields.append("definition_artifact")
        if missing_fields:
            display_symbol = raw_symbol or "<empty>"
            fixes.append(
                f"符号 {display_symbol} 缺少 meaning/unit/source 字段: "
                + ", ".join(missing_fields)
            )

    used_symbols = _symbols_used_in_text(paper_text, defined_symbols)
    missing_symbols = sorted(used_symbols - defined_symbols)
    if missing_symbols:
        fixes.append("论文使用未在符号表定义的符号: " + ", ".join(missing_symbols))
    unused_symbols = sorted(defined_symbols - used_symbols)
    if unused_symbols:
        fixes.append("符号表包含正文未使用的符号: " + ", ".join(unused_symbols))

    return _quality_report("symbol_table", fixes, total_checks=max(2, len(symbols) + 1))


def evaluate_staged_solution_package(
    contract: SubproblemSolutionContract, artifact_root: Path
) -> QualityReport:
    fixes: list[str] = []
    root = Path(artifact_root).resolve(strict=False)
    resolved_paths: dict[str, Path] = {}

    for field_name, label in REQUIRED_ARTIFACT_FIELDS.items():
        raw_path = getattr(contract, field_name)
        resolved_path, path_fix = _resolve_required_artifact(raw_path, root, label)
        if path_fix:
            fixes.append(path_fix)
            continue
        if resolved_path is None:
            continue
        resolved_paths[field_name] = resolved_path
        if not resolved_path.exists() or not resolved_path.is_file():
            fixes.append(f"缺少阶段产物: {label} ({raw_path})")

    if str(contract.status).strip().lower() != "complete":
        fixes.append(f"{contract.subproblem_id} solution contract status 不是 complete")

    if not fixes:
        derivation_report = evaluate_derivation_artifact(
            resolved_paths["model_derivation_path"], contract.problem_type
        )
        algorithm_report = evaluate_algorithm_artifact(
            resolved_paths["algorithm_path"], resolved_paths["result_path"]
        )
        for report in (derivation_report, algorithm_report):
            fixes.extend(report.required_fixes)

    return _quality_report(
        "staged_solution_package",
        fixes,
        total_checks=len(REQUIRED_ARTIFACT_FIELDS) + 2,
    )


def _read_required_text(path: Path, label: str, fixes: list[str]) -> str:
    if not path.exists() or not path.is_file():
        fixes.append(f"缺少阶段产物: {label} ({path})")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        fixes.append(f"无法读取阶段产物: {label} ({path})")
        return ""


def _result_shape(path: Path, text: str) -> ResultShape:
    if path.suffix.lower() == ".json":
        return _json_result_shape(text)

    rows = list(csv.reader(StringIO(text)))
    if not rows:
        return ResultShape(columns=[], has_records=False)
    columns = [cell.strip() for cell in rows[0] if cell.strip()]
    has_records = any(any(cell.strip() for cell in row) for row in rows[1:])
    return ResultShape(columns=columns, has_records=has_records)


def _json_result_shape(text: str) -> ResultShape:
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        return ResultShape(columns=[], has_records=False)
    if isinstance(payload, dict):
        columns = [str(key) for key in payload]
        return ResultShape(columns=columns, has_records=_has_non_empty_value(payload))
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        columns = sorted({str(key) for item in payload for key in item})
        has_records = any(_has_non_empty_value(item) for item in payload)
        return ResultShape(columns=columns, has_records=has_records)
    return ResultShape(columns=[], has_records=False)


def _has_non_empty_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_has_non_empty_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_non_empty_value(item) for item in value)
    return True


def _has_required_result_column(columns: list[str]) -> bool:
    normalized_columns = [_normalize_column(column) for column in columns]
    return any(
        term in column
        for column in normalized_columns
        for term in RESULT_COLUMN_TERMS
    )


def _normalize_column(column: str) -> str:
    return re.sub(r"[\s\-]+", "_", column.strip().lower())


def _is_unset_symbol_path(path: Path) -> bool:
    return Path(path) in {Path(""), Path(".")}


def _symbols_used_in_text(paper_text: str, defined_symbols: set[str]) -> set[str]:
    symbols = _symbols_used_in_math(paper_text)
    for token in PLAIN_SUBSCRIPT_SYMBOL_PATTERN.findall(paper_text):
        normalized = _normalize_symbol(token)
        if normalized:
            symbols.add(normalized)
    for token in PLAIN_EXPECTATION_SYMBOL_PATTERN.findall(paper_text):
        symbols.add(token)
    for symbol in defined_symbols:
        if _contains_symbol_literal(paper_text, symbol):
            symbols.add(symbol)
    return symbols


def _symbols_used_in_math(paper_text: str) -> set[str]:
    symbols: set[str] = set()
    for match in MATH_BLOCK_PATTERN.finditer(paper_text):
        block = next(group for group in match.groups() if group is not None)
        symbols.update(_latex_symbol_commands(block))
        scrubbed_block = _strip_latex_commands(block)
        for token in SYMBOL_TOKEN_PATTERN.findall(scrubbed_block):
            normalized = _normalize_symbol(token)
            if normalized and normalized.lower() not in COMMON_MATH_WORDS:
                symbols.add(normalized)
    return symbols


def _latex_symbol_commands(block: str) -> set[str]:
    symbols: set[str] = set()
    for match in LATEX_COMMAND_PATTERN.finditer(block):
        command = match.group(1)
        subscript = match.group(2)
        if command not in LATEX_SYMBOL_COMMANDS:
            continue
        symbol = f"\\{command}"
        if subscript:
            symbol += f"_{subscript}"
        symbols.add(symbol)
    return symbols


def _strip_latex_commands(block: str) -> str:
    without_text = LATEX_TEXT_COMMAND_PATTERN.sub(" ", block)
    return LATEX_COMMAND_PATTERN.sub(" ", without_text)


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().replace("{", "").replace("}", "")


def _contains_symbol_literal(text: str, symbol: str) -> bool:
    if not symbol:
        return False
    return re.search(
        rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])",
        text,
    ) is not None


def _resolve_required_artifact(
    raw_path: Path | str | None, artifact_root: Path, label: str
) -> tuple[Path | None, str | None]:
    if raw_path is None:
        return None, f"{label} 未设置有效文件路径，不能指向 artifact_root"

    try:
        relative_or_absolute = Path(raw_path)
    except TypeError:
        return None, f"{label} 未设置有效文件路径，不能指向 artifact_root"

    candidate = (
        relative_or_absolute
        if relative_or_absolute.is_absolute()
        else artifact_root / relative_or_absolute
    )
    resolved = candidate.resolve(strict=False)
    if resolved == artifact_root:
        return None, f"{label} 未设置有效文件路径，不能指向 artifact_root"
    if artifact_root not in resolved.parents:
        return None, f"{label} 路径必须位于 artifact_root 内: {raw_path}"
    return resolved, None


def _quality_report(
    gate_name: str, fixes: list[str], total_checks: int
) -> QualityReport:
    passed = not fixes
    return QualityReport(
        gate_name=gate_name,
        passed=passed,
        score=1.0 if passed else max(0.0, 1.0 - len(fixes) / total_checks),
        required_fixes=fixes,
    )
