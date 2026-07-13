"""File-backed repositories for workspace state."""
from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path
from typing import Generic, Protocol, TypeVar

from ..core.config import APP_ROOT
from .models import (
    ConsistencyProfile,
    CostLedgerEntry,
    DramaProjectPackage,
    DramaProjectSession,
    DramaStageVersion,
    DramaVideoJob,
    DramaVideoRun,
    Material,
    OperationLog,
    Project,
    ProjectRelease,
    PublishPackage,
    Review,
    ReviewDraft,
    Story,
    StoryTask,
    TopicCard,
    VideoAsset,
)


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


class SQLiteStore(Generic[RecordT]):
    """Small SQLite-backed store for dataclass records.

    The record payload is stored as JSON to keep the public repository contract
    compatible with the existing JSONL stores while giving production installs
    a transactional SQL backend.
    """

    def __init__(self, db_path: Path, table: str, loader: Callable[[dict], RecordT]) -> None:
        self.db_path = db_path
        self.table = table
        self.loader = loader
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_table()

    def list(self) -> list[RecordT]:
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT payload FROM {self.table} ORDER BY rowid ASC"
            ).fetchall()
        records: list[RecordT] = []
        for (payload,) in rows:
            try:
                records.append(self.loader(json.loads(payload)))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return records

    def append(self, record: RecordT) -> RecordT:
        return self.save(record)

    def replace_all(self, records: Iterable[RecordT]) -> None:
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {self.table}")
            conn.executemany(
                f"INSERT INTO {self.table} (id, payload) VALUES (?, ?)",
                [
                    (record.id, json.dumps(record.to_dict(), ensure_ascii=False))
                    for record in records
                ],
            )
        return None

    def get(self, record_id: str) -> RecordT | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT payload FROM {self.table} WHERE id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            return self.loader(json.loads(row[0]))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def save(self, record: RecordT) -> RecordT:
        with self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {self.table} (id, payload)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (record.id, json.dumps(record.to_dict(), ensure_ascii=False)),
            )
        return record

    def update(self, record_id: str, changes: dict) -> RecordT:
        existing = self.get(record_id)
        if existing is None:
            raise KeyError(record_id)
        updated = replace(existing, **changes)
        return self.save(updated)

    def _init_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


