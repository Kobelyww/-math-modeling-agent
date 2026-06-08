# Zhihu Fiction Workspace Business Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the file-backed `zhihu_fiction` workspace loop from materials to topic cards, queued story tasks, review drafts, and publish packages.

**Architecture:** Add a focused `zhihu_fiction/workspace/` domain package with dataclass models, file-backed repositories, services, and a single-worker queue. Mount workspace FastAPI routes from `server.py`, reuse `Pipeline.run()` for generation, and keep the existing CLI and old Web run APIs compatible.

**Tech Stack:** Python 3.11, dataclasses, pathlib/json/threading/queue from the standard library, FastAPI, pytest, existing `Pipeline`, existing `Exporter`, Alpine/Tailwind static frontend.

---

## Scope

This plan implements the approved design in `docs/superpowers/specs/2026-06-08-zhihu-fiction-workspace-business-modules-design.md`.

It does not add SQLite, multi-worker concurrency, user accounts, a rich text editor, automatic publishing, or new platform implementations.

## File Structure

### Create

- `zhihu_fiction/workspace/__init__.py`
  - Package exports for the workspace layer.

- `zhihu_fiction/workspace/models.py`
  - Dataclass domain objects: `Material`, `TopicCard`, `StoryTask`, `ReviewDraft`, `PublishPackage`.
  - Status constants and serialization helpers.

- `zhihu_fiction/workspace/repositories.py`
  - File-backed repository implementation under `zhihu_fiction/data/workspace/`.
  - JSONL helpers for list/update records and JSON file helpers for draft/package bodies.

- `zhihu_fiction/workspace/services.py`
  - Business operations: import materials, create/approve topic cards, create tasks, create/update drafts, generate package records.

- `zhihu_fiction/workspace/queue.py`
  - Single-worker queue that claims one queued task at a time and runs a pipeline factory.

- `zhihu_fiction/workspace/schemas.py`
  - FastAPI request models.

- `zhihu_fiction/workspace_routes.py`
  - FastAPI router for `/api/workspace/*`.

- `zhihu_fiction/tests/test_workspace_models.py`
- `zhihu_fiction/tests/test_workspace_repositories.py`
- `zhihu_fiction/tests/test_workspace_services.py`
- `zhihu_fiction/tests/test_workspace_queue.py`
- `zhihu_fiction/tests/test_workspace_api.py`

### Modify

- `zhihu_fiction/server.py`
  - Mount `workspace_routes.router`.
  - Initialize the workspace repository/service/queue.

- `zhihu_fiction/static/index.html`
  - Add workspace tabs and client-side calls for materials, topic cards, tasks, drafts, and packages.
  - Keep existing tabs functional.

- `zhihu_fiction/README.md`
  - Document the workspace flow and API surface at a high level.

---

## Task 1: Add Workspace Domain Models

**Files:**
- Create: `zhihu_fiction/workspace/__init__.py`
- Create: `zhihu_fiction/workspace/models.py`
- Create: `zhihu_fiction/tests/test_workspace_models.py`

- [ ] **Step 1: Write model tests**

Create `zhihu_fiction/tests/test_workspace_models.py`:

```python
"""Tests for workspace domain models."""
from __future__ import annotations

import pytest

from zhihu_fiction.workspace.models import (
    MATERIAL_STATUSES,
    PACKAGE_STATUSES,
    TASK_STATUSES,
    Material,
    PublishPackage,
    ReviewDraft,
    StoryTask,
    TopicCard,
    new_id,
)


def test_new_id_includes_prefix():
    value = new_id("mat")
    assert value.startswith("mat_")
    assert len(value) > len("mat_")


def test_material_round_trip():
    material = Material(
        id="mat_1",
        source="manual",
        title="热榜标题",
        excerpt="摘要",
        content="正文",
        url="https://example.test",
        hot_score=12.5,
        tags=["悬疑"],
        captured_at="2026-06-08T12:00:00",
        status="selected",
    )

    loaded = Material.from_dict(material.to_dict())

    assert loaded == material
    assert loaded.status in MATERIAL_STATUSES


def test_topic_card_defaults_to_draft():
    card = TopicCard(
        id="card_1",
        title="密室选题",
        source_material_ids=["mat_1"],
        genre="悬疑",
        platform="zhihu",
        hook="开门就是尸体",
        angle="第一人称误导",
        risk_notes="避免血腥细节",
        target_reader="喜欢反转的知乎读者",
        created_at="2026-06-08T12:00:00",
    )

    assert card.status == "draft"
    assert card.to_dict()["source_material_ids"] == ["mat_1"]


def test_story_task_rejects_invalid_status():
    with pytest.raises(ValueError, match="Invalid StoryTask.status"):
        StoryTask(
            id="task_1",
            topic_card_id="card_1",
            topic="密室选题",
            genre="悬疑",
            platform="zhihu",
            chapters=1,
            mode="full",
            priority=0,
            created_at="2026-06-08T12:00:00",
            status="done",
        )


def test_story_task_defaults_are_queue_ready():
    task = StoryTask(
        id="task_1",
        topic_card_id="card_1",
        topic="密室选题",
        genre="悬疑",
        platform="zhihu",
        chapters=1,
        mode="full",
        priority=0,
        created_at="2026-06-08T12:00:00",
    )

    assert task.status == "queued"
    assert task.retry_count == 0
    assert task.status in TASK_STATUSES


def test_review_draft_round_trip_keeps_original_body():
    draft = ReviewDraft(
        id="draft_1",
        task_id="task_1",
        story_path="output/story.md",
        original_body="原始正文",
        title="标题",
        synopsis="简介",
        tags=["知乎", "悬疑"],
        body="编辑正文",
        review_result={"score": 7.5},
        editor_notes="需要改标题",
        updated_at="2026-06-08T12:00:00",
    )

    loaded = ReviewDraft.from_dict(draft.to_dict())

    assert loaded.original_body == "原始正文"
    assert loaded.body == "编辑正文"


def test_publish_package_status_values():
    package = PublishPackage(
        id="pkg_1",
        task_id="task_1",
        platform="zhihu",
        title="标题",
        synopsis="简介",
        tags=["悬疑"],
        content_path="content.md",
        metadata_path="metadata.md",
        package_dir="pkg_1",
        created_at="2026-06-08T12:00:00",
    )

    assert package.status == "generated"
    assert package.status in PACKAGE_STATUSES
```

