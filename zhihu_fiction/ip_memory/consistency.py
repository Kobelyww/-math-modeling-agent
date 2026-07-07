"""Deterministic consistency checks against IP memory."""
from __future__ import annotations

import re

from zhihu_fiction.ip_memory.models import IPMemory


_CLAUSE_SPLIT_RE = re.compile(r"[，。；！？!?;,\n]+")
_VISUAL_CONTEXT_CHARS = 12


def review_consistency(stage: str, output: str, memory: IPMemory | None) -> dict:
    """Review generated output against known IP memory facts."""
    if memory is None:
        return {
            "stage": stage,
            "status": "ok",
            "warnings": [],
            "score": 1.0,
        }

    text = str(output or "")
    warnings: list[str] = []
    warnings.extend(_character_identity_warnings(text, memory))
    warnings.extend(_world_fact_warnings(text, memory))
    return {
        "stage": stage,
        "status": "warning" if warnings else "ok",
        "warnings": warnings,
        "score": _score(warnings),
    }


def _character_identity_warnings(output: str, memory: IPMemory) -> list[str]:
    warnings: list[str] = []
    known_names = [card.name for card in memory.characters if card.name]
    for card in memory.characters:
        if not card.name or card.name not in output or not card.visual_identity:
            continue
        conflicts = []
        other_names = [name for name in known_names if name != card.name]
        for clause in _clauses_containing(output, card.name):
            for local_context in _local_contexts_around_name(
                clause,
                card.name,
                other_names,
            ):
                conflicts.extend(_visual_conflicts(card.visual_identity, local_context))
        if conflicts:
            detail = "、".join(_dedupe(conflicts))
            warnings.append(
                f"{card.name}的视觉身份与记忆不一致：记忆为{card.visual_identity}，输出出现{detail}。"
            )
    return warnings


def _clauses_containing(output: str, name: str) -> list[str]:
    return [
        clause.strip()
        for clause in _CLAUSE_SPLIT_RE.split(output)
        if name in clause
    ]


def _local_contexts_around_name(
    clause: str,
    name: str,
    other_names: list[str],
) -> list[str]:
    contexts: list[str] = []
    search_from = 0
    while (start := clause.find(name, search_from)) >= 0:
        end = start + len(name)
        left_boundary = max(0, start - _VISUAL_CONTEXT_CHARS)
        right_boundary = min(len(clause), end + _VISUAL_CONTEXT_CHARS)

        previous_other_end = max(
            [
                index + len(other_name)
                for other_name in other_names
                if (index := clause.rfind(other_name, 0, start)) >= 0
            ],
            default=0,
        )
        next_other_start = min(
            [
                index
                for other_name in other_names
                if (index := clause.find(other_name, end)) >= 0
            ],
            default=len(clause),
        )

        contexts.append(
            clause[
                max(left_boundary, previous_other_end) : min(
                    right_boundary,
                    next_other_start,
                )
            ]
        )
        search_from = end
    return contexts


def _visual_conflicts(identity: str, output: str) -> list[str]:
    conflicts: list[str] = []
    if "长发" in identity and "短发" in output:
        conflicts.append("短发")
    if "短发" in identity and "长发" in output:
        conflicts.append("长发")
    if "黑" in identity and any(
        color in output for color in ("金发", "金色", "白发", "银发", "红发")
    ):
        conflicts.append("非黑发色")
    if "金" in identity and "黑发" in output:
        conflicts.append("黑发")
    return conflicts


def _world_fact_warnings(output: str, memory: IPMemory) -> list[str]:
    warnings: list[str] = []
    for fact in memory.world_facts:
        if not fact.text:
            continue
        if _is_modern_yuncheng_fact(fact.text) and _contradicts_modern_yuncheng(
            output
        ):
            warnings.append(f"世界事实不一致：记忆为{fact.text}，输出改变了时代或地点。")
    return warnings


def _is_modern_yuncheng_fact(text: str) -> bool:
    return "现代" in text and "运城" in text


def _contradicts_modern_yuncheng(output: str) -> bool:
    normalized = re.sub(r"\s+", "", output)
    if "古代" in output:
        return True
    if re.search(r"民国的?(运城|北京|上海)", normalized):
        return True
    if re.search(r"现代的?(北京|上海)", normalized):
        return True
    if "未来上海" in normalized:
        return True
    return "未来" in normalized and "上海" in normalized


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _score(warnings: list[str]) -> float:
    if not warnings:
        return 1.0
    return max(0.0, round(1.0 - 0.25 * len(warnings), 2))
