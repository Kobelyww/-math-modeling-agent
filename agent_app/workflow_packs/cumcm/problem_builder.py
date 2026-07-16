from __future__ import annotations

import hashlib
import re
from pathlib import Path

from agent_app.domain.contracts import ProblemContract, ProjectType
from agent_app.workflow_packs.cumcm.recognizer import recognize_subproblems


def build_cumcm_problem_contract(
    problem_text: str,
    source_text_path: Path,
    tables: list[dict] | None = None,
    figures: list[dict] | None = None,
) -> ProblemContract:
    return ProblemContract(
        project_type=ProjectType.CUMCM,
        title=_extract_title(problem_text),
        year=_extract_year(problem_text),
        source_text_path=source_text_path,
        raw_text_digest=hashlib.sha256(problem_text.encode("utf-8")).hexdigest(),
        subproblems=recognize_subproblems(problem_text),
        required_deliverables=["modeling_report.md", "solve.py", "paper.md", "paper.tex", "review_report.md"],
    )


def _extract_year(problem_text: str) -> str:
    match = re.search(r"(20[0-9]{2})\s*年", problem_text)
    return match.group(1) if match else ""


def _extract_title(problem_text: str) -> str:
    match = re.search(r"([ABCDEF]\s*题\s*[^\n]+)", problem_text)
    if match:
        return " ".join(match.group(1).split())
    first_nonempty = next((line.strip() for line in problem_text.splitlines() if line.strip()), "")
    return first_nonempty[:80]
