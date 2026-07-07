"""Deterministic consistency checks against IP memory."""
from __future__ import annotations

import re

from zhihu_fiction.ip_memory.models import IPMemory


_CLAUSE_SPLIT_RE = re.compile(r"[，。；！？!?;,\n]+")


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
    for card in memory.characters:
        if not card.name or card.name not in output or not card.visual_identity:
            continue
        conflicts = []
        for clause in _clauses_containing(output, card.name):
            conflicts.extend(_visual_conflicts(card.visual_identity, clause))
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
    if "古代" in output:
        return True
    if "民国" in output and "运城" in output:
        return True
    if "现代北京" in output or "现代上海" in output:
        return True
    if "未来上海" in output:
        return True
    return "未来" in output and "上海" in output


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
