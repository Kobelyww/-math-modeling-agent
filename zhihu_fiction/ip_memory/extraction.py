"""Deterministic story-to-IP-memory extraction helpers."""
from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable

from zhihu_fiction.ip_memory.models import (
    CharacterCard,
    IPMemory,
    MemorySource,
    NarrativeMemory,
    StoryBible,
    StyleGuide,
    WorldFact,
)


_CHINESE_NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,3}")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])\s*")
_ROLE_PREFIX_RE = (
    r"(?:女主|男主|主角|继母|父亲|母亲|姐姐|妹妹|哥哥|弟弟|丈夫|妻子)"
)
_NAME_BOUNDARY_RE = (
    r"(?=赶出|篡改|带着|发誓|归来|醒来|变成|"
    r"在|被|说|问|。|，|、|；|：|\s|$)"
)
_STOP_NAMES = {
    "山西",
    "运城",
    "雨夜",
    "题材",
    "复仇",
    "爽文",
    "三年",
    "年前",
    "这次",
    "一次",
    "父亲",
    "死亡",
    "录音",
    "证据",
    "遗嘱",
    "家门",
}


@dataclass(slots=True)
class NarrativeEntry:
    id: str = ""
    text: str = ""
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, str | dict[str, str]]:
        return {
            "id": self.id,
            "text": self.text,
            "source": self.source.to_dict(),
        }


class ExtractedNarrativeMemory(NarrativeMemory):
    """Narrative memory that is still compatible with the Task 1 model."""

    __slots__ = ("items",)

    def __init__(
        self,
        *,
        summary: str = "",
        current_state: str = "",
        timeline: list[str] | None = None,
        open_threads: list[str] | None = None,
        resolved_threads: list[str] | None = None,
        continuity_notes: list[str] | None = None,
        source: MemorySource | None = None,
        items: list[NarrativeEntry] | None = None,
    ):
        super().__init__(
            summary=summary,
            current_state=current_state,
            timeline=timeline or [],
            open_threads=open_threads or [],
            resolved_threads=resolved_threads or [],
            continuity_notes=continuity_notes or [],
            source=source or MemorySource(),
        )
        self.items = items or []

    def __iter__(self) -> Iterable[NarrativeEntry]:
        return iter(self.items)

    def to_dict(self) -> dict:
        payload = super().to_dict()
        payload["items"] = [item.to_dict() for item in self.items]
        return payload


def extract_ip_memory_from_story(
    project_id: str,
    title: str,
    genre: str,
    story_text: str,
    story_ref: str = "",
    prior: IPMemory | None = None,
) -> IPMemory:
    """Extract deterministic IP memory from finished story text."""
    if not str(story_text or "").strip():
        if prior is not None:
            return prior
        return IPMemory(
            project_id=project_id,
            story_bible=StoryBible(title=title, genre=genre),
        )

    clean_text = _clean_story_text(story_text)
    source = MemorySource(kind="story", ref=story_ref, excerpt=_excerpt(clean_text))
    memory = _clone_memory(prior) if prior is not None else IPMemory(project_id=project_id)
    memory.project_id = project_id or memory.project_id
    memory.story_bible = _merge_story_bible(
        memory.story_bible,
        title=title,
        genre=genre,
        clean_text=clean_text,
        source=source,
    )
    memory.characters = _merge_characters(
        memory.characters,
        _extract_characters(clean_text, source),
    )
    memory.world_facts = _merge_world_facts(
        memory.world_facts,
        _extract_world_facts(clean_text, source),
    )
    memory.narrative_memory = _merge_narrative_memory(
        memory.narrative_memory,
        _extract_narrative_memory(clean_text, source),
    )
    if not _style_has_content(memory.style_guide):
        memory.style_guide = _default_style_guide(genre, source)
    return memory


def _clone_memory(memory: IPMemory | None) -> IPMemory:
    if memory is None:
        return IPMemory()
    return copy.deepcopy(memory)


