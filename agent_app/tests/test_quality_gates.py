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


def test_input_gate_accepts_question_and_existing_manifest(tmp_path):
    manifest_path = tmp_path / "inputs_manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")

    report = evaluate_input(question="题目", manifest_path=manifest_path)

    assert report.passed is True
    assert report.score == 1.0


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


def test_experiment_gate_accepts_failed_run_with_clear_diagnostic():
    result = ExperimentResult(
        code_path=Path("solve.py"),
        execution_status="failed",
        stderr="ValueError: input column missing",
        reproducibility_notes="失败原因已定位为输入字段缺失",
    )

    report = evaluate_experiment(result)

    assert report.passed is False
    assert "需要至少一次成功执行记录，或清晰失败诊断" not in report.required_fixes
    assert any("结果表格" in item for item in report.required_fixes)


def test_experiment_gate_accepts_complete_result():
    result = ExperimentResult(
        code_path=Path("solve.py"),
        execution_status="success",
        result_files=[Path("results.csv")],
        figure_files=[Path("figure.png")],
        sensitivity_results=["容量参数上调 5% 时目标值变化 1.2%"],
    )

    report = evaluate_experiment(result)

    assert report.passed is True
    assert report.score == 1.0


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


def test_paper_gate_requires_section_key_even_if_body_mentions_section(tmp_path):
    paper = PaperDraft(
        markdown_path=tmp_path / "paper.md",
        latex_path=tmp_path / "paper.tex",
        sections={
            "摘要": "本文分析问题",
            "关键词": "建模",
            "问题重述": "见题目",
            "模型假设": "样本独立",
            "符号说明": "x 表示需求量",
            "问题分析": "参考文献将在后续章节列出",
            "模型建立与求解": "建立规划模型",
            "结果分析": "结果稳定",
            "灵敏度": "扰动参数后结果稳定",
            "模型评价": "模型可解释",
            "附录": "代码见附录",
        },
    )

    report = evaluate_paper(paper)

    assert report.passed is False
    assert "缺少论文章节: 参考文献" in report.required_fixes


def test_paper_gate_allows_normal_words_containing_lue(tmp_path):
    paper = PaperDraft(
        markdown_path=tmp_path / "paper.md",
        latex_path=tmp_path / "paper.tex",
        sections={
            "摘要": "本文分析交通调度策略",
            "关键词": "建模；策略；优化",
            "问题重述": "重述赛题要求",
            "模型假设": "省略异常值不会影响总体趋势",
            "符号说明": "x 表示需求量",
            "问题分析": "分析约束与目标",
            "模型建立与求解": "建立规划模型并求解",
            "结果分析": "结果稳定",
            "灵敏度": "扰动参数后结果稳定",
            "模型评价": "模型可解释",
            "参考文献": "列出参考资料",
            "附录": "代码见附录",
        },
    )

    report = evaluate_paper(paper)

    assert not any("占" + "位" in item for item in report.required_fixes)


def test_paper_gate_accepts_complete_paper(tmp_path):
    paper = PaperDraft(
        markdown_path=tmp_path / "paper.md",
        latex_path=tmp_path / "paper.tex",
        sections={
            "摘要": "本文分析问题",
            "关键词": "建模",
            "问题重述": "重述赛题要求",
            "模型假设": "样本独立",
            "符号说明": "x 表示需求量",
            "问题分析": "分析约束与目标",
            "模型建立与求解": "建立规划模型并求解",
            "结果分析": "结果稳定",
            "灵敏度": "扰动参数后结果稳定",
            "模型评价": "模型可解释",
            "参考文献": "列出参考资料",
            "附录": "代码见附录",
        },
    )

    report = evaluate_paper(paper)

    assert report.passed is True
    assert report.score == 1.0


def test_submission_gate_requires_core_artifacts():
    artifacts = [
        ArtifactRef(name="modeling_report", path=Path("modeling_report.md"), kind="markdown"),
        ArtifactRef(name="solve_py", path=Path("solve.py"), kind="python"),
    ]

    report = evaluate_submission(artifacts)

    assert report.passed is False
    assert any("paper.tex" in item for item in report.required_fixes)


def test_submission_gate_accepts_core_artifacts():
    artifacts = [
        ArtifactRef(name="modeling_report", path=Path("modeling_report.md"), kind="markdown"),
        ArtifactRef(name="solve_py", path=Path("solve.py"), kind="python"),
        ArtifactRef(name="paper_tex", path=Path("paper.tex"), kind="latex"),
        ArtifactRef(name="review_report", path=Path("review_report.md"), kind="markdown"),
        ArtifactRef(name="final_synthesis", path=Path("final_synthesis.md"), kind="markdown"),
        ArtifactRef(name="run_json", path=Path("run.json"), kind="json"),
    ]

    report = evaluate_submission(artifacts)

    assert report.passed is True
    assert report.score == 1.0
