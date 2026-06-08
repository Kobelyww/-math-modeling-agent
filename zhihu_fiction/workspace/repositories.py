"""File-backed repositories for workspace state."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path
from typing import Generic, Protocol, TypeVar

from ..config import APP_ROOT
from .models import Material, PublishPackage, ReviewDraft, StoryTask, TopicCard


WORKSPACE_DIR = APP_ROOT / "data" / "workspace"


class JsonlRecord(Protocol):
    id: str

    def to_dict(self) -> dict:
        ...


RecordT = TypeVar("RecordT", bound=JsonlRecord)


class JsonlStore(Generic[RecordT]):
    """Persist dataclass records as JSON Lines."""

    def __init__(self, path: Path, loader: Callable[[dict], RecordT]) -> None:
        self.path = path
        self.loader = loader
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[RecordT]:
        if not self.path.exists():
            return []

        records: list[RecordT] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(self.loader(json.loads(line)))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
        return records

    def append(self, record: RecordT) -> RecordT:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False))
            handle.write("\n")
        return record

    def replace_all(self, records: Iterable[RecordT]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record.to_dict(), ensure_ascii=False))
                handle.write("\n")

    def get(self, record_id: str) -> RecordT | None:
        for record in self.list():
            if record.id == record_id:
                return record
        return None

    def save(self, record: RecordT) -> RecordT:
        records = self.list()
        for index, existing in enumerate(records):
            if existing.id == record.id:
                records[index] = record
                self.replace_all(records)
                return record

        self.append(record)
        return record

    def update(self, record_id: str, changes: dict) -> RecordT:
        records = self.list()
        for index, existing in enumerate(records):
            if existing.id == record_id:
                updated = replace(existing, **changes)
                records[index] = updated
                self.replace_all(records)
                return updated

        raise KeyError(record_id)


class WorkspaceRepository:
    """Coordinate file-backed stores under one workspace root."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else WORKSPACE_DIR
        self.root.mkdir(parents=True, exist_ok=True)

        self.drafts_dir = self.root / "drafts"
        self.reviews_dir = self.root / "reviews"
        self.publish_packages_dir = self.root / "publish_packages"
        for directory in (self.drafts_dir, self.reviews_dir, self.publish_packages_dir):
            directory.mkdir(parents=True, exist_ok=True)

        self.materials = JsonlStore(self.root / "materials.jsonl", Material.from_dict)
        self.topic_cards = JsonlStore(self.root / "topic_cards.jsonl", TopicCard.from_dict)
        self.tasks = JsonlStore(self.root / "tasks.jsonl", StoryTask.from_dict)
        self.packages = JsonlStore(
            self.root / "publish_packages.jsonl",
            PublishPackage.from_dict,
        )

    def save_material(self, material: Material) -> Material:
        return self.materials.save(material)

    def list_materials(self) -> list[Material]:
        return self.materials.list()

    def get_material(self, material_id: str) -> Material | None:
        return self.materials.get(material_id)

    def update_material(self, material_id: str, changes: dict) -> Material:
        return self.materials.update(material_id, changes)

    def save_topic_card(self, topic_card: TopicCard) -> TopicCard:
        return self.topic_cards.save(topic_card)

    def list_topic_cards(self) -> list[TopicCard]:
        return self.topic_cards.list()

    def get_topic_card(self, topic_card_id: str) -> TopicCard | None:
        return self.topic_cards.get(topic_card_id)

    def update_topic_card(self, topic_card_id: str, changes: dict) -> TopicCard:
        return self.topic_cards.update(topic_card_id, changes)

    def save_task(self, task: StoryTask) -> StoryTask:
        return self.tasks.save(task)

    def list_tasks(self) -> list[StoryTask]:
        return self.tasks.list()

    def get_task(self, task_id: str) -> StoryTask | None:
        return self.tasks.get(task_id)

    def update_task(self, task_id: str, changes: dict) -> StoryTask:
        return self.tasks.update(task_id, changes)

    def list_queued_tasks(self) -> list[StoryTask]:
        tasks = [task for task in self.list_tasks() if task.status == "queued"]
        return sorted(tasks, key=lambda task: (-task.priority, task.created_at, task.id))

    def list_running_tasks(self) -> list[StoryTask]:
        return [task for task in self.list_tasks() if task.status == "running"]

    def save_review_draft(self, draft: ReviewDraft) -> ReviewDraft:
        path = self.drafts_dir / f"{draft.task_id}.json"
        path.write_text(
            json.dumps(draft.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return draft

    def get_review_draft(self, task_id: str) -> ReviewDraft | None:
        return self._load_review_draft(self.drafts_dir / f"{task_id}.json")

    def list_review_drafts(self) -> list[ReviewDraft]:
        drafts: list[tuple[float, ReviewDraft]] = []
        for path in self.drafts_dir.glob("*.json"):
            draft = self._load_review_draft(path)
            if draft is None:
                continue
            try:
                modified_at = path.stat().st_mtime
            except OSError:
                continue
            drafts.append((modified_at, draft))

        drafts.sort(key=lambda item: item[0], reverse=True)
        return [draft for _, draft in drafts]

    def save_publish_package(self, package: PublishPackage) -> PublishPackage:
        return self.packages.save(package)

    def list_publish_packages(self) -> list[PublishPackage]:
        return self.packages.list()

    def get_publish_package(self, package_id: str) -> PublishPackage | None:
        return self.packages.get(package_id)

    def update_publish_package(self, package_id: str, changes: dict) -> PublishPackage:
        return self.packages.update(package_id, changes)

    def _load_review_draft(self, path: Path) -> ReviewDraft | None:
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ReviewDraft.from_dict(data)
        except (json.JSONDecodeError, TypeError, ValueError, UnicodeDecodeError):
            return None
