from __future__ import annotations

from agent_app.domain.models import ModelingPlan, QualityReport


EXPERIMENT_CONCLUSION_TERM = "论文结论"
EXPERIMENT_RELATION_TERMS = ("支撑", "限制", "证伪", "判断", "约束")


def _has_experiment_conclusion_link(value: str) -> bool:
    return EXPERIMENT_CONCLUSION_TERM in value and any(
        relation in value for relation in EXPERIMENT_RELATION_TERMS
    )


def _has_experiment_conclusion_links(value: list[str]) -> bool:
    links = [str(item).strip() for item in value if str(item).strip()]
    if not links:
        return False
    return all(_has_experiment_conclusion_link(item) for item in links)


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
        (
            _has_experiment_conclusion_links(plan.experiment_conclusion_links),
            "需要说明实验方案与论文结论关系",
        ),
    ]
    fixes = [message for passed, message in checks if not passed]
    passed = not fixes

    return QualityReport(
        gate_name="modeling",
        passed=passed,
        score=1.0 if passed else max(0.0, 1.0 - len(fixes) / len(checks)),
        required_fixes=fixes,
    )