- [ ] **Step 2: Run model tests to verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_models.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'zhihu_fiction.workspace'
```

- [ ] **Step 3: Add package exports**

Create `zhihu_fiction/workspace/__init__.py`:

```python
"""Workspace business layer for zhihu_fiction."""
```

- [ ] **Step 4: Implement domain models**

Create `zhihu_fiction/workspace/models.py`:

```python
"""Domain models for the local content production workspace."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from uuid import uuid4

MATERIAL_STATUSES = {"inbox", "selected", "archived"}
TOPIC_CARD_STATUSES = {"draft", "approved", "archived"}
TASK_STATUSES = {"queued", "running", "needs_review", "approved", "failed", "canceled"}
DRAFT_STATUSES = {"needs_edit", "ready_for_package", "rejected"}
PACKAGE_STATUSES = {"generated", "confirmed", "exported"}


def utc_now_iso() -> str:
    """Return a stable ISO timestamp for persisted records."""
    return datetime.utcnow().replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    """Create a short unique id with a business-object prefix."""
    return f"{prefix}_{uuid4().hex[:12]}"


def _validate_status(kind: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(f"Invalid {kind}.status={value!r}; expected one of: {allowed_text}")


@dataclass
class Material:
    id: str
    source: str
    title: str
    excerpt: str = ""
    content: str = ""
    url: str = ""
    hot_score: float = 0.0
    tags: list[str] = field(default_factory=list)
    captured_at: str = field(default_factory=utc_now_iso)
    status: str = "inbox"

    def __post_init__(self) -> None:
        _validate_status("Material", self.status, MATERIAL_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Material":
        return cls(**data)


@dataclass
class TopicCard:
    id: str
    title: str
    source_material_ids: list[str] = field(default_factory=list)
    genre: str = ""
    platform: str = "zhihu"
    hook: str = ""
    angle: str = ""
    risk_notes: str = ""
    target_reader: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    status: str = "draft"

    def __post_init__(self) -> None:
        _validate_status("TopicCard", self.status, TOPIC_CARD_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TopicCard":
        return cls(**data)


@dataclass
class StoryTask:
    id: str
    topic_card_id: str
    topic: str
    genre: str
    platform: str = "zhihu"
    chapters: int = 1
    mode: str = "full"
    priority: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    started_at: str = ""
    finished_at: str = ""
    status: str = "queued"
    error: str = ""
    failed_stage: str = ""
    retry_count: int = 0
    run_id: str = ""

    def __post_init__(self) -> None:
        _validate_status("StoryTask", self.status, TASK_STATUSES)
        if self.chapters < 1:
            raise ValueError("StoryTask.chapters must be >= 1")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StoryTask":
        return cls(**data)


@dataclass
class ReviewDraft:
    id: str
    task_id: str
    story_path: str
    original_body: str
    title: str
    synopsis: str = ""
    tags: list[str] = field(default_factory=list)
    body: str = ""
    review_result: dict = field(default_factory=dict)
    editor_notes: str = ""
    updated_at: str = field(default_factory=utc_now_iso)
    status: str = "needs_edit"

    def __post_init__(self) -> None:
        _validate_status("ReviewDraft", self.status, DRAFT_STATUSES)
        if not self.body:
            self.body = self.original_body

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewDraft":
        return cls(**data)


@dataclass
class PublishPackage:
    id: str
    task_id: str
    platform: str
    title: str
    synopsis: str
    tags: list[str]
    content_path: str
    metadata_path: str
    package_dir: str
    created_at: str = field(default_factory=utc_now_iso)
    status: str = "generated"

    def __post_init__(self) -> None:
        _validate_status("PublishPackage", self.status, PACKAGE_STATUSES)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PublishPackage":
        return cls(**data)
```

- [ ] **Step 5: Run model tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_models.py -v
```

Expected:

```text
7 passed
```

- [ ] **Step 6: Commit models**

Run:

```bash
git add zhihu_fiction/workspace/__init__.py zhihu_fiction/workspace/models.py zhihu_fiction/tests/test_workspace_models.py
git commit -m "feat: add workspace domain models"
```

---

## Task 2: Add File-Backed Repositories

**Files:**
- Create: `zhihu_fiction/workspace/repositories.py`
- Create: `zhihu_fiction/tests/test_workspace_repositories.py`

- [ ] **Step 1: Write repository tests**

Create `zhihu_fiction/tests/test_workspace_repositories.py`:

```python
"""Tests for workspace file repositories."""
from __future__ import annotations

import json

from zhihu_fiction.workspace.models import Material, ReviewDraft, StoryTask, TopicCard
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def test_save_and_list_materials(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    material = Material(id="mat_1", source="manual", title="标题")

    repo.save_material(material)

    assert repo.list_materials() == [material]
    assert repo.get_material("mat_1") == material


def test_update_material_replaces_record(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_material(Material(id="mat_1", source="manual", title="旧标题"))

    updated = repo.update_material("mat_1", {"title": "新标题", "status": "selected"})

    assert updated.title == "新标题"
    assert updated.status == "selected"
    assert repo.list_materials()[0].title == "新标题"


def test_corrupted_jsonl_line_is_skipped(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_material(Material(id="mat_1", source="manual", title="标题"))
    with (tmp_path / "materials.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{bad json\n")

    assert repo.list_materials() == [Material(id="mat_1", source="manual", title="标题")]


def test_topic_card_and_task_round_trip(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    card = TopicCard(id="card_1", title="选题", source_material_ids=["mat_1"])
    task = StoryTask(
        id="task_1",
        topic_card_id="card_1",
        topic="选题",
        genre="悬疑",
        created_at="2026-06-08T12:00:00",
    )

    repo.save_topic_card(card)
    repo.save_task(task)

    assert repo.get_topic_card("card_1") == card
    assert repo.get_task("task_1") == task


def test_save_and_load_review_draft(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    draft = ReviewDraft(
        id="draft_1",
        task_id="task_1",
        story_path="output/story.md",
        original_body="原文",
        title="标题",
    )

    repo.save_review_draft(draft)

    assert repo.get_review_draft("task_1") == draft
    stored = json.loads((tmp_path / "drafts" / "task_1.json").read_text(encoding="utf-8"))
    assert stored["original_body"] == "原文"


def test_list_queued_tasks_sorts_by_priority_then_created_at(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_task(StoryTask(
        id="task_low",
        topic_card_id="card_1",
        topic="低优先",
        genre="悬疑",
        priority=0,
        created_at="2026-06-08T12:00:01",
    ))
    repo.save_task(StoryTask(
        id="task_high",
        topic_card_id="card_2",
        topic="高优先",
        genre="悬疑",
        priority=10,
        created_at="2026-06-08T12:00:02",
    ))

    queued = repo.list_queued_tasks()

    assert [task.id for task in queued] == ["task_high", "task_low"]
```

- [ ] **Step 2: Run repository tests to verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_repositories.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'zhihu_fiction.workspace.repositories'
```

- [ ] **Step 3: Implement repositories**

Create `zhihu_fiction/workspace/repositories.py`:

```python
"""File-backed repositories for workspace business objects."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Callable, Generic, TypeVar

from zhihu_fiction.config import APP_ROOT

from .models import Material, PublishPackage, ReviewDraft, StoryTask, TopicCard

WORKSPACE_DIR = APP_ROOT / "data" / "workspace"

T = TypeVar("T")


