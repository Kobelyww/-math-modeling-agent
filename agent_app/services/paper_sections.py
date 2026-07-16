from __future__ import annotations

from pathlib import Path
from typing import Any


REQUIRED_SECTION_FILES: tuple[str, ...] = (
    "00_abstract.md",
    "01_problem_restatement.md",
    "02_assumptions.md",
    "03_symbols.md",
    "04_model_building.md",
    "05_solution_results.md",
    "06_sensitivity.md",
    "07_model_evaluation.md",
    "08_references.md",
    "09_appendix.md",
)

SECTION_TITLES: dict[str, str] = {
    "00_abstract.md": "摘要",
    "01_problem_restatement.md": "问题重述",
    "02_assumptions.md": "模型假设",
    "03_symbols.md": "符号说明",
    "04_model_building.md": "模型建立",
    "05_solution_results.md": "求解与结果分析",
    "06_sensitivity.md": "灵敏度分析",
    "07_model_evaluation.md": "模型评价",
    "08_references.md": "参考文献",
    "09_appendix.md": "附录",
}


def section_path(run_dir: Path, filename: str) -> Path:
    return run_dir / "paper" / "sections" / filename


def section_generation_order() -> tuple[str, ...]:
    return tuple(name for name in REQUIRED_SECTION_FILES if name != "00_abstract.md") + ("00_abstract.md",)


def build_section_context(
    section_file: str,
    problem_brief: dict[str, Any],
    modeling_plan: dict[str, Any],
    experiment_result: dict[str, Any],
    evidence_notes: list[str],
) -> dict[str, Any]:
    return {
        "section_file": section_file,
        "section_title": SECTION_TITLES.get(section_file, section_file),
        "problem_brief": problem_brief,
        "modeling_plan": modeling_plan,
        "result_paths": experiment_result.get("result_paths", []),
        "evidence_notes": evidence_notes,
    }


def merge_section_texts(run_dir: Path, section_files: tuple[str, ...] = REQUIRED_SECTION_FILES) -> str:
    parts = []
    for section_file in section_files:
        path = section_path(run_dir, section_file)
        if path.exists():
            parts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(part for part in parts if part) + "\n"
