from __future__ import annotations

import re

from agent_app.domain.contracts import SubproblemContract
from agent_app.workflow_packs.cumcm.taxonomy import classify_subproblem


QUESTION_PATTERN = re.compile(r"(?:问题|第)\s*(?P<num>[0-9一二三四五六七八九十]+)\s*[：:]")
QUESTION_REF_PATTERN = re.compile(r"问题\s*(?P<num>[0-9一二三四五六七八九十]+)")
NUMBER_MAP = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _question_number(raw_num: str, fallback: int) -> int:
    if raw_num in NUMBER_MAP:
        return NUMBER_MAP[raw_num]
    if raw_num.isdigit():
        return int(raw_num)
    return fallback


def recognize_subproblems(problem_text: str) -> list[SubproblemContract]:
    matches = list(QUESTION_PATTERN.finditer(problem_text))
    if not matches:
        classification = classify_subproblem(problem_text)
        return [
            SubproblemContract(
                subproblem_id="q1",
                question_text=problem_text.strip(),
                primary_type=classification.primary,
                secondary_types=classification.secondary,
                expected_outputs=["results/q1_result.csv"],
            )
        ]

    subproblems: list[SubproblemContract] = []
    for index, match in enumerate(matches):
        raw_num = match.group("num")
        number = _question_number(raw_num, fallback=index + 1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(problem_text)
        question_text = problem_text[start:end].strip()
        classification = classify_subproblem(question_text)
        problem_id = f"q{number}"
        subproblems.append(
            SubproblemContract(
                subproblem_id=problem_id,
                question_text=question_text,
                primary_type=classification.primary,
                secondary_types=classification.secondary,
                dependencies=_dependencies(question_text, current=problem_id),
                expected_outputs=[f"results/{problem_id}_result.csv"],
            )
        )
    return subproblems


def _dependencies(text: str, current: str) -> list[str]:
    dependencies: list[str] = []
    for match in QUESTION_REF_PATTERN.finditer(text):
        raw_num = match.group("num")
        number = _question_number(raw_num, fallback=0)
        dependency = f"q{number}"
        if dependency != current and dependency not in dependencies:
            dependencies.append(dependency)
    return dependencies