class WorkspaceRepository:
    """Coordinate file-backed stores under one workspace root."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        backend: str | None = None,
        sqlite_path: Path | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else WORKSPACE_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        self.backend = (backend or os.getenv("ZH_WORKSPACE_BACKEND") or "jsonl").lower()
        self.sqlite_path = Path(
            sqlite_path
            or os.getenv("ZH_WORKSPACE_SQLITE_PATH")
            or (self.root / "workspace.sqlite3")
        )

        self.drafts_dir = self.root / "drafts"
        self.reviews_dir = self.root / "reviews"
        self.publish_packages_dir = self.root / "publish_packages"
        self.drama_projects_dir = self.root / "drama_projects"
        for directory in (
            self.drafts_dir,
            self.reviews_dir,
            self.publish_packages_dir,
            self.drama_projects_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        self.materials = self._store("materials", Material.from_dict)
        self.topic_cards = self._store("topic_cards", TopicCard.from_dict)
        self.tasks = self._store("tasks", StoryTask.from_dict)
        self.packages = self._store(
            "publish_packages",
            PublishPackage.from_dict,
        )
        self.projects = self._store("projects", Project.from_dict)
        self.stories = self._store("stories", Story.from_dict)
        self.video_assets = self._store("video_assets", VideoAsset.from_dict)
        self.reviews = self._store("reviews", Review.from_dict)
        self.project_releases = self._store(
            "project_releases",
            ProjectRelease.from_dict,
        )
        self.cost_ledger_entries = self._store(
            "cost_ledger_entries",
            CostLedgerEntry.from_dict,
        )
        self.consistency_profiles = self._store(
            "consistency_profiles",
            ConsistencyProfile.from_dict,
        )
        self.operation_logs = self._store(
            "operation_logs",
            OperationLog.from_dict,
        )
        self.drama_sessions = self._store(
            "drama_sessions",
            DramaProjectSession.from_dict,
        )
        self.drama_stage_versions = self._store(
            "drama_stage_versions",
            DramaStageVersion.from_dict,
        )
        self.drama_project_packages = self._store(
            "drama_project_packages",
            DramaProjectPackage.from_dict,
        )
        self.drama_video_runs = self._store(
            "drama_video_runs",
            DramaVideoRun.from_dict,
        )
        self.drama_video_jobs = self._store(
            "drama_video_jobs",
            DramaVideoJob.from_dict,
        )

    def _store(self, name: str, loader: Callable[[dict], RecordT]):
        if self.backend == "sqlite":
            table = name.replace("-", "_")
            return SQLiteStore(self.sqlite_path, table, loader)
        return JsonlStore(
            self.root / "publish_packages.jsonl",
            loader,
        ) if name == "publish_packages" else JsonlStore(self.root / f"{name}.jsonl", loader)

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

    def save_project(self, project: Project) -> Project:
        return self.projects.save(project)

    def get_project(self, project_id: str) -> Project | None:
        return self.projects.get(project_id)

    def list_projects(self) -> list[Project]:
        return sorted(self.projects.list(), key=lambda item: item.updated_at, reverse=True)

    def update_project(self, project_id: str, changes: dict) -> Project:
        return self.projects.update(project_id, changes)

    def save_story(self, story: Story) -> Story:
        return self.stories.save(story)

    def get_story(self, story_id: str) -> Story | None:
        return self.stories.get(story_id)

    def list_stories(self, project_id: str | None = None) -> list[Story]:
        stories = self.stories.list()
        if project_id is not None:
            stories = [story for story in stories if story.project_id == project_id]
        return sorted(stories, key=lambda item: item.created_at, reverse=True)

    def save_video_asset(self, asset: VideoAsset) -> VideoAsset:
        return self.video_assets.save(asset)

    def get_video_asset(self, asset_id: str) -> VideoAsset | None:
        return self.video_assets.get(asset_id)

    def list_video_assets(self, project_id: str | None = None) -> list[VideoAsset]:
        assets = self.video_assets.list()
        if project_id is not None:
            assets = [asset for asset in assets if asset.project_id == project_id]
        return sorted(assets, key=lambda item: item.created_at, reverse=True)

    def save_review(self, review: Review) -> Review:
        return self.reviews.save(review)

    def get_review(self, review_id: str) -> Review | None:
        return self.reviews.get(review_id)

    def list_reviews(self, project_id: str | None = None) -> list[Review]:
        reviews = self.reviews.list()
        if project_id is not None:
            reviews = [review for review in reviews if review.project_id == project_id]
        return sorted(reviews, key=lambda item: item.created_at, reverse=True)

    def project_timeline(self, project_id: str) -> list[dict]:
        events: list[dict] = []
        project_story_paths = {
            story.body_path
            for story in self.list_stories(project_id)
        }
        project_session_ids: set[str] = set()
        for story in self.list_stories(project_id):
            events.append({
                "kind": "story",
                "id": story.id,
                "project_id": project_id,
                "created_at": story.created_at,
                "record": story.to_dict(),
            })
        for asset in self.list_video_assets(project_id):
            events.append({
                "kind": "video_asset",
                "id": asset.id,
                "project_id": project_id,
                "created_at": asset.created_at,
                "record": asset.to_dict(),
            })
        for review in self.list_reviews(project_id):
            events.append({
                "kind": "review",
                "id": review.id,
                "project_id": project_id,
                "created_at": review.created_at,
                "record": review.to_dict(),
            })
        for session in self.list_drama_sessions():
            if session.project_id == project_id or (
                not session.project_id and session.story_path in project_story_paths
            ):
                project_session_ids.add(session.id)
                events.append({
                    "kind": "drama_session",
                    "id": session.id,
                    "project_id": project_id,
                    "created_at": session.updated_at,
                    "record": session.to_dict(),
                })
        for version in self.drama_stage_versions.list():
            if version.project_id == project_id or (
                not version.project_id and version.run_id in project_session_ids
            ):
                project_session_ids.add(version.run_id)
                events.append({
                    "kind": "drama_stage_version",
                    "id": version.id,
                    "project_id": project_id,
                    "created_at": version.created_at,
                    "record": version.to_dict(),
                })
        for run in self.list_drama_video_runs():
            if run.project_id == project_id or (
                not run.project_id and run.story_path in project_story_paths
            ):
                events.append({
                    "kind": "drama_video_run",
                    "id": run.id,
                    "project_id": project_id,
                    "created_at": run.updated_at,
                    "record": run.to_dict(),
                })
        for package in self.drama_project_packages.list():
            if package.run_id in project_session_ids or package.story_path in project_story_paths:
                events.append({
                    "kind": "drama_project_package",
                    "id": package.id,
                    "project_id": project_id,
                    "created_at": package.created_at,
                    "record": package.to_dict(),
                })
        return sorted(events, key=lambda item: item["created_at"], reverse=True)

    def project_assets(self, project_id: str) -> list[dict]:
        assets: list[dict] = []
        latest_reviews = self._latest_asset_reviews(project_id)
        project_story_paths = {
            story.body_path
            for story in self.list_stories(project_id)
        }
        project_session_ids = {
            session.id
            for session in self.list_drama_sessions()
            if session.project_id == project_id or (
                not session.project_id and session.story_path in project_story_paths
            )
        }
        for asset in self.list_video_assets(project_id):
            title = asset.shot_id or asset.uri or asset.id
            target_kind = "video_asset"
            assets.append({
                "source": "video_asset",
                "id": asset.id,
                "project_id": project_id,
                "kind": asset.kind,
                "title": title,
                "uri": asset.uri,
                "content_type": asset.content_type,
                "created_at": asset.created_at,
                "review_target_kind": target_kind,
                "review": self._asset_review_payload(
                    target_kind,
                    asset.id,
                    latest_reviews.get((target_kind, asset.id)),
                ),
                "record": asset.to_dict(),
            })
        for version in self.drama_stage_versions.list():
            if version.project_id == project_id or (
                not version.project_id and version.run_id in project_session_ids
            ):
                target_kind = "stage_version"
                assets.append({
                    "source": "stage_version",
                    "id": version.id,
                    "project_id": project_id,
                    "kind": "prompt",
                    "title": f"{version.stage} / {version.event}",
                    "uri": "",
                    "content_type": "text/plain",
                    "created_at": version.created_at,
                    "review_target_kind": target_kind,
                    "review": self._asset_review_payload(
                        target_kind,
                        version.id,
                        latest_reviews.get((target_kind, version.id)),
                    ),
                    "record": version.to_dict(),
                })
        for package in self.drama_project_packages.list():
            if package.run_id in project_session_ids or package.story_path in project_story_paths:
                target_kind = "drama_project_package"
                assets.append({
                    "source": "drama_project_package",
                    "id": package.id,
                    "project_id": project_id,
                    "kind": "package",
                    "title": "短剧项目包",
                    "uri": package.package_uri,
                    "content_type": "application/json",
                    "created_at": package.created_at,
                    "review_target_kind": target_kind,
                    "review": self._asset_review_payload(
                        target_kind,
                        package.id,
                        latest_reviews.get((target_kind, package.id)),
                    ),
                    "record": package.to_dict(),
                })
        return sorted(assets, key=lambda item: item["created_at"], reverse=True)

    def project_asset_summary(self, project_id: str) -> dict:
        assets = self.project_assets(project_id)
        by_kind: dict[str, int] = {}
        by_source: dict[str, int] = {}
        review = {
            "unreviewed": 0,
            "pending": 0,
            "approved": 0,
            "changes_requested": 0,
            "rejected": 0,
        }

        for asset in assets:
            kind = asset.get("kind") or "unknown"
            source = asset.get("source") or "unknown"
            by_kind[kind] = by_kind.get(kind, 0) + 1
            by_source[source] = by_source.get(source, 0) + 1
            decision = (asset.get("review") or {}).get("decision") or "unreviewed"
            review[decision] = review.get(decision, 0) + 1

        return {
            "total": len(assets),
            "by_kind": dict(sorted(by_kind.items())),
            "by_source": dict(sorted(by_source.items())),
            "review": review,
            "awaiting_review": review["unreviewed"] + review["pending"],
            "needs_changes": review["changes_requested"] + review["rejected"],
        }

    def _latest_asset_reviews(self, project_id: str) -> dict[tuple[str, str], Review]:
        latest: dict[tuple[str, str], Review] = {}
        for review in self.list_reviews(project_id):
            key = (review.target_kind, review.target_id)
            current = latest.get(key)
            if current is None or review.created_at > current.created_at:
                latest[key] = review
        return latest

    def _asset_review_payload(
        self,
        target_kind: str,
        target_id: str,
        review: Review | None,
    ) -> dict:
        if review is None:
            return {
                "target_kind": target_kind,
                "target_id": target_id,
                "decision": "unreviewed",
            }
        return review.to_dict()

    def save_drama_session(self, session: DramaProjectSession) -> DramaProjectSession:
        return self.drama_sessions.save(session)

    def get_drama_session(self, run_id: str) -> DramaProjectSession | None:
        return self.drama_sessions.get(run_id)

    def list_drama_sessions(self) -> list[DramaProjectSession]:
        sessions = self.drama_sessions.list()
        return sorted(sessions, key=lambda item: item.updated_at, reverse=True)

    def update_drama_session(self, run_id: str, changes: dict) -> DramaProjectSession:
        return self.drama_sessions.update(run_id, changes)

    def save_drama_stage_version(self, version: DramaStageVersion) -> DramaStageVersion:
        return self.drama_stage_versions.save(version)

    def list_drama_stage_versions(
        self,
        run_id: str,
        stage: str | None = None,
    ) -> list[DramaStageVersion]:
        versions = [
            version
            for version in self.drama_stage_versions.list()
            if version.run_id == run_id and (stage is None or version.stage == stage)
        ]
        return sorted(versions, key=lambda item: item.created_at)

    def save_drama_project_package(
        self,
        package: DramaProjectPackage,
    ) -> DramaProjectPackage:
        return self.drama_project_packages.save(package)

    def get_drama_project_package(self, package_id: str) -> DramaProjectPackage | None:
        return self.drama_project_packages.get(package_id)

    def update_drama_project_package(
        self,
        package_id: str,
        changes: dict,
    ) -> DramaProjectPackage:
        return self.drama_project_packages.update(package_id, changes)

    def save_project_release(self, release: ProjectRelease) -> ProjectRelease:
        return self.project_releases.save(release)

    def get_project_release(self, release_id: str) -> ProjectRelease | None:
        return self.project_releases.get(release_id)

    def list_project_releases(self, project_id: str | None = None) -> list[ProjectRelease]:
        releases = self.project_releases.list()
        if project_id is not None:
            releases = [release for release in releases if release.project_id == project_id]
        return sorted(releases, key=lambda item: item.created_at, reverse=True)

    def get_project_release_for_package(
        self,
        project_id: str,
        package_id: str,
    ) -> ProjectRelease | None:
        for release in self.list_project_releases(project_id):
            if release.package_id == package_id:
                return release
        return None

    def save_cost_ledger_entry(self, entry: CostLedgerEntry) -> CostLedgerEntry:
        return self.cost_ledger_entries.save(entry)

    def list_cost_ledger_entries(
        self,
        project_id: str | None = None,
        release_id: str | None = None,
    ) -> list[CostLedgerEntry]:
        entries = self.cost_ledger_entries.list()
        if project_id is not None:
            entries = [entry for entry in entries if entry.project_id == project_id]
        if release_id is not None:
            entries = [entry for entry in entries if entry.release_id == release_id]
        return sorted(entries, key=lambda item: item.created_at, reverse=True)

    def get_cost_ledger_entry_for_release(
        self,
        release_id: str,
        source: str | None = None,
    ) -> CostLedgerEntry | None:
        for entry in self.list_cost_ledger_entries(release_id=release_id):
            if source is None or entry.source == source:
                return entry
        return None

    def sum_cost_ledger_entries_for_day(
        self,
        date_iso: str,
        project_id: str | None = None,
    ) -> float:
        entries = self.list_effective_cost_ledger_entries_for_day(
            date_iso,
            project_id=project_id,
        )
        return round(sum(float(entry.amount_cny or 0.0) for entry in entries), 2)

    def list_effective_cost_ledger_entries_for_day(
        self,
        date_iso: str,
        project_id: str | None = None,
    ) -> list[CostLedgerEntry]:
        entries = self._cost_ledger_entries_for_day(date_iso, project_id=project_id)
        provider_actual_keys = self._provider_actual_cost_keys(entries)
        effective_entries: list[CostLedgerEntry] = []
        for entry in entries:
            if self._video_estimate_is_covered(entry, provider_actual_keys):
                continue
            effective_entries.append(entry)
        return effective_entries

    def list_covered_video_estimate_entries_for_day(
        self,
        date_iso: str,
        project_id: str | None = None,
    ) -> list[CostLedgerEntry]:
        entries = self._cost_ledger_entries_for_day(date_iso, project_id=project_id)
        provider_actual_keys = self._provider_actual_cost_keys(entries)
        return [
            entry
            for entry in entries
            if self._video_estimate_is_covered(entry, provider_actual_keys)
        ]

    def _cost_ledger_entries_for_day(
        self,
        date_iso: str,
        project_id: str | None = None,
    ) -> list[CostLedgerEntry]:
        day = str(date_iso or "")[:10]
        if not day:
            return []
        return [
            entry
            for entry in self.list_cost_ledger_entries(project_id=project_id)
            if str(entry.created_at or "")[:10] == day
        ]

    def _provider_actual_cost_keys(
        self,
        entries: list[CostLedgerEntry],
    ) -> set[tuple[str, str]]:
        return {
            (entry.project_id, entry.run_id)
            for entry in entries
            if not entry.estimated and str(entry.source or "").startswith("provider_")
        }

    def _video_estimate_is_covered(
        self,
        entry: CostLedgerEntry,
        provider_actual_keys: set[tuple[str, str]],
    ) -> bool:
        return (
            (entry.project_id, entry.run_id) in provider_actual_keys
            and entry.estimated
            and entry.source in {"video_run_estimate", "video_retry_estimate"}
        )

    def save_consistency_profile(
        self,
        profile: ConsistencyProfile,
    ) -> ConsistencyProfile:
        return self.consistency_profiles.save(profile)

    def get_consistency_profile(
        self,
        profile_id: str,
    ) -> ConsistencyProfile | None:
        return self.consistency_profiles.get(profile_id)

    def list_consistency_profiles(
        self,
        project_id: str | None = None,
    ) -> list[ConsistencyProfile]:
        profiles = self.consistency_profiles.list()
        if project_id is not None:
            profiles = [
                profile for profile in profiles
                if profile.project_id == project_id
            ]
        return sorted(profiles, key=lambda item: item.updated_at, reverse=True)

    def latest_consistency_profile_for_session(
        self,
        session_id: str,
    ) -> ConsistencyProfile | None:
        profiles = [
            profile for profile in self.consistency_profiles.list()
            if profile.session_id == session_id
        ]
        if not profiles:
            return None
        return sorted(profiles, key=lambda item: item.updated_at, reverse=True)[0]

    def save_operation_log(self, log: OperationLog) -> OperationLog:
        return self.operation_logs.save(log)

    def list_operation_logs(
        self,
        project_id: str | None = None,
    ) -> list[OperationLog]:
        logs = self.operation_logs.list()
        if project_id is not None:
            logs = [log for log in logs if log.project_id == project_id]
        indexed_logs = list(enumerate(logs))
        return [
            log for _, log in sorted(
                indexed_logs,
                key=lambda item: (item[1].created_at, item[0]),
                reverse=True,
            )
        ]

    def list_drama_project_packages(
        self,
        run_id: str | None = None,
    ) -> list[DramaProjectPackage]:
        packages = self.drama_project_packages.list()
        if run_id is not None:
            packages = [package for package in packages if package.run_id == run_id]
        return sorted(packages, key=lambda item: item.created_at, reverse=True)

    def save_drama_video_run(self, run: DramaVideoRun) -> DramaVideoRun:
        return self.drama_video_runs.save(run)

    def get_drama_video_run(self, run_id: str) -> DramaVideoRun | None:
        return self.drama_video_runs.get(run_id)

    def list_drama_video_runs(self) -> list[DramaVideoRun]:
        runs = self.drama_video_runs.list()
        return sorted(runs, key=lambda item: item.updated_at, reverse=True)

    def update_drama_video_run(self, run_id: str, changes: dict) -> DramaVideoRun:
        return self.drama_video_runs.update(run_id, changes)

    def save_drama_video_job(self, job: DramaVideoJob) -> DramaVideoJob:
        return self.drama_video_jobs.save(job)

    def get_drama_video_job(self, job_id: str) -> DramaVideoJob | None:
        return self.drama_video_jobs.get(job_id)

    def list_drama_video_jobs(self, run_id: str | None = None) -> list[DramaVideoJob]:
        jobs = self.drama_video_jobs.list()
        if run_id is not None:
            jobs = [job for job in jobs if job.run_id == run_id]
        return sorted(jobs, key=lambda item: item.updated_at, reverse=True)

    def update_drama_video_job(self, job_id: str, changes: dict) -> DramaVideoJob:
        return self.drama_video_jobs.update(job_id, changes)

    def _load_review_draft(self, path: Path) -> ReviewDraft | None:
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ReviewDraft.from_dict(data)
        except (json.JSONDecodeError, TypeError, ValueError, UnicodeDecodeError):
            return None
