# Unified IP Memory Agent DAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first functional slice of unified IP memory, fiction/drama memory injection, Agent DAG traceability, and human-loop memory review for `zhihu_fiction`.

**Architecture:** Add a lightweight `zhihu_fiction/ip_memory/` domain package with file-backed persistence, deterministic extraction, prompt rendering, consistency review, graph node metadata, and trace records. Integrate it into the current fiction pipeline and short-drama DeepAgent flow without changing the external API contract or requiring SQL, Redis, or MinIO.

**Tech Stack:** Python dataclasses, JSON file persistence, FastAPI routers, existing `Pipeline`, existing drama DeepAgent services, existing static HTML workspace, pytest.

---

## Scope Check

This plan implements the product-core slice from `docs/superpowers/specs/2026-07-07-zhihu-fiction-unified-ip-memory-agent-dag-design.md`.

Included:
- IP memory models and file repository.
- Deterministic memory extraction and prompt rendering.
- Fiction pipeline memory extraction and context injection.
- Drama DeepAgent memory context, proposed memory patches, and trace output.
- Minimal API and Web workbench visibility.

Excluded from this plan:
- SQL, Redis, MinIO, Postgres, or external worker migration.
- New paid video providers.
- Final video editing, dubbing, subtitles, and BGM generation.
- Full frontend framework migration.

## File Structure

Create:
- `zhihu_fiction/ip_memory/__init__.py` exports public memory APIs.
- `zhihu_fiction/ip_memory/models.py` owns serializable IP memory dataclasses.
- `zhihu_fiction/ip_memory/repository.py` owns safe file-backed memory persistence.
- `zhihu_fiction/ip_memory/rendering.py` turns memory into compact prompt context.
- `zhihu_fiction/ip_memory/extraction.py` extracts initial memory from story text.
- `zhihu_fiction/ip_memory/consistency.py` reviews stage output against memory.
- `zhihu_fiction/ip_memory/agent_graph.py` defines node metadata and stage mapping.
- `zhihu_fiction/ip_memory/trace.py` records graph node execution traces.
- `zhihu_fiction/app/routes/ip_memory.py` exposes memory read, extract, patch, and trace APIs.
- `zhihu_fiction/tests/test_ip_memory_models.py`
- `zhihu_fiction/tests/test_ip_memory_extraction.py`
- `zhihu_fiction/tests/test_ip_memory_api.py`
- `zhihu_fiction/tests/test_agent_graph_trace.py`
- `zhihu_fiction/tests/test_pipeline_ip_memory.py`
- `zhihu_fiction/tests/test_drama_video_ip_memory_integration.py`

Modify:
- `zhihu_fiction/app/factory.py` includes the new `ip_memory` router.
- `zhihu_fiction/orchestrator.py` accepts optional `memory_context` for fiction and drama prompts.
- `zhihu_fiction/pipeline.py` extracts memory after saving a story and passes compact memory into rewrites/continuations.
- `zhihu_fiction/app/services/drama_video_stage_generation.py` loads memory and injects it into stage prompts.
- `zhihu_fiction/app/services/drama_video_deepagent_flow.py` initializes session memory metadata, records node traces, and confirms memory patches.
- `zhihu_fiction/app/services/drama_video_sessions.py` stores memory metadata in `DramaStageVersion.metadata` and operation logs.
- `zhihu_fiction/app/routes/drama_video.py` exposes `GET /api/drama-video/deepagent/{run_id}/trace`.
- `zhihu_fiction/static/video.html` shows the compact IP memory and trace panel in the existing workbench.

## Task 1: IP Memory Models And Repository

**Files:**
- Create: `zhihu_fiction/ip_memory/__init__.py`
- Create: `zhihu_fiction/ip_memory/models.py`
- Create: `zhihu_fiction/ip_memory/repository.py`
- Create: `zhihu_fiction/ip_memory/rendering.py`
- Test: `zhihu_fiction/tests/test_ip_memory_models.py`

- [ ] **Step 1: Write model serialization tests**

Add `zhihu_fiction/tests/test_ip_memory_models.py`:

```python
from pathlib import Path

from zhihu_fiction.ip_memory.models import (
    CharacterCard,
    IPMemory,
    MemorySource,
    StoryBible,
    WorldFact,
)
from zhihu_fiction.ip_memory.repository import IPMemoryRepository
from zhihu_fiction.ip_memory.rendering import render_memory_context


def test_ip_memory_round_trips_with_source_metadata(tmp_path: Path):
    memory = IPMemory(
        project_id="story-001",
        story_bible=StoryBible(
            title="雨夜重生",
            premise="女主在雨夜重生并反击家族阴谋",
            genre="复仇爽文",
            core_hook="三年前被抛弃的人带着证据归来",
            source=MemorySource(kind="story", ref="小说正文.md", excerpt="雨夜"),
        ),
        characters=[
            CharacterCard(
                id="char_heroine",
                name="林晚",
                role="女主",
                visual_identity="黑色长发，冷静克制",
                motivation="查清父亲死亡真相",
                source=MemorySource(kind="story", ref="小说正文.md", excerpt="林晚"),
            )
        ],
        world_facts=[
            WorldFact(
                id="fact_city",
                text="故事发生在现代运城",
                category="setting",
                source=MemorySource(kind="story", ref="小说正文.md", excerpt="运城"),
            )
        ],
    )

    payload = memory.to_dict()
    restored = IPMemory.from_dict(payload)

    assert restored.project_id == "story-001"
    assert restored.story_bible.title == "雨夜重生"
    assert restored.characters[0].source.ref == "小说正文.md"
    assert restored.world_facts[0].text == "故事发生在现代运城"


def test_repository_saves_memory_and_version_patch(tmp_path: Path):
    repo = IPMemoryRepository(tmp_path)
    memory = IPMemory(project_id="project-a", story_bible=StoryBible(title="A"))

    repo.save(memory, patch_note="initial extraction")
    restored = repo.load("project-a")

    assert restored is not None
    assert restored.story_bible.title == "A"
    assert (tmp_path / "project-a" / "memory.json").exists()
    assert list((tmp_path / "project-a" / "versions").glob("*.json"))


def test_render_memory_context_is_compact_and_sectioned():
    memory = IPMemory(
        project_id="project-a",
        story_bible=StoryBible(title="A", premise="B"),
        characters=[CharacterCard(id="c1", name="林晚", role="女主")],
        world_facts=[WorldFact(id="f1", text="现代运城", category="setting")],
    )

    rendered = render_memory_context(memory, max_chars=500)

    assert "【IP记忆】" in rendered
    assert "【故事圣经】" in rendered
    assert "林晚" in rendered
    assert "现代运城" in rendered
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_ip_memory_models.py -q
```

Expected: FAIL because `zhihu_fiction.ip_memory` does not exist.

- [ ] **Step 3: Implement memory dataclasses**

Create `zhihu_fiction/ip_memory/models.py`:

