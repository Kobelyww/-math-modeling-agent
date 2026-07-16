from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_app.domain.contracts import SubproblemSolutionContract
from agent_app.domain.models import (
    ArtifactRef,
    ExperimentResult,
    ModelingPlan,
    PaperDraft,
)
from agent_app.domain.serialization import to_json_dict
from agent_app.evaluators import (
    evaluate_experiment,
    evaluate_input,
    evaluate_modeling,
    evaluate_paper,
    evaluate_submission,
)
from agent_app.evaluators.paper_gate import BANNED_INTERNAL_MARKERS


def _complete_paper_sections() -> dict[str, str]:
    def expanded(sentence: str, repeat: int = 12) -> str:
        return " ".join([sentence] * repeat)

    return {
        "摘要": expanded("本文围绕赛题目标建立可复现实验流程，并给出主要结论。", 6),
        "关键词": "数学建模；优化决策；证据追踪",
        "问题重述": expanded("本节重述赛题要求、输入数据、约束条件与需要提交的结果。"),
        "模型假设": expanded("样本相互独立，参数均来自题面、数据文件或显式实验估计。"),
        "符号说明": expanded("x 表示核心决策变量，c 表示成本参数，y 表示输出指标。"),
        "问题分析": expanded("本节分析约束与目标之间的关系，并说明各子问题依赖顺序。"),
        "模型建立与求解": expanded("建立规划模型并给出求解算法、变量定义、约束和结果文件。"),
        "结果分析": expanded("结果显示主要指标稳定，并能追踪到对应实验表格和 claim。"),
        "灵敏度": expanded("扰动关键参数后比较目标值变化，用于限定结论的适用范围。"),
        "模型评价": expanded("模型具有可解释性和可复现性，但对数据质量仍存在依赖。"),
        "参考文献": expanded("列出质量控制、运筹优化和统计推断相关参考资料。"),
        "附录": expanded("附录包含代码入口、实验数据、结果文件和审查报告路径。"),
    }


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
        experiment_conclusion_links=[
            "基线对比 -> 对应论文结论：回归模型可解释地预测交通流；关系：支撑",
            "灵敏度分析 -> 对应论文结论：结论在容量参数扰动下保持稳定；关系：限制",
        ],
    )

    report = evaluate_modeling(plan)

    assert report.passed is True
    assert report.score == 1.0


def test_modeling_gate_requires_experiment_conclusion_links():
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

    assert report.passed is False
    assert any("实验方案与论文结论关系" in item for item in report.required_fixes)


def test_modeling_gate_rejects_experiment_links_without_per_experiment_relationships():
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
        experiment_conclusion_links=[
            "基线对比",
            "灵敏度分析",
            "论文结论：回归模型可解释地预测交通流；关系：支撑",
        ],
    )

    report = evaluate_modeling(plan)

    assert report.passed is False
    assert any("实验方案与论文结论关系" in item for item in report.required_fixes)


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


def test_paper_gate_rejects_internal_context_and_thin_sections(tmp_path):
    paper = PaperDraft(
        markdown_path=tmp_path / "paper.md",
        latex_path=tmp_path / "paper.tex",
        sections={
            "摘要": "本文建立可复现的建模流程，并用结果文件支撑主要结论。",
            "关键词": "建模；优化；证据追踪",
            "问题重述": "Claim-Aware Section Context: internal planner notes must not leak.",
            "模型假设": "样本独立。",
            "符号说明": "x 表示决策变量。",
            "问题分析": "分析。",
            "模型建立与求解": "建立模型。",
            "结果分析": "结果稳定。",
            "灵敏度": "扰动参数。",
            "模型评价": "可解释。",
            "参考文献": "列出参考资料。",
            "附录": "代码见附录。",
        },
    )

    report = evaluate_paper(paper)

    assert report.passed is False
    assert any("内部上下文" in item or "internal" in item for item in report.required_fixes)
    assert any("章节内容过短" in item for item in report.required_fixes)


