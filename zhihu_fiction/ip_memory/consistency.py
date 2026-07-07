"""Deterministic consistency checks against IP memory."""
from __future__ import annotations

from zhihu_fiction.ip_memory.models import IPMemory


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
        conflicts = _visual_conflicts(card.visual_identity, output)
        if conflicts:
            detail = "、".join(conflicts)
            warnings.append(
                f"{card.name}的视觉身份与记忆不一致：记忆为{card.visual_identity}，输出出现{detail}。"
            )
    return warnings


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
    if "未来上海" in output:
        return True
    return "未来" in output and "上海" in output


def _score(warnings: list[str]) -> float:
    if not warnings:
        return 1.0
    return max(0.0, round(1.0 - 0.25 * len(warnings), 2))
