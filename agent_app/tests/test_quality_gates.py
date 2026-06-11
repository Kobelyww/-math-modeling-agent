from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import (
    ArtifactRef,
    ExperimentResult,
    ModelingPlan,
    PaperDraft,
)
from agent_app.evaluators import (
    evaluate_experiment,
    evaluate_input,
    evaluate_modeling,
    evaluate_paper,
    evaluate_submission,
)


def test_input_gate_requires_question_and_manifest(tmp_path):
    report = evaluate_input(question="题目", manifest_path=tmp_path / "inputs_manifest.json")

    assert report.passed is False
    assert any("inputs_manifest.json" in item for item in report.required_fixes)


def test_modeling_gate_accepts_complete_plan():
    plan = ModelingPlan(
        subproblem_plans=["问题一：建立回归预测模型"],
        variables={"x": "输入特征"},
        parameters={"beta": "回归系数"},
        assumptions=["样本独立"],
        objective_functions=["最小化均方误差"],
        constraints=["道路容量非负"],
        candidate_models=["线性回归", "随机森林"],
        selected_model="线性回归",
        algorithm_plan="最小二乘求解",
        evaluation_metrics=["RMSE"],
        sensitivity_plan="扰动容量参数 5% 比较结果",
    )

    report = evaluate_modeling(plan)

    assert report.passed is True
    assert report.score == 1.0


def test_experiment_gate_rejects_missing_code_and_sensitivity():
    result = ExperimentResult(execution_status="success")

    report = evaluate_experiment(result)

    assert report.passed is False
    assert any("solve.py" in item for item in report.required_fixes)
    assert any("灵敏度" in item for item in report.required_fixes)


def test_paper_gate_rejects_missing_sections_and_placeholder_text(tmp_path):
    paper = PaperDraft(
        markdown_path=tmp_path / "paper.md",
        latex_path=tmp_path / "paper.tex",
        sections={
            "摘要": "本文分析问题",
            "关键词": "建模",
            "问题重述": "见题目",
            "模型假设": "TO" + "DO",
        },
    )

    report = evaluate_paper(paper)

    assert report.passed is False
    assert any("符号说明" in item for item in report.required_fixes)
    assert any("占" + "位" in item for item in report.required_fixes)


def test_submission_gate_requires_core_artifacts():
    artifacts = [
        ArtifactRef(name="modeling_report", path=Path("modeling_report.md"), kind="markdown"),
        ArtifactRef(name="solve_py", path=Path("solve.py"), kind="python"),
    ]

    report = evaluate_submission(artifacts)

    assert report.passed is False
    assert any("paper.tex" in item for item in report.required_fixes)