@pytest.mark.parametrize("marker", BANNED_INTERNAL_MARKERS)
def test_paper_gate_rejects_banned_markers_in_latex(tmp_path, marker):
    latex_path = tmp_path / "paper.tex"
    latex_path.write_text(
        "\\documentclass{ctexart}\n"
        "\\begin{document}\n"
        f"{marker}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    paper = PaperDraft(
        markdown_path=tmp_path / "paper.md",
        latex_path=latex_path,
        sections=_complete_paper_sections(),
    )

    report = evaluate_paper(paper)

    assert report.passed is False
    assert any("内部上下文" in item or "占" + "位" in item for item in report.required_fixes)


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
    latex_path = tmp_path / "paper.tex"
    latex_path.write_text(
        "\\documentclass{ctexart}\n\\begin{document}\n\\section{摘要} 完整论文。\n\\end{document}\n",
        encoding="utf-8",
    )
    paper = PaperDraft(
        markdown_path=tmp_path / "paper.md",
        latex_path=latex_path,
        sections=_complete_paper_sections(),
    )

    report = evaluate_paper(paper)

    assert report.passed is True
    assert report.score == 1.0


def test_paper_gate_rejects_missing_latex_file(tmp_path):
    paper = PaperDraft(
        markdown_path=tmp_path / "paper.md",
        latex_path=tmp_path / "paper.tex",
        sections=_complete_paper_sections(),
    )

    report = evaluate_paper(paper)

    assert report.passed is False
    assert "缺少 paper.tex" in report.required_fixes


def test_paper_gate_rejects_workflow_summary_even_with_required_sections(tmp_path):
    latex_path = tmp_path / "paper.tex"
    latex_path.write_text(
        "\\documentclass{ctexart}\n\\begin{document}\n\\section{摘要} 完整论文。\n\\end{document}\n",
        encoding="utf-8",
    )
    sections = _complete_paper_sections()
    sections["模型建立与求解"] = (
        "solver strategy 选择求解方式；baseline 求解流程；workflow summary。"
    )
    sections["结果分析"] = (
        "claim map 追踪到具体文件，但这里只是 workflow summary，没有真实结果解释。"
    )
    paper = PaperDraft(
        markdown_path=tmp_path / "paper.md",
        latex_path=latex_path,
        sections=sections,
    )

    report = evaluate_paper(paper)

    assert report.passed is False
    assert any(
        ("baseline" in item.lower() or "workflow" in item.lower())
        and ("真实推导" in item or "真实" in item)
        for item in report.required_fixes
    )


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


def test_submission_gate_rejects_placeholder_artifact_content(tmp_path):
    files = {
        "modeling_report.md": "# Modeling Plan\nDeepAgent generated model\n",
        "solve.py": "print('DeepAgent competition experiment placeholder')\n",
        "paper.tex": (
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "This draft summarizes the local modeling workflow.\n"
            "\\end{document}\n"
        ),
        "review_report.md": "# Review\n",
        "final_synthesis.md": "# Final\n",
        "run.json": "{}\n",
    }
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    artifacts = [
        ArtifactRef(name=name, path=Path(name), kind=Path(name).suffix.lstrip("."))
        for name in files
    ]

    report = evaluate_submission(artifacts, artifact_root=tmp_path)

    assert report.passed is False
    assert any("占位" in item for item in report.required_fixes)


