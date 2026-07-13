"""Compatibility entrypoint for the Zhihu Fiction FastAPI application."""
from __future__ import annotations

import asyncio

from .app.dependencies import AppDependencies
from .app.factory import create_app
from .app.services import drama_video_runtime
from .app.services.pipeline_runtime import execute_pipeline_in_background, read_runs
from .app.state import AppState
from .core.config import APP_ROOT
from .drama import DramaAdapter, DramaAdapterError, DramaExporter
from .drama.video import BailianVideoProvider, DramaVideoError, VideoJobStore, create_video_provider
from .exporter import Exporter
from .core.llm import create_llm
from .fiction.orchestrator import (
    StageResult,
    WorkflowResult,
    create_drama_video_coordinator,
    create_orchestrator,
    run_drama_video_coordinator,
)
from .fiction.pipeline import Pipeline, RUN_DIR
from .fiction.skills_store import SkillsStore
from .workspace.queue import WorkspaceQueue
from .workspace.queue_backends import create_queue_backend
from .workspace.repositories import WorkspaceRepository
from .workspace.services import WorkspaceService

dependencies = AppDependencies()
runtime_state = AppState()
app = create_app(dependencies=dependencies, state=runtime_state)

settings = dependencies.settings
skills_store = dependencies.skills_store
workspace_repo = dependencies.workspace_repo
workspace_service = dependencies.workspace_service
queue_backend = dependencies.queue_backend
workspace_queue = dependencies.workspace_queue

OUTPUT_DIR = APP_ROOT / "output"

_run_events = runtime_state.run_events
_run_progress = runtime_state.run_progress
_video_events = runtime_state.video_events
_video_progress = runtime_state.video_progress
_video_specs = runtime_state.video_specs
_video_deepagent_specs = runtime_state.video_deepagent_specs
_video_deepagent_stage_tasks = runtime_state.video_deepagent_stage_tasks
_video_lock = runtime_state.video_lock
_video_deepagent_lock = runtime_state.video_deepagent_lock
_active_lock = runtime_state.active_lock

_VIDEO_STAGE_DRAFT_LABELS = drama_video_runtime.VIDEO_STAGE_DRAFT_LABELS
_VIDEO_DEEPAGENT_STAGES = drama_video_runtime.VIDEO_DEEPAGENT_STAGES
_VIDEO_TEXT_STAGE_INSTRUCTIONS = drama_video_runtime.VIDEO_TEXT_STAGE_INSTRUCTIONS


class _NoopPublisher:
    def publish(self, title: str, content: str, tags=None, genre: str = "") -> dict:
        return {
            "success": True,
            "url": "",
            "message": "publish skipped (use /autopublish or scheduler)",
        }


def _create_pipeline() -> Pipeline:
    return dependencies.create_pipeline()


def _create_exporter() -> Exporter:
    return dependencies.create_exporter()


def _read_runs(limit: int = 50) -> list[dict]:
    return read_runs(limit)


def _list_story_dirs() -> list[dict]:
    from .app.services.story_library import list_story_dirs

    return list_story_dirs()


def _story_result_from_file(story_file):
    from .app.services.story_library import story_result_from_file

    return story_result_from_file(story_file)


def _extract_web_story_body(text: str) -> tuple[str, str]:
    from .app.services.story_library import extract_web_story_body

    return extract_web_story_body(text)


def _safe_story_file(story_path: str):
    from .app.services.story_library import safe_story_file

    return safe_story_file(story_path)


def _parse_shot_limit(value) -> int:
    return drama_video_runtime.parse_shot_limit(value)


def _parse_video_stage_drafts(value) -> dict[str, str]:
    return drama_video_runtime.parse_video_stage_drafts(value)


def _merge_video_stage_drafts(result: WorkflowResult, stage_drafts: dict[str, str]) -> WorkflowResult:
    return drama_video_runtime.merge_video_stage_drafts(result, stage_drafts)


def _deepseek_v4pro_settings():
    return drama_video_runtime.deepseek_v4pro_settings(settings)


