"""Business services for workspace workflows."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from ..orchestrator import WorkflowResult
from .models import (
    Material,
    PublishPackage,
    ReviewDraft,
    StoryTask,
    TopicCard,
    new_id,
    utc_now_iso,
)
from .repositories import WorkspaceRepository


class WorkspaceService:
    """Coordinate workspace workflow operations across repository stores."""

    def __init__(self, repo: WorkspaceRepository) -> None:
        self.repo = repo

    def import_scraped_items(
        self,
        items: list[dict],
        source: str = "scraped",
    ) -> dict:
        imported: list[Material] = []
        failed: list[dict] = []

        for index, item in enumerate(items):
            title = _clean_text(item.get("title", ""))
            if not title:
                failed.append({"index": index, "reason": "missing title"})
                continue

            material = Material(
                id=new_id("mat"),
                source=item.get("source", source) or source,
                title=title,
                excerpt=_clean_text(item.get("excerpt", "")),
                content=_clean_text(item.get("content", "")),
                url=_clean_text(item.get("url", "")),
                hot_score=_coerce_float(item.get("hot_score") or item.get("votes")),
                tags=list(item.get("tags", []) or []),
                captured_at=item.get("scraped_at") or utc_now_iso(),
            )
            imported.append(self.repo.save_material(material))

        return {
            "imported": len(imported),
            "failed": failed,
            "items": [material.to_dict() for material in imported],
        }

    def create_manual_material(
        self,
        title: str,
        content: str = "",
        excerpt: str = "",
        tags: list[str] | None = None,
        url: str = "",
        hot_score: float = 0.0,
    ) -> Material:
        clean_title = _require_title(title)
        material = Material(
            id=new_id("mat"),
            source="manual",
            title=clean_title,
            excerpt=_clean_text(excerpt),
            content=_clean_text(content),
            url=_clean_text(url),
            hot_score=_coerce_float(hot_score),
            tags=list(tags or []),
        )
        return self.repo.save_material(material)

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
        clean_title = _require_title(title)
        material_ids = list(source_material_ids or [])

        for material_id in material_ids:
            if self.repo.get_material(material_id) is None:
                raise KeyError(material_id)

        card = TopicCard(
            id=new_id("card"),
            title=clean_title,
            source_material_ids=material_ids,
            genre=_clean_text(genre),
            platform=_clean_text(platform) or "zhihu",
            hook=_clean_text(hook),
            angle=_clean_text(angle),
            risk_notes=_clean_text(risk_notes),
            target_reader=_clean_text(target_reader),
        )
        saved = self.repo.save_topic_card(card)

        for material_id in material_ids:
            self.repo.update_material(material_id, {"status": "selected"})

        return saved

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
        return self.repo.save_task(task)

    def create_review_draft_from_result(
        self,
        task: StoryTask,
        story_path: str | Path,
        body: str,
        review_result: dict,
    ) -> ReviewDraft:
        draft = ReviewDraft(
            id=new_id("draft"),
            task_id=task.id,
            story_path=str(story_path),
            original_body=body,
            title=task.topic,
            synopsis=body[:200],
            tags=[task.genre] if task.genre else [],
            body=body,
            review_result=dict(review_result),
        )
        return self.repo.save_review_draft(draft)

    def update_review_draft(self, task_id: str, changes: dict) -> ReviewDraft:
        draft = self.repo.get_review_draft(task_id)
        if draft is None:
            raise KeyError(task_id)

        allowed = {"title", "synopsis", "tags", "body", "editor_notes", "status"}
        updates = {key: value for key, value in changes.items() if key in allowed}
        updates["updated_at"] = utc_now_iso()

        updated = replace(draft, **updates)
        return self.repo.save_review_draft(updated)

    def mark_draft_ready(self, task_id: str) -> ReviewDraft:
        task = self.repo.get_task(task_id)
        if task is None:
            raise KeyError(task_id)

        draft = self.repo.get_review_draft(task_id)
        if draft is None:
            raise KeyError(task_id)

        now = utc_now_iso()
        ready = replace(draft, status="ready_for_package", updated_at=now)
        self.repo.save_review_draft(ready)
        self.repo.update_task(
            task_id,
            {"status": "approved", "finished_at": task.finished_at or now},
        )
        return ready

    def generate_publish_package(
        self,
        task_id: str,
        platform: str,
        exporter: Any,
    ) -> PublishPackage:
        task = self.repo.get_task(task_id)
        if task is None:
            raise KeyError(task_id)

        draft = self.repo.get_review_draft(task_id)
        if draft is None:
            raise KeyError(task_id)
        if draft.status != "ready_for_package":
            raise ValueError("Review draft must be ready for package generation")

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
            exported = exporter.export(result, platforms=[platform])
            package_dir_value = exported.get(platform)
            if package_dir_value is None:
                package_dir_value = self._write_fallback_package(task, draft, platform)
        except Exception:
            package_dir_value = self._write_fallback_package(task, draft, platform)

        package_dir = Path(package_dir_value)
        content_path = ""
        metadata_path = ""
        if package_dir.exists():
            content_path = str(package_dir / "发布内容.md")
            metadata_path = str(package_dir / "元数据.md")

        package = PublishPackage(
            id=new_id("pkg"),
            task_id=task.id,
            platform=platform,
            title=draft.title,
            synopsis=draft.synopsis,
            tags=list(draft.tags),
            content_path=content_path,
            metadata_path=metadata_path,
            package_dir=str(package_dir),
        )
        return self.repo.save_publish_package(package)

    def confirm_package(self, package_id: str) -> PublishPackage:
        package = self.repo.get_publish_package(package_id)
        if package is None:
            raise KeyError(package_id)

        return self.repo.update_publish_package(package_id, {"status": "confirmed"})

    def _write_fallback_package(
        self,
        task: StoryTask,
        draft: ReviewDraft,
        platform: str,
    ) -> str:
        package_dir = self.repo.root / "publish_packages" / new_id("fallback")
        package_dir.mkdir(parents=True, exist_ok=True)

        content_path = package_dir / "发布内容.md"
        content_path.write_text(draft.body or draft.original_body, encoding="utf-8")

        metadata_path = package_dir / "元数据.md"
        metadata_lines = [
            f"# {draft.title}",
            "",
            f"平台：{platform}",
            f"题材：{task.genre}",
            f"标签：{', '.join(draft.tags)}",
            f"简介：{draft.synopsis}",
        ]
        metadata_path.write_text("\n".join(metadata_lines), encoding="utf-8")

        return str(package_dir)


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _require_title(title: str) -> str:
    clean_title = _clean_text(title)
    if not clean_title:
        raise ValueError("title is required")
    return clean_title


def _coerce_float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
