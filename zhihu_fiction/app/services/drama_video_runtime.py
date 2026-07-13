"""Runtime service for short-drama video production APIs."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import HTTPException

from ...core.config import APP_ROOT
from ...core.llm import create_llm
from ...drama import DramaAdapter, DramaExporter
from ...drama.video import VideoJobStore, create_video_provider
from ...workspace.models import DramaVideoJob
from ..drama_video_stages import (
    DEEPAGENT_STAGES,
    STAGE_LABELS,
    TEXT_STAGE_INSTRUCTIONS,
    assert_previous_stages_confirmed,
    next_unconfirmed_stage,
    parse_shot_limit,
    parse_stage_drafts,
)
from ..legacy_compat import runtime_server_attr, server_path_attr
from . import drama_video_execution, drama_video_sessions, drama_video_stage_generation
from .drama_video_queue import create_video_queue
from .infrastructure import infrastructure_status as build_infrastructure_status

logger = logging.getLogger("zhihu_fiction.server")

VIDEO_STAGE_DRAFT_LABELS = STAGE_LABELS
VIDEO_DEEPAGENT_STAGES = DEEPAGENT_STAGES
VIDEO_TEXT_STAGE_INSTRUCTIONS = TEXT_STAGE_INSTRUCTIONS


def app_root():
    return server_path_attr("APP_ROOT", APP_ROOT)


def create_background_task(coro):
    asyncio_module = runtime_server_attr("asyncio", asyncio)
    return asyncio_module.create_task(coro)


def enqueue_video_task(job_id: str, submit):
    queue = create_video_queue()
    return queue.enqueue(job_id, submit)


def parse_video_stage_drafts(value) -> dict[str, str]:
    return parse_stage_drafts(value)


def merge_video_stage_drafts(result, stage_drafts: dict[str, str]):
    return drama_video_execution.merge_stage_drafts_into_result(
        result,
        stage_drafts,
        VIDEO_STAGE_DRAFT_LABELS,
    )


def deepseek_v4pro_settings(settings):
    return drama_video_stage_generation.deepseek_v4pro_settings(settings)


def format_video_stage_context(stage_drafts: dict[str, str]) -> str:
    return drama_video_stage_generation.format_stage_context(stage_drafts)


def build_video_stage_prompt(result, stage: str, stage_drafts: dict[str, str]) -> str:
    return drama_video_stage_generation.build_stage_prompt(result, stage, stage_drafts)


def run_video_stage_deepagent(
    dependencies,
    story_path: str,
    stage: str,
    stage_drafts: dict[str, str],
    current_draft: str = "",
    human_feedback: str = "",
) -> dict:
    override = runtime_server_attr("_run_video_stage_deepagent")
    if override is not None:
        return override(
            story_path,
            stage,
            stage_drafts,
            current_draft=current_draft,
            human_feedback=human_feedback,
        )
    return drama_video_stage_generation.run_stage_deepagent(
        dependencies,
        story_path,
        stage,
        stage_drafts,
        current_draft=current_draft,
        human_feedback=human_feedback,
        compat_attr=runtime_server_attr,
    )


def generate_video_stage_draft(
    dependencies,
    story_path: str,
    stage: str,
    stage_drafts: dict[str, str],
) -> dict:
    override = runtime_server_attr("_generate_video_stage_draft")
    if override is not None:
        return override(story_path, stage, stage_drafts)
    return run_video_stage_deepagent(dependencies, story_path, stage, stage_drafts)


def new_video_run_id(prefix: str) -> str:
    return prefix + "_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def start_drama_video_spec(
    state,
    story_path: str,
    shot_limit: int,
    stage_drafts: dict[str, str],
    dependencies=None,
    project_id: str = "",
) -> str:
    return drama_video_execution.start_video_run_spec(
        state,
        story_path,
        shot_limit,
        stage_drafts,
        dependencies=dependencies,
        project_id=project_id,
        id_factory=new_video_run_id,
    )


def start_deepagent_video_loop(
    dependencies,
    state,
    story_path: str,
    shot_limit: int,
    stage_drafts: dict[str, str] | None = None,
    project_id: str = "",
) -> dict:
    return __import__(
        "zhihu_fiction.app.services.drama_video_deepagent_flow",
        fromlist=["start_deepagent_video_loop"],
    ).start_deepagent_video_loop(
        dependencies,
        state,
        story_path=story_path,
        project_id=project_id,
        shot_limit=shot_limit,
        stage_drafts=stage_drafts or {},
        model_runner=lambda stage, context: generate_video_stage_draft(
            dependencies,
            story_path,
            stage,
            context.get("stage_drafts") or {},
        ),
        id_factory=new_video_run_id,
    )


def next_video_deepagent_stage(spec: dict) -> str | None:
    return next_unconfirmed_stage(spec)


def assert_video_deepagent_previous_stages_confirmed(spec: dict, stage: str) -> None:
    assert_previous_stages_confirmed(spec, stage)


def session_to_spec(session) -> dict:
    return drama_video_sessions.session_to_spec(session)


def persist_video_deepagent_session(
    dependencies,
    run_id: str,
    spec: dict,
    status: str,
    error: str = "",
):
    return drama_video_sessions.persist_session(
        dependencies,
        run_id,
        spec,
        status,
        error=error,
    )


def record_drama_stage_version(
    dependencies,
    run_id: str,
    stage: str,
    content: str,
    event: str,
    *,
    project_id: str = "",
    human_feedback: str = "",
    metadata: dict | None = None,
):
    return drama_video_sessions.record_stage_version(
        dependencies,
        run_id,
        stage,
        content,
        event,
        project_id=project_id,
        human_feedback=human_feedback,
        metadata=metadata,
    )


def get_video_deepagent_spec(dependencies, state, run_id: str) -> dict | None:
    return drama_video_sessions.get_session_spec(dependencies, state, run_id)


def latest_video_deepagent_session_for_story(dependencies, story_path: str):
    sessions = [
        session
        for session in dependencies.workspace_repo.list_drama_sessions()
        if session.story_path == story_path
    ]
    return sessions[0] if sessions else None


def infrastructure_status(dependencies) -> dict:
    return build_infrastructure_status(dependencies)


async def generate_video_deepagent_stage_in_background(
    dependencies,
    state,
    run_id: str,
    stage: str,
) -> None:
    loop = asyncio.get_event_loop()
    try:
        spec = get_video_deepagent_spec(dependencies, state, run_id)
        if spec is None:
            return
        draft = await loop.run_in_executor(
            None,
            lambda: generate_video_stage_draft(
                dependencies,
                spec["story_path"],
                stage,
                spec.get("stage_drafts") or {},
            ),
        )
        spec = get_video_deepagent_spec(dependencies, state, run_id)
        if spec is None:
            return
        spec["pending_stage"] = stage
        spec.setdefault("drafts", {})[stage] = draft["content"]
        record_drama_stage_version(
            dependencies,
            run_id,
            stage,
            draft["content"],
            "draft",
            project_id=spec.get("project_id") or "",
            metadata={"events": draft.get("events", [])},
        )
        drama_video_sessions.store_session_spec(dependencies, state, run_id, spec, "awaiting_confirmation")
    except Exception as exc:
        spec = get_video_deepagent_spec(dependencies, state, run_id) or {}
        spec["pending_stage"] = stage
        drama_video_sessions.store_session_spec(dependencies, state, run_id, spec, "failed", error=str(exc))
        logger.exception("DeepAgent background stage failed: run_id=%s stage=%s", run_id, stage)
    finally:
        state.video_deepagent_stage_tasks.pop(run_id, None)


def drama_video_payload(
    dependencies,
    story_path: str,
    shot_limit: int,
    stage_drafts: dict[str, str] | None = None,
    emit=None,
) -> dict:
    settings = runtime_server_attr("settings", dependencies.settings)
    llm_factory = runtime_server_attr("create_llm", create_llm)
    adapter_cls = runtime_server_attr("DramaAdapter", DramaAdapter)
    exporter_cls = runtime_server_attr("DramaExporter", DramaExporter)
    provider_factory = runtime_server_attr("create_video_provider", create_video_provider)
    job_store_cls = runtime_server_attr("VideoJobStore", VideoJobStore)
    proxy_dependencies = type("VideoExecutionDeps", (), {"settings": settings})()
    return drama_video_execution.create_video_tasks_payload(
        proxy_dependencies,
        story_path,
        shot_limit,
        stage_drafts=stage_drafts,
        emit=emit,
        stage_labels=VIDEO_STAGE_DRAFT_LABELS,
        llm_factory=llm_factory,
        adapter_cls=adapter_cls,
        exporter_cls=exporter_cls,
        provider_factory=provider_factory,
        job_store_cls=job_store_cls,
    )


async def execute_drama_video_in_background(
    dependencies,
    state,
    run_id: str,
    story_path: str,
    shot_limit: int,
    stage_drafts: dict[str, str] | None = None,
    project_id: str = "",
):
    await drama_video_execution.execute_video_run_in_background(
        dependencies,
        state,
        run_id,
        story_path,
        shot_limit,
        stage_drafts=stage_drafts,
        project_id=project_id,
        payload_factory=drama_video_payload,
    )


def export_drama_video_project_package(dependencies, state, run_id: str) -> dict:
    return drama_video_execution.export_project_package(
        dependencies,
        state,
        run_id,
        infrastructure_factory=infrastructure_status,
        app_root=app_root,
    )


def refresh_drama_video_run_jobs(dependencies, run_id: str) -> dict:
    provider_factory = runtime_server_attr("create_video_provider", create_video_provider)
    job_store_cls = runtime_server_attr("VideoJobStore", VideoJobStore)
    return drama_video_execution.refresh_video_run_jobs(
        dependencies,
        run_id,
        provider_factory=provider_factory,
        job_store_cls=job_store_cls,
    )


def list_drama_video_runs_for_story(dependencies, story_path: str) -> dict:
    job_store_cls = runtime_server_attr("VideoJobStore", VideoJobStore)
    return drama_video_execution.list_video_runs_for_story(
        dependencies,
        story_path,
        job_store_cls=job_store_cls,
    )


def retry_drama_video_run_job(dependencies, state, run_id: str, shot_id: str) -> dict:
    provider_factory = runtime_server_attr("create_video_provider", create_video_provider)
    job_store_cls = runtime_server_attr("VideoJobStore", VideoJobStore)
    retry_job_id = new_video_run_id("video_retry")
    run = dependencies.workspace_repo.get_drama_video_run(run_id)
    state.video_retry_jobs[retry_job_id] = {
        "id": retry_job_id,
        "run_id": run_id,
        "shot_id": shot_id,
        "status": "queued",
    }
    drama_video_execution.save_video_job(
        dependencies,
        DramaVideoJob(
            id=retry_job_id,
            kind="retry_shot",
            run_id=run_id,
            shot_id=shot_id,
            status="queued",
            payload={"shot_id": shot_id},
        ),
    )
    drama_video_execution.ensure_video_retry_estimated_cost(
        dependencies,
        run,
        retry_job_id,
        shot_id,
    )
    enqueue_video_task(
        retry_job_id,
        lambda: create_background_task(drama_video_execution.execute_video_retry_job(
            dependencies,
            state,
            retry_job_id,
            run_id,
            shot_id,
            provider_factory=provider_factory,
            job_store_cls=job_store_cls,
        )),
    )
    return {
        "status": "queued",
        "retry_job_id": retry_job_id,
        "retry_url": f"/api/drama-video/retry/{retry_job_id}",
        "run_id": run_id,
        "shot_id": shot_id,
    }


def get_drama_video_retry_job(state, retry_job_id: str) -> dict | None:
    return state.video_retry_jobs.get(retry_job_id)