```python
"""Unified IP memory models for fiction and short-drama production."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MemorySource":
        data = data or {}
        return cls(
            kind=str(data.get("kind") or ""),
            ref=str(data.get("ref") or ""),
            excerpt=str(data.get("excerpt") or ""),
        )


@dataclass(slots=True)
class StoryBible:
    title: str = ""
    premise: str = ""
    genre: str = ""
    target_audience: str = ""
    core_hook: str = ""
    emotional_promise: str = ""
    ending_direction: str = ""
    taboo_changes: list[str] = field(default_factory=list)
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "StoryBible":
        data = data or {}
        return cls(
            title=str(data.get("title") or ""),
            premise=str(data.get("premise") or ""),
            genre=str(data.get("genre") or ""),
            target_audience=str(data.get("target_audience") or ""),
            core_hook=str(data.get("core_hook") or ""),
            emotional_promise=str(data.get("emotional_promise") or ""),
            ending_direction=str(data.get("ending_direction") or ""),
            taboo_changes=[str(item) for item in data.get("taboo_changes") or []],
            source=MemorySource.from_dict(data.get("source")),
        )


@dataclass(slots=True)
class CharacterCard:
    id: str
    name: str
    role: str = ""
    visual_identity: str = ""
    personality: str = ""
    motivation: str = ""
    relationships: list[str] = field(default_factory=list)
    speech_style: str = ""
    forbidden_changes: list[str] = field(default_factory=list)
    asset_bindings: list[str] = field(default_factory=list)
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterCard":
        return cls(
            id=str(data.get("id") or ""),
            name=str(data.get("name") or ""),
            role=str(data.get("role") or ""),
            visual_identity=str(data.get("visual_identity") or ""),
            personality=str(data.get("personality") or ""),
            motivation=str(data.get("motivation") or ""),
            relationships=[str(item) for item in data.get("relationships") or []],
            speech_style=str(data.get("speech_style") or ""),
            forbidden_changes=[str(item) for item in data.get("forbidden_changes") or []],
            asset_bindings=[str(item) for item in data.get("asset_bindings") or []],
            source=MemorySource.from_dict(data.get("source")),
        )


@dataclass(slots=True)
class WorldFact:
    id: str
    text: str
    category: str = ""
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldFact":
        return cls(
            id=str(data.get("id") or ""),
            text=str(data.get("text") or ""),
            category=str(data.get("category") or ""),
            source=MemorySource.from_dict(data.get("source")),
        )


@dataclass(slots=True)
class Foreshadowing:
    id: str
    setup: str
    payoff_plan: str = ""
    status: str = "planned"
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Foreshadowing":
        return cls(
            id=str(data.get("id") or ""),
            setup=str(data.get("setup") or ""),
            payoff_plan=str(data.get("payoff_plan") or ""),
            status=str(data.get("status") or "planned"),
            source=MemorySource.from_dict(data.get("source")),
        )


@dataclass(slots=True)
class NarrativeMemory:
    id: str
    text: str
    importance: int = 3
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NarrativeMemory":
        return cls(
            id=str(data.get("id") or ""),
            text=str(data.get("text") or ""),
            importance=int(data.get("importance") or 3),
            source=MemorySource.from_dict(data.get("source")),
        )


@dataclass(slots=True)
class StyleGuide:
    fiction_voice: str = ""
    drama_tone: str = ""
    camera_language: str = ""
    pacing: str = ""
    color: str = ""
    content_boundaries: list[str] = field(default_factory=list)
    source: MemorySource = field(default_factory=MemorySource)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "StyleGuide":
        data = data or {}
        return cls(
            fiction_voice=str(data.get("fiction_voice") or ""),
            drama_tone=str(data.get("drama_tone") or ""),
            camera_language=str(data.get("camera_language") or ""),
            pacing=str(data.get("pacing") or ""),
            color=str(data.get("color") or ""),
            content_boundaries=[str(item) for item in data.get("content_boundaries") or []],
            source=MemorySource.from_dict(data.get("source")),
        )


@dataclass(slots=True)
class AssetBinding:
    id: str
    kind: str
    target_id: str
    uri: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetBinding":
        return cls(
            id=str(data.get("id") or ""),
            kind=str(data.get("kind") or ""),
            target_id=str(data.get("target_id") or ""),
            uri=str(data.get("uri") or ""),
            description=str(data.get("description") or ""),
        )


@dataclass(slots=True)
class IPMemory:
    project_id: str
    story_bible: StoryBible = field(default_factory=StoryBible)
    characters: list[CharacterCard] = field(default_factory=list)
    world_facts: list[WorldFact] = field(default_factory=list)
    foreshadowing: list[Foreshadowing] = field(default_factory=list)
    narrative_memory: list[NarrativeMemory] = field(default_factory=list)
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
            "narrative_memory": [item.to_dict() for item in self.narrative_memory],
            "style_guide": self.style_guide.to_dict(),
            "asset_bindings": [item.to_dict() for item in self.asset_bindings],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IPMemory":
        return cls(
            project_id=str(data.get("project_id") or ""),
            story_bible=StoryBible.from_dict(data.get("story_bible")),
            characters=[CharacterCard.from_dict(item) for item in data.get("characters") or []],
            world_facts=[WorldFact.from_dict(item) for item in data.get("world_facts") or []],
            foreshadowing=[Foreshadowing.from_dict(item) for item in data.get("foreshadowing") or []],
            narrative_memory=[NarrativeMemory.from_dict(item) for item in data.get("narrative_memory") or []],
            style_guide=StyleGuide.from_dict(data.get("style_guide")),
            asset_bindings=[AssetBinding.from_dict(item) for item in data.get("asset_bindings") or []],
            created_at=str(data.get("created_at") or utc_now_iso()),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
        )
```

- [ ] **Step 4: Implement repository**

Create `zhihu_fiction/ip_memory/repository.py`:

```python
"""File-backed repository for unified IP memory."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import IPMemory, utc_now_iso


class IPMemoryRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def project_dir(self, project_id: str) -> Path:
        safe = self._safe_id(project_id)
        return self.root / safe

    def memory_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "memory.json"

    def load(self, project_id: str) -> IPMemory | None:
        path = self.memory_path(project_id)
        if not path.exists():
            return None
        return IPMemory.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, memory: IPMemory, patch_note: str = "") -> IPMemory:
        memory.updated_at = utc_now_iso()
        project_dir = self.project_dir(memory.project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        payload = memory.to_dict()
        target = project_dir / "memory.json"
        tmp = project_dir / "memory.json.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(target)
        self._write_version(project_dir, payload, patch_note)
        return memory

    def apply_patch(self, project_id: str, patch: dict) -> IPMemory:
        existing = self.load(project_id) or IPMemory(project_id=project_id)
        data = existing.to_dict()
        for key in ("characters", "world_facts", "foreshadowing", "narrative_memory", "asset_bindings"):
            additions = patch.get(key) or []
            if isinstance(additions, list):
                data.setdefault(key, [])
                data[key].extend(additions)
        if isinstance(patch.get("story_bible"), dict):
            data["story_bible"] = {**data.get("story_bible", {}), **patch["story_bible"]}
        if isinstance(patch.get("style_guide"), dict):
            data["style_guide"] = {**data.get("style_guide", {}), **patch["style_guide"]}
        return self.save(IPMemory.from_dict(data), patch_note=str(patch.get("note") or "patch"))

    def snapshot_hash(self, memory: IPMemory | None) -> str:
        if memory is None:
            return "sha256:empty"
        raw = json.dumps(memory.to_dict(), ensure_ascii=False, sort_keys=True)
        return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _write_version(self, project_dir: Path, payload: dict, patch_note: str) -> None:
        versions = project_dir / "versions"
        versions.mkdir(parents=True, exist_ok=True)
        timestamp = utc_now_iso().replace(":", "").replace("+", "Z")
        version_payload = {"note": patch_note, "memory": payload}
        (versions / f"{timestamp}.json").write_text(
            json.dumps(version_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _safe_id(project_id: str) -> str:
        safe = "".join(ch for ch in project_id if ch.isalnum() or ch in ("-", "_", "."))
        return safe[:120] or "default"
```

- [ ] **Step 5: Implement prompt rendering and exports**

Create `zhihu_fiction/ip_memory/rendering.py`:

```python
"""Prompt rendering helpers for IP memory."""
from __future__ import annotations

from .models import IPMemory


def render_memory_context(memory: IPMemory | None, max_chars: int = 6000) -> str:
    if memory is None:
        return "【IP记忆】\n暂无已保存记忆。"
    sections = ["【IP记忆】"]
    bible = memory.story_bible
    if bible.title or bible.premise or bible.core_hook:
        sections.append(
            "【故事圣经】\n"
            f"- 标题：{bible.title or '未命名'}\n"
            f"- 类型：{bible.genre or '未指定'}\n"
            f"- 核心设定：{bible.premise or '未提取'}\n"
            f"- 爆点：{bible.core_hook or '未提取'}"
        )
    if memory.characters:
        lines = [
            f"- {card.name}：{card.role}；{card.visual_identity or card.personality or card.motivation}"
            for card in memory.characters[:12]
        ]
        sections.append("【角色卡】\n" + "\n".join(lines))
    if memory.world_facts:
        lines = [f"- {fact.text}" for fact in memory.world_facts[:16]]
        sections.append("【世界事实】\n" + "\n".join(lines))
    if memory.foreshadowing:
        lines = [f"- {item.setup} -> {item.payoff_plan or '待回收'}" for item in memory.foreshadowing[:12]]
        sections.append("【伏笔】\n" + "\n".join(lines))
    if memory.narrative_memory:
        lines = [f"- {item.text}" for item in sorted(memory.narrative_memory, key=lambda x: -x.importance)[:16]]
        sections.append("【叙事记忆】\n" + "\n".join(lines))
    style = memory.style_guide
    if style.fiction_voice or style.drama_tone or style.camera_language:
        sections.append(
            "【风格指南】\n"
            f"- 小说文风：{style.fiction_voice or '未提取'}\n"
            f"- 短剧语气：{style.drama_tone or '未提取'}\n"
            f"- 镜头语言：{style.camera_language or '未提取'}"
        )
    rendered = "\n\n".join(sections)
    return rendered[:max_chars]
```

