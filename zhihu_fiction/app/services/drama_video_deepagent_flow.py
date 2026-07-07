"""DeepAgent workflow state transitions for short-drama production."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException

from ..drama_video_stages import (
    DEEPAGENT_STAGES,
    STAGE_LABELS,
    assert_previous_stages_confirmed,
    next_unconfirmed_stage,
)
from .drama_video_execution import default_video_run_id, start_video_run_spec
from .drama_video_sessions import (
    get_session_spec,
    persist_session,
    record_agent_trace,
    record_operation_log,
    record_stage_version,
    store_session_spec,
    update_consistency_profile_from_stage,
)
from .story_library import safe_story_file


def start_deepagent_run(
    dependencies,
    state,
    *,
    story_path: str,
    project_id: str = "",
    shot_limit: int,
    stage_drafts: dict[str, str],
    id_factory: Callable[[str], str] = default_video_run_id,
) -> dict:
    safe_story_file(story_path)
    confirmed_stages = [stage for stage in DEEPAGENT_STAGES if stage in stage_drafts]
    run_id = id_factory("deepagent")
    spec = {
        "story_path": story_path,
        "project_id": project_id,
        "shot_limit": shot_limit,
        "stage_drafts": stage_drafts,
        "drafts": {},
        "confirmed_stages": confirmed_stages,
        "pending_stage": None,
        "video_run_id": "",
    }
    store_session_spec(dependencies, state, run_id, spec, "started")
    record_operation_log(
        dependencies,
        project_id,
        "system",
        "start_session",
        "drama_session",
        run_id,
        metadata={"story_path": story_path, "shot_limit": shot_limit},
    )
    return {
        "run_id": run_id,
        "status": "started",
        "agent": "deepagent",
        "next_stage": next_unconfirmed_stage(spec),
    }


def start_deepagent_video_loop(
    dependencies,
    state,
    *,
    story_path: str,
    project_id: str = "",
    shot_limit: int,
    stage_drafts: dict[str, str] | None = None,
    model_runner: Callable,
    id_factory: Callable[[str], str] = default_video_run_id,
) -> dict:
    safe_story_file(story_path)
    initial_drafts = dict(stage_drafts or {})
    confirmed_stages = [stage for stage in DEEPAGENT_STAGES if stage in initial_drafts]
    run_id = id_factory("deepagent")
    spec = {
        "story_path": story_path,
        "project_id": project_id,
        "shot_limit": shot_limit,
        "stage_drafts": initial_drafts,
        "drafts": {},
        "confirmed_stages": confirmed_stages,
        "pending_stage": None,
        "video_run_id": "",
    }
    stage = next_unconfirmed_stage(spec)
    if stage is None:
        store_session_spec(dependencies, state, run_id, spec, "completed")
        record_operation_log(
            dependencies,
            project_id,
            "system",
            "start_session",
            "drama_session",
            run_id,
            metadata={"story_path": story_path, "shot_limit": shot_limit},
        )
        return {
            "run_id": run_id,
            "status": "completed",
            "agent": "deepagent",
            "pending_stage": "",
            "draft": "",
        }

    raw_draft = model_runner(stage, {
        "story_path": story_path,
        "shot_limit": shot_limit,
        "stage_drafts": initial_drafts,
    })
    if isinstance(raw_draft, dict):
        content = str(raw_draft.get("content") or "")
        events = raw_draft.get("events") or []
    else:
        content = str(raw_draft)
        events = []
    spec["pending_stage"] = stage
    spec.setdefault("drafts", {})[stage] = content
    version = record_stage_version(
        dependencies,
        run_id,
        stage,
        content,
        "draft",
        project_id=project_id,
        metadata={"events": events},
    )
    record_agent_trace(
        dependencies,
        run_id,
        stage,
        "draft_created",
        content,
        project_id=project_id,
        version_id=version.id,
        events=events,
    )
    store_session_spec(dependencies, state, run_id, spec, "awaiting_confirmation")
    record_operation_log(
        dependencies,
        project_id,
        "system",
        "start_session",
        "drama_session",
        run_id,
        metadata={"story_path": story_path, "shot_limit": shot_limit},
    )
    return {
        "run_id": run_id,
        "status": "awaiting_confirmation",
        "agent": "deepagent",
        "pending_stage": stage,
        "stage": stage,
        "label": STAGE_LABELS[stage],
        "draft": content,
        "content": content,
        "events": events,
    }


def advance_deepagent(
    dependencies,
    state,
    run_id: str,
    *,
    background: bool = False,
    generator: Callable | None = None,
    background_scheduler: Callable | None = None,
    background_coro_factory: Callable | None = None,
) -> dict:
    spec = get_session_spec(dependencies, state, run_id)
    if spec is None:
        raise HTTPException(404, "DeepAgent 会话未找到")
    session = dependencies.workspace_repo.get_drama_session(run_id)
    if session is not None and session.status == "failed":
        raise HTTPException(409, "DeepAgent 会话已失败，请先重试失败阶段")

    stage = next_unconfirmed_stage(spec)
    if stage is None:
        video_run_id = spec.get("video_run_id") or ""
        return {
            "run_id": run_id,
            "status": "completed",
            "agent": "deepagent",
            "stage": "video",
            "video_run_id": video_run_id,
            "stream_url": f"/api/drama-video/stream/{video_run_id}" if video_run_id else "",
        }

    assert_previous_stages_confirmed(spec, stage)
    cached_content = (spec.get("drafts") or {}).get(stage, "").strip()
    if spec.get("pending_stage") == stage and cached_content:
        return {
            "run_id": run_id,
            "status": "awaiting_confirmation",
            "stage": stage,
            "label": STAGE_LABELS[stage],
            "model": "deepseek-v4-pro",
            "agent": "deepagent",
            "content": cached_content,
            "events": [],
        }

    if background:
        running_task = state.video_deepagent_stage_tasks.get(run_id)
        if running_task is None or running_task.done():
            spec["pending_stage"] = stage
            store_session_spec(dependencies, state, run_id, spec, "generating")
            if background_scheduler is not None and background_coro_factory is not None:
                state.video_deepagent_stage_tasks[run_id] = background_scheduler(
                    background_coro_factory(run_id, stage)
                )
        elif session is None or session.status != "generating":
            persist_session(dependencies, run_id, spec, "generating")
        return {
            "run_id": run_id,
            "status": "generating",
            "stage": stage,
            "label": STAGE_LABELS[stage],
            "model": "deepseek-v4-pro",
            "agent": "deepagent",
            "poll_url": f"/api/drama-video/deepagent/{run_id}",
            "versions_url": f"/api/drama-video/deepagent/{run_id}/versions",
        }

    if generator is None:
        raise RuntimeError("generator is required for foreground advance")
    draft = generator(spec["story_path"], stage, spec.get("stage_drafts") or {})
    spec["pending_stage"] = stage
    spec.setdefault("drafts", {})[stage] = draft["content"]
    version = record_stage_version(
        dependencies,
        run_id,
        stage,
        draft["content"],
        "draft",
        project_id=spec.get("project_id") or "",
        metadata={"events": draft.get("events", [])},
    )
    record_agent_trace(
        dependencies,
        run_id,
        stage,
        "draft_created",
        draft["content"],
        project_id=spec.get("project_id") or "",
        version_id=version.id,
        events=draft.get("events", []),
    )
    store_session_spec(dependencies, state, run_id, spec, "awaiting_confirmation")
    return {
        **draft,
        "run_id": run_id,
        "status": "awaiting_confirmation",
        "agent": "deepagent",
    }


def confirm_stage(
    dependencies,
    state,
    run_id: str,
    stage: str,
    content: str,
    *,
    video_starter: Callable = start_video_run_spec,
) -> dict:
    if stage not in DEEPAGENT_STAGES:
        raise HTTPException(400, "stage must be one of script, style, plot, character_refs, storyboard")
    spec = get_session_spec(dependencies, state, run_id)
    if spec is None:
        raise HTTPException(404, "DeepAgent 会话未找到")

    assert_previous_stages_confirmed(spec, stage)
    if not content:
        content = (spec.get("drafts") or {}).get(stage, "").strip()
    if not content:
        raise HTTPException(400, "content is required")

    spec.setdefault("stage_drafts", {})[stage] = content[:12000]
    confirmed = spec.setdefault("confirmed_stages", [])
    if stage not in confirmed:
        confirmed.append(stage)
    if spec.get("pending_stage") == stage:
        spec["pending_stage"] = None

    version = record_stage_version(
        dependencies,
        run_id,
        stage,
        content,
        "confirmation",
        project_id=spec.get("project_id") or "",
    )
    record_agent_trace(
        dependencies,
        run_id,
        stage,
        "human_confirmed",
        content,
        project_id=spec.get("project_id") or "",
        version_id=version.id,
        human_decision={"decision": "confirm"},
    )
    update_consistency_profile_from_stage(
        dependencies,
        run_id,
        stage,
        content,
        version,
    )
    record_operation_log(
        dependencies,
        spec.get("project_id") or "",
        "human",
        "confirm_stage",
        "stage_version",
        version.id,
        metadata={"run_id": run_id, "stage": stage},
    )
    next_stage = next_unconfirmed_stage(spec)
    if next_stage is None:
        video_run_id = spec.get("video_run_id")
        if not video_run_id:
            video_run_id = video_starter(
                state,
                spec["story_path"],
                spec["shot_limit"],
                spec.get("stage_drafts") or {},
                project_id=spec.get("project_id") or "",
            )
            spec["video_run_id"] = video_run_id
        store_session_spec(dependencies, state, run_id, spec, "video_started")
        return {
            "run_id": run_id,
            "status": "video_started",
            "agent": "deepagent",
            "stage": "video",
            "video_run_id": video_run_id,
            "stream_url": f"/api/drama-video/stream/{video_run_id}",
        }

    store_session_spec(dependencies, state, run_id, spec, "ready_for_next_stage")
    return {
        "run_id": run_id,
        "status": "ready_for_next_stage",
        "agent": "deepagent",
        "stage": stage,
        "next_stage": next_stage,
    }


def revise_stage(
    dependencies,
    state,
    run_id: str,
    stage: str,
    *,
    current_draft: str,
    feedback: str,
    reviser: Callable,
) -> dict:
    if stage not in DEEPAGENT_STAGES:
        raise HTTPException(400, "stage must be one of script, style, plot, character_refs, storyboard")
    if not feedback:
        raise HTTPException(400, "feedback is required")
    spec = get_session_spec(dependencies, state, run_id)
    if spec is None:
        raise HTTPException(404, "DeepAgent 会话未找到")

    assert_previous_stages_confirmed(spec, stage)
    if not current_draft:
        current_draft = (spec.get("drafts") or {}).get(stage, "").strip()
    draft = reviser(
        spec["story_path"],
        stage,
        spec.get("stage_drafts") or {},
        current_draft=current_draft,
        human_feedback=feedback,
    )
    spec["pending_stage"] = stage
    spec.setdefault("drafts", {})[stage] = draft["content"]
    version = record_stage_version(
        dependencies,
        run_id,
        stage,
        draft["content"],
        "revision",
        project_id=spec.get("project_id") or "",
        human_feedback=feedback,
        metadata={"events": draft.get("events", [])},
    )
    record_agent_trace(
        dependencies,
        run_id,
        stage,
        "human_revision_requested",
        draft["content"],
        project_id=spec.get("project_id") or "",
        version_id=version.id,
        events=draft.get("events", []),
        feedback=feedback,
        human_decision={"decision": "revise", "feedback": feedback},
    )
    completed_rework = _complete_rework_request(spec, stage, feedback, version.id)
    store_session_spec(dependencies, state, run_id, spec, "awaiting_confirmation")
    response = {
        **draft,
        "run_id": run_id,
        "status": "awaiting_confirmation",
        "agent": "deepagent",
    }
    if completed_rework is not None:
        response["rework_request"] = completed_rework
    return response


def retry_failed_stage(
    dependencies,
    state,
    run_id: str,
    *,
    generator: Callable,
) -> dict:
    spec = get_session_spec(dependencies, state, run_id)
    if spec is None:
        raise HTTPException(404, "DeepAgent 会话未找到")

    session = dependencies.workspace_repo.get_drama_session(run_id)
    if session is None or session.status != "failed":
        raise HTTPException(409, "只有失败的 DeepAgent 会话可以重试")

    stage = str(spec.get("pending_stage") or "") or next_unconfirmed_stage(spec)
    if stage not in DEEPAGENT_STAGES:
        raise HTTPException(409, "失败会话没有可重试的阶段")
    if stage in set(spec.get("confirmed_stages") or []):
        raise HTTPException(409, f"{STAGE_LABELS[stage]}已确认，不能重试覆盖")
    assert_previous_stages_confirmed(spec, stage)

    try:
        draft = generator(spec["story_path"], stage, spec.get("stage_drafts") or {})
        if isinstance(draft, dict):
            content = str(draft.get("content") or "")
            events = draft.get("events") or []
        else:
            content = str(draft)
            events = []
        if not content.strip():
            raise RuntimeError("DeepAgent 重试未返回内容")

        spec["pending_stage"] = stage
        spec.setdefault("drafts", {})[stage] = content
        version = record_stage_version(
            dependencies,
            run_id,
            stage,
            content,
            "restore",
            project_id=spec.get("project_id") or "",
            metadata={"events": events, "retry": True},
        )
        record_agent_trace(
            dependencies,
            run_id,
            stage,
            "draft_created",
            content,
            project_id=spec.get("project_id") or "",
            version_id=version.id,
            events=events,
            metadata={"retry": True},
        )
        store_session_spec(dependencies, state, run_id, spec, "awaiting_confirmation")
        record_operation_log(
            dependencies,
            spec.get("project_id") or "",
            "system",
            "recover_task",
            "drama_session",
            run_id,
            metadata={"run_id": run_id, "stage": stage},
        )
        return {
            "run_id": run_id,
            "status": "awaiting_confirmation",
            "stage": stage,
            "label": STAGE_LABELS[stage],
            "model": "deepseek-v4-pro",
            "agent": "deepagent",
            "content": content,
            "events": events,
        }
    except Exception as exc:
        spec["pending_stage"] = stage
        store_session_spec(dependencies, state, run_id, spec, "failed", error=str(exc))
        raise


def _complete_rework_request(spec: dict, stage: str, feedback: str, version_id: str) -> dict | None:
    for request in spec.get("rework_requests") or []:
        if request.get("status") != "requested":
            continue
        if request.get("stage") != stage:
            continue
        instruction = str(request.get("instruction") or request.get("comment") or "")
        if instruction and instruction != feedback:
            continue
        request["status"] = "completed"
        request["completed_stage_version_id"] = version_id
        return request
    return None