def test_submission_gate_does_not_infer_benchmark_from_model_text(tmp_path):
    files = {
        "modeling_report.md": "# Modeling Report\n\n" + "通用抽样问题使用二项抽样估计参数，但不是 2024 B benchmark。\n" * 80,
        "solve.py": (
            "def main():\n"
            "    subproblem_id = 'q1'\n"
            "    print(subproblem_id)\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        ),
        "paper.tex": "\\documentclass{ctexart}\n\\begin{document}\n\\section{摘要} 通用问题。\n\\end{document}\n",
        "review_report.md": "# Review\n",
        "final_synthesis.md": "# Final\n",
        "run.json": "{}\n",
    }
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    artifacts = [
        ArtifactRef(name=name, path=Path(name), kind=Path(name).suffix.lstrip("."))
        for name in files
    ]

    report = evaluate_submission(artifacts, artifact_root=tmp_path)

    assert report.passed is True


def test_submission_gate_rejects_incomplete_subproblem_solution_contract(tmp_path):
    files = {
        "modeling_report.md": (
            "# Modeling Report\n\n"
            + "通用问题包含变量、约束、实验和结论映射。\n" * 80
        ),
        "solve.py": (
            "def main():\n"
            "    subproblem_id = 'q1'\n"
            "    print(subproblem_id)\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        ),
        "paper.tex": (
            "\\documentclass{ctexart}\n"
            "\\begin{document}\n"
            "\\section{摘要} 通用问题。\n"
            "\\end{document}\n"
        ),
        "review_report.md": "# Review\n",
        "final_synthesis.md": "# Final\n",
        "run.json": "{}\n",
    }
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    contract = SubproblemSolutionContract(
        subproblem_id="q1",
        question_text="评价水质",
        problem_type="optimization",
        status="draft",
        model_derivation_path=Path("subproblems/q1/model_derivation.md"),
        algorithm_path=Path("subproblems/q1/algorithm.md"),
        solver_path=Path("subproblems/q1/solver.py"),
        result_path=Path("subproblems/q1/result.csv"),
        result_interpretation_path=Path("subproblems/q1/result_interpretation.md"),
        symbol_delta_path=Path("subproblems/q1/symbol_delta.json"),
        claim_delta_path=Path("subproblems/q1/claim_delta.json"),
    )
    contract_path = tmp_path / "subproblems" / "q1" / "solution_contract.json"
    contract_path.parent.mkdir(parents=True)
    contract_path.write_text(
        json.dumps(to_json_dict(contract), ensure_ascii=False),
        encoding="utf-8",
    )
    artifacts = [
        ArtifactRef(name=name, path=Path(name), kind=Path(name).suffix.lstrip("."))
        for name in files
    ]

    report = evaluate_submission(artifacts, artifact_root=tmp_path)

    assert report.passed is False
    assert any("子问题求解包" in item for item in report.required_fixes)


def test_submission_gate_requires_benchmark_results_when_explicit(tmp_path):
    files = {
        "modeling_report.md": "# Modeling Report\n\n" + "显式 benchmark 需要固定结果文件。\n" * 80,
        "solve.py": (
            "def expected_profit():\n"
            "    return 1.0\n"
            "\n"
            "def main():\n"
            "    print(expected_profit())\n"
        ),
        "paper.tex": "\\documentclass{ctexart}\n\\begin{document}\n\\section{摘要} Benchmark。\n\\end{document}\n",
        "review_report.md": "# Review\n",
        "final_synthesis.md": "# Final\n",
        "run.json": "{}\n",
    }
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    artifacts = [
        ArtifactRef(name=name, path=Path(name), kind=Path(name).suffix.lstrip("."))
        for name in files
    ]

    report = evaluate_submission(
        artifacts,
        artifact_root=tmp_path,
        require_benchmark_results=True,
    )

    assert report.passed is False
    assert any("B 题子问题求解结果" in item for item in report.required_fixes)


def test_submission_gate_accepts_explicit_benchmark_canonical_results(tmp_path):
    files = {
        "modeling_report.md": "# Modeling Report\n\n" + "显式 benchmark 已生成 canonical 结果文件。\n" * 80,
        "solve.py": (
            "def expected_profit():\n"
            "    return 1.0\n"
            "\n"
            "def main():\n"
            "    print(expected_profit())\n"
        ),
        "paper.tex": "\\documentclass{ctexart}\n\\begin{document}\n\\section{摘要} Benchmark。\n\\end{document}\n",
        "review_report.md": "# Review\n",
        "final_synthesis.md": "# Final\n",
        "run.json": "{}\n",
    }
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    result_files = {
        "results/q1_sampling_plan.csv": "case,n,k\nq1,100,10\n",
        "results/q2_table1_decisions.csv": "case,expected_profit\n1,1.0\n",
        "results/q3_table2_tree_decisions.csv": "node,decision\nroot,inspect\n",
        "results/q4_uncertainty_re_solve.csv": "case,decision\nbase,stable\n",
        "results/parameter_audit.json": "{}\n",
        "results/model_equations.md": "# Equations\n",
    }
    for relative_path, content in result_files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    artifacts = [
        ArtifactRef(name=name, path=Path(name), kind=Path(name).suffix.lstrip("."))
        for name in files
    ]

    report = evaluate_submission(
        artifacts,
        artifact_root=tmp_path,
        require_benchmark_results=True,
    )

    assert report.passed is True
