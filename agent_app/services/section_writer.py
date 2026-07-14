from __future__ import annotations

from pathlib import Path

from agent_app.domain.contracts import Claim


CUMCM_SECTION_ORDER = [
    ("00_title", "title"),
    ("01_abstract", "abstract"),
    ("02_keywords", "keywords"),
    ("03_problem_restatement", "problem_restatement"),
    ("04_problem_analysis", "problem_analysis"),
    ("05_assumptions", "assumptions"),
    ("06_symbols", "symbols"),
    ("07_model_solution", "model_solution"),
    ("08_result_analysis", "result_analysis"),
    ("09_robustness_analysis", "robustness_analysis"),
    ("10_model_evaluation", "model_evaluation"),
    ("11_references", "references"),
    ("12_appendix", "appendix"),
]


def build_section_context(section: str, claims: list[Claim]) -> dict:
    matching = [claim for claim in claims if claim.section == section]
    return {
        "section": section,
        "claim_ids": [claim.claim_id for claim in matching],
        "claims": [
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "evidence": [str(evidence.path) for evidence in claim.evidence],
            }
            for claim in matching
        ],
    }


def write_section_files(run_dir: Path | str, claims: list[Claim]) -> list[Path]:
    root = Path(run_dir)
    section_dir = root / "sections"
    section_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for filename, section in CUMCM_SECTION_ORDER:
        context = build_section_context(section, claims)
        path = section_dir / f"{filename}.md"
        path.write_text(_render_claim_section(section, context), encoding="utf-8")
        paths.append(path)
    return paths


def _render_claim_section(section: str, context: dict) -> str:
    lines = [f"# {section}", ""]
    if context["claims"]:
        lines.append("## Claims")
        lines.extend(f"- {claim['claim_id']}: {claim['text']}" for claim in context["claims"])
    else:
        lines.append("本节暂无已支持结论；若后续写作需要新增结论，必须先补充 ClaimMap 和证据。")
    return "\n".join(lines) + "\n"
