"""Application dependency container."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import load_settings
from ..exporter import Exporter
from ..llm import create_llm
from ..pipeline import Pipeline
from ..skills_store import SkillsStore
from ..workspace.queue import WorkspaceQueue
from ..workspace.queue_backends import create_queue_backend
from ..workspace.repositories import WorkspaceRepository
from ..workspace.services import WorkspaceService
from .settings import WebSettings, load_web_settings
from .services.infrastructure import infrastructure_status


class _NoopPublisher:
    """Publisher used by the web app when real publishing is not requested."""

    def publish(self, title: str, content: str, tags=None, genre: str = "") -> dict:
        return {
            "success": True,
            "url": "",
            "message": "publish skipped (use /autopublish or scheduler)",
        }


@dataclass
class AppDependencies:
    """Long-lived application services shared by route modules."""

    settings: Any = field(default_factory=load_settings)
    web_settings: WebSettings = field(default_factory=load_web_settings)
    skills_store: SkillsStore = field(default_factory=SkillsStore)
    workspace_repo: WorkspaceRepository = field(default_factory=WorkspaceRepository)

    def __post_init__(self) -> None:
        self.scheduler_pipeline: Pipeline | None = None
        self.workspace_service = WorkspaceService(self.workspace_repo)
        self.queue_backend = create_queue_backend()
        self.workspace_queue = WorkspaceQueue(
            self.workspace_repo,
            self.workspace_service,
            pipeline_factory=self.create_pipeline,
        )
        self.workspace_queue.repair_stale_running()
        self.video_job_recovery = {"refresh_queued": 0, "failed": 0}

    def create_pipeline(self) -> Pipeline:
        from ..orchestrator import create_orchestrator

        coordinator, reviewer, llm = create_orchestrator(
            self.settings,
            skills_store=self.skills_store,
        )
        return Pipeline(
            coordinator=coordinator,
            reviewer=reviewer,
            llm=llm,
            publisher=_NoopPublisher(),
            quality_threshold=6.0,
            max_rewrites=2,
        )

    def create_exporter(self) -> Exporter:
        return Exporter(create_llm(self.settings, temperature=0.3))

    def infrastructure_status(self) -> dict:
        return infrastructure_status(self)
