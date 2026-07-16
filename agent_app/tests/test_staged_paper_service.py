from __future__ import annotations

import importlib
import json
from typing import Any

import pytest


def _staged_paper_module() -> Any:
    try:
        return importlib.import_module("agent_app.services.staged_paper")
    except ModuleNotFoundError as exc:
        if exc.name == "agent_app.services.staged_paper":
            pytest.fail("agent_app.services.staged_paper module is missing")
        raise


def test_build_paper_outline_marks_abstract_last():
    staged_paper = _staged_paper_module()
    problem_brief = {
        "title": "生产过程中的决策问题",
        "background": "企业需要在检测成本和调换损失之间权衡。",
        "subproblems": [{"id": "q1"}, {"id": "q2"}],
    }

    outline = staged_paper.build_paper_outline(problem_brief)

    assert outline.title == "生产过程中的决策问题"
    assert outline.problem_background_summary == "企业需要在检测成本和调换损失之间权衡。"
    assert outline.subproblem_ids == ["q1", "q2"]
    assert outline.abstract_policy == "write_last_after_results"
    assert "01_abstract.md" in outline.deferred_sections
    assert "03_problem_background.md" in outline.deferred_sections
    assert "04_problem_restatement.md" in outline.deferred_sections
    assert "05_problem_analysis.md" in outline.deferred_sections
    assert "06_assumptions.md" in outline.deferred_sections
    assert outline.section_order == list(staged_paper.FINAL_SECTION_FILES)
    assert outline.early_sections == list(staged_paper.EARLY_SECTION_FILES)


def test_write_early_sections_does_not_write_abstract(tmp_path):
    staged_paper = _staged_paper_module()
    problem_brief = {
        "title": "生产过程中的决策问题",
        "background": "企业需要在检测成本和调换损失之间权衡。",
        "subproblems": [
            {"id": "q1", "objective": "设计抽样检测方案，控制检测成本。"},
            {"id": "q2", "objective": "建立生产决策模型，降低调换损失。"},
        ],
    }

    paths = staged_paper.write_early_sections(tmp_path, problem_brief)

    outline_path = tmp_path / "paper_outline.json"
    problem_restatement_path = tmp_path / "paper" / "pre_sections" / "02_problem_restatement.md"
    abstract_path = tmp_path / "paper" / "pre_sections" / "01_abstract.md"

    assert outline_path.exists()
    outline_payload = json.loads(outline_path.read_text(encoding="utf-8"))
    assert outline_payload["abstract_policy"] == "write_last_after_results"
    assert problem_restatement_path.exists()
    assert not abstract_path.exists()
    assert [path.name for path in paths] == list(staged_paper.EARLY_SECTION_FILES)

    problem_restatement = problem_restatement_path.read_text(encoding="utf-8")
    assert "q1" in problem_restatement
    assert "设计抽样检测方案，控制检测成本。" in problem_restatement

    forbidden_final_result_language = ("最终结果", "实验表明", "见结果表")
    for path in paths:
        section_text = path.read_text(encoding="utf-8")
        assert not any(phrase in section_text for phrase in forbidden_final_result_language)

    assumptions = (tmp_path / "paper" / "pre_sections" / "04_preliminary_assumptions.md").read_text(
        encoding="utf-8"
    )
    assert "初步" in assumptions
    assert "仅基于题目与输入资料" in assumptions


def test_write_early_sections_avoids_placeholder_language_for_missing_objective(tmp_path):
    staged_paper = _staged_paper_module()
    problem_brief = {
        "title": "通用建模题",
        "subproblems": [{"id": "q1"}],
    }

    paths = staged_paper.write_early_sections(tmp_path, problem_brief)

    combined_text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "待补充" not in combined_text
    assert "q1" in combined_text
    assert "从题面进一步确认建模目标" in combined_text


def test_write_early_sections_uses_question_text_and_title_for_objectives(tmp_path):
    staged_paper = _staged_paper_module()
    problem_brief = {
        "title": "生产决策题",
        "subproblems": [
            {"id": "q1", "question_text": "请设计抽样检测方案。"},
            {"id": "q2", "title": "建立拆解与退货决策模型"},
        ],
    }

    paths = staged_paper.write_early_sections(tmp_path, problem_brief)

    combined_text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "请设计抽样检测方案。" in combined_text
    assert "建立拆解与退货决策模型" in combined_text
    assert "从题面进一步确认建模目标" not in combined_text
