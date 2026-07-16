from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_app.domain.contracts import PaperOutline
from agent_app.domain.serialization import to_json_dict


EARLY_SECTION_FILES: tuple[str, ...] = (
    "00_title.md",
    "01_problem_background.md",
    "02_problem_restatement.md",
    "03_problem_analysis.md",
    "04_preliminary_assumptions.md",
)

FINAL_SECTION_FILES: tuple[str, ...] = (
    "00_title.md",
    "01_abstract.md",
    "02_keywords.md",
    "03_problem_background.md",
    "04_problem_restatement.md",
    "05_problem_analysis.md",
    "06_assumptions.md",
    "07_symbols.md",
    "08_model_derivation.md",
    "09_algorithm_and_solution.md",
    "10_results.md",
    "11_sensitivity.md",
    "12_model_evaluation.md",
    "13_references.md",
    "14_appendix.md",
)

def build_paper_outline(problem_brief: dict[str, Any]) -> PaperOutline:
    title = _clean_text(problem_brief.get("title")) or "数学建模竞赛论文"
    background = _clean_text(problem_brief.get("background"))
    subproblem_ids = [item["id"] for item in _subproblem_items(problem_brief)]

    deferred_sections = [section_file for section_file in FINAL_SECTION_FILES if section_file != "00_title.md"]

    return PaperOutline(
        title=title,
        problem_background_summary=background,
        subproblem_ids=subproblem_ids,
        section_order=list(FINAL_SECTION_FILES),
        early_sections=list(EARLY_SECTION_FILES),
        deferred_sections=deferred_sections,
        abstract_policy="write_last_after_results",
    )


def write_early_sections(run_dir: Path | str, problem_brief: dict[str, Any]) -> list[Path]:
    run_path = Path(run_dir)
    outline = build_paper_outline(problem_brief)

    outline_path = run_path / "paper_outline.json"
    outline_path.parent.mkdir(parents=True, exist_ok=True)
    outline_path.write_text(
        json.dumps(to_json_dict(outline), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    pre_sections_dir = run_path / "paper" / "pre_sections"
    pre_sections_dir.mkdir(parents=True, exist_ok=True)

    section_texts = _early_section_texts(outline, problem_brief)
    paths: list[Path] = []
    for section_file in EARLY_SECTION_FILES:
        path = pre_sections_dir / section_file
        path.write_text(section_texts[section_file], encoding="utf-8")
        paths.append(path)
    return paths


def _early_section_texts(outline: PaperOutline, problem_brief: dict[str, Any]) -> dict[str, str]:
    subproblems = _subproblem_items(problem_brief)
    background = outline.problem_background_summary or "题目未提供单独的背景说明，后续将以输入资料为准补充。"
    subproblem_lines = _subproblem_lines(subproblems)

    return {
        "00_title.md": f"# {outline.title}\n",
        "01_problem_background.md": (
            "# 问题背景\n\n"
            f"{background}\n"
        ),
        "02_problem_restatement.md": (
            "# 问题重述\n\n"
            "本文前期围绕以下子问题整理建模任务：\n\n"
            f"{subproblem_lines}\n"
        ),
        "03_problem_analysis.md": (
            "# 问题分析\n\n"
            "本阶段只进行题意拆解与建模准备，不写入求解结论。\n\n"
            f"{_analysis_lines(subproblems)}\n"
        ),
        "04_preliminary_assumptions.md": (
            "# 初步假设\n\n"
            "以下假设仅基于题目与输入资料，用于前期建模准备，后续需结合求解过程与证据审查更新。\n\n"
            "- 题目给出的数据、约束和业务描述在前期建模中暂按可信输入处理。\n"
            "- 未在题面中明确给出的参数先作为待审查参数记录，不在本阶段给出结论性取值。\n"
        ),
    }


def _subproblem_items(problem_brief: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    raw_subproblems = problem_brief.get("subproblems", [])
    if not isinstance(raw_subproblems, list):
        return items

    for raw_item in raw_subproblems:
        if not isinstance(raw_item, dict):
            continue
        subproblem_id = _clean_text(raw_item.get("id"))
        if not subproblem_id:
            continue
        items.append(
            {
                "id": subproblem_id,
                "objective": _first_present_text(
                    raw_item,
                    ("objective", "question_text", "title"),
                ),
            }
        )
    return items


def _subproblem_lines(subproblems: list[dict[str, str]]) -> str:
    if not subproblems:
        return "- 暂未识别到编号子问题，后续需从题面补充。\n"
    return "".join(
        f"- {item['id']}: {item['objective'] or '从题面进一步确认建模目标。'}\n"
        for item in subproblems
    )


def _analysis_lines(subproblems: list[dict[str, str]]) -> str:
    if not subproblems:
        return "- 先确认题目目标、约束、输入数据和可交付内容。\n"
    return "".join(
        f"- {item['id']}: 明确目标、约束、输入资料和后续模型接口。"
        f"{' 目标：' + item['objective'] if item['objective'] else ''}\n"
        for item in subproblems
    )


def _clean_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _first_present_text(source: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _clean_text(source.get(key))
        if value:
            return value
    return ""


__all__ = [
    "EARLY_SECTION_FILES",
    "FINAL_SECTION_FILES",
    "build_paper_outline",
    "write_early_sections",
]