def _format_video_stage_context(stage_drafts: dict[str, str]) -> str:
    return drama_video_runtime.format_video_stage_context(stage_drafts)


def _build_video_stage_prompt(result: WorkflowResult, stage: str, stage_drafts: dict[str, str]) -> str:
    return drama_video_runtime.build_video_stage_prompt(result, stage, stage_drafts)


def _run_video_stage_deepagent(
    story_path: str,
    stage: str,
    stage_drafts: dict[str, str],
    current_draft: str = "",
    human_feedback: str = "",
) -> dict:
    return drama_video_runtime.run_video_stage_deepagent(
        dependencies,
        story_path,
        stage,
        stage_drafts,
        current_draft=current_draft,
        human_feedback=human_feedback,
    )


def _generate_video_stage_draft(story_path: str, stage: str, stage_drafts: dict[str, str]) -> dict:
    return drama_video_runtime.generate_video_stage_draft(
        dependencies,
        story_path,
        stage,
        stage_drafts,
    )


def _new_video_run_id(prefix: str) -> str:
    return drama_video_runtime.new_video_run_id(prefix)


def _start_drama_video_spec(story_path: str, shot_limit: int, stage_drafts: dict[str, str]) -> str:
    return drama_video_runtime.start_drama_video_spec(
        runtime_state,
        story_path,
        shot_limit,
        stage_drafts,
    )


def _next_video_deepagent_stage(spec: dict) -> str | None:
    return drama_video_runtime.next_video_deepagent_stage(spec)


def _assert_video_deepagent_previous_stages_confirmed(spec: dict, stage: str) -> None:
    drama_video_runtime.assert_video_deepagent_previous_stages_confirmed(spec, stage)


def _session_to_spec(session):
    return drama_video_runtime.session_to_spec(session)


def _persist_video_deepagent_session(run_id: str, spec: dict, status: str, error: str = ""):
    return drama_video_runtime.persist_video_deepagent_session(
        dependencies,
        run_id,
        spec,
        status,
        error=error,
    )


def _record_drama_stage_version(
    run_id: str,
    stage: str,
    content: str,
    event: str,
    *,
    human_feedback: str = "",
    metadata: dict | None = None,
):
    return drama_video_runtime.record_drama_stage_version(
        dependencies,
        run_id,
        stage,
        content,
        event,
        human_feedback=human_feedback,
        metadata=metadata,
    )


def _get_video_deepagent_spec(run_id: str) -> dict | None:
    return drama_video_runtime.get_video_deepagent_spec(dependencies, runtime_state, run_id)


def _infrastructure_status() -> dict:
    return drama_video_runtime.infrastructure_status(dependencies)


async def _generate_video_deepagent_stage_in_background(run_id: str, stage: str) -> None:
    await drama_video_runtime.generate_video_deepagent_stage_in_background(
        dependencies,
        runtime_state,
        run_id,
        stage,
    )


def _drama_video_payload(
    story_path: str,
    shot_limit: int,
    stage_drafts: dict[str, str] | None = None,
    emit=None,
) -> dict:
    return drama_video_runtime.drama_video_payload(
        dependencies,
        story_path,
        shot_limit,
        stage_drafts=stage_drafts,
        emit=emit,
    )


async def _execute_drama_video_in_background(
    run_id: str,
    story_path: str,
    shot_limit: int,
    stage_drafts: dict[str, str] | None = None,
):
    await drama_video_runtime.execute_drama_video_in_background(
        dependencies,
        runtime_state,
        run_id,
        story_path,
        shot_limit,
        stage_drafts=stage_drafts,
    )


async def _execute_in_background(
    run_id: str,
    pipeline: Pipeline,
    topic: str | None,
    genre: str | None,
    chapters: int = 1,
):
    await execute_pipeline_in_background(
        runtime_state,
        run_id,
        pipeline,
        topic,
        genre,
        chapters,
    )


for _name in (
    "_run_video_stage_deepagent",
    "_generate_video_stage_draft",
):
    globals()[_name]._runtime_delegate = True