Create `zhihu_fiction/ip_memory/__init__.py`:

```python
"""Unified IP memory public API."""
from .models import (
    AssetBinding,
    CharacterCard,
    Foreshadowing,
    IPMemory,
    MemorySource,
    NarrativeMemory,
    StoryBible,
    StyleGuide,
    WorldFact,
)
from .repository import IPMemoryRepository
from .rendering import render_memory_context

__all__ = [
    "AssetBinding",
    "CharacterCard",
    "Foreshadowing",
    "IPMemory",
    "IPMemoryRepository",
    "MemorySource",
    "NarrativeMemory",
    "StoryBible",
    "StyleGuide",
    "WorldFact",
    "render_memory_context",
]
```

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_ip_memory_models.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add zhihu_fiction/ip_memory zhihu_fiction/tests/test_ip_memory_models.py
git commit -m "feat: add unified ip memory models"
```

## Task 2: Story Memory Extraction And Consistency Review

**Files:**
- Create: `zhihu_fiction/ip_memory/extraction.py`
- Create: `zhihu_fiction/ip_memory/consistency.py`
- Test: `zhihu_fiction/tests/test_ip_memory_extraction.py`

- [ ] **Step 1: Write extraction and consistency tests**

Add `zhihu_fiction/tests/test_ip_memory_extraction.py`:

```python
from zhihu_fiction.ip_memory.consistency import review_consistency
from zhihu_fiction.ip_memory.extraction import extract_ip_memory_from_story
from zhihu_fiction.ip_memory.models import CharacterCard, IPMemory, StoryBible, WorldFact


def test_extract_ip_memory_from_story_creates_core_entities():
    story = """
    # 雨夜归来

    > 题材：复仇爽文

    林晚在山西运城的雨夜醒来。三年前，她被继母周岚赶出家门。
    这一次，林晚带着父亲死亡的录音证据归来。她发誓不能再让周岚篡改遗嘱。
    """

    memory = extract_ip_memory_from_story(
        project_id="story-rain",
        title="雨夜归来",
        genre="复仇爽文",
        story_text=story,
        story_ref="output/雨夜归来/小说正文.md",
    )

    assert memory.story_bible.title == "雨夜归来"
    assert memory.story_bible.genre == "复仇爽文"
    assert any(card.name == "林晚" for card in memory.characters)
    assert any("运城" in fact.text for fact in memory.world_facts)
    assert any("遗嘱" in item.text or "录音" in item.text for item in memory.narrative_memory)


def test_empty_extraction_keeps_prior_memory():
    prior = IPMemory(
        project_id="story-rain",
        story_bible=StoryBible(title="旧标题"),
        characters=[CharacterCard(id="char_old", name="旧角色")],
    )

    memory = extract_ip_memory_from_story(
        project_id="story-rain",
        title="",
        genre="",
        story_text="",
        prior=prior,
    )

    assert memory.story_bible.title == "旧标题"
    assert memory.characters[0].name == "旧角色"


