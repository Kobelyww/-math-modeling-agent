"""Serializable IP memory models for short-drama generation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class MemorySource:
    kind: str = ""
    ref: str = ""
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "ref": self.ref,
            "excerpt": self.excerpt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | "MemorySource" | None) -> "MemorySource":
        if isinstance(data, cls):
            return data
        values = data or {}
        return cls(
            kind=str(values.get("kind", "")),
            ref=str(values.get("ref", "")),
            excerpt=str(values.get("excerpt", "")),
        )


@dataclass(slots=True)
class StoryBible:
    title: str = ""
    premise: str = ""
    genre: str = ""
    core_hook: str = ""
    emotional_promise: str = ""
    theme: str = ""
    audience: str = ""
    tone: str = ""
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "premise": self.premise,
            "genre": self.genre,
            "core_hook": self.core_hook,
            "emotional_promise": self.emotional_promise,
            "theme": self.theme,
            "audience": self.audience,
            "tone": self.tone,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | "StoryBible" | None) -> "StoryBible":
        if isinstance(data, cls):
            return data
        values = data or {}
        return cls(
            title=str(values.get("title", "")),
            premise=str(values.get("premise", "")),
            genre=str(values.get("genre", "")),
            core_hook=str(values.get("core_hook", "")),
            emotional_promise=str(values.get("emotional_promise", "")),
            theme=str(values.get("theme", "")),
            audience=str(values.get("audience", "")),
            tone=str(values.get("tone", "")),
            source=MemorySource.from_dict(values.get("source")),
        )


@dataclass(slots=True)
class CharacterCard:
    id: str = ""
    name: str = ""
    role: str = ""
    visual_identity: str = ""
    appearance: str = ""
    personality: str = ""
    motivation: str = ""
    voice: str = ""
    relationship_notes: str = ""
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "visual_identity": self.visual_identity,
            "appearance": self.appearance,
            "personality": self.personality,
            "motivation": self.motivation,
            "voice": self.voice,
            "relationship_notes": self.relationship_notes,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | "CharacterCard" | None) -> "CharacterCard":
        if isinstance(data, cls):
            return data
        values = data or {}
        return cls(
            id=str(values.get("id", "")),
            name=str(values.get("name", "")),
            role=str(values.get("role", "")),
            visual_identity=str(values.get("visual_identity", "")),
            appearance=str(values.get("appearance", "")),
            personality=str(values.get("personality", "")),
            motivation=str(values.get("motivation", "")),
            voice=str(values.get("voice", "")),
            relationship_notes=str(values.get("relationship_notes", "")),
            source=MemorySource.from_dict(values.get("source")),
        )


@dataclass(slots=True)
class WorldFact:
    id: str = ""
    text: str = ""
    category: str = ""
    scope: str = ""
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "category": self.category,
            "scope": self.scope,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | "WorldFact" | None) -> "WorldFact":
        if isinstance(data, cls):
            return data
        values = data or {}
        return cls(
            id=str(values.get("id", "")),
            text=str(values.get("text", "")),
            category=str(values.get("category", "")),
            scope=str(values.get("scope", "")),
            source=MemorySource.from_dict(values.get("source")),
        )


@dataclass(slots=True)
class Foreshadowing:
    id: str = ""
    setup: str = ""
    clue: str = ""
    payoff: str = ""
    status: str = ""
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "setup": self.setup,
            "clue": self.clue,
            "payoff": self.payoff,
            "status": self.status,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | "Foreshadowing" | None) -> "Foreshadowing":
        if isinstance(data, cls):
            return data
        values = data or {}
        return cls(
            id=str(values.get("id", "")),
            setup=str(values.get("setup", "")),
            clue=str(values.get("clue", "")),
            payoff=str(values.get("payoff", "")),
            status=str(values.get("status", "")),
            source=MemorySource.from_dict(values.get("source")),
        )


@dataclass(slots=True)
class NarrativeMemory:
    summary: str = ""
    current_state: str = ""
    timeline: list[str] = field(default_factory=list)
    open_threads: list[str] = field(default_factory=list)
    resolved_threads: list[str] = field(default_factory=list)
    continuity_notes: list[str] = field(default_factory=list)
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "current_state": self.current_state,
            "timeline": list(self.timeline),
            "open_threads": list(self.open_threads),
            "resolved_threads": list(self.resolved_threads),
            "continuity_notes": list(self.continuity_notes),
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any] | "NarrativeMemory" | None,
    ) -> "NarrativeMemory":
        if isinstance(data, cls):
            return data
        values = data or {}
        return cls(
            summary=str(values.get("summary", "")),
            current_state=str(values.get("current_state", "")),
            timeline=_string_list(values.get("timeline", [])),
            open_threads=_string_list(values.get("open_threads", [])),
            resolved_threads=_string_list(values.get("resolved_threads", [])),
            continuity_notes=_string_list(values.get("continuity_notes", [])),
            source=MemorySource.from_dict(values.get("source")),
        )


@dataclass(slots=True)
class StyleGuide:
    tone: str = ""
    pov: str = ""
    pacing: str = ""
    language: str = ""
    visual_style: str = ""
    taboo: str = ""
    taboos: list[str] = field(default_factory=list)
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tone": self.tone,
            "pov": self.pov,
            "pacing": self.pacing,
            "language": self.language,
            "visual_style": self.visual_style,
            "taboo": self.taboo,
            "taboos": list(self.taboos),
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | "StyleGuide" | None) -> "StyleGuide":
        if isinstance(data, cls):
            return data
        values = data or {}
        return cls(
            tone=str(values.get("tone", "")),
            pov=str(values.get("pov", "")),
            pacing=str(values.get("pacing", "")),
            language=str(values.get("language", "")),
            visual_style=str(values.get("visual_style", "")),
            taboo=str(values.get("taboo", "")),
            taboos=_string_list(values.get("taboos", [])),
            source=MemorySource.from_dict(values.get("source")),
        )


@dataclass(slots=True)
class AssetBinding:
    id: str = ""
    kind: str = ""
    ref: str = ""
    uri: str = ""
    target_id: str = ""
    description: str = ""
    consistency_prompt: str = ""
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "ref": self.ref,
            "uri": self.uri,
            "target_id": self.target_id,
            "description": self.description,
            "consistency_prompt": self.consistency_prompt,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | "AssetBinding" | None) -> "AssetBinding":
        if isinstance(data, cls):
            return data
        values = data or {}
        return cls(
            id=str(values.get("id", "")),
            kind=str(values.get("kind", "")),
            ref=str(values.get("ref", "")),
            uri=str(values.get("uri", "")),
            target_id=str(values.get("target_id", "")),
            description=str(values.get("description", "")),
            consistency_prompt=str(values.get("consistency_prompt", "")),
            source=MemorySource.from_dict(values.get("source")),
        )


@dataclass(slots=True)
class IPMemory:
    project_id: str = ""
    story_bible: StoryBible = field(default_factory=StoryBible)
    characters: list[CharacterCard] = field(default_factory=list)
    world_facts: list[WorldFact] = field(default_factory=list)
    foreshadowing: list[Foreshadowing] = field(default_factory=list)
    narrative_memory: NarrativeMemory = field(default_factory=NarrativeMemory)
    style_guide: StyleGuide = field(default_factory=StyleGuide)
    asset_bindings: list[AssetBinding] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "story_bible": self.story_bible.to_dict(),
            "characters": [item.to_dict() for item in self.characters],
            "world_facts": [item.to_dict() for item in self.world_facts],
            "foreshadowing": [item.to_dict() for item in self.foreshadowing],
            "narrative_memory": self.narrative_memory.to_dict(),
            "style_guide": self.style_guide.to_dict(),
            "asset_bindings": [item.to_dict() for item in self.asset_bindings],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | "IPMemory" | None) -> "IPMemory":
        if isinstance(data, cls):
            return data
        values = data or {}
        return cls(
            project_id=str(values.get("project_id", "")),
            story_bible=StoryBible.from_dict(values.get("story_bible")),
            characters=_model_list(values.get("characters", []), CharacterCard),
            world_facts=_model_list(values.get("world_facts", []), WorldFact),
            foreshadowing=_model_list(values.get("foreshadowing", []), Foreshadowing),
            narrative_memory=NarrativeMemory.from_dict(values.get("narrative_memory")),
            style_guide=StyleGuide.from_dict(values.get("style_guide")),
            asset_bindings=_model_list(values.get("asset_bindings", []), AssetBinding),
            created_at=str(values.get("created_at", utc_now_iso())),
            updated_at=str(values.get("updated_at", utc_now_iso())),
        )


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return [str(value)]
    return [str(item) for item in value]


def _model_list(value: Any, model: type[Any]) -> list[Any]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [
        item if isinstance(item, model) else model.from_dict(item)
        for item in items
    ]
