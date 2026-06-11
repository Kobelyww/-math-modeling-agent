from __future__ import annotations

from agent_app.domain.models import ExperimentResult, QualityReport


def evaluate_experiment(result: ExperimentResult) -> QualityReport:
    fixes: list[str] = []

    has_failure_diagnostic = bool(result.stderr.strip() or result.reproducibility_notes.strip())

    if result.code_path is None or result.code_path.name != "solve.py":
        fixes.append("缺少 solve.py")
    if result.execution_status != "success" and not has_failure_diagnostic:
        fixes.append("需要至少一次成功执行记录，或清晰失败诊断")
    if not (result.result_files or result.tables or result.metrics):
        fixes.append("需要结果表格、指标或结构化结果")
    if not result.figure_files:
        fixes.append("需要图表生成计划或图表产物")
    if not result.sensitivity_results:
        fixes.append("需要灵敏度或鲁棒性分析结果")

    passed = not fixes
    return QualityReport(
        gate_name="experiment",
        passed=passed,
        score=1.0 if passed else max(0.0, 1.0 - len(fixes) / 5),
        required_fixes=fixes,
    )
