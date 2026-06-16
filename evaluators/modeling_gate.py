from __future__ import annotations

from agent_app.domain.models import ModelingPlan, QualityReport


def evaluate_modeling(plan: ModelingPlan) -> QualityReport:
    checks = [
        (bool(plan.subproblem_plans), "每个小问需要建模目标"),
        (bool(plan.variables), "需要变量定义"),
        (bool(plan.assumptions), "需要模型假设"),
        (
            bool(plan.objective_functions or plan.evaluation_metrics),
            "需要目标函数或评价指标",
        ),
        (
            bool(plan.candidate_models and len(plan.candidate_models) >= 2),
            "需要主模型和备选或对比模型",
        ),
        (bool(plan.algorithm_plan), "需要求解算法说明"),
        (bool(plan.sensitivity_plan), "需要灵敏度或鲁棒性分析计划"),
    ]
    fixes = [message for passed, message in checks if not passed]
    passed = not fixes

    return QualityReport(
        gate_name="modeling",
        passed=passed,
        score=1.0 if passed else max(0.0, 1.0 - len(fixes) / len(checks)),
        required_fixes=fixes,
    )