class JsonlStore(Generic[T]):
    """Small JSONL table with rewrite-on-update semantics."""

    def __init__(self, path: Path, loader: Callable[[dict], T]) -> None:
        self.path = path
        self.loader = loader
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[T]:
        if not self.path.exists():
            return []
        records: list[T] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(self.loader(json.loads(line)))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return records

    def append(self, record: T) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def replace_all(self, records: list[T]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = "".join(json.dumps(record.to_dict(), ensure_ascii=False) + "\n" for record in records)
        self.path.write_text(content, encoding="utf-8")

    def get(self, record_id: str) -> T | None:
        for record in self.list():
            if getattr(record, "id") == record_id:
                return record
        return None

    def save(self, record: T) -> None:
        records = self.list()
        for idx, existing in enumerate(records):
            if getattr(existing, "id") == getattr(record, "id"):
                records[idx] = record
                self.replace_all(records)
                return
        self.append(record)

    def update(self, record_id: str, changes: dict) -> T:
        records = self.list()
        for idx, existing in enumerate(records):
            if getattr(existing, "id") == record_id:
                updated = replace(existing, **changes)
                records[idx] = updated
                self.replace_all(records)
                return updated
        raise KeyError(record_id)


class WorkspaceRepository:
    """File-backed repository for workspace records."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else WORKSPACE_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        self.materials = JsonlStore(self.root / "materials.jsonl", Material.from_dict)
        self.topic_cards = JsonlStore(self.root / "topic_cards.jsonl", TopicCard.from_dict)
        self.tasks = JsonlStore(self.root / "tasks.jsonl", StoryTask.from_dict)
        self.packages = JsonlStore(self.root / "packages.jsonl", PublishPackage.from_dict)
        (self.root / "drafts").mkdir(parents=True, exist_ok=True)
        (self.root / "reviews").mkdir(parents=True, exist_ok=True)
        (self.root / "publish_packages").mkdir(parents=True, exist_ok=True)

    def save_material(self, material: Material) -> None:
        self.materials.save(material)

    def list_materials(self) -> list[Material]:
        return self.materials.list()

    def get_material(self, material_id: str) -> Material | None:
        return self.materials.get(material_id)

    def update_material(self, material_id: str, changes: dict) -> Material:
        return self.materials.update(material_id, changes)

    def save_topic_card(self, card: TopicCard) -> None:
        self.topic_cards.save(card)

    def list_topic_cards(self) -> list[TopicCard]:
        return self.topic_cards.list()

    def get_topic_card(self, card_id: str) -> TopicCard | None:
        return self.topic_cards.get(card_id)

    def update_topic_card(self, card_id: str, changes: dict) -> TopicCard:
        return self.topic_cards.update(card_id, changes)

    def save_task(self, task: StoryTask) -> None:
        self.tasks.save(task)

    def list_tasks(self) -> list[StoryTask]:
        return self.tasks.list()

    def get_task(self, task_id: str) -> StoryTask | None:
        return self.tasks.get(task_id)

    def update_task(self, task_id: str, changes: dict) -> StoryTask:
        return self.tasks.update(task_id, changes)

    def list_queued_tasks(self) -> list[StoryTask]:
        queued = [task for task in self.list_tasks() if task.status == "queued"]
        return sorted(queued, key=lambda task: (-task.priority, task.created_at, task.id))

    def list_running_tasks(self) -> list[StoryTask]:
        return [task for task in self.list_tasks() if task.status == "running"]

    def save_review_draft(self, draft: ReviewDraft) -> None:
        path = self.root / "drafts" / f"{draft.task_id}.json"
        path.write_text(json.dumps(draft.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def get_review_draft(self, task_id: str) -> ReviewDraft | None:
        path = self.root / "drafts" / f"{task_id}.json"
        if not path.exists():
            return None
        try:
            return ReviewDraft.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def list_review_drafts(self) -> list[ReviewDraft]:
        drafts: list[ReviewDraft] = []
        for path in sorted((self.root / "drafts").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                drafts.append(ReviewDraft.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return drafts

    def save_publish_package(self, package: PublishPackage) -> None:
        self.packages.save(package)

    def list_publish_packages(self) -> list[PublishPackage]:
        return self.packages.list()

    def get_publish_package(self, package_id: str) -> PublishPackage | None:
        return self.packages.get(package_id)

    def update_publish_package(self, package_id: str, changes: dict) -> PublishPackage:
        return self.packages.update(package_id, changes)
```

- [ ] **Step 4: Run repository tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_repositories.py -v
```

Expected:

```text
6 passed
```

- [ ] **Step 5: Commit repositories**

Run:

```bash
git add zhihu_fiction/workspace/repositories.py zhihu_fiction/tests/test_workspace_repositories.py
git commit -m "feat: add workspace file repositories"
```

---

## Task 3: Add Workspace Services

**Files:**
- Create: `zhihu_fiction/workspace/services.py`
- Create: `zhihu_fiction/tests/test_workspace_services.py`

- [ ] **Step 1: Write service tests**

Create `zhihu_fiction/tests/test_workspace_services.py`:

```python
"""Tests for workspace services."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from zhihu_fiction.orchestrator import WorkflowResult
from zhihu_fiction.workspace.models import StoryTask
from zhihu_fiction.workspace.repositories import WorkspaceRepository
from zhihu_fiction.workspace.services import WorkspaceService


def _service(tmp_path: Path) -> WorkspaceService:
    return WorkspaceService(WorkspaceRepository(tmp_path))


def test_import_scraped_items_creates_materials(tmp_path):
    service = _service(tmp_path)

    result = service.import_scraped_items([
        {"title": "热榜1", "excerpt": "摘要", "hot_score": 123, "url": "https://example.test/1"},
        {"title": "", "excerpt": "没有标题"},
    ])

    assert result["imported"] == 1
    assert len(result["failed"]) == 1
    assert service.repo.list_materials()[0].title == "热榜1"


def test_create_topic_card_marks_materials_selected(tmp_path):
    service = _service(tmp_path)
    material = service.create_manual_material(title="素材", content="正文", tags=["悬疑"])

    card = service.create_topic_card(
        title="选题卡",
        source_material_ids=[material.id],
        genre="悬疑",
        platform="zhihu",
        hook="强钩子",
        angle="反转视角",
        risk_notes="降低血腥",
        target_reader="知乎读者",
    )

    assert card.source_material_ids == [material.id]
    assert service.repo.get_material(material.id).status == "selected"


def test_approve_card_and_create_task(tmp_path):
    service = _service(tmp_path)
    card = service.create_topic_card(title="选题卡", genre="悬疑", platform="zhihu")

    approved = service.approve_topic_card(card.id)
    task = service.create_task_from_topic_card(approved.id, chapters=3, mode="full", priority=5)

    assert approved.status == "approved"
    assert task.status == "queued"
    assert task.topic == "选题卡"
    assert task.chapters == 3
    assert task.priority == 5


def test_create_task_requires_approved_card(tmp_path):
    service = _service(tmp_path)
    card = service.create_topic_card(title="选题卡")

    try:
        service.create_task_from_topic_card(card.id)
    except ValueError as exc:
        assert "must be approved" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_create_review_draft_from_completed_task(tmp_path):
    service = _service(tmp_path)
    task = StoryTask(
        id="task_1",
        topic_card_id="card_1",
        topic="任务标题",
        genre="悬疑",
        created_at="2026-06-08T12:00:00",
        status="needs_review",
    )
    service.repo.save_task(task)

    draft = service.create_review_draft_from_result(
        task,
        story_path="output/story.md",
        body="# 任务标题\n\n正文",
        review_result={"score": 7.5},
    )

    assert draft.task_id == task.id
    assert draft.title == "任务标题"
    assert draft.original_body == "# 任务标题\n\n正文"


def test_update_draft_and_mark_ready_updates_task(tmp_path):
    service = _service(tmp_path)
    service.repo.save_task(StoryTask(
        id="task_1",
        topic_card_id="card_1",
        topic="标题",
        genre="悬疑",
        created_at="2026-06-08T12:00:00",
        status="needs_review",
    ))
    service.create_review_draft_from_result(
        service.repo.get_task("task_1"),
        story_path="output/story.md",
        body="正文",
        review_result={},
    )

    draft = service.update_review_draft("task_1", {"title": "新标题", "tags": ["悬疑"]})
    ready = service.mark_draft_ready("task_1")

    assert draft.title == "新标题"
    assert ready.status == "ready_for_package"
    assert service.repo.get_task("task_1").status == "approved"


def test_generate_publish_package_uses_exporter(tmp_path):
    service = _service(tmp_path)
    service.repo.save_task(StoryTask(
        id="task_1",
        topic_card_id="card_1",
        topic="标题",
        genre="悬疑",
        created_at="2026-06-08T12:00:00",
        status="approved",
    ))
    service.create_review_draft_from_result(
        service.repo.get_task("task_1"),
        story_path="output/story.md",
        body="正文",
        review_result={},
    )
    service.mark_draft_ready("task_1")
    exporter = MagicMock()
    exporter.export.return_value = {"zhihu": str(tmp_path / "zhihu_pkg")}

    package = service.generate_publish_package("task_1", "zhihu", exporter)

    assert package.platform == "zhihu"
    assert package.status == "generated"
    assert package.package_dir.endswith("zhihu_pkg")
    exporter.export.assert_called_once()
```

- [ ] **Step 2: Run service tests to verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_services.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'zhihu_fiction.workspace.services'
```

- [ ] **Step 3: Implement workspace services**

Create `zhihu_fiction/workspace/services.py`:

```python
"""Business services for the workspace flow."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from zhihu_fiction.orchestrator import WorkflowResult

from .models import Material, PublishPackage, ReviewDraft, StoryTask, TopicCard, new_id, utc_now_iso
from .repositories import WorkspaceRepository


class WorkspaceService:
    """High-level operations for materials, topic cards, tasks, drafts, and packages."""

    def __init__(self, repo: WorkspaceRepository) -> None:
        self.repo = repo

    def import_scraped_items(self, items: list[dict], source: str = "scraped") -> dict:
        imported: list[Material] = []
        failed: list[dict] = []
        for index, item in enumerate(items):
            title = str(item.get("title", "")).strip()
            if not title:
                failed.append({"index": index, "reason": "missing title"})
                continue
            material = Material(
                id=new_id("mat"),
                source=item.get("source", source) or source,
                title=title,
                excerpt=str(item.get("excerpt", "")),
                content=str(item.get("content", "")),
                url=str(item.get("url", "")),
                hot_score=float(item.get("hot_score", item.get("votes", 0)) or 0),
                tags=list(item.get("tags", [])),
                captured_at=str(item.get("scraped_at", "")) or utc_now_iso(),
            )
            self.repo.save_material(material)
            imported.append(material)
        return {"imported": len(imported), "failed": failed, "items": [m.to_dict() for m in imported]}

    def create_manual_material(
        self,
        title: str,
        content: str = "",
        excerpt: str = "",
        tags: list[str] | None = None,
        url: str = "",
        hot_score: float = 0.0,
    ) -> Material:
        if not title.strip():
            raise ValueError("Material title is required")
        material = Material(
            id=new_id("mat"),
            source="manual",
            title=title.strip(),
            excerpt=excerpt.strip(),
            content=content.strip(),
            url=url.strip(),
            hot_score=hot_score,
            tags=tags or [],
        )
        self.repo.save_material(material)
        return material

    def create_topic_card(
        self,
        title: str,
        source_material_ids: list[str] | None = None,
        genre: str = "",
        platform: str = "zhihu",
        hook: str = "",
        angle: str = "",
        risk_notes: str = "",
        target_reader: str = "",
    ) -> TopicCard:
        if not title.strip():
            raise ValueError("Topic card title is required")
        source_ids = source_material_ids or []
        for material_id in source_ids:
            if self.repo.get_material(material_id) is None:
                raise KeyError(material_id)
        card = TopicCard(
            id=new_id("card"),
            title=title.strip(),
            source_material_ids=source_ids,
            genre=genre.strip(),
            platform=platform.strip() or "zhihu",
            hook=hook.strip(),
            angle=angle.strip(),
            risk_notes=risk_notes.strip(),
            target_reader=target_reader.strip(),
        )
        self.repo.save_topic_card(card)
        for material_id in source_ids:
            self.repo.update_material(material_id, {"status": "selected"})
        return card

    def approve_topic_card(self, card_id: str) -> TopicCard:
        card = self.repo.get_topic_card(card_id)
        if card is None:
            raise KeyError(card_id)
        if card.status == "archived":
            raise ValueError("Archived topic cards cannot be approved")
        return self.repo.update_topic_card(card_id, {"status": "approved"})

    def create_task_from_topic_card(
        self,
        card_id: str,
        chapters: int = 1,
        mode: str = "full",
        priority: int = 0,
    ) -> StoryTask:
        card = self.repo.get_topic_card(card_id)
        if card is None:
            raise KeyError(card_id)
        if card.status != "approved":
            raise ValueError("Topic card must be approved before creating a task")
        task = StoryTask(
            id=new_id("task"),
            topic_card_id=card.id,
            topic=card.title,
            genre=card.genre or "未指定",
            platform=card.platform or "zhihu",
            chapters=chapters,
            mode=mode,
            priority=priority,
        )
        self.repo.save_task(task)
        return task

    def create_review_draft_from_result(
        self,
        task: StoryTask,
        story_path: str,
        body: str,
        review_result: dict,
    ) -> ReviewDraft:
        draft = ReviewDraft(
            id=new_id("draft"),
            task_id=task.id,
            story_path=story_path,
            original_body=body,
            title=task.topic,
            synopsis=body[:200],
            tags=[task.genre] if task.genre else [],
            body=body,
            review_result=review_result,
        )
        self.repo.save_review_draft(draft)
        return draft

    def update_review_draft(self, task_id: str, changes: dict) -> ReviewDraft:
        draft = self.repo.get_review_draft(task_id)
        if draft is None:
            raise KeyError(task_id)
        allowed = {"title", "synopsis", "tags", "body", "editor_notes", "status"}
        clean_changes = {key: value for key, value in changes.items() if key in allowed}
        clean_changes["updated_at"] = utc_now_iso()
        updated = replace(draft, **clean_changes)
        self.repo.save_review_draft(updated)
        return updated

    def mark_draft_ready(self, task_id: str) -> ReviewDraft:
        task = self.repo.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        updated = self.update_review_draft(task_id, {"status": "ready_for_package"})
        self.repo.update_task(task_id, {"status": "approved", "finished_at": task.finished_at or utc_now_iso()})
        return updated

    def generate_publish_package(self, task_id: str, platform: str, exporter: Any) -> PublishPackage:
        task = self.repo.get_task(task_id)
        draft = self.repo.get_review_draft(task_id)
        if task is None or draft is None:
            raise KeyError(task_id)
        if draft.status != "ready_for_package":
            raise ValueError("Review draft must be ready_for_package before package generation")

        result = WorkflowResult(
            topic=draft.title,
            genre=task.genre,
            topic_analysis="",
            outline="",
            draft=draft.original_body,
            polished=draft.body,
            review=str(draft.review_result),
            synthesis=draft.synopsis,
        )
        try:
            output_dirs = exporter.export(result, platforms=[platform])
            package_dir = output_dirs.get(platform, "")
        except Exception:
            package_dir = self._write_fallback_package(task, draft, platform)

        package_path = Path(package_dir)
        package = PublishPackage(
            id=new_id("pkg"),
            task_id=task.id,
            platform=platform,
            title=draft.title,
            synopsis=draft.synopsis,
            tags=draft.tags,
            content_path=str(package_path / "发布内容.md") if package_dir else "",
            metadata_path=str(package_path / "元数据.md") if package_dir else "",
            package_dir=package_dir,
        )
        self.repo.save_publish_package(package)
        return package

    def confirm_package(self, package_id: str) -> PublishPackage:
        package = self.repo.get_publish_package(package_id)
        if package is None:
            raise KeyError(package_id)
        return self.repo.update_publish_package(package_id, {"status": "confirmed"})

    def _write_fallback_package(self, task: StoryTask, draft: ReviewDraft, platform: str) -> str:
        package_id = new_id("fallback_pkg")
        package_dir = self.repo.root / "publish_packages" / package_id
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "发布内容.md").write_text(draft.body, encoding="utf-8")
        metadata = "\n".join([
            f"# {draft.title}",
            "",
            f"平台：{platform}",
            f"题材：{task.genre}",
            f"标签：{', '.join(draft.tags)}",
            "",
            draft.synopsis or draft.body[:200],
        ])
        (package_dir / "元数据.md").write_text(metadata, encoding="utf-8")
        return str(package_dir)
```

- [ ] **Step 4: Run service tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_services.py -v
```

Expected:

```text
7 passed
```

- [ ] **Step 5: Commit services**

Run:

```bash
git add zhihu_fiction/workspace/services.py zhihu_fiction/tests/test_workspace_services.py
git commit -m "feat: add workspace business services"
```

---

## Task 4: Add Single-Worker Workspace Queue

**Files:**
- Create: `zhihu_fiction/workspace/queue.py`
- Create: `zhihu_fiction/tests/test_workspace_queue.py`

- [ ] **Step 1: Write queue tests**

Create `zhihu_fiction/tests/test_workspace_queue.py`:

```python
"""Tests for workspace task queue."""
from __future__ import annotations

from dataclasses import dataclass

from zhihu_fiction.workspace.models import StoryTask
from zhihu_fiction.workspace.repositories import WorkspaceRepository
from zhihu_fiction.workspace.services import WorkspaceService
from zhihu_fiction.workspace.queue import WorkspaceQueue


@dataclass
class FakeStage:
    status: str = "ok"
    duration_s: float = 0.1
    extra: dict | None = None


@dataclass
class FakeResult:
    run_id: str
    topic: str
    genre: str
    published_url: str
    stages: dict
    error: str = ""


class FakePipeline:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def run(self, topic=None, genre=None, chapters=1, stream_callback=None, on_progress=None):
        self.calls.append({"topic": topic, "genre": genre, "chapters": chapters})
        if self.fail:
            raise RuntimeError("pipeline failed")
        return FakeResult(
            run_id="run_1",
            topic=topic,
            genre=genre,
            published_url="output/story.md",
            stages={"review": FakeStage(extra={"score": 7.5})},
        )


def _task(task_id: str, priority: int = 0) -> StoryTask:
    return StoryTask(
        id=task_id,
        topic_card_id="card_1",
        topic=f"主题 {task_id}",
        genre="悬疑",
        priority=priority,
        created_at=f"2026-06-08T12:00:0{priority}",
    )


def test_run_next_processes_one_queued_task(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    repo.save_task(_task("task_1"))
    pipeline = FakePipeline()
    queue = WorkspaceQueue(repo, service, pipeline_factory=lambda: pipeline)

    processed = queue.run_next()

    assert processed is True
    assert repo.get_task("task_1").status == "needs_review"
    assert repo.get_task("task_1").run_id == "run_1"
    assert repo.get_review_draft("task_1").review_result["score"] == 7.5
    assert pipeline.calls == [{"topic": "主题 task_1", "genre": "悬疑", "chapters": 1}]


def test_run_next_returns_false_when_no_queued_task(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    queue = WorkspaceQueue(repo, WorkspaceService(repo), pipeline_factory=lambda: FakePipeline())

    assert queue.run_next() is False


def test_kick_starts_background_worker_until_idle(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    repo.save_task(_task("task_1"))
    repo.save_task(_task("task_2"))
    queue = WorkspaceQueue(repo, service, pipeline_factory=lambda: FakePipeline())

    started = queue.kick()
    queue.wait_until_idle(timeout_s=2)

    assert started is True
    assert repo.get_task("task_1").status == "needs_review"
    assert repo.get_task("task_2").status == "needs_review"


def test_failed_pipeline_marks_task_failed(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    repo.save_task(_task("task_1"))
    queue = WorkspaceQueue(repo, service, pipeline_factory=lambda: FakePipeline(fail=True))

    processed = queue.run_next()

    assert processed is True
    task = repo.get_task("task_1")
    assert task.status == "failed"
    assert "pipeline failed" in task.error


def test_retry_failed_task_returns_to_queued(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    repo.save_task(StoryTask(
        id="task_1",
        topic_card_id="card_1",
        topic="主题",
        genre="悬疑",
        created_at="2026-06-08T12:00:00",
        status="failed",
        retry_count=1,
    ))
    queue = WorkspaceQueue(repo, service, pipeline_factory=lambda: FakePipeline())

    task = queue.retry("task_1")

    assert task.status == "queued"
    assert task.retry_count == 2
    assert task.error == ""


def test_cancel_only_cancels_queued_task(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    repo.save_task(_task("task_1"))
    queue = WorkspaceQueue(repo, service, pipeline_factory=lambda: FakePipeline())

    task = queue.cancel("task_1")

    assert task.status == "canceled"


def test_startup_repair_marks_running_failed(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    repo.save_task(StoryTask(
        id="task_1",
        topic_card_id="card_1",
        topic="主题",
        genre="悬疑",
        created_at="2026-06-08T12:00:00",
        status="running",
    ))
    queue = WorkspaceQueue(repo, service, pipeline_factory=lambda: FakePipeline())

    repaired = queue.repair_stale_running()

    assert repaired == 1
    assert repo.get_task("task_1").status == "failed"
    assert "server restarted" in repo.get_task("task_1").error
```

- [ ] **Step 2: Run queue tests to verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_queue.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'zhihu_fiction.workspace.queue'
```

- [ ] **Step 3: Implement queue**

Create `zhihu_fiction/workspace/queue.py`:

```python
"""Single-worker queue for workspace story tasks."""
from __future__ import annotations

import threading
import time
from typing import Callable

from .models import StoryTask, utc_now_iso
from .repositories import WorkspaceRepository
from .services import WorkspaceService


class WorkspaceQueue:
    """Runs at most one workspace story task at a time."""

    def __init__(
        self,
        repo: WorkspaceRepository,
        service: WorkspaceService,
        pipeline_factory: Callable,
    ) -> None:
        self.repo = repo
        self.service = service
        self.pipeline_factory = pipeline_factory
        self._lock = threading.Lock()
        self._worker_lock = threading.Lock()
        self._worker_thread: threading.Thread | None = None

    def repair_stale_running(self) -> int:
        repaired = 0
        for task in self.repo.list_running_tasks():
            self.repo.update_task(task.id, {
                "status": "failed",
                "error": "Task marked failed because server restarted while it was running.",
                "failed_stage": "startup_repair",
                "finished_at": utc_now_iso(),
            })
            repaired += 1
        return repaired

    def run_next(self) -> bool:
        with self._lock:
            if self.repo.list_running_tasks():
                return False
            queued = self.repo.list_queued_tasks()
            if not queued:
                return False
            task = queued[0]
            task = self.repo.update_task(task.id, {
                "status": "running",
                "started_at": utc_now_iso(),
                "error": "",
                "failed_stage": "",
            })

        self._run_claimed_task(task)
        return True

    def run_until_idle(self) -> int:
        processed = 0
        while self.run_next():
            processed += 1
        return processed

    def kick(self) -> bool:
        """Start a background drain worker if one is not already active."""
        with self._worker_lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return False
            self._worker_thread = threading.Thread(target=self.run_until_idle, daemon=True)
            self._worker_thread.start()
            return True

    def wait_until_idle(self, timeout_s: float = 5.0) -> bool:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            thread = self._worker_thread
            if thread is None or not thread.is_alive():
                return True
            time.sleep(0.01)
        return False

    def retry(self, task_id: str) -> StoryTask:
        task = self.repo.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status != "failed":
            raise ValueError("Only failed tasks can be retried")
        return self.repo.update_task(task_id, {
            "status": "queued",
            "retry_count": task.retry_count + 1,
            "error": "",
            "failed_stage": "",
            "started_at": "",
            "finished_at": "",
        })

    def cancel(self, task_id: str) -> StoryTask:
        task = self.repo.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status != "queued":
            raise ValueError("Only queued tasks can be canceled in the first workspace version")
        return self.repo.update_task(task_id, {"status": "canceled", "finished_at": utc_now_iso()})

    def _run_claimed_task(self, task: StoryTask) -> None:
        try:
            pipeline = self.pipeline_factory()
            result = pipeline.run(topic=task.topic, genre=task.genre, chapters=task.chapters)
            review_stage = result.stages.get("review")
            review_result = {}
            if review_stage is not None:
                review_result = review_stage.extra or {}
            body = self._read_story_body(result.published_url)
            self.service.create_review_draft_from_result(
                task=task,
                story_path=result.published_url,
                body=body,
                review_result=review_result,
            )
            self.repo.update_task(task.id, {
                "status": "needs_review",
                "run_id": result.run_id,
                "finished_at": utc_now_iso(),
            })
        except Exception as exc:
            self.repo.update_task(task.id, {
                "status": "failed",
                "error": str(exc),
                "failed_stage": "pipeline",
                "finished_at": utc_now_iso(),
            })

    def _read_story_body(self, story_path: str) -> str:
        from pathlib import Path

        if story_path:
            path = Path(story_path)
            if path.exists() and path.is_file():
                return path.read_text(encoding="utf-8")
        return ""
```

- [ ] **Step 4: Run queue tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_queue.py -v
```

Expected:

```text
7 passed
```

- [ ] **Step 5: Commit queue**

Run:

```bash
git add zhihu_fiction/workspace/queue.py zhihu_fiction/tests/test_workspace_queue.py
git commit -m "feat: add workspace task queue"
```

---

## Task 5: Add Workspace API Routes

**Files:**
- Create: `zhihu_fiction/workspace/schemas.py`
- Create: `zhihu_fiction/workspace_routes.py`
- Create: `zhihu_fiction/tests/test_workspace_api.py`
- Modify: `zhihu_fiction/server.py`

- [ ] **Step 1: Write API tests**

Create `zhihu_fiction/tests/test_workspace_api.py`:

```python
"""API tests for workspace routes."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from zhihu_fiction.workspace.repositories import WorkspaceRepository
from zhihu_fiction.workspace.services import WorkspaceService
from zhihu_fiction.workspace.queue import WorkspaceQueue
from zhihu_fiction.workspace_routes import create_workspace_router


class FakeExporter:
    def __init__(self, package_dir: str) -> None:
        self.package_dir = package_dir

    def export(self, result, platforms=None):
        return {platforms[0]: self.package_dir}


class FakeQueue:
    def __init__(self, service):
        self.service = service
        self.kick_count = 0

    def kick(self):
        self.kick_count += 1
        return True

    def retry(self, task_id):
        task = self.service.repo.update_task(task_id, {"status": "queued", "retry_count": 1})
        return task

    def cancel(self, task_id):
        return self.service.repo.update_task(task_id, {"status": "canceled"})


def _client(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    queue = FakeQueue(service)
    exporter_factory = lambda: FakeExporter(str(tmp_path / "pkg"))
    app = FastAPI()
    app.include_router(create_workspace_router(service, queue, exporter_factory))
    return TestClient(app), service, queue


def test_material_manual_endpoint(tmp_path):
    client, _service, _queue = _client(tmp_path)

    response = client.post("/api/workspace/materials/manual", json={
        "title": "素材",
        "content": "正文",
        "tags": ["悬疑"],
    })

    assert response.status_code == 200
    assert response.json()["title"] == "素材"


def test_topic_card_to_task_flow(tmp_path):
    client, _service, queue = _client(tmp_path)
    material = client.post("/api/workspace/materials/manual", json={"title": "素材"}).json()
    card = client.post("/api/workspace/topic-cards", json={
        "title": "选题卡",
        "source_material_ids": [material["id"]],
        "genre": "悬疑",
        "platform": "zhihu",
    }).json()

    approved = client.post(f"/api/workspace/topic-cards/{card['id']}/approve")
    task = client.post(f"/api/workspace/topic-cards/{card['id']}/create-task", json={
        "chapters": 2,
        "mode": "full",
        "priority": 3,
    })

    assert approved.status_code == 200
    assert task.status_code == 200
    assert task.json()["status"] == "queued"
    assert task.json()["chapters"] == 2
    assert queue.kick_count == 1


def test_create_task_from_unapproved_card_returns_409(tmp_path):
    client, _service, _queue = _client(tmp_path)
    card = client.post("/api/workspace/topic-cards", json={"title": "选题卡"}).json()

    response = client.post(f"/api/workspace/topic-cards/{card['id']}/create-task", json={})

    assert response.status_code == 409


def test_draft_update_ready_and_package_generation(tmp_path):
    client, service, _queue = _client(tmp_path)
    card = service.create_topic_card(title="选题卡")
    card = service.approve_topic_card(card.id)
    task = service.create_task_from_topic_card(card.id)
    service.repo.update_task(task.id, {"status": "needs_review"})
    service.create_review_draft_from_result(
        service.repo.get_task(task.id),
        story_path="output/story.md",
        body="正文",
        review_result={"score": 8},
    )

    updated = client.patch(f"/api/workspace/drafts/{task.id}", json={
        "title": "新标题",
        "synopsis": "新简介",
        "tags": ["悬疑"],
        "body": "编辑正文",
    })
    ready = client.post(f"/api/workspace/drafts/{task.id}/ready")
    package = client.post("/api/workspace/packages/generate", json={
        "task_id": task.id,
        "platform": "zhihu",
    })

    assert updated.status_code == 200
    assert ready.status_code == 200
    assert package.status_code == 200
    assert package.json()["platform"] == "zhihu"
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_api.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'zhihu_fiction.workspace_routes'
```

- [ ] **Step 3: Implement request schemas**

Create `zhihu_fiction/workspace/schemas.py`:

```python
"""FastAPI schemas for workspace routes."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ManualMaterialRequest(BaseModel):
    title: str
    content: str = ""
    excerpt: str = ""
    tags: list[str] = Field(default_factory=list)
    url: str = ""
    hot_score: float = 0.0


class ImportScrapedRequest(BaseModel):
    items: list[dict]


class TopicCardRequest(BaseModel):
    title: str
    source_material_ids: list[str] = Field(default_factory=list)
    genre: str = ""
    platform: str = "zhihu"
    hook: str = ""
    angle: str = ""
    risk_notes: str = ""
    target_reader: str = ""


class CreateTaskRequest(BaseModel):
    chapters: int = Field(default=1, ge=1)
    mode: str = "full"
    priority: int = 0


class DraftUpdateRequest(BaseModel):
    title: str | None = None
    synopsis: str | None = None
    tags: list[str] | None = None
    body: str | None = None
    editor_notes: str | None = None


class GeneratePackageRequest(BaseModel):
    task_id: str
    platform: str = "zhihu"
```

- [ ] **Step 4: Implement workspace router**

Create `zhihu_fiction/workspace_routes.py`:

```python
"""FastAPI routes for workspace business modules."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException

from .workspace.queue import WorkspaceQueue
from .workspace.schemas import (
    CreateTaskRequest,
    DraftUpdateRequest,
    GeneratePackageRequest,
    ImportScrapedRequest,
    ManualMaterialRequest,
    TopicCardRequest,
)
from .workspace.services import WorkspaceService


def _not_found(name: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{name} not found")


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=409, detail=message)


def _model_dump(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def create_workspace_router(
    service: WorkspaceService,
    queue: WorkspaceQueue,
    exporter_factory: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/api/workspace", tags=["workspace"])

    @router.get("/materials")
    async def list_materials():
        return [material.to_dict() for material in service.repo.list_materials()]

    @router.post("/materials/import-scraped")
    async def import_scraped(req: ImportScrapedRequest):
        return service.import_scraped_items(req.items)

    @router.post("/materials/manual")
    async def create_manual_material(req: ManualMaterialRequest):
        try:
            material = service.create_manual_material(
                title=req.title,
                content=req.content,
                excerpt=req.excerpt,
                tags=req.tags,
                url=req.url,
                hot_score=req.hot_score,
            )
            return material.to_dict()
        except ValueError as exc:
            raise _conflict(str(exc)) from exc

    @router.patch("/materials/{material_id}")
    async def update_material(material_id: str, changes: dict):
        try:
            return service.repo.update_material(material_id, changes).to_dict()
        except KeyError as exc:
            raise _not_found("material") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc

    @router.get("/topic-cards")
    async def list_topic_cards():
        return [card.to_dict() for card in service.repo.list_topic_cards()]

    @router.post("/topic-cards")
    async def create_topic_card(req: TopicCardRequest):
        try:
            return service.create_topic_card(**_model_dump(req)).to_dict()
        except KeyError as exc:
            raise _not_found("material") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc

    @router.patch("/topic-cards/{card_id}")
    async def update_topic_card(card_id: str, changes: dict):
        try:
            return service.repo.update_topic_card(card_id, changes).to_dict()
        except KeyError as exc:
            raise _not_found("topic card") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc

    @router.post("/topic-cards/{card_id}/approve")
    async def approve_topic_card(card_id: str):
        try:
            return service.approve_topic_card(card_id).to_dict()
        except KeyError as exc:
            raise _not_found("topic card") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc

    @router.post("/topic-cards/{card_id}/create-task")
    async def create_task(card_id: str, req: CreateTaskRequest):
        try:
            task = service.create_task_from_topic_card(
                card_id,
                chapters=req.chapters,
                mode=req.mode,
                priority=req.priority,
            )
            queue.kick()
            return task.to_dict()
        except KeyError as exc:
            raise _not_found("topic card") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc

    @router.get("/tasks")
    async def list_tasks():
        return [task.to_dict() for task in service.repo.list_tasks()]

    @router.post("/tasks/{task_id}/retry")
    async def retry_task(task_id: str):
        try:
            task = queue.retry(task_id)
            queue.kick()
            return task.to_dict()
        except KeyError as exc:
            raise _not_found("task") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc

    @router.post("/tasks/{task_id}/cancel")
    async def cancel_task(task_id: str):
        try:
            return queue.cancel(task_id).to_dict()
        except KeyError as exc:
            raise _not_found("task") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc

    @router.get("/drafts")
    async def list_drafts():
        return [draft.to_dict() for draft in service.repo.list_review_drafts()]

    @router.get("/drafts/{task_id}")
    async def get_draft(task_id: str):
        draft = service.repo.get_review_draft(task_id)
        if draft is None:
            raise _not_found("draft")
        return draft.to_dict()

    @router.patch("/drafts/{task_id}")
    async def update_draft(task_id: str, req: DraftUpdateRequest):
        changes = {key: value for key, value in _model_dump(req).items() if value is not None}
        try:
            return service.update_review_draft(task_id, changes).to_dict()
        except KeyError as exc:
            raise _not_found("draft") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc

    @router.post("/drafts/{task_id}/ready")
    async def mark_draft_ready(task_id: str):
        try:
            return service.mark_draft_ready(task_id).to_dict()
        except KeyError as exc:
            raise _not_found("draft") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc

    @router.get("/packages")
    async def list_packages():
        return [package.to_dict() for package in service.repo.list_publish_packages()]

    @router.post("/packages/generate")
    async def generate_package(req: GeneratePackageRequest):
        try:
            exporter = exporter_factory()
            return service.generate_publish_package(req.task_id, req.platform, exporter).to_dict()
        except KeyError as exc:
            raise _not_found("task") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc

    @router.post("/packages/{package_id}/confirm")
    async def confirm_package(package_id: str):
        try:
            return service.confirm_package(package_id).to_dict()
        except KeyError as exc:
            raise _not_found("package") from exc

    @router.get("/packages/{package_id}/files")
    async def package_files(package_id: str):
        package = service.repo.get_publish_package(package_id)
        if package is None:
            raise _not_found("package")
        return package.to_dict()

    return router
```

- [ ] **Step 5: Run API tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_api.py -v
```

Expected:

```text
4 passed
```

- [ ] **Step 6: Mount workspace routes in server**

Modify `zhihu_fiction/server.py` near existing global initialization after `skills_store = SkillsStore()`:

```python
from .exporter import Exporter
from .llm import create_llm
from .workspace.repositories import WorkspaceRepository
from .workspace.services import WorkspaceService
from .workspace.queue import WorkspaceQueue
from .workspace_routes import create_workspace_router
```

Add after `_create_pipeline()` is defined:

```python
workspace_repo = WorkspaceRepository()
workspace_service = WorkspaceService(workspace_repo)
workspace_queue = WorkspaceQueue(workspace_repo, workspace_service, pipeline_factory=_create_pipeline)
workspace_queue.repair_stale_running()


def _create_exporter() -> Exporter:
    return Exporter(create_llm(settings, temperature=0.3))


app.include_router(create_workspace_router(workspace_service, workspace_queue, _create_exporter))
```

If import placement causes circular initialization, keep the imports at the top but move object creation to after `_create_pipeline()` exactly as shown.

- [ ] **Step 7: Run API and existing server-adjacent tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_api.py zhihu_fiction/tests/test_pipeline.py -v
```

Expected:

```text
passed
```

- [ ] **Step 8: Commit API routes**

Run:

```bash
git add zhihu_fiction/workspace/schemas.py zhihu_fiction/workspace_routes.py zhihu_fiction/server.py zhihu_fiction/tests/test_workspace_api.py
git commit -m "feat: add workspace API routes"
```

---

## Task 6: Add Minimal Web Workspace Tabs

**Files:**
- Modify: `zhihu_fiction/static/index.html`

- [ ] **Step 1: Add workspace state to Alpine app**

In `zhihu_fiction/static/index.html`, inside the object returned by `app()`, add these properties after `stories: []`:

```javascript
    workspaceMaterials: [],
    workspaceCards: [],
    workspaceTasks: [],
    workspaceDrafts: [],
    workspacePackages: [],
    materialForm: { title: '', content: '', excerpt: '', tagsText: '' },
    cardForm: { title: '', source_material_ids: [], genre: '', platform: 'zhihu', hook: '', angle: '', risk_notes: '', target_reader: '' },
    selectedDraft: null,
    draftEdit: { title: '', synopsis: '', tagsText: '', body: '', editor_notes: '' },
```

- [ ] **Step 2: Add workspace load and mutation methods**

In the same Alpine object, add these methods before the closing `}`:

```javascript
    async loadWorkspace() {
      await Promise.all([
        this.loadWorkspaceMaterials(),
        this.loadWorkspaceCards(),
        this.loadWorkspaceTasks(),
        this.loadWorkspaceDrafts(),
        this.loadWorkspacePackages(),
      ]);
    },
    async loadWorkspaceMaterials() {
      try { this.workspaceMaterials = await (await fetch('/api/workspace/materials')).json(); } catch(e) {}
    },
    async loadWorkspaceCards() {
      try { this.workspaceCards = await (await fetch('/api/workspace/topic-cards')).json(); } catch(e) {}
    },
    async loadWorkspaceTasks() {
      try { this.workspaceTasks = await (await fetch('/api/workspace/tasks')).json(); } catch(e) {}
    },
    async loadWorkspaceDrafts() {
      try { this.workspaceDrafts = await (await fetch('/api/workspace/drafts')).json(); } catch(e) {}
    },
    async loadWorkspacePackages() {
      try { this.workspacePackages = await (await fetch('/api/workspace/packages')).json(); } catch(e) {}
    },
    async createWorkspaceMaterial() {
      const payload = {
        title: this.materialForm.title,
        content: this.materialForm.content,
        excerpt: this.materialForm.excerpt,
        tags: this.materialForm.tagsText.split(',').map(x => x.trim()).filter(Boolean),
      };
      await fetch('/api/workspace/materials/manual', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      this.materialForm = { title: '', content: '', excerpt: '', tagsText: '' };
      await this.loadWorkspaceMaterials();
    },
    async createWorkspaceCard() {
      const payload = {...this.cardForm};
      await fetch('/api/workspace/topic-cards', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      this.cardForm = { title: '', source_material_ids: [], genre: '', platform: 'zhihu', hook: '', angle: '', risk_notes: '', target_reader: '' };
      await Promise.all([this.loadWorkspaceCards(), this.loadWorkspaceMaterials()]);
    },
    async approveWorkspaceCard(card) {
      await fetch('/api/workspace/topic-cards/'+encodeURIComponent(card.id)+'/approve', {method:'POST'});
      await this.loadWorkspaceCards();
    },
    async createTaskFromCard(card) {
      await fetch('/api/workspace/topic-cards/'+encodeURIComponent(card.id)+'/create-task', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({chapters: 1, mode: 'full', priority: 0}),
      });
      await this.loadWorkspaceTasks();
    },
    async retryWorkspaceTask(task) {
      await fetch('/api/workspace/tasks/'+encodeURIComponent(task.id)+'/retry', {method:'POST'});
      await this.loadWorkspaceTasks();
    },
    async cancelWorkspaceTask(task) {
      await fetch('/api/workspace/tasks/'+encodeURIComponent(task.id)+'/cancel', {method:'POST'});
      await this.loadWorkspaceTasks();
    },
    openDraft(draft) {
      this.selectedDraft = draft;
      this.draftEdit = {
        title: draft.title || '',
        synopsis: draft.synopsis || '',
        tagsText: (draft.tags || []).join(', '),
        body: draft.body || '',
        editor_notes: draft.editor_notes || '',
      };
    },
    async saveDraft() {
      if (!this.selectedDraft) return;
      await fetch('/api/workspace/drafts/'+encodeURIComponent(this.selectedDraft.task_id), {
        method:'PATCH',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          title: this.draftEdit.title,
          synopsis: this.draftEdit.synopsis,
          tags: this.draftEdit.tagsText.split(',').map(x => x.trim()).filter(Boolean),
          body: this.draftEdit.body,
          editor_notes: this.draftEdit.editor_notes,
        }),
      });
      await this.loadWorkspaceDrafts();
    },
    async markDraftReady() {
      if (!this.selectedDraft) return;
      await fetch('/api/workspace/drafts/'+encodeURIComponent(this.selectedDraft.task_id)+'/ready', {method:'POST'});
      await Promise.all([this.loadWorkspaceDrafts(), this.loadWorkspaceTasks()]);
    },
    async generatePackage(taskId, platform='zhihu') {
      await fetch('/api/workspace/packages/generate', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({task_id: taskId, platform}),
      });
      await this.loadWorkspacePackages();
    },
    async confirmPackage(pkg) {
      await fetch('/api/workspace/packages/'+encodeURIComponent(pkg.id)+'/confirm', {method:'POST'});
      await this.loadWorkspacePackages();
    },
```

- [ ] **Step 3: Add workspace navigation tabs**

In the header tab list in `zhihu_fiction/static/index.html`, add these buttons after the existing `作品` button:

```html
    <button @click="tab='workspace_materials'; loadWorkspace()" :class="tab==='workspace_materials'?'tab-active':''"
      class="px-5 py-3 text-sm font-medium text-gray-500 hover:text-gray-700 transition">素材</button>
    <button @click="tab='workspace_cards'; loadWorkspace()" :class="tab==='workspace_cards'?'tab-active':''"
      class="px-5 py-3 text-sm font-medium text-gray-500 hover:text-gray-700 transition">选题卡</button>
    <button @click="tab='workspace_tasks'; loadWorkspace()" :class="tab==='workspace_tasks'?'tab-active':''"
      class="px-5 py-3 text-sm font-medium text-gray-500 hover:text-gray-700 transition">任务</button>
    <button @click="tab='workspace_review'; loadWorkspace()" :class="tab==='workspace_review'?'tab-active':''"
      class="px-5 py-3 text-sm font-medium text-gray-500 hover:text-gray-700 transition">审核</button>
    <button @click="tab='workspace_packages'; loadWorkspace()" :class="tab==='workspace_packages'?'tab-active':''"
      class="px-5 py-3 text-sm font-medium text-gray-500 hover:text-gray-700 transition">发布包</button>
```

- [ ] **Step 4: Add minimal workspace sections**

Before `</main>`, add:

```html
  <section x-show="tab==='workspace_materials'" x-cloak>
    <div class="bg-white rounded-lg shadow p-4 mb-4">
      <h2 class="text-base font-semibold mb-3">素材录入</h2>
      <div class="grid grid-cols-2 gap-3">
        <input x-model="materialForm.title" class="border rounded px-3 py-2 text-sm" placeholder="标题">
        <input x-model="materialForm.tagsText" class="border rounded px-3 py-2 text-sm" placeholder="标签，逗号分隔">
        <textarea x-model="materialForm.excerpt" class="border rounded px-3 py-2 text-sm col-span-2" rows="2" placeholder="摘要"></textarea>
        <textarea x-model="materialForm.content" class="border rounded px-3 py-2 text-sm col-span-2" rows="4" placeholder="正文片段"></textarea>
      </div>
      <button @click="createWorkspaceMaterial()" class="mt-3 px-4 py-2 bg-indigo-600 text-white rounded text-sm">保存素材</button>
    </div>
    <div class="space-y-3">
      <template x-for="m in workspaceMaterials" :key="m.id">
        <div class="bg-white rounded-lg shadow p-4">
          <div class="flex justify-between gap-3">
            <div>
              <div class="font-medium text-sm" x-text="m.title"></div>
              <div class="text-xs text-gray-500 mt-1" x-text="m.source + ' · ' + m.status"></div>
            </div>
            <label class="text-xs flex items-center gap-1">
              <input type="checkbox" :value="m.id" x-model="cardForm.source_material_ids"> 加入选题卡
            </label>
          </div>
          <p class="text-sm text-gray-600 mt-2" x-text="m.excerpt || m.content"></p>
        </div>
      </template>
    </div>
  </section>

  <section x-show="tab==='workspace_cards'" x-cloak>
    <div class="bg-white rounded-lg shadow p-4 mb-4">
      <h2 class="text-base font-semibold mb-3">创建选题卡</h2>
      <div class="grid grid-cols-2 gap-3">
        <input x-model="cardForm.title" class="border rounded px-3 py-2 text-sm" placeholder="选题标题">
        <input x-model="cardForm.genre" class="border rounded px-3 py-2 text-sm" placeholder="题材">
        <input x-model="cardForm.platform" class="border rounded px-3 py-2 text-sm" placeholder="平台">
        <input x-model="cardForm.hook" class="border rounded px-3 py-2 text-sm" placeholder="开篇钩子">
        <textarea x-model="cardForm.angle" class="border rounded px-3 py-2 text-sm col-span-2" rows="2" placeholder="切入角度"></textarea>
        <textarea x-model="cardForm.risk_notes" class="border rounded px-3 py-2 text-sm col-span-2" rows="2" placeholder="风险提示"></textarea>
      </div>
      <button @click="createWorkspaceCard()" class="mt-3 px-4 py-2 bg-indigo-600 text-white rounded text-sm">创建选题卡</button>
    </div>
    <div class="space-y-3">
      <template x-for="c in workspaceCards" :key="c.id">
        <div class="bg-white rounded-lg shadow p-4 flex justify-between gap-4">
          <div>
            <div class="font-medium text-sm" x-text="c.title"></div>
            <div class="text-xs text-gray-500 mt-1" x-text="c.genre + ' · ' + c.platform + ' · ' + c.status"></div>
            <p class="text-sm text-gray-600 mt-2" x-text="c.hook || c.angle"></p>
          </div>
          <div class="flex gap-2 shrink-0">
            <button x-show="c.status==='draft'" @click="approveWorkspaceCard(c)" class="px-3 py-1.5 border rounded text-sm">批准</button>
            <button x-show="c.status==='approved'" @click="createTaskFromCard(c)" class="px-3 py-1.5 bg-indigo-600 text-white rounded text-sm">建任务</button>
          </div>
        </div>
      </template>
    </div>
  </section>

  <section x-show="tab==='workspace_tasks'" x-cloak>
    <div class="space-y-3">
      <template x-for="t in workspaceTasks" :key="t.id">
        <div class="bg-white rounded-lg shadow p-4 flex justify-between gap-4">
          <div>
            <div class="font-medium text-sm" x-text="t.topic"></div>
            <div class="text-xs text-gray-500 mt-1" x-text="t.status + ' · ' + t.genre + ' · ' + t.chapters + '章'"></div>
            <p x-show="t.error" class="text-sm text-red-500 mt-2" x-text="t.error"></p>
          </div>
          <div class="flex gap-2 shrink-0">
            <button x-show="t.status==='failed'" @click="retryWorkspaceTask(t)" class="px-3 py-1.5 border rounded text-sm">重试</button>
            <button x-show="t.status==='queued'" @click="cancelWorkspaceTask(t)" class="px-3 py-1.5 border rounded text-sm">取消</button>
          </div>
        </div>
      </template>
    </div>
  </section>

  <section x-show="tab==='workspace_review'" x-cloak>
    <div class="grid grid-cols-3 gap-4">
      <div class="space-y-3">
        <template x-for="d in workspaceDrafts" :key="d.id">
          <div @click="openDraft(d)" class="bg-white rounded-lg shadow p-4 cursor-pointer">
            <div class="font-medium text-sm" x-text="d.title"></div>
            <div class="text-xs text-gray-500 mt-1" x-text="d.status"></div>
          </div>
        </template>
      </div>
      <div class="bg-white rounded-lg shadow p-4 col-span-2" x-show="selectedDraft">
        <input x-model="draftEdit.title" class="w-full border rounded px-3 py-2 text-sm mb-3" placeholder="标题">
        <input x-model="draftEdit.synopsis" class="w-full border rounded px-3 py-2 text-sm mb-3" placeholder="简介">
        <input x-model="draftEdit.tagsText" class="w-full border rounded px-3 py-2 text-sm mb-3" placeholder="标签">
        <textarea x-model="draftEdit.body" class="w-full border rounded px-3 py-2 text-sm h-96 mb-3"></textarea>
        <textarea x-model="draftEdit.editor_notes" class="w-full border rounded px-3 py-2 text-sm mb-3" rows="2" placeholder="编辑备注"></textarea>
        <div class="flex gap-2">
          <button @click="saveDraft()" class="px-4 py-2 border rounded text-sm">保存</button>
          <button @click="markDraftReady()" class="px-4 py-2 bg-indigo-600 text-white rounded text-sm">可生成发布包</button>
          <button @click="generatePackage(selectedDraft.task_id, 'zhihu')" class="px-4 py-2 border rounded text-sm">生成知乎发布包</button>
        </div>
      </div>
    </div>
  </section>

  <section x-show="tab==='workspace_packages'" x-cloak>
    <div class="space-y-3">
      <template x-for="p in workspacePackages" :key="p.id">
        <div class="bg-white rounded-lg shadow p-4 flex justify-between gap-4">
          <div>
            <div class="font-medium text-sm" x-text="p.title"></div>
            <div class="text-xs text-gray-500 mt-1" x-text="p.platform + ' · ' + p.status"></div>
            <p class="text-sm text-gray-600 mt-2" x-text="p.package_dir"></p>
          </div>
          <button x-show="p.status==='generated'" @click="confirmPackage(p)" class="px-3 py-1.5 bg-indigo-600 text-white rounded text-sm">确认</button>
        </div>
      </template>
    </div>
  </section>
```

- [ ] **Step 5: Smoke-test static page parses**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path("zhihu_fiction/static/index.html").read_text(encoding="utf-8")
for needle in ["workspace_materials", "createWorkspaceMaterial", "workspace_packages"]:
    assert needle in text, needle
print("workspace static markers ok")
PY
```

Expected:

```text
workspace static markers ok
```

- [ ] **Step 6: Commit Web workspace**

Run:

```bash
git add zhihu_fiction/static/index.html
git commit -m "feat: add workspace web tabs"
```

---

## Task 7: Update Documentation

**Files:**
- Modify: `zhihu_fiction/README.md`

- [ ] **Step 1: Add workspace section to README**

In `zhihu_fiction/README.md`, add this section after the Web service API list:

```markdown
## Workspace 业务工作台

Workspace 将一次性创作流程扩展为本地内容生产闭环：

```text
素材库 → 选题卡 → 任务队列 → 审核草稿 → 发布包
```

核心页面：

- **素材**：录入、导入、筛选创作素材。
- **选题卡**：把一条或多条素材整理成可批准的创作 brief。
- **任务**：查看排队、运行、失败和待审核任务。
- **审核**：轻量编辑标题、简介、标签和正文。
- **发布包**：从审核后的草稿生成平台发布包并确认导出。

Workspace API 位于 `/api/workspace/*`。第一版使用 `zhihu_fiction/data/workspace/` 下的 JSONL/JSON 文件存储，不需要数据库。
```
```

If the README already has a similar section, merge this wording without duplicating headings.

- [ ] **Step 2: Commit docs**

Run:

```bash
git add zhihu_fiction/README.md
git commit -m "docs: document zhihu fiction workspace"
```

---

## Task 8: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused workspace tests**

Run:

```bash
python -m pytest \
  zhihu_fiction/tests/test_workspace_models.py \
  zhihu_fiction/tests/test_workspace_repositories.py \
  zhihu_fiction/tests/test_workspace_services.py \
  zhihu_fiction/tests/test_workspace_queue.py \
  zhihu_fiction/tests/test_workspace_api.py \
  -v
```

Expected:

```text
passed
```

- [ ] **Step 2: Run all zhihu_fiction tests**

Run:

```bash
python -m pytest zhihu_fiction/tests -v
```

Expected:

```text
passed
```

- [ ] **Step 3: Start local server**

Run:

```bash
uvicorn zhihu_fiction.server:app --reload --port 8000
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8000
```

- [ ] **Step 4: Manual browser smoke test**

Open:

```text
http://127.0.0.1:8000
```

Check:

- Existing `运行`, `历史`, `技能`, `调度`, and `作品` tabs still render.
- New `素材`, `选题卡`, `任务`, `审核`, and `发布包` tabs render.
- Manual material creation appears in the material list.
- A topic card can be created and approved.
- A task can be created from the approved topic card.

- [ ] **Step 5: Commit verification fixes if needed**

If verification reveals fixes, make only the required scoped edits and commit:

```bash
git add zhihu_fiction
git commit -m "fix: stabilize workspace flow"
```

If no fixes are needed, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: materials, topic cards, single-worker queue, review drafts, publish packages, API, Web, tests, and README are each covered by a task.
- Storage boundary: all file IO is concentrated in `WorkspaceRepository`; services use repository methods.
- Queue boundary: queue reuses `Pipeline.run()`, does not duplicate generation logic, and exposes `kick()` so API task creation can start background processing without blocking the request.
- Compatibility: existing CLI and legacy `/api/run` routes are not removed or renamed.
- Intentional first-version limitation: the queue drains pending tasks only when kicked by create/retry paths or direct caller action; it does not run a permanent polling loop.