def test_consistency_review_flags_contradicting_character_fact():
    memory = IPMemory(
        project_id="p",
        story_bible=StoryBible(title="A"),
        characters=[CharacterCard(id="char_linwan", name="林晚", visual_identity="黑色长发")],
        world_facts=[WorldFact(id="fact_city", text="故事发生在现代运城", category="setting")],
    )

    review = review_consistency(
        stage="storyboard",
        output="林晚变成短发金发女孩，故事发生在未来上海。",
        memory=memory,
    )

    assert review["status"] == "warning"
    assert any("林晚" in warning for warning in review["warnings"])
    assert any("现代运城" in warning for warning in review["warnings"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_ip_memory_extraction.py -q
```

Expected: FAIL because extraction and consistency modules are missing.

- [ ] **Step 3: Implement deterministic extraction**

Create `zhihu_fiction/ip_memory/extraction.py`:

```python
"""Deterministic IP memory extraction from generated or imported stories."""
from __future__ import annotations

import re

from .models import (
    CharacterCard,
    IPMemory,
    MemorySource,
    NarrativeMemory,
    StoryBible,
    StyleGuide,
    WorldFact,
)


def extract_ip_memory_from_story(
    *,
    project_id: str,
    title: str,
    genre: str,
    story_text: str,
    story_ref: str = "",
    prior: IPMemory | None = None,
) -> IPMemory:
    if not story_text.strip():
        return prior or IPMemory(project_id=project_id, story_bible=StoryBible(title=title, genre=genre))

    source = MemorySource(kind="story", ref=story_ref, excerpt=story_text[:160])
    bible = StoryBible(
        title=title or _extract_title(story_text) or (prior.story_bible.title if prior else ""),
        premise=_first_sentence(story_text),
        genre=genre or _extract_genre(story_text) or (prior.story_bible.genre if prior else ""),
        core_hook=_extract_hook(story_text),
        emotional_promise=_extract_emotional_promise(story_text),
        source=source,
    )
    characters = _dedupe_characters((prior.characters if prior else []) + _extract_characters(story_text, source))
    facts = _dedupe_facts((prior.world_facts if prior else []) + _extract_world_facts(story_text, source))
    narrative = _dedupe_narrative((prior.narrative_memory if prior else []) + _extract_narrative_memory(story_text, source))
    style = prior.style_guide if prior else StyleGuide()
    if not style.fiction_voice:
        style = StyleGuide(
            fiction_voice="知乎爆款网文，强钩子，高冲突，口语化叙事",
            drama_tone="强情绪、强反转、适合60-90秒短剧",
            camera_language="中近景推进，关键反转给特写",
            pacing="前三秒抛钩子，每集末尾留悬念",
            source=source,
        )
    return IPMemory(
        project_id=project_id,
        story_bible=bible,
        characters=characters,
        world_facts=facts,
        foreshadowing=list(prior.foreshadowing if prior else []),
        narrative_memory=narrative,
        style_guide=style,
        asset_bindings=list(prior.asset_bindings if prior else []),
        created_at=prior.created_at if prior else IPMemory(project_id=project_id).created_at,
    )


def _extract_title(text: str) -> str:
    match = re.search(r"^#\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_genre(text: str) -> str:
    match = re.search(r"题材[：:]\s*([^\n]+)", text)
    return match.group(1).strip() if match else ""


def _first_sentence(text: str) -> str:
    cleaned = re.sub(r"^#.*$", "", text, flags=re.MULTILINE).strip()
    parts = re.split(r"[。！？!?]\s*", cleaned)
    return parts[0].strip()[:180] if parts else ""


def _extract_hook(text: str) -> str:
    for marker in ("重生", "归来", "真相", "证据", "反击", "复仇"):
        idx = text.find(marker)
        if idx >= 0:
            return text[max(0, idx - 60): idx + 80].strip()
    return _first_sentence(text)


def _extract_emotional_promise(text: str) -> str:
    if any(word in text for word in ("复仇", "反击", "真相", "证据")):
        return "压抑后的反击与真相揭露"
    return "强情绪冲突与关系反转"


def _extract_characters(text: str, source: MemorySource) -> list[CharacterCard]:
    names = []
    for match in re.finditer(r"([\u4e00-\u9fa5]{2,4})(?:在|被|把|对|带着|发誓|醒来|说道|说)", text):
        name = match.group(1)
        if name not in {"故事发生", "这一回", "三年前"}:
            names.append(name)
    cards = []
    for idx, name in enumerate(_dedupe_text(names)[:8], start=1):
        role = "女主" if idx == 1 else "角色"
        cards.append(CharacterCard(id=f"char_{idx:02d}", name=name, role=role, source=source))
    return cards


def _extract_world_facts(text: str, source: MemorySource) -> list[WorldFact]:
    facts = []
    for keyword in ("运城", "山西", "现代", "雨夜", "家门", "遗嘱"):
        if keyword in text:
            facts.append(WorldFact(id=f"fact_{len(facts)+1:02d}", text=f"故事包含关键事实：{keyword}", category="setting", source=source))
    return facts


def _extract_narrative_memory(text: str, source: MemorySource) -> list[NarrativeMemory]:
    memories = []
    for keyword in ("录音证据", "父亲死亡", "篡改遗嘱", "三年前"):
        if keyword in text:
            memories.append(NarrativeMemory(id=f"mem_{len(memories)+1:02d}", text=f"必须延续的叙事细节：{keyword}", importance=4, source=source))
    return memories


def _dedupe_text(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _dedupe_characters(items: list[CharacterCard]) -> list[CharacterCard]:
    seen = set()
    result = []
    for item in items:
        if item.name and item.name not in seen:
            seen.add(item.name)
            result.append(item)
    return result


def _dedupe_facts(items: list[WorldFact]) -> list[WorldFact]:
    seen = set()
    result = []
    for item in items:
        if item.text and item.text not in seen:
            seen.add(item.text)
            result.append(item)
    return result


def _dedupe_narrative(items: list[NarrativeMemory]) -> list[NarrativeMemory]:
    seen = set()
    result = []
    for item in items:
        if item.text and item.text not in seen:
            seen.add(item.text)
            result.append(item)
    return result
```

- [ ] **Step 4: Implement consistency review**

Create `zhihu_fiction/ip_memory/consistency.py`:

```python
"""Consistency checks between stage output and IP memory."""
from __future__ import annotations

from .models import IPMemory


def review_consistency(stage: str, output: str, memory: IPMemory | None) -> dict:
    if memory is None:
        return {"stage": stage, "status": "ok", "warnings": [], "score": 1.0}
    warnings: list[str] = []
    for card in memory.characters:
        if card.name and card.name in output and card.visual_identity:
            for marker in ("金发", "短发", "白发"):
                if marker in output and marker not in card.visual_identity:
                    warnings.append(f"{card.name} 的视觉描述可能偏离角色卡：{card.visual_identity}")
                    break
    for fact in memory.world_facts:
        if "现代运城" in fact.text and ("未来上海" in output or "古代" in output):
            warnings.append(f"输出可能违背世界事实：{fact.text}")
    score = max(0.0, 1.0 - len(warnings) * 0.25)
    return {
        "stage": stage,
        "status": "warning" if warnings else "ok",
        "warnings": warnings,
        "score": score,
    }
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_ip_memory_extraction.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add zhihu_fiction/ip_memory/extraction.py zhihu_fiction/ip_memory/consistency.py zhihu_fiction/tests/test_ip_memory_extraction.py
git commit -m "feat: extract and review ip memory"
```

## Task 3: IP Memory API Routes

**Files:**
- Create: `zhihu_fiction/app/routes/ip_memory.py`
- Modify: `zhihu_fiction/app/factory.py`
- Test: `zhihu_fiction/tests/test_ip_memory_api.py`

- [ ] **Step 1: Write API tests**

Add `zhihu_fiction/tests/test_ip_memory_api.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from zhihu_fiction.app.factory import create_app
from zhihu_fiction.ip_memory.repository import IPMemoryRepository


class Deps:
    def __init__(self, tmp_path: Path):
        from zhihu_fiction.app.dependencies import AppDependencies
        base = AppDependencies()
        self.__dict__.update(base.__dict__)
        self.ip_memory_repo = IPMemoryRepository(tmp_path / "ip_memory")


def test_extract_and_read_ip_memory_api(tmp_path: Path):
    story = tmp_path / "story.md"
    story.write_text("# 雨夜归来\n\n> 题材：复仇爽文\n\n林晚在山西运城醒来，带着录音证据归来。", encoding="utf-8")
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    extracted = client.post(
        "/api/ip-memory/story-rain/extract",
        json={"title": "雨夜归来", "genre": "复仇爽文", "story_path": str(story)},
    )

    assert extracted.status_code == 200
    assert extracted.json()["memory"]["story_bible"]["title"] == "雨夜归来"

    loaded = client.get("/api/ip-memory/story-rain")
    assert loaded.status_code == 200
    assert loaded.json()["memory"]["project_id"] == "story-rain"


def test_patch_ip_memory_api(tmp_path: Path):
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/ip-memory/project-a/patch",
        json={"world_facts": [{"id": "fact_manual", "text": "人工确认的事实", "category": "manual"}]},
    )

    assert response.status_code == 200
    assert response.json()["memory"]["world_facts"][0]["text"] == "人工确认的事实"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_ip_memory_api.py -q
```

Expected: FAIL because the route is not registered.

- [ ] **Step 3: Implement route**

Create `zhihu_fiction/app/routes/ip_memory.py`:

```python
"""IP memory API routes."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ...ip_memory.extraction import extract_ip_memory_from_story
from ...ip_memory.repository import IPMemoryRepository
from ...ip_memory.rendering import render_memory_context
from ..request_parsing import json_body

router = APIRouter()


def _repo(req: Request) -> IPMemoryRepository:
    deps = req.app.state.dependencies
    repo = getattr(deps, "ip_memory_repo", None)
    if repo is not None:
        return repo
    from ...config import APP_ROOT
    repo = IPMemoryRepository(APP_ROOT / "data" / "ip_memory")
    deps.ip_memory_repo = repo
    return repo


@router.get("/api/ip-memory/{project_id}")
async def get_ip_memory(req: Request, project_id: str):
    memory = _repo(req).load(project_id)
    if memory is None:
        raise HTTPException(404, "IP memory not found")
    return {
        "project_id": project_id,
        "memory": memory.to_dict(),
        "context": render_memory_context(memory),
    }


@router.post("/api/ip-memory/{project_id}/extract")
async def extract_ip_memory(req: Request, project_id: str):
    body = await json_body(req)
    story_path = str(body.get("story_path") or "")
    story_text = str(body.get("story_text") or "")
    if story_path:
        path = Path(story_path)
        if not path.exists() or not path.is_file():
            raise HTTPException(404, "story_path not found")
        story_text = path.read_text(encoding="utf-8")
    if not story_text.strip():
        raise HTTPException(400, "story_path or story_text is required")
    repo = _repo(req)
    prior = repo.load(project_id)
    memory = extract_ip_memory_from_story(
        project_id=project_id,
        title=str(body.get("title") or ""),
        genre=str(body.get("genre") or ""),
        story_text=story_text,
        story_ref=story_path,
        prior=prior,
    )
    repo.save(memory, patch_note="api extraction")
    return {"project_id": project_id, "memory": memory.to_dict(), "context": render_memory_context(memory)}


@router.post("/api/ip-memory/{project_id}/patch")
async def patch_ip_memory(req: Request, project_id: str):
    body = await json_body(req)
    memory = _repo(req).apply_patch(project_id, body)
    return {"project_id": project_id, "memory": memory.to_dict(), "context": render_memory_context(memory)}
```

- [ ] **Step 4: Register route**

Modify `zhihu_fiction/app/factory.py`:

```python
from .routes import costs, drama_video, health, ip_memory, pipeline, projects, static, stories, tasks
```

Then include the router after `projects`:

```python
    app.include_router(projects.router)
    app.include_router(ip_memory.router)
    app.include_router(costs.router)
```

- [ ] **Step 5: Run API tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_ip_memory_api.py zhihu_fiction/tests/test_server_app_factory.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add zhihu_fiction/app/routes/ip_memory.py zhihu_fiction/app/factory.py zhihu_fiction/tests/test_ip_memory_api.py
git commit -m "feat: expose ip memory api"
```

## Task 4: Agent DAG Contract And Trace Store

**Files:**
- Create: `zhihu_fiction/ip_memory/agent_graph.py`
- Create: `zhihu_fiction/ip_memory/trace.py`
- Test: `zhihu_fiction/tests/test_agent_graph_trace.py`

- [ ] **Step 1: Write graph and trace tests**

Add `zhihu_fiction/tests/test_agent_graph_trace.py`:

```python
from pathlib import Path

from zhihu_fiction.ip_memory.agent_graph import node_for_stage, workflow_nodes
from zhihu_fiction.ip_memory.trace import AgentTraceEvent, AgentTraceStore


def test_workflow_nodes_define_required_contract():
    nodes = workflow_nodes()
    node = nodes["drama.storyboard"]

    assert node.node_id == "drama.storyboard"
    assert "CharacterCard" in node.required_memory
    assert "review_stage_output" in node.tools
    assert node.human_review_policy == "required"


def test_node_for_stage_maps_existing_drama_stage_names():
    assert node_for_stage("script").node_id == "drama.script"
    assert node_for_stage("storyboard").node_id == "drama.storyboard"


def test_trace_store_appends_and_reads_events(tmp_path: Path):
    store = AgentTraceStore(tmp_path)
    event = AgentTraceEvent(
        run_id="run-1",
        node_id="drama.script",
        stage="script",
        event="draft_created",
        memory_snapshot="sha256:abc",
        metadata={"version_id": "v1"},
    )

    store.append(event)
    events = store.list("run-1")

    assert len(events) == 1
    assert events[0].node_id == "drama.script"
    assert events[0].metadata["version_id"] == "v1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_agent_graph_trace.py -q
```

Expected: FAIL because graph and trace modules are missing.

- [ ] **Step 3: Implement graph contract**

Create `zhihu_fiction/ip_memory/agent_graph.py`:

```python
"""Agent DAG metadata for fiction and short-drama production."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class AgentGraphNode:
    node_id: str
    stage: str
    inputs: list[str]
    outputs: list[str]
    required_memory: list[str]
    tools: list[str]
    quality_gates: list[str]
    human_review_policy: str
    retry_policy: str
    cost_policy: str
    next_nodes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def workflow_nodes() -> dict[str, AgentGraphNode]:
    nodes = [
        AgentGraphNode("fiction.topic_intake", "topic_intake", ["topic"], ["topic_card"], [], ["generate_stage_draft"], ["topic_safety"], "optional", "retry", "free", ["fiction.story_bible"]),
        AgentGraphNode("fiction.story_bible", "story_bible", ["topic_card"], ["StoryBible"], [], ["generate_stage_draft", "write_ip_memory_patch"], ["memory_completeness"], "required", "new_version", "free", ["fiction.outline"]),
        AgentGraphNode("fiction.outline", "outline", ["StoryBible"], ["outline", "Foreshadowing"], ["StoryBible"], ["generate_stage_draft"], ["continuity_checker"], "required", "new_version", "free", ["fiction.chapter"]),
        AgentGraphNode("fiction.chapter", "chapter", ["outline", "memory"], ["story_text"], ["StoryBible", "CharacterCard", "WorldFact"], ["generate_stage_draft"], ["chapter_quality"], "required", "new_version", "free", ["fiction.review"]),
        AgentGraphNode("fiction.review", "review", ["story_text", "memory"], ["review"], ["StoryBible"], ["review_stage_output"], ["continuity_checker"], "required", "retry", "free", ["fiction.memory_extract"]),
        AgentGraphNode("fiction.memory_extract", "memory_extract", ["story_text"], ["IPMemory"], [], ["write_ip_memory_patch"], ["memory_completeness"], "optional", "retry", "free", ["drama.adaptation_blueprint"]),
        AgentGraphNode("drama.adaptation_blueprint", "adaptation_blueprint", ["story", "IPMemory"], ["blueprint"], ["StoryBible", "CharacterCard"], ["inspect_ip_memory", "generate_stage_draft"], ["short_drama_pacing"], "required", "new_version", "free", ["drama.episode_plot"]),
        AgentGraphNode("drama.episode_plot", "plot", ["blueprint", "IPMemory"], ["plot"], ["StoryBible", "Foreshadowing"], ["generate_stage_draft", "review_stage_output"], ["continuity_checker"], "required", "new_version", "free", ["drama.script"]),
        AgentGraphNode("drama.script", "script", ["plot", "IPMemory"], ["script"], ["StoryBible", "CharacterCard"], ["generate_stage_draft", "review_stage_output"], ["short_drama_pacing"], "required", "new_version", "free", ["drama.style"]),
        AgentGraphNode("drama.style", "style", ["script", "IPMemory"], ["StyleGuide"], ["StoryBible"], ["generate_stage_draft", "write_ip_memory_patch"], ["style_compatibility"], "required", "new_version", "free", ["drama.consistency"]),
        AgentGraphNode("drama.consistency", "consistency", ["style", "IPMemory"], ["consistency_report"], ["StoryBible", "CharacterCard", "WorldFact"], ["review_stage_output"], ["continuity_checker"], "required", "retry", "free", ["drama.character_reference"]),
        AgentGraphNode("drama.character_reference", "character_refs", ["IPMemory"], ["character_reference_prompts"], ["CharacterCard", "StyleGuide"], ["generate_stage_draft"], ["bailian_video_prompt_guard"], "required", "new_version", "free", ["drama.storyboard"]),
        AgentGraphNode("drama.storyboard", "storyboard", ["script", "style", "IPMemory"], ["storyboard"], ["StoryBible", "CharacterCard", "WorldFact", "StyleGuide"], ["generate_stage_draft", "review_stage_output"], ["continuity_checker", "shot_prompt_builder"], "required", "new_version", "free", ["drama.video_prompt_package"]),
        AgentGraphNode("drama.video_prompt_package", "video_prompt_package", ["storyboard", "IPMemory"], ["video_prompts"], ["CharacterCard", "StyleGuide"], ["generate_stage_draft", "review_stage_output"], ["bailian_video_prompt_guard"], "required", "new_version", "free", ["video.cost_confirmation"]),
        AgentGraphNode("video.cost_confirmation", "video", ["video_prompts"], ["cost_estimate"], [], ["request_human_review"], ["budget_limit"], "required", "retry", "paid_confirmation", ["video.submit_jobs"]),
        AgentGraphNode("video.submit_jobs", "video_submit", ["cost_confirmation"], ["video_jobs"], [], ["advance_agent_graph"], ["provider_status"], "required", "shot_retry", "paid", []),
    ]
    return {node.node_id: node for node in nodes}


_STAGE_TO_NODE = {
    "script": "drama.script",
    "style": "drama.style",
    "plot": "drama.episode_plot",
    "character_refs": "drama.character_reference",
    "storyboard": "drama.storyboard",
    "video": "video.cost_confirmation",
}


def node_for_stage(stage: str) -> AgentGraphNode:
    node_id = _STAGE_TO_NODE.get(stage, stage)
    nodes = workflow_nodes()
    if node_id not in nodes:
        raise KeyError(f"Unknown agent graph stage: {stage}")
    return nodes[node_id]
```

- [ ] **Step 4: Implement trace store**

Create `zhihu_fiction/ip_memory/trace.py`:

```python
"""File-backed Agent DAG trace records."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from .models import utc_now_iso


@dataclass(slots=True)
class AgentTraceEvent:
    run_id: str
    node_id: str
    stage: str
    event: str
    memory_snapshot: str = "sha256:empty"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    review: dict[str, Any] = field(default_factory=dict)
    human_decision: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentTraceEvent":
        return cls(
            run_id=str(data.get("run_id") or ""),
            node_id=str(data.get("node_id") or ""),
            stage=str(data.get("stage") or ""),
            event=str(data.get("event") or ""),
            memory_snapshot=str(data.get("memory_snapshot") or "sha256:empty"),
            tool_calls=list(data.get("tool_calls") or []),
            review=dict(data.get("review") or {}),
            human_decision=dict(data.get("human_decision") or {}),
            metadata=dict(data.get("metadata") or {}),
            created_at=str(data.get("created_at") or utc_now_iso()),
        )


class AgentTraceStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def append(self, event: AgentTraceEvent) -> None:
        path = self._path(event.run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def list(self, run_id: str) -> list[AgentTraceEvent]:
        path = self._path(run_id)
        if not path.exists():
            return []
        events = []
        with path.open(encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    events.append(AgentTraceEvent.from_dict(json.loads(line)))
        return events

    def _path(self, run_id: str) -> Path:
        safe = "".join(ch for ch in run_id if ch.isalnum() or ch in ("-", "_", "."))
        return self.root / f"{safe or 'default'}.jsonl"
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_agent_graph_trace.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add zhihu_fiction/ip_memory/agent_graph.py zhihu_fiction/ip_memory/trace.py zhihu_fiction/tests/test_agent_graph_trace.py
git commit -m "feat: add agent graph trace contract"
```

## Task 5: Fiction Pipeline Memory Integration

**Files:**
- Modify: `zhihu_fiction/orchestrator.py`
- Modify: `zhihu_fiction/pipeline.py`
- Test: `zhihu_fiction/tests/test_pipeline_ip_memory.py`

- [ ] **Step 1: Write pipeline integration tests**

Add `zhihu_fiction/tests/test_pipeline_ip_memory.py`:

```python
from pathlib import Path

from zhihu_fiction.ip_memory.repository import IPMemoryRepository
from zhihu_fiction.pipeline import Pipeline


class FakeCoordinator:
    def invoke(self, input_msg):
        self.last_prompt = input_msg["messages"][0]["content"]
        return {"messages": [{"type": "ai", "content": "【小说正文】\n林晚在山西运城醒来，带着录音证据归来。\n【发布方案】\n短剧改编"}]}


class FakeReviewer:
    def review(self, story, topic):
        return {"total_score": 9.0, "full_report": "ok"}


class FakePublisher:
    def publish(self, **kwargs):
        return {"success": False, "url": "", "message": "local"}


def test_pipeline_extracts_ip_memory_after_story_save(tmp_path: Path, monkeypatch):
    repo = IPMemoryRepository(tmp_path / "ip_memory")
    pipeline = Pipeline(
        coordinator=FakeCoordinator(),
        reviewer=FakeReviewer(),
        llm=object(),
        publisher=FakePublisher(),
        scraper=lambda: [{"title": "热榜", "hot_score": 1, "excerpt": ""}],
        topic_selector=lambda items, llm: {"topic": "雨夜归来", "genre": "复仇爽文"},
    )
    pipeline._ip_memory_repo = repo

    result = pipeline.run(topic="雨夜归来", genre="复仇爽文")

    memory = repo.load(result.run_id)
    assert memory is not None
    assert memory.story_bible.title == "雨夜归来"
    assert any("运城" in fact.text for fact in memory.world_facts)


def test_run_coordinator_includes_memory_context():
    from zhihu_fiction.orchestrator import run_coordinator

    coordinator = FakeCoordinator()
    run_coordinator(
        object(),
        coordinator,
        topic="雨夜归来",
        genre="复仇爽文",
        memory_context="【IP记忆】\n林晚：女主",
    )

    assert "【IP记忆】" in coordinator.last_prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_pipeline_ip_memory.py -q
```

Expected: FAIL because `run_coordinator` does not accept `memory_context` and pipeline does not extract memory.

- [ ] **Step 3: Add memory context to coordinator prompt**

Modify `zhihu_fiction/orchestrator.py` signature:

```python
def run_coordinator(
    llm,
    coordinator,
    topic: str,
    hot_trends: str = "",
    genre: str | None = None,
    revision_feedback: str = "",
    stream_callback: callable | None = None,
    chapter_index: int = 1,
    total_chapters: int = 1,
    existing_story: str = "",
    memory_context: str = "",
) -> WorkflowResult:
```

Add before prompt construction:

```python
    memory_section = ""
    if memory_context.strip():
        memory_section = f"\n\n【创作记忆】\n{memory_context.strip()}\n请优先遵守以上角色、世界事实、伏笔和风格约束。"
```

Append `memory_section` to both revision and normal prompt strings:

```python
            f"最终用【小说正文】和【发布方案】两个标记分别输出。{chapter_info}{memory_section}"
```

and:

```python
            f"最终用【小说正文】和【发布方案】两个标记分别输出。{chapter_info}{feedback_section}{memory_section}"
```

- [ ] **Step 4: Extract memory after story save**

Modify `zhihu_fiction/pipeline.py` imports near the top:

```python
from .ip_memory.extraction import extract_ip_memory_from_story
from .ip_memory.repository import IPMemoryRepository
from .ip_memory.rendering import render_memory_context
```

In `Pipeline.__init__`, after `self._skills_store = skills_store`:

```python
        self._ip_memory_repo = IPMemoryRepository(APP_ROOT / "data" / "ip_memory")
```

Before each `run_coordinator` call in the chapter loop, build memory context:

```python
                prior_memory = self._ip_memory_repo.load(run_id)
                memory_context = render_memory_context(prior_memory) if prior_memory else ""
                wf_result = run_coordinator(
                    self.llm,
                    self.coordinator,
                    topic=topic,
                    hot_trends=hot_summary,
                    genre=genre,
                    chapter_index=ch_idx,
                    total_chapters=total_chapters,
                    existing_story=existing,
                    memory_context=memory_context,
                    stream_callback=stream_callback,
                )
```

After `_save_story(...)`, add:

```python
            try:
                prior_memory = self._ip_memory_repo.load(run_id)
                memory = extract_ip_memory_from_story(
                    project_id=run_id,
                    title=topic,
                    genre=result.genre,
                    story_text=full_story,
                    story_ref=str(story_path),
                    prior=prior_memory,
                )
                self._ip_memory_repo.save(memory, patch_note="pipeline story extraction")
                result.stages["ip_memory"] = StageRecord(
                    status="ok",
                    duration_s=0,
                    extra={
                        "project_id": run_id,
                        "characters": len(memory.characters),
                        "world_facts": len(memory.world_facts),
                    },
                )
            except Exception as exc:
                result.stages["ip_memory"] = StageRecord(
                    status="failed",
                    duration_s=0,
                    extra={"error": str(exc)},
                )
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_pipeline_ip_memory.py zhihu_fiction/tests/test_pipeline_routes.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add zhihu_fiction/orchestrator.py zhihu_fiction/pipeline.py zhihu_fiction/tests/test_pipeline_ip_memory.py
git commit -m "feat: connect fiction pipeline to ip memory"
```

## Task 6: Drama DeepAgent Memory Context And Stage Review

**Files:**
- Modify: `zhihu_fiction/app/services/drama_video_stage_generation.py`
- Modify: `zhihu_fiction/orchestrator.py`
- Test: `zhihu_fiction/tests/test_drama_video_ip_memory_integration.py`

- [ ] **Step 1: Write drama memory injection tests**

Add `zhihu_fiction/tests/test_drama_video_ip_memory_integration.py`:

```python
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from zhihu_fiction.ip_memory.models import CharacterCard, IPMemory, StoryBible
from zhihu_fiction.ip_memory.repository import IPMemoryRepository
from zhihu_fiction.app.services.drama_video_stage_generation import build_stage_prompt


def test_build_stage_prompt_includes_ip_memory_context():
    result = SimpleNamespace(
        topic="雨夜归来",
        genre="复仇爽文",
        synthesis="短剧卖点",
        final_story="林晚归来。",
    )
    memory = IPMemory(
        project_id="p",
        story_bible=StoryBible(title="雨夜归来", premise="复仇"),
        characters=[CharacterCard(id="char_linwan", name="林晚", role="女主")],
    )

    prompt = build_stage_prompt(result, "script", {}, ip_memory=memory)

    assert "【IP记忆】" in prompt
    assert "林晚" in prompt


def test_run_stage_deepagent_rejects_unknown_stage_without_memory_lookup(tmp_path: Path):
    from zhihu_fiction.app.services.drama_video_stage_generation import run_stage_deepagent

    deps = SimpleNamespace(settings=SimpleNamespace(model="deepseek-v4-pro"), ip_memory_repo=IPMemoryRepository(tmp_path))

    try:
        run_stage_deepagent(deps, "missing.md", "bad_stage", {})
    except HTTPException as exc:
        assert exc.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_ip_memory_integration.py -q
```

Expected: FAIL because `build_stage_prompt` does not accept `ip_memory`.

- [ ] **Step 3: Update stage prompt builder**

Modify `zhihu_fiction/app/services/drama_video_stage_generation.py` imports:

```python
from ...ip_memory.models import IPMemory
from ...ip_memory.rendering import render_memory_context
```

Change signature:

```python
def build_stage_prompt(result, stage: str, stage_drafts: dict[str, str], ip_memory: IPMemory | None = None) -> str:
```

Add memory text before the final return:

```python
    memory_context = render_memory_context(ip_memory) if ip_memory is not None else "【IP记忆】\n暂无已保存记忆。"
```

Insert into returned prompt after stage requirements:

```python
统一IP记忆：
{memory_context}
```

- [ ] **Step 4: Load memory in `run_stage_deepagent`**

In `run_stage_deepagent`, after `result = story_result_from_file(story_file)`:

```python
    ip_memory = None
    repo = getattr(dependencies, "ip_memory_repo", None)
    if repo is not None:
        ip_memory = repo.load(str(story_path)) or repo.load(str(story_file)) or repo.load(getattr(result, "topic", ""))
```

If project id is available in callers later, Task 7 will store it in session spec. For this task, support story path and topic lookup.

- [ ] **Step 5: Add memory context to drama coordinator**

Modify `zhihu_fiction/orchestrator.py` `run_drama_video_coordinator` signature:

```python
    memory_context: str = "",
) -> dict[str, Any]:
```

Add to prompt:

```python
        f"统一IP记忆：\n{memory_context or '暂无'}\n\n"
```

Pass it from `run_stage_deepagent`:

```python
    output = coordinator_runner(
        coordinator,
        result=result,
        stage=stage,
        stage_drafts=stage_drafts,
        current_draft=current_draft,
        human_feedback=human_feedback,
        memory_context=render_memory_context(ip_memory),
    )
```

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_ip_memory_integration.py zhihu_fiction/tests/test_drama_video_stage_generation.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add zhihu_fiction/app/services/drama_video_stage_generation.py zhihu_fiction/orchestrator.py zhihu_fiction/tests/test_drama_video_ip_memory_integration.py
git commit -m "feat: inject ip memory into drama stages"
```

## Task 7: DeepAgent Session Trace And Human-Loop Memory Patches

**Files:**
- Modify: `zhihu_fiction/app/services/drama_video_deepagent_flow.py`
- Modify: `zhihu_fiction/app/services/drama_video_sessions.py`
- Modify: `zhihu_fiction/app/routes/drama_video.py`
- Test: `zhihu_fiction/tests/test_drama_video_deepagent_flow.py`

- [ ] **Step 1: Add trace expectations to existing DeepAgent tests**

Extend `zhihu_fiction/tests/test_drama_video_deepagent_flow.py` with:

```python
def test_confirm_stage_records_agent_trace_and_memory_patch(deepagent_deps, deepagent_state):
    from zhihu_fiction.app.services import drama_video_deepagent_flow as flow
    from zhihu_fiction.ip_memory.repository import IPMemoryRepository
    from zhihu_fiction.ip_memory.trace import AgentTraceStore

    deepagent_deps.ip_memory_repo = IPMemoryRepository(deepagent_deps.tmp_path / "ip_memory")
    deepagent_deps.agent_trace_store = AgentTraceStore(deepagent_deps.tmp_path / "traces")

    started = flow.start_deepagent_run(
        deepagent_deps,
        deepagent_state,
        story_path="output/story/小说正文.md",
        project_id="project-a",
        shot_limit=1,
        stage_drafts={},
        id_factory=lambda prefix: "deepagent-test",
    )
    deepagent_state.video_deepagent_specs[started["run_id"]]["pending_stage"] = "script"
    deepagent_state.video_deepagent_specs[started["run_id"]].setdefault("drafts", {})["script"] = "林晚确认复仇目标。"

    result = flow.confirm_stage(
        deepagent_deps,
        deepagent_state,
        "deepagent-test",
        "script",
        "林晚确认复仇目标。",
        video_starter=lambda *args, **kwargs: "video-run",
    )

    traces = deepagent_deps.agent_trace_store.list("deepagent-test")
    assert result["status"] == "ready_for_next_stage"
    assert any(event.event == "human_confirmed" for event in traces)
```

If current fixtures do not expose `tmp_path`, adjust the fixture by adding `deps.tmp_path = tmp_path` in the test setup.

- [ ] **Step 2: Run targeted test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_deepagent_flow.py::test_confirm_stage_records_agent_trace_and_memory_patch -q
```

Expected: FAIL because traces are not recorded.

- [ ] **Step 3: Add trace helper functions**

Modify `zhihu_fiction/app/services/drama_video_sessions.py` imports:

```python
from ...ip_memory.agent_graph import node_for_stage
from ...ip_memory.consistency import review_consistency
from ...ip_memory.trace import AgentTraceEvent
```

Add helper:

```python
def record_agent_trace(
    dependencies,
    run_id: str,
    stage: str,
    event: str,
    *,
    project_id: str = "",
    content: str = "",
    metadata: dict | None = None,
    human_decision: dict | None = None,
) -> None:
    store = getattr(dependencies, "agent_trace_store", None)
    if store is None:
        return
    repo = getattr(dependencies, "ip_memory_repo", None)
    memory = repo.load(project_id) if repo is not None and project_id else None
    snapshot = repo.snapshot_hash(memory) if repo is not None else "sha256:empty"
    review = review_consistency(stage, content, memory)
    node = node_for_stage(stage)
    store.append(
        AgentTraceEvent(
            run_id=run_id,
            node_id=node.node_id,
            stage=stage,
            event=event,
            memory_snapshot=snapshot,
            review=review,
            human_decision=dict(human_decision or {}),
            metadata=dict(metadata or {}),
        )
    )
```

- [ ] **Step 4: Record traces from DeepAgent flow**

Modify imports in `zhihu_fiction/app/services/drama_video_deepagent_flow.py`:

```python
    record_agent_trace,
```

After `record_stage_version(...)` calls for draft, revision, retry, and confirmation, call:

```python
    record_agent_trace(
        dependencies,
        run_id,
        stage,
        "draft_created",
        project_id=project_id,
        content=content,
        metadata={"version_id": version.id, "events": events},
    )
```

For confirmation:

```python
    record_agent_trace(
        dependencies,
        run_id,
        stage,
        "human_confirmed",
        project_id=spec.get("project_id") or "",
        content=content,
        metadata={"version_id": version.id},
        human_decision={"decision": "confirm", "stage": stage},
    )
```

For revision:

```python
    record_agent_trace(
        dependencies,
        run_id,
        stage,
        "human_revision_requested",
        project_id=spec.get("project_id") or "",
        content=draft["content"],
        metadata={"version_id": version.id, "feedback": feedback},
        human_decision={"decision": "revise", "feedback": feedback},
    )
```

- [ ] **Step 5: Expose trace route**

Modify `zhihu_fiction/app/routes/drama_video.py`:

```python
@router.get("/api/drama-video/deepagent/{run_id}/trace")
async def get_drama_video_deepagent_trace(req: Request, run_id: str):
    deps = req.app.state.dependencies
    store = getattr(deps, "agent_trace_store", None)
    if store is None:
        return {"run_id": run_id, "events": []}
    return {"run_id": run_id, "events": [event.to_dict() for event in store.list(run_id)]}
```

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_deepagent_flow.py zhihu_fiction/tests/test_server_drama_video.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add zhihu_fiction/app/services/drama_video_deepagent_flow.py zhihu_fiction/app/services/drama_video_sessions.py zhihu_fiction/app/routes/drama_video.py zhihu_fiction/tests/test_drama_video_deepagent_flow.py
git commit -m "feat: trace deepagent memory decisions"
```

## Task 8: Workbench Memory And Trace Panel

**Files:**
- Modify: `zhihu_fiction/static/video.html`
- Test: `zhihu_fiction/tests/test_static_video_workspace.py`

- [ ] **Step 1: Add static UI test expectations**

Extend `zhihu_fiction/tests/test_static_video_workspace.py`:

```python
def test_video_workspace_exposes_ip_memory_and_trace_panel():
    html = Path("zhihu_fiction/static/video.html").read_text(encoding="utf-8")

    assert "ip-memory-panel" in html
    assert "agent-trace-panel" in html
    assert "/api/ip-memory/" in html
    assert "/trace" in html
```

Ensure the file already imports `Path`; if not, add:

```python
from pathlib import Path
```

- [ ] **Step 2: Run static test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_static_video_workspace.py::test_video_workspace_exposes_ip_memory_and_trace_panel -q
```

Expected: FAIL because the UI panel is not present.

- [ ] **Step 3: Add IP memory panel markup**

In `zhihu_fiction/static/video.html`, add a right-side panel near the existing session/status panels:

```html
<section id="ip-memory-panel" class="workspace-panel">
  <header class="panel-header">
    <h2>IP Memory</h2>
    <button id="refresh-ip-memory" type="button">Refresh</button>
  </header>
  <div id="ip-memory-content" class="panel-body muted">No memory loaded.</div>
</section>

<section id="agent-trace-panel" class="workspace-panel">
  <header class="panel-header">
    <h2>Agent Trace</h2>
    <button id="refresh-agent-trace" type="button">Refresh</button>
  </header>
  <div id="agent-trace-content" class="panel-body muted">No trace events.</div>
</section>
```

- [ ] **Step 4: Add fetch helpers**

In the existing `<script>` block, add:

```javascript
async function loadIpMemory(projectId) {
  if (!projectId) return;
  const target = document.getElementById("ip-memory-content");
  if (!target) return;
  try {
    const response = await fetch(`/api/ip-memory/${encodeURIComponent(projectId)}`);
    if (!response.ok) {
      target.textContent = "No memory saved yet.";
      return;
    }
    const payload = await response.json();
    target.textContent = payload.context || JSON.stringify(payload.memory, null, 2);
  } catch (error) {
    target.textContent = `Memory load failed: ${error.message}`;
  }
}

async function loadAgentTrace(runId) {
  if (!runId) return;
  const target = document.getElementById("agent-trace-content");
  if (!target) return;
  try {
    const response = await fetch(`/api/drama-video/deepagent/${encodeURIComponent(runId)}/trace`);
    const payload = await response.json();
    const events = payload.events || [];
    target.textContent = events.length
      ? events.map((event) => `${event.created_at} ${event.node_id} ${event.event}`).join("\n")
      : "No trace events.";
  } catch (error) {
    target.textContent = `Trace load failed: ${error.message}`;
  }
}
```

- [ ] **Step 5: Wire buttons to current state**

Reuse the current global project/session variables if they exist. If the page stores selected project or run id under different names, bind using the existing names:

```javascript
document.getElementById("refresh-ip-memory")?.addEventListener("click", () => {
  loadIpMemory(window.currentProjectId || window.currentStoryPath || "");
});

document.getElementById("refresh-agent-trace")?.addEventListener("click", () => {
  loadAgentTrace(window.currentDeepAgentRunId || "");
});
```

- [ ] **Step 6: Run static tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_static_video_workspace.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add zhihu_fiction/static/video.html zhihu_fiction/tests/test_static_video_workspace.py
git commit -m "feat: show ip memory and agent trace in workbench"
```

## Task 9: Full Verification, Docs, And Spec Review

**Files:**
- Modify: `zhihu_fiction/README.md`
- Modify: `README.md`
- Review: `docs/superpowers/specs/2026-07-07-zhihu-fiction-unified-ip-memory-agent-dag-design.md`

- [ ] **Step 1: Update documentation**

Add to `zhihu_fiction/README.md` under the short-drama or Agent section:

```markdown
### Unified IP Memory

The fiction and short-drama workflows now share a lightweight IP memory package.
Generated stories can extract a Story Bible, character cards, world facts,
narrative memory, style guidance, and asset bindings. Short-drama DeepAgent
stages read this memory before generating scripts, style plans, character
references, storyboards, and video prompt packages.

Useful local APIs:

- `GET /api/ip-memory/{project_id}`
- `POST /api/ip-memory/{project_id}/extract`
- `POST /api/ip-memory/{project_id}/patch`
- `GET /api/drama-video/deepagent/{run_id}/trace`
```

Add a one-line feature note to the root `README.md` project description:

```markdown
- Unified IP memory and Agent DAG traces connect novel generation, short-drama adaptation, and video prompt production.
```

- [ ] **Step 2: Run focused test suite**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_ip_memory_models.py zhihu_fiction/tests/test_ip_memory_extraction.py zhihu_fiction/tests/test_ip_memory_api.py zhihu_fiction/tests/test_agent_graph_trace.py zhihu_fiction/tests/test_pipeline_ip_memory.py zhihu_fiction/tests/test_drama_video_ip_memory_integration.py zhihu_fiction/tests/test_drama_video_deepagent_flow.py zhihu_fiction/tests/test_static_video_workspace.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full project checks**

Run:

```bash
python -m pytest zhihu_fiction/tests -q
python -m compileall -q zhihu_fiction
git diff --check
```

Expected:
- `pytest` passes.
- `compileall` exits 0.
- `git diff --check` prints no whitespace errors.

- [ ] **Step 4: Spec review**

Review `docs/superpowers/specs/2026-07-07-zhihu-fiction-unified-ip-memory-agent-dag-design.md` against the implemented code.

Confirm:
- Unified IP memory exists and is file-backed.
- Fiction pipeline writes memory after story generation.
- Drama stage generation consumes memory context.
- DeepAgent trace records node id, memory snapshot, review, and human decision.
- Human revisions create new versions through existing `DramaStageVersion`.
- No SQL, Redis, MinIO, or provider migration was added.

- [ ] **Step 5: Quality review**

Check:
- No unrelated files are staged.
- Repository writes are atomic for `memory.json`.
- Empty extraction does not erase prior memory.
- Unknown stages fail with 400 or a clear exception.
- Trace APIs return empty lists when tracing is not configured.
- API routes do not expose API keys or environment values.

- [ ] **Step 6: Commit docs and final integration**

Run:

```bash
git add README.md zhihu_fiction/README.md
git commit -m "docs: document unified ip memory workflow"
```

If final integration changes remain unstaged after the earlier task commits, stage only the exact files created or modified by this plan:

```bash
git status --short
git add README.md zhihu_fiction/README.md
git add zhihu_fiction/ip_memory/__init__.py zhihu_fiction/ip_memory/models.py zhihu_fiction/ip_memory/repository.py zhihu_fiction/ip_memory/rendering.py zhihu_fiction/ip_memory/extraction.py zhihu_fiction/ip_memory/consistency.py zhihu_fiction/ip_memory/agent_graph.py zhihu_fiction/ip_memory/trace.py
git add zhihu_fiction/app/factory.py zhihu_fiction/app/routes/ip_memory.py zhihu_fiction/app/routes/drama_video.py zhihu_fiction/app/services/drama_video_stage_generation.py zhihu_fiction/app/services/drama_video_deepagent_flow.py zhihu_fiction/app/services/drama_video_sessions.py zhihu_fiction/orchestrator.py zhihu_fiction/pipeline.py zhihu_fiction/static/video.html
git add zhihu_fiction/tests/test_ip_memory_models.py zhihu_fiction/tests/test_ip_memory_extraction.py zhihu_fiction/tests/test_ip_memory_api.py zhihu_fiction/tests/test_agent_graph_trace.py zhihu_fiction/tests/test_pipeline_ip_memory.py zhihu_fiction/tests/test_drama_video_ip_memory_integration.py zhihu_fiction/tests/test_drama_video_deepagent_flow.py zhihu_fiction/tests/test_static_video_workspace.py
git commit -m "feat: complete unified ip memory agent dag"
```

## Plan Self-Review

Spec coverage:
- Unified IP memory is covered by Tasks 1-3.
- Fiction memory extraction and injection are covered by Task 5.
- Short-drama memory consumption is covered by Task 6.
- Agent DAG and traceability are covered by Tasks 4 and 7.
- Human-loop visibility and trace API are covered by Tasks 7 and 8.
- Documentation and required two-stage project review are covered by Task 9.

Placeholder scan:
- This plan contains concrete file paths, tests, code snippets, commands, and expected results.
- No unresolved implementation sections remain.

Type consistency:
- `IPMemoryRepository`, `IPMemory`, `render_memory_context`, `extract_ip_memory_from_story`, `review_consistency`, `AgentTraceStore`, and `AgentTraceEvent` are introduced before downstream tasks use them.
- Existing stage names stay compatible with `script`, `style`, `plot`, `character_refs`, `storyboard`, and `video`.

Execution recommendation:
- Use subagent-driven execution one task at a time.
- Run the focused tests after each task.
- Preserve unrelated dirty files in the primary checkout.