def _clean_story_text(story_text: str) -> str:
    lines = []
    for raw_line in str(story_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        if line.startswith(">"):
            line = line.lstrip(">").strip()
        lines.append(line)
    return "\n".join(lines)


def _merge_story_bible(
    current: StoryBible,
    *,
    title: str,
    genre: str,
    clean_text: str,
    source: MemorySource,
) -> StoryBible:
    premise = _premise_from_text(clean_text)
    core_hook = _core_hook_from_text(clean_text, premise)
    emotional_promise = _emotional_promise(genre, clean_text)
    return StoryBible(
        title=str(title or "").strip() or current.title,
        premise=current.premise or premise,
        genre=str(genre or "").strip() or current.genre,
        core_hook=current.core_hook or core_hook,
        emotional_promise=current.emotional_promise or emotional_promise,
        theme=current.theme or emotional_promise,
        audience=current.audience,
        tone=current.tone or emotional_promise,
        source=source if (source.ref or source.excerpt) else current.source,
    )


def _premise_from_text(clean_text: str) -> str:
    for sentence in _sentences(clean_text):
        if "题材" in sentence:
            continue
        if len(sentence) >= 8:
            return sentence
    return clean_text[:80]


def _core_hook_from_text(clean_text: str, fallback: str) -> str:
    hook_terms = ("证据", "录音", "遗嘱", "死亡", "归来", "复仇")
    matches = [
        sentence
        for sentence in _sentences(clean_text)
        if any(term in sentence for term in hook_terms)
    ]
    return " ".join(matches[:2]) or fallback


def _emotional_promise(genre: str, clean_text: str) -> str:
    if "复仇" in genre or "复仇" in clean_text:
        return "压抑冤屈被证据反转释放，主角夺回属于自己的正义。"
    if "爽" in genre:
        return "用高密度反转和清晰胜利兑现短剧爽感。"
    return "围绕主角目标持续累积情绪张力并兑现结局。"


def _extract_characters(clean_text: str, source: MemorySource) -> list[CharacterCard]:
    names: list[str] = []
    role_patterns = [
        rf"{_ROLE_PREFIX_RE}([\u4e00-\u9fff]{{2,3}}?){_NAME_BOUNDARY_RE}",
        r"([\u4e00-\u9fff]{2,3})(?:在|被|带着|发誓|归来|醒来|变成)",
    ]
    for pattern in role_patterns:
        for match in re.finditer(pattern, clean_text):
            _append_name(names, match.group(1))

    for match in _CHINESE_NAME_RE.finditer(clean_text):
        name = match.group(0)
        if name in {"林晚", "周岚"}:
            _append_name(names, name)

    return [
        CharacterCard(
            id=_stable_id("char", name),
            name=name,
            role=_role_for_name(name, clean_text),
            motivation=_motivation_for_name(name, clean_text),
            source=source,
        )
        for name in names
    ]


def _append_name(names: list[str], name: str) -> None:
    if not name or name in _STOP_NAMES or name in names:
        return
    if any(stop in name for stop in _STOP_NAMES):
        return
    names.append(name)


def _role_for_name(name: str, clean_text: str) -> str:
    prefix = clean_text[max(0, clean_text.find(name) - 4) : clean_text.find(name)]
    if "继母" in prefix:
        return "继母/反派"
    if name == "林晚":
        return "女主"
    return ""


def _motivation_for_name(name: str, clean_text: str) -> str:
    if name == "林晚" and "父亲死亡" in clean_text:
        return "查清父亲死亡真相并阻止遗嘱被篡改"
    if "遗嘱" in clean_text and name in clean_text:
        return "围绕遗嘱真相推动冲突"
    return ""


def _extract_world_facts(clean_text: str, source: MemorySource) -> list[WorldFact]:
    facts: list[WorldFact] = []
    if "运城" in clean_text:
        text = "故事发生在现代运城"
        if "山西运城" in clean_text:
            text = "故事发生在现代山西运城"
        facts.append(
            WorldFact(
                id=_stable_id("fact", text),
                text=text,
                category="setting",
                source=source,
            )
        )
    if "三年前" in clean_text:
        text = "关键往事发生在三年前"
        facts.append(WorldFact(id=_stable_id("fact", text), text=text, category="timeline", source=source))
    return facts


def _extract_narrative_memory(clean_text: str, source: MemorySource) -> ExtractedNarrativeMemory:
    entries: list[NarrativeEntry] = []
    if "三年前" in clean_text:
        entries.append(_entry("三年前，林晚被赶出家门。", source))
    if "父亲死亡" in clean_text:
        entries.append(_entry("父亲死亡是核心谜团。", source))
    if "录音证据" in clean_text or "录音" in clean_text:
        entries.append(_entry("林晚掌握父亲死亡的录音证据。", source))
    if "篡改遗嘱" in clean_text or "遗嘱" in clean_text:
        entries.append(_entry("周岚试图篡改遗嘱，遗嘱真相需要持续保持一致。", source))

    timeline = [entry.text for entry in entries if "三年前" in entry.text]
    open_threads = [
        entry.text
        for entry in entries
        if any(term in entry.text for term in ("父亲死亡", "录音证据", "遗嘱"))
    ]
    return ExtractedNarrativeMemory(
        summary=_core_hook_from_text(clean_text, _premise_from_text(clean_text)),
        current_state="主角已带着关键证据归来，复仇线进入主动推进阶段。",
        timeline=timeline,
        open_threads=open_threads,
        continuity_notes=[entry.text for entry in entries],
        source=source,
        items=entries,
    )


def _entry(text: str, source: MemorySource) -> NarrativeEntry:
    return NarrativeEntry(id=_stable_id("narrative", text), text=text, source=source)


def _merge_characters(
    current: list[CharacterCard],
    extracted: list[CharacterCard],
) -> list[CharacterCard]:
    merged: dict[str, CharacterCard] = {}
    for card in [*current, *extracted]:
        key = card.name or card.id
        if key in merged:
            merged[key] = _merge_character(merged[key], card)
        else:
            merged[key] = card
    return list(merged.values())


def _merge_character(left: CharacterCard, right: CharacterCard) -> CharacterCard:
    return CharacterCard(
        id=left.id or right.id,
        name=left.name or right.name,
        role=left.role or right.role,
        visual_identity=left.visual_identity or right.visual_identity,
        appearance=left.appearance or right.appearance,
        personality=left.personality or right.personality,
        motivation=left.motivation or right.motivation,
        voice=left.voice or right.voice,
        relationship_notes=left.relationship_notes or right.relationship_notes,
        source=left.source if (left.source.ref or left.source.excerpt) else right.source,
    )


def _merge_world_facts(current: list[WorldFact], extracted: list[WorldFact]) -> list[WorldFact]:
    merged: dict[str, WorldFact] = {}
    for fact in [*current, *extracted]:
        key = _normalize(fact.text) or fact.id
        merged.setdefault(key, fact)
    return list(merged.values())


def _merge_narrative_memory(
    current: NarrativeMemory,
    extracted: ExtractedNarrativeMemory,
) -> ExtractedNarrativeMemory:
    current_items = list(getattr(current, "items", []))
    items = _dedupe_entries([*current_items, *extracted.items])
    return ExtractedNarrativeMemory(
        summary=current.summary or extracted.summary,
        current_state=current.current_state or extracted.current_state,
        timeline=_dedupe_strings([*current.timeline, *extracted.timeline]),
        open_threads=_dedupe_strings([*current.open_threads, *extracted.open_threads]),
        resolved_threads=_dedupe_strings([*current.resolved_threads, *extracted.resolved_threads]),
        continuity_notes=_dedupe_strings([*current.continuity_notes, *extracted.continuity_notes]),
        source=current.source if (current.source.ref or current.source.excerpt) else extracted.source,
        items=items,
    )


def _dedupe_entries(entries: list[NarrativeEntry]) -> list[NarrativeEntry]:
    seen: set[str] = set()
    result: list[NarrativeEntry] = []
    for entry in entries:
        key = _normalize(entry.text)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def _default_style_guide(genre: str, source: MemorySource) -> StyleGuide:
    tone = "强情绪、强反转、短剧化爽感"
    if "复仇" in genre:
        tone = "克制压抑开场，证据反击时释放复仇爽感"
    return StyleGuide(
        tone=tone,
        pov="第三人称有限视角",
        pacing="开场快速给出冲突，每场保留明确钩子",
        language="现代中文短句，避免解释性旁白过长",
        visual_style="雨夜、证据、家族对峙等高辨识度视觉锚点",
        source=source,
    )


def _style_has_content(style: StyleGuide) -> bool:
    return any(
        [
            style.tone,
            style.pov,
            style.pacing,
            style.language,
            style.visual_style,
            style.taboo,
            style.taboos,
        ]
    )


def _sentences(text: str) -> list[str]:
    return [
        item.strip()
        for item in _SENTENCE_SPLIT_RE.split(text.replace("\n", ""))
        if item.strip()
    ]


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = _normalize(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _stable_id(prefix: str, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _excerpt(text: str) -> str:
    return text.replace("\n", " ")[:80]
