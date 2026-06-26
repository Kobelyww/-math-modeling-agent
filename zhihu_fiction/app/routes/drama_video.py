"""Short-drama video production API routes."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from ..request_parsing import json_body, require_stripped, stripped_or_none
from ..sse import queue_streaming_response
from ...drama import DramaAdapterError
from ...drama.stage_assets import estimate_video_cost
from ...drama.video import DramaVideoError, VideoJobStore
from ..services import drama_video_deepagent_flow as deepagent_flow
from ..services import drama_video_jobs
from ..services import drama_video_runtime as runtime
from ..services.drama_video_recovery import drama_video_recovery_summary

router = APIRouter()


@router.post("/api/drama-video")
async def create_drama_video_tasks(req: Request):
    deps = req.app.state.dependencies
    body = await json_body(req)
    story_path = require_stripped(body, "story_path")
    shot_limit = runtime.parse_shot_limit(body.get("shot_limit", 1))
    stage_drafts = runtime.parse_video_stage_drafts(body.get("stage_drafts"))
    _require_video_cost_confirmation(deps.workspace_repo, shot_limit, body)

    try:
        return runtime.drama_video_payload(deps, story_path, shot_limit, stage_drafts=stage_drafts)
    except DramaAdapterError as exc:
        raise HTTPException(500, f"短剧 Prompt 生成失败: {exc}") from exc
    except DramaVideoError as exc:
        raise HTTPException(502, f"百炼视频任务提交失败: {exc}") from exc


@router.post("/api/drama-video/stage")
async def create_drama_video_stage(req: Request):
    deps = req.app.state.dependencies
    body = await json_body(req)
    story_path = require_stripped(body, "story_path")
    stage = stripped_or_none(body, "stage") or ""
    stage_drafts = runtime.parse_video_stage_drafts(body.get("stage_drafts"))

    try:
        return runtime.generate_video_stage_draft(deps, story_path, stage, stage_drafts)
    except DramaAdapterError as exc:
        raise HTTPException(500, f"短剧阶段创作失败: {exc}") from exc


@router.post("/api/drama-video/deepagent/run")
async def start_drama_video_deepagent_run(req: Request):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    body = await json_body(req)
    story_path = require_stripped(body, "story_path")
    project_id = stripped_or_none(body, "project_id") or ""

    shot_limit = runtime.parse_shot_limit(body.get("shot_limit", 1))
    stage_drafts = runtime.parse_video_stage_drafts(body.get("stage_drafts"))
    return deepagent_flow.start_deepagent_run(
        deps,
        state,
        story_path=story_path,
        project_id=project_id,
        shot_limit=shot_limit,
        stage_drafts=stage_drafts,
        id_factory=runtime.new_video_run_id,
    )


@router.post("/api/drama-video/deepagent/advance")
async def advance_drama_video_deepagent(req: Request):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    body = await json_body(req)
    run_id = require_stripped(body, "run_id")
    background = bool(body.get("background"))
    return deepagent_flow.advance_deepagent(
        deps,
        state,
        run_id,
        background=background,
        generator=lambda story_path, stage, stage_drafts: runtime.generate_video_stage_draft(
            deps,
            story_path,
            stage,
            stage_drafts,
        ),
        background_scheduler=runtime.create_background_task,
        background_coro_factory=lambda next_run_id, stage: runtime.generate_video_deepagent_stage_in_background(
            deps,
            state,
            next_run_id,
            stage,
        ),
    )


@router.post("/api/drama-video/deepagent/loop")
async def start_drama_video_deepagent_loop(req: Request):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    body = await json_body(req)
    story_path = require_stripped(body, "story_path")
    shot_limit = runtime.parse_shot_limit(body.get("shot_limit", 1))
    project_id = stripped_or_none(body, "project_id") or ""
    stage_drafts = runtime.parse_video_stage_drafts(body.get("stage_drafts"))
    return runtime.start_deepagent_video_loop(
        deps,
        state,
        story_path,
        shot_limit,
        stage_drafts,
        project_id=project_id,
    )


@router.post("/api/drama-video/deepagent/confirm")
async def confirm_drama_video_deepagent_stage(req: Request):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    body = await json_body(req)
    run_id = require_stripped(body, "run_id")
    stage = stripped_or_none(body, "stage") or ""
    content = stripped_or_none(body, "content") or ""
    _require_deepagent_video_cost_confirmation(deps, state, run_id, stage, body)
    return deepagent_flow.confirm_stage(
        deps,
        state,
        run_id,
        stage,
        content,
        video_starter=_guarded_video_starter(deps, body),
    )


@router.post("/api/drama-video/deepagent/revise")
async def revise_drama_video_deepagent_stage(req: Request):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    body = await json_body(req)
    run_id = require_stripped(body, "run_id")
    stage = stripped_or_none(body, "stage") or ""
    current_draft = stripped_or_none(body, "current_draft") or ""
    feedback = stripped_or_none(body, "feedback") or ""
    return deepagent_flow.revise_stage(
        deps,
        state,
        run_id,
        stage,
        current_draft=current_draft,
        feedback=feedback,
        reviser=lambda story_path, next_stage, stage_drafts, current_draft="", human_feedback="": (
            runtime.run_video_stage_deepagent(
                deps,
                story_path,
                next_stage,
                stage_drafts,
                current_draft=current_draft,
                human_feedback=human_feedback,
            )
        ),
    )


@router.post("/api/drama-video/deepagent/retry")
async def retry_drama_video_deepagent_stage(req: Request):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    body = await json_body(req)
    run_id = require_stripped(body, "run_id")
    return deepagent_flow.retry_failed_stage(
        deps,
        state,
        run_id,
        generator=lambda story_path, stage, stage_drafts: runtime.generate_video_stage_draft(
            deps,
            story_path,
            stage,
            stage_drafts,
        ),
    )


@router.get("/api/drama-video/deepagent/latest")
async def get_latest_drama_video_deepagent_session(
    req: Request,
    story_path: str = Query(...),
):
    deps = req.app.state.dependencies
    session = runtime.latest_video_deepagent_session_for_story(deps, story_path)
    if session is None:
        return {
            "session": None,
            "next_stage": None,
            "versions": [],
            "infrastructure": runtime.infrastructure_status(deps),
        }
    versions = deps.workspace_repo.list_drama_stage_versions(session.id)
    return {
        "session": session.to_dict(),
        "next_stage": runtime.next_video_deepagent_stage(runtime.session_to_spec(session)),
        "versions": [version.to_dict() for version in versions],
        "infrastructure": runtime.infrastructure_status(deps),
    }


@router.get("/api/drama-video/deepagent/{run_id}")
async def get_drama_video_deepagent_session(req: Request, run_id: str):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    session = deps.workspace_repo.get_drama_session(run_id)
    if session is None:
        spec = state.video_deepagent_specs.get(run_id)
        if spec is None:
            raise HTTPException(404, "DeepAgent 会话未找到")
        session = runtime.persist_video_deepagent_session(deps, run_id, spec, "started")
    return {
        "session": session.to_dict(),
        "next_stage": runtime.next_video_deepagent_stage(runtime.session_to_spec(session)),
        "infrastructure": runtime.infrastructure_status(deps),
    }


@router.get("/api/drama-video/deepagent/{run_id}/versions")
async def list_drama_video_deepagent_versions(
    req: Request,
    run_id: str,
    stage: str | None = Query(None),
):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    if deps.workspace_repo.get_drama_session(run_id) is None and run_id not in state.video_deepagent_specs:
        raise HTTPException(404, "DeepAgent 会话未找到")
    if stage and stage not in runtime.VIDEO_DEEPAGENT_STAGES:
        raise HTTPException(400, "stage must be one of script, style, plot, character_refs, storyboard")
    versions = deps.workspace_repo.list_drama_stage_versions(run_id, stage=stage)
    return {"run_id": run_id, "versions": [version.to_dict() for version in versions]}


@router.get("/api/drama-video/infrastructure")
async def get_drama_video_infrastructure(req: Request):
    return runtime.infrastructure_status(req.app.state.dependencies)


@router.get("/api/drama-video/recovery")
async def get_drama_video_recovery(req: Request):
    repo = req.app.state.dependencies.workspace_repo
    return drama_video_recovery_summary(repo)


@router.post("/api/drama-video/package/export")
async def export_drama_video_project_package(req: Request):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    body = await json_body(req)
    run_id = require_stripped(body, "run_id")
    return runtime.export_drama_video_project_package(deps, state, run_id)


@router.post("/api/drama-video/run")
async def start_drama_video_run(req: Request):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    body = await json_body(req)
    story_path = require_stripped(body, "story_path")
    project_id = stripped_or_none(body, "project_id") or ""

    shot_limit = runtime.parse_shot_limit(body.get("shot_limit", 1))
    _require_video_cost_confirmation(deps.workspace_repo, shot_limit, body)
    stage_drafts = runtime.parse_video_stage_drafts(body.get("stage_drafts"))
    run_id = runtime.start_drama_video_spec(
        state,
        story_path,
        shot_limit,
        stage_drafts,
        dependencies=deps,
        project_id=project_id,
    )
    return {"run_id": run_id, "status": "started"}


@router.get("/api/drama-video/runs")
async def list_drama_video_runs(req: Request, story_path: str = Query(...)):
    deps = req.app.state.dependencies
    return runtime.list_drama_video_runs_for_story(deps, story_path)


@router.get("/api/drama-video/jobs")
async def list_drama_video_jobs(req: Request, run_id: str | None = Query(None)):
    deps = req.app.state.dependencies
    return drama_video_jobs.list_drama_video_jobs(deps, run_id)


@router.post("/api/drama-video/run/{run_id}/refresh")
async def refresh_drama_video_run(req: Request, run_id: str):
    deps = req.app.state.dependencies
    return runtime.refresh_drama_video_run_jobs(deps, run_id)


@router.post("/api/drama-video/run/{run_id}/retry")
async def retry_drama_video_run_job(req: Request, run_id: str):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    body = await json_body(req)
    shot_id = require_stripped(body, "shot_id")
    run = deps.workspace_repo.get_drama_video_run(run_id)
    if run is None:
        raise HTTPException(404, "视频任务未找到")
    _require_retry_shot_exists(run, shot_id)
    _require_video_cost_confirmation(deps.workspace_repo, 1, body)
    return runtime.retry_drama_video_run_job(deps, state, run_id, shot_id)


@router.get("/api/drama-video/retry/{retry_job_id}")
async def get_drama_video_retry_job(req: Request, retry_job_id: str):
    state = req.app.state.runtime
    job = runtime.get_drama_video_retry_job(state, retry_job_id)
    if job is None:
        raise HTTPException(404, "镜头重试任务未找到")
    return job


@router.get("/api/drama-video/stream/{run_id}")
async def stream_drama_video_run(req: Request, run_id: str):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    queue = state.video_events.get(run_id)
    if queue is None:
        raise HTTPException(404, "视频任务未找到")

    spec = state.video_specs.get(run_id)
    if spec is not None:
        with state.video_lock:
            if not spec.get("started"):
                spec["started"] = True
                runtime.enqueue_video_task(
                    run_id,
                    lambda: runtime.create_background_task(runtime.execute_drama_video_in_background(
                        deps,
                        state,
                        run_id,
                        spec["story_path"],
                        spec["shot_limit"],
                        spec.get("stage_drafts") or {},
                        project_id=spec.get("project_id") or "",
                    )),
                )

    return queue_streaming_response(queue, event_types=("stage_update",))


def _require_retry_shot_exists(run, shot_id: str) -> None:
    if not run.jobs_path:
        raise HTTPException(400, "video run has no jobs_path")
    current_jobs = VideoJobStore(Path(run.jobs_path)).list()
    if not any(job.shot_id == shot_id for job in current_jobs):
        raise HTTPException(404, "镜头任务未找到")


def _require_deepagent_video_cost_confirmation(deps, state, run_id: str, stage: str, body: dict) -> None:
    if stage != "storyboard":
        return
    spec = runtime.get_video_deepagent_spec(deps, state, run_id)
    if spec is None:
        return
    if spec.get("video_run_id"):
        return
    content = stripped_or_none(body, "content") or (spec.get("drafts") or {}).get(stage, "").strip()
    if not content:
        return
    confirmed = set(spec.get("confirmed_stages") or [])
    required_previous = set(runtime.VIDEO_DEEPAGENT_STAGES) - {"storyboard"}
    if not required_previous.issubset(confirmed):
        return
    _require_video_cost_confirmation(deps.workspace_repo, int(spec.get("shot_limit") or 1), body)


def _guarded_video_starter(deps, body: dict):
    def start(state, story_path, shot_limit, stage_drafts, project_id=""):
        _require_video_cost_confirmation(deps.workspace_repo, shot_limit, body)
        return runtime.start_drama_video_spec(
            state,
            story_path,
            shot_limit,
            stage_drafts,
            dependencies=deps,
            project_id=project_id,
        )

    return start


def _require_video_cost_confirmation(repo, shot_count: int, body: dict) -> dict:
    guardrail = _video_cost_guardrail(repo, shot_count)
    _raise_if_cost_confirmation_required(guardrail, body)
    return guardrail


def _raise_if_cost_confirmation_required(guardrail: dict, body: dict) -> None:
    if guardrail["configured"] and not guardrail["within_budget"] and not _confirm_cost_requested(body):
        raise HTTPException(
            409,
            {
                "message": "video generation budget requires confirmation",
                "requires_confirmation": True,
                "cost_guardrail": guardrail,
            },
        )


def _video_cost_guardrail(repo, shot_count: int) -> dict:
    unit_price = _float_env("ZH_VIDEO_UNIT_PRICE_CNY", 0.0)
    daily_budget = _optional_float_env("ZH_DAILY_BUDGET_CNY")
    spent_today = _today_spend_cny(repo)
    estimate = estimate_video_cost(
        shot_count=shot_count,
        seconds_per_shot=6,
        unit_price_cny=unit_price,
    )
    configured = daily_budget is not None
    remaining = max(0.0, round((daily_budget or 0.0) - spent_today, 2)) if configured else 0.0
    within_budget = True if not configured else estimate["estimated_total_cny"] <= remaining
    return {
        "currency": "CNY",
        "billable_stage": "video",
        "estimate": estimate,
        "budget": {
            "daily_budget_cny": daily_budget or 0.0,
            "spent_today_cny": round(spent_today, 2),
            "remaining_today_cny": remaining,
        },
        "within_budget": within_budget,
        "configured": configured,
    }


def _today_spend_cny(repo) -> float:
    env_spend = _float_env("ZH_TODAY_SPEND_CNY", 0.0)
    today = datetime.now(timezone.utc).date().isoformat()
    ledger_spend = repo.sum_cost_ledger_entries_for_day(today)
    return round(env_spend + ledger_spend, 2)


def _confirm_cost_requested(body: dict) -> bool:
    return body.get("confirm_cost") is True


def _optional_float_env(name: str) -> float | None:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default
