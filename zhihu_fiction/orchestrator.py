"""Compatibility exports for fiction workflow orchestration."""

from __future__ import annotations

from zhihu_fiction.fiction.orchestrator import (
    Orchestrator,
    OrchestratorCompat,
    StageResult,
    WorkflowResult,
    create_drama_video_coordinator,
    create_orchestrator,
    run_coordinator,
    run_drama_video_coordinator,
)

__all__ = [
    "Orchestrator",
    "OrchestratorCompat",
    "StageResult",
    "WorkflowResult",
    "create_drama_video_coordinator",
    "create_orchestrator",
    "run_coordinator",
    "run_drama_video_coordinator",
]
