"""Prompt rendering helpers for IP memory."""
from __future__ import annotations

from zhihu_fiction.ip_memory.models import (
    AssetBinding,
    CharacterCard,
    Foreshadowing,
    IPMemory,
    StyleGuide,
    WorldFact,
)


def render_memory_context(memory: IPMemory, max_chars: int = 6000) -> str:
    if max_chars <= 0:
        return ""

    lines = [f"【IP记忆】项目：{memory.project_id or '未命名'}"]

    story_lines = _story_bible_lines(memory)
    if story_lines:
        lines.extend(["", "【故事圣经】", *story_lines])

    if memory.characters:
        lines.extend(["", "【角色卡】"])
        lines.extend(_character_line(item) for item in memory.characters)

    if memory.world_facts:
        lines.extend(["", "【世界事实】"])
        lines.extend(_world_fact_line(item) for item in memory.world_facts)

    if memory.foreshadowing:
        lines.extend(["", "【伏笔】"])
        lines.extend(_foreshadowing_line(item) for item in memory.foreshadowing)

    narrative_lines = _narrative_lines(memory)
    if narrative_lines:
        lines.extend(["", "【叙事记忆】", *narrative_lines])

    style_lines = _style_lines(memory.style_guide)
    if style_lines:
        lines.extend(["", "【风格指南】", *style_lines])

    if memory.asset_bindings:
        lines.extend(["", "【资产绑定】"])
        lines.extend(_asset_line(item) for item in memory.asset_bindings)

    rendered = "\n".join(line for line in lines if line is not None)
    if len(rendered) <= max_chars:
        return rendered
    return rendered[:max_chars]


def _story_bible_lines(memory: IPMemory) -> list[str]:
    story = memory.story_bible
    fields = [
        ("标题", story.title),
        ("类型", story.genre),
        ("前提", story.premise),
        ("核心钩子", story.core_hook),
        ("主题", story.theme),
        ("受众", story.audience),
        ("基调", story.tone),
    ]
    lines = [f"- {label}：{value}" for label, value in fields if value]
    source = _source_suffix(story.source)
    if source and lines:
        lines[-1] = f"{lines[-1]} {source}"
    return lines


def _character_line(card: CharacterCard) -> str:
    parts = [
        _label(card.id, card.name),
        card.role,
        card.visual_identity or card.appearance,
        card.personality,
        card.motivation,
        card.voice,
        card.relationship_notes,
    ]
    return "- " + "；".join(part for part in parts if part) + _source_suffix(card.source)


def _world_fact_line(fact: WorldFact) -> str:
    head = _label(fact.id, fact.category)
    parts = [head, fact.text, fact.scope]
    return "- " + "；".join(part for part in parts if part) + _source_suffix(fact.source)


def _foreshadowing_line(item: Foreshadowing) -> str:
    setup = item.setup or item.clue
    parts = [
        _label(item.id, item.status),
        f"埋设：{setup}" if setup else "",
        f"回收：{item.payoff}" if item.payoff else "",
    ]
    return "- " + "；".join(part for part in parts if part) + _source_suffix(item.source)


def _narrative_lines(memory: IPMemory) -> list[str]:
    narrative = memory.narrative_memory
    lines = []
    if narrative.summary:
        lines.append(f"- 概要：{narrative.summary}")
    if narrative.current_state:
        lines.append(f"- 当前状态：{narrative.current_state}")
    lines.extend(f"- 时间线：{item}" for item in narrative.timeline)
    lines.extend(f"- 未回收：{item}" for item in narrative.open_threads)
    lines.extend(f"- 已回收：{item}" for item in narrative.resolved_threads)
    lines.extend(f"- 连贯性：{item}" for item in narrative.continuity_notes)
    return lines


def _style_lines(style: StyleGuide) -> list[str]:
    fields = [
        ("语气", style.tone),
        ("视角", style.pov),
        ("节奏", style.pacing),
        ("语言", style.language),
        ("视觉风格", style.visual_style),
        ("禁忌", style.taboo),
    ]
    lines = [f"- {label}：{value}" for label, value in fields if value]
    lines.extend(f"- 禁忌：{item}" for item in style.taboos)
    return lines


def _asset_line(binding: AssetBinding) -> str:
    ref = binding.ref or binding.uri
    parts = [
        _label(binding.id, binding.kind),
        binding.target_id,
        ref,
        binding.description,
        binding.consistency_prompt,
    ]
    return "- " + "；".join(part for part in parts if part) + _source_suffix(binding.source)


def _label(first: str, second: str) -> str:
    if first and second:
        return f"{first}/{second}"
    return first or second


def _source_suffix(source) -> str:
    if not source or not (source.ref or source.excerpt):
        return ""
    bits = [source.ref, source.excerpt]
    return "（来源：" + "，".join(bit for bit in bits if bit) + "）"
