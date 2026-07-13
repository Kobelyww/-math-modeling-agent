"""Short-drama video execution and packaging service."""
from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

from ...drama import DramaAdapter, DramaExporter
from ...drama.assets import create_asset_store
from ...drama.models import DramaShot
from ...drama.stage_assets import estimate_video_cost, normalize_stage_asset
from ...drama.video import VideoJobStore, create_video_provider
from ...core.llm import create_llm
from ...workspace.models import (
    CostLedgerEntry,
    DramaProjectPackage,
    DramaVideoJob,
    DramaVideoRun,
    VideoAsset,
    new_id,
    utc_now_iso,
)
from ..drama_video_stages import DEEPAGENT_STAGES
from .story_library import safe_story_file, story_result_from_file
from .drama_video_sessions import get_session_spec, persist_session
from .object_storage import create_object_storage


PROVIDER_STATUS_TO_NORMALIZED = {
    "PENDING": "polling",
    "RUNNING": "polling",
    "PROCESSING": "polling",
    "QUEUED": "polling",
    "SUCCEEDED": "succeeded",
    "SUCCESS": "succeeded",
    "FAILED": "failed",
    "ERROR": "failed",
    "CANCELED": "canceled",
    "CANCELLED": "canceled",
}


def default_video_run_id(prefix: str) -> str:
    return prefix + "_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def normalize_provider_video_status(status: str) -> str:
    normalized = PROVIDER_STATUS_TO_NORMALIZED.get(str(status or "").strip().upper())
    return normalized or "unknown"


def video_job_to_dict(job) -> dict:
    data = job.to_dict()
    raw_status = getattr(job, "status", data.get("status", ""))
    data["raw_status"] = raw_status
    data["normalized_status"] = normalize_provider_video_status(raw_status)
    return data


def summarize_video_job_states(jobs) -> dict:
    raw: dict[str, int] = {}
    normalized: dict[str, int] = {}
    for job in jobs:
        raw[job.status] = raw.get(job.status, 0) + 1
        state = normalize_provider_video_status(job.status)
        normalized[state] = normalized.get(state, 0) + 1
    return {
        "raw": raw,
        "normalized": normalized,
        "total": len(jobs),
        "terminal": normalized.get("succeeded", 0) + normalized.get("failed", 0) + normalized.get("canceled", 0),
    }


def start_video_run_spec(
    state,
    story_path: str,
    shot_limit: int,
    stage_drafts: dict[str, str],
    *,
    dependencies=None,
    project_id: str = "",
    id_factory: Callable[[str], str] = default_video_run_id,
) -> str:
    safe_story_file(story_path)
    run_id = id_factory("video")
    state.video_events[run_id] = asyncio.Queue()
    state.video_progress[run_id] = {"status": "starting"}
    state.video_specs[run_id] = {
        "story_path": story_path,
        "shot_limit": shot_limit,
        "stage_drafts": dict(stage_drafts),
        "project_id": project_id,
        "started": False,
    }
    saved_run = save_video_run(
        dependencies,
        DramaVideoRun(
            id=run_id,
            story_path=story_path,
            project_id=project_id,
            shot_limit=shot_limit,
            stage_drafts=dict(stage_drafts),
            status="queued",
        ),
    )
    save_video_job(
        dependencies,
        DramaVideoJob(
            id=run_id,
            kind="generate_video",
            run_id=run_id,
            status="queued",
            payload={
                "story_path": story_path,
                "shot_limit": shot_limit,
                "stage_drafts": dict(stage_drafts),
                "project_id": project_id,
            },
        ),
    )
    ensure_video_run_estimated_cost(dependencies, saved_run)
    return run_id


def save_video_run(dependencies, run: DramaVideoRun) -> DramaVideoRun | None:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None:
        return None
    return repo.save_drama_video_run(run)


def update_video_run(dependencies, run_id: str, changes: dict) -> DramaVideoRun | None:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None:
        return None
    existing = repo.get_drama_video_run(run_id)
    now = utc_now_iso()
    if existing is None:
        base = DramaVideoRun(
            id=run_id,
            story_path=str(changes.get("story_path") or ""),
            project_id=str(changes.get("project_id") or ""),
            shot_limit=int(changes.get("shot_limit") or 1),
            stage_drafts=dict(changes.get("stage_drafts") or {}),
        )
        repo.save_drama_video_run(base)
    else:
        if "project_id" in changes and not changes.get("project_id") and existing.project_id:
            changes = {**changes, "project_id": existing.project_id}
    return repo.update_drama_video_run(run_id, {**changes, "updated_at": now})


def save_video_job(dependencies, job: DramaVideoJob) -> DramaVideoJob | None:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None:
        return None
    return repo.save_drama_video_job(job)


def ensure_video_run_estimated_cost(dependencies, run: DramaVideoRun | None) -> CostLedgerEntry | None:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None or run is None or not run.project_id:
        return None
    entry_id = _video_run_estimated_cost_entry_id(run.id)
    existing = repo.cost_ledger_entries.get(entry_id)
    if existing is not None:
        return existing
    estimate = estimate_video_cost(
        shot_count=run.shot_limit,
        seconds_per_shot=6,
        unit_price_cny=_float_env("ZH_VIDEO_UNIT_PRICE_CNY", 0.0),
    )
    return repo.save_cost_ledger_entry(CostLedgerEntry(
        id=entry_id,
        project_id=run.project_id,
        release_id=f"video_run_{run.id}",
        package_id=f"video_run_{run.id}",
        run_id=run.id,
        source="video_run_estimate",
        amount_cny=float(estimate["estimated_total_cny"]),
        estimated=True,
        metadata={
            "billable_stage": "video",
            "estimate": estimate,
            "story_path": run.story_path,
        },
    ))


def ensure_video_retry_estimated_cost(
    dependencies,
    run: DramaVideoRun | None,
    retry_job_id: str,
    shot_id: str,
) -> CostLedgerEntry | None:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None or run is None or not run.project_id:
        return None
    entry_id = _video_retry_estimated_cost_entry_id(retry_job_id)
    existing = repo.cost_ledger_entries.get(entry_id)
    if existing is not None:
        return existing
    estimate = estimate_video_cost(
        shot_count=1,
        seconds_per_shot=6,
        unit_price_cny=_float_env("ZH_VIDEO_UNIT_PRICE_CNY", 0.0),
    )
    return repo.save_cost_ledger_entry(CostLedgerEntry(
        id=entry_id,
        project_id=run.project_id,
        release_id=f"video_retry_{retry_job_id}",
        package_id=f"{run.id}:{shot_id}",
        run_id=run.id,
        source="video_retry_estimate",
        amount_cny=float(estimate["estimated_total_cny"]),
        estimated=True,
        metadata={
            "billable_stage": "video",
            "estimate": estimate,
            "retry_job_id": retry_job_id,
            "shot_id": shot_id,
            "story_path": run.story_path,
        },
    ))


def update_video_job(dependencies, job_id: str, changes: dict) -> DramaVideoJob | None:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None:
        return None
    existing = repo.get_drama_video_job(job_id)
    if existing is None:
        return None
    return repo.update_drama_video_job(job_id, {**changes, "updated_at": utc_now_iso()})


def refresh_video_run_jobs(
    dependencies,
    run_id: str,
    *,
    provider_factory=create_video_provider,
    job_store_cls=VideoJobStore,
    job_id_factory=new_id,
) -> dict:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None:
        raise HTTPException(500, "workspace repository is not configured")
    run = repo.get_drama_video_run(run_id)
    if run is None:
        raise HTTPException(404, "视频任务未找到")
    if not run.jobs_path:
        raise HTTPException(400, "video run has no jobs_path")

    refresh_job_id = job_id_factory("video_refresh")
    save_video_job(
        dependencies,
        DramaVideoJob(
            id=refresh_job_id,
            kind="refresh_status",
            run_id=run_id,
            status="running",
            payload={"run_id": run_id, "jobs_path": run.jobs_path},
        ),
    )
    store = job_store_cls(Path(run.jobs_path))
    try:
        jobs = store.list()
        provider = provider_factory()
        refreshed = [
            provider.get_job(job.provider_job_id, shot_id=job.shot_id)
            for job in jobs
        ]
        store.replace_all(refreshed)
        record_provider_actual_costs(repo, run, refreshed)
    except Exception as exc:
        update_video_job(
            dependencies,
            refresh_job_id,
            {"status": "failed", "error": str(exc)},
        )
        raise

    state_summary = summarize_video_job_states(refreshed)
    summary = state_summary["raw"]
    normalized_summary = state_summary["normalized"]
    failed_count = normalized_summary.get("failed", 0)
    succeeded_count = normalized_summary.get("succeeded", 0)
    if refreshed and succeeded_count == len(refreshed):
        run_status = "completed"
        response_status = "completed"
        error = ""
    elif failed_count:
        run_status = "failed"
        response_status = "partial_failed" if succeeded_count else "failed"
        error = f"{failed_count} video job(s) failed"
    else:
        run_status = "running"
        response_status = "running"
        error = ""

    updated = update_video_run(
        dependencies,
        run_id,
        {
            "status": run_status,
            "submitted_count": len(refreshed),
            "error": error,
        },
    )
    response = {
        "run_id": run_id,
        "status": response_status,
        "run": updated.to_dict() if updated is not None else None,
        "summary": summary,
        "state_summary": state_summary,
        "jobs": [video_job_to_dict(job) for job in refreshed],
    }
    update_video_job(
        dependencies,
        refresh_job_id,
        {
            "status": "failed" if response_status == "failed" else "completed",
            "result": response,
            "error": error,
        },
    )
    return response


def load_shot_from_package(package_dir: str, shot_id: str) -> DramaShot:
    shot_table_path = Path(package_dir) / "镜头表.json"
    if not shot_table_path.exists():
        raise HTTPException(400, "video package has no shot table")
    try:
        rows = json.loads(shot_table_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(400, "video package shot table is invalid") from exc
    if not isinstance(rows, list):
        raise HTTPException(400, "video package shot table is invalid")
    for row in rows:
        if isinstance(row, dict) and row.get("id") == shot_id:
            data = dict(row)
            data.pop("episode_title", None)
            try:
                return DramaShot(**data)
            except TypeError as exc:
                raise HTTPException(400, "video package shot data is invalid") from exc
    raise HTTPException(404, "镜头未找到")


def retry_video_run_job(
    dependencies,
    run_id: str,
    shot_id: str,
    *,
    provider_factory=create_video_provider,
    job_store_cls=VideoJobStore,
) -> dict:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None:
        raise HTTPException(500, "workspace repository is not configured")
    run = repo.get_drama_video_run(run_id)
    if run is None:
        raise HTTPException(404, "视频任务未找到")
    if not run.jobs_path:
        raise HTTPException(400, "video run has no jobs_path")
    if not run.package_dir:
        raise HTTPException(400, "video run has no package_dir")

    store = job_store_cls(Path(run.jobs_path))
    current_jobs = store.list()
    if current_jobs and not any(job.shot_id == shot_id for job in current_jobs):
        raise HTTPException(404, "镜头任务未找到")

    shot = load_shot_from_package(run.package_dir, shot_id)
    retried_job = provider_factory().submit_shot(shot)
    next_jobs = [job for job in current_jobs if job.shot_id != shot_id]
    next_jobs.append(retried_job)
    store.replace_all(next_jobs)
    summary = summarize_video_jobs(next_jobs)
    updated = update_video_run(
        dependencies,
        run_id,
        {
            "status": "running",
            "submitted_count": len(next_jobs),
            "error": "",
        },
    )
    return {
        "run_id": run_id,
        "shot_id": shot_id,
        "status": "retried",
        "run": updated.to_dict() if updated is not None else None,
        "summary": summary,
        "state_summary": summarize_video_job_states(next_jobs),
        "job": video_job_to_dict(retried_job),
        "jobs": [video_job_to_dict(job) for job in next_jobs],
    }


async def execute_video_retry_job(
    dependencies,
    state,
    retry_job_id: str,
    run_id: str,
    shot_id: str,
    *,
    provider_factory=create_video_provider,
    job_store_cls=VideoJobStore,
) -> None:
    state.video_retry_jobs[retry_job_id] = {
        **state.video_retry_jobs.get(retry_job_id, {}),
        "id": retry_job_id,
        "run_id": run_id,
        "shot_id": shot_id,
        "status": "running",
        "error": "",
    }
    update_video_job(dependencies, retry_job_id, {"status": "running", "error": ""})
    queue = state.video_events.get(run_id)
    if queue is not None:
        await queue.put({"type": "stage_update", "data": {
            "run_id": run_id,
            "stage": "video",
            "status": "running",
            "message": f"镜头 {shot_id} 重试已开始",
            "progress": 90,
        }})
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: retry_video_run_job(
                dependencies,
                run_id,
                shot_id,
                provider_factory=provider_factory,
                job_store_cls=job_store_cls,
            ),
        )
        state.video_retry_jobs[retry_job_id] = {
            **state.video_retry_jobs.get(retry_job_id, {}),
            "status": "completed",
            "result": result,
            "error": "",
        }
        update_video_job(
            dependencies,
            retry_job_id,
            {"status": "completed", "result": result, "error": ""},
        )
        if queue is not None:
            await queue.put({"type": "stage_update", "data": {
                "run_id": run_id,
                "stage": "video",
                "status": "running",
                "message": f"镜头 {shot_id} 已重新提交",
                "progress": 95,
                "job": result.get("job"),
            }})
    except Exception as exc:
        state.video_retry_jobs[retry_job_id] = {
            **state.video_retry_jobs.get(retry_job_id, {}),
            "status": "failed",
            "error": str(exc),
        }
        update_video_job(dependencies, retry_job_id, {"status": "failed", "error": str(exc)})
        if queue is not None:
            await queue.put({"type": "stage_update", "data": {
                "run_id": run_id,
                "stage": "video",
                "status": "failed",
                "message": f"镜头 {shot_id} 重试失败：{exc}",
                "progress": -1,
            }})


def summarize_video_jobs(jobs) -> dict[str, int]:
    return summarize_video_job_states(jobs)["raw"]


def record_provider_actual_costs(repo, run: DramaVideoRun, jobs) -> list[CostLedgerEntry]:
    entries: list[CostLedgerEntry] = []
    project_id = str(getattr(run, "project_id", "") or "")
    if not project_id:
        return entries

    for job in jobs:
        amount = provider_job_actual_cost_cny(job)
        if amount <= 0:
            continue
        provider = str(getattr(job, "provider", "") or "provider").strip().lower() or "provider"
        provider_job_id = str(getattr(job, "provider_job_id", "") or "").strip()
        if not provider_job_id:
            continue
        shot_id = str(getattr(job, "shot_id", "") or "").strip()
        entry = CostLedgerEntry(
            id=_provider_cost_entry_id(provider, provider_job_id),
            project_id=project_id,
            release_id=f"provider_{provider_job_id}",
            package_id=f"{run.id}:{shot_id or provider_job_id}",
            run_id=run.id,
            source=f"provider_{provider}",
            amount_cny=amount,
            estimated=False,
            metadata=_provider_cost_metadata(job),
        )
        entries.append(repo.save_cost_ledger_entry(entry))
    return entries


def provider_job_actual_cost_cny(job) -> float:
    data = job.to_dict() if hasattr(job, "to_dict") else {}
    raw_response = data.get("raw_response") if isinstance(data.get("raw_response"), dict) else {}
    for candidate in (data, raw_response):
        for path in (
            ("billing", "amount_cny"),
            ("cost", "amount_cny"),
            ("usage", "cost_cny"),
            ("usage", "amount_cny"),
        ):
            amount = _nested_money(candidate, path)
            if amount > 0:
                return amount
    return 0.0


def _nested_money(data: dict, path: tuple[str, str]) -> float:
    if not isinstance(data, dict):
        return 0.0
    parent = data.get(path[0])
    if not isinstance(parent, dict):
        return 0.0
    try:
        return round(float(parent.get(path[1]) or 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


def _provider_cost_entry_id(provider: str, provider_job_id: str) -> str:
    safe_provider = "".join(char if char.isalnum() else "_" for char in provider)
    safe_job_id = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in provider_job_id
    )
    return f"cost_provider_{safe_provider}_{safe_job_id}"


def _video_run_estimated_cost_entry_id(run_id: str) -> str:
    safe_run_id = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in str(run_id or "")
    )
    return f"cost_video_run_estimate_{safe_run_id}"


def _video_retry_estimated_cost_entry_id(retry_job_id: str) -> str:
    safe_retry_job_id = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in str(retry_job_id or "")
    )
    return f"cost_video_retry_estimate_{safe_retry_job_id}"


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


def _provider_cost_metadata(job) -> dict:
    data = job.to_dict() if hasattr(job, "to_dict") else {}
    raw_response = data.get("raw_response") if isinstance(data.get("raw_response"), dict) else {}
    metadata = {
        "provider": str(data.get("provider") or ""),
        "provider_job_id": str(data.get("provider_job_id") or ""),
        "shot_id": str(data.get("shot_id") or ""),
        "status": str(data.get("status") or ""),
        "video_url": str(data.get("video_url") or ""),
    }
    for key in ("billing", "cost", "usage"):
        if isinstance(raw_response.get(key), dict):
            metadata[key] = raw_response[key]
        elif isinstance(data.get(key), dict):
            metadata[key] = data[key]
    return metadata


def video_run_history_item(run: DramaVideoRun, *, job_store_cls=VideoJobStore) -> dict:
    jobs = []
    if run.jobs_path:
        jobs = job_store_cls(Path(run.jobs_path)).list()
    return {
        "run": run.to_dict(),
        "summary": summarize_video_jobs(jobs),
        "state_summary": summarize_video_job_states(jobs),
        "jobs": [video_job_to_dict(job) for job in jobs],
    }


def list_video_runs_for_story(
    dependencies,
    story_path: str,
    *,
    job_store_cls=VideoJobStore,
) -> dict:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None:
        raise HTTPException(500, "workspace repository is not configured")
    runs = [
        run
        for run in repo.list_drama_video_runs()
        if run.story_path == story_path
    ]
    items = [
        video_run_history_item(run, job_store_cls=job_store_cls)
        for run in runs
    ]
    return {
        "story_path": story_path,
        "latest": items[0] if items else None,
        "runs": items,
    }


def merge_stage_drafts_into_result(result, stage_drafts: dict[str, str], stage_labels: dict[str, str]):
    if not stage_drafts:
        return result

    sections = ["【短剧工作台确认稿】"]
    for stage_id, label in stage_labels.items():
        draft = stage_drafts.get(stage_id)
        if draft:
            sections.append(f"【{label}】\n{draft}")

    synthesis_parts = []
    if result.synthesis:
        synthesis_parts.append(result.synthesis)
    synthesis_parts.append("\n\n".join(sections))

    from ...fiction.orchestrator import WorkflowResult

    return WorkflowResult(
        topic=result.topic,
        genre=result.genre,
        topic_analysis=result.topic_analysis,
        outline=result.outline,
        draft=result.draft,
        polished=result.polished,
        review=result.review,
        synthesis="\n\n".join(synthesis_parts),
    )


def create_video_tasks_payload(
    dependencies,
    story_path: str,
    shot_limit: int,
    stage_drafts: dict[str, str] | None = None,
    emit=None,
    *,
    stage_labels: dict[str, str] | None = None,
    llm_factory=create_llm,
    adapter_cls=DramaAdapter,
    exporter_cls=DramaExporter,
    provider_factory=create_video_provider,
    job_store_cls=VideoJobStore,
) -> dict:
    from ..drama_video_stages import STAGE_LABELS

    labels = stage_labels or STAGE_LABELS

    def emit_stage(stage: str, status: str, message: str, progress: int, **extra):
        if emit is not None:
            emit(stage, status, message, progress, **extra)

    emit_stage("script", "running", "读取小说并准备转化为短剧剧本...", 5, story_path=story_path)
    story_file = safe_story_file(story_path)
    result = story_result_from_file(story_file)
    result = merge_stage_drafts_into_result(result, stage_drafts or {}, labels)
    emit_stage(
        "script",
        "completed",
        f"已完成《{result.topic}》的剧本输入整理",
        15,
        topic=result.topic,
        genre=result.genre,
    )

    emit_stage("style", "running", "生成短剧风格、角色一致性和镜头语言...", 25)
    llm = llm_factory(dependencies.settings, temperature=0.3)
    project = adapter_cls(llm).adapt_result(result)
    emit_stage(
        "style",
        "completed",
        "已锁定视觉风格和一致性设定",
        35,
        title=project.title,
        character_count=len(project.characters),
        location_count=len(project.locations),
    )

    emit_stage("plot", "running", "整理短剧剧情结构、反转点和集尾悬念...", 40)
    emit_stage(
        "plot",
        "completed",
        f"已生成 {project.episode_count} 集剧情设计",
        50,
        episode_count=project.episode_count,
        adaptation_notes=project.adaptation_notes,
    )

    emit_stage("character_refs", "running", "生成人物参考图 Prompt 和角色一致性规则...", 55)
    emit_stage(
        "character_refs",
        "completed",
        f"已生成 {len(project.characters)} 个角色参考 Prompt",
        62,
        character_count=len(project.characters),
    )

    emit_stage("storyboard", "running", "生成分镜、镜头动作和视频 Prompt 包...", 65)
    shots = [shot for episode in project.episodes for shot in episode.shots]
    selected_shots = shots[:shot_limit]
    emit_stage(
        "storyboard",
        "completed",
        f"已生成 {len(shots)} 个分镜，准备提交 {len(selected_shots)} 个镜头",
        72,
        title=project.title,
        episode_count=project.episode_count,
        shot_count=len(shots),
        selected_count=len(selected_shots),
    )

    emit_stage("storyboard", "running", "导出短剧 Prompt 包...", 75)
    output_dir = exporter_cls().export(project)
    jobs_path = output_dir / "video_jobs.jsonl"
    emit_stage(
        "storyboard",
        "completed",
        "Prompt 包已导出",
        80,
        package_dir=str(output_dir),
        jobs_path=str(jobs_path),
    )

    emit_stage(
        "video",
        "running",
        f"准备提交 {len(selected_shots)} 个百炼视频任务...",
        82,
        shot_count=len(selected_shots),
    )
    provider = provider_factory()
    store = job_store_cls(jobs_path)
    jobs = []
    for index, shot in enumerate(selected_shots, start=1):
        progress = 82 + int(index / max(len(selected_shots), 1) * 13)
        emit_stage(
            "video",
            "running",
            f"提交镜头 {index}/{len(selected_shots)}：{shot.id}",
            progress,
            shot_id=shot.id,
            shot_index=index,
            shot_count=len(selected_shots),
        )
        job = provider.submit_shot(shot)
        store.append(job)
        job_data = video_job_to_dict(job)
        jobs.append(job_data)
        emit_stage(
            "video",
            "running",
            f"镜头 {shot.id} 已提交，任务 ID：{job.provider_job_id}",
            progress,
            shot_id=shot.id,
            provider_job_id=job.provider_job_id,
            job=job_data,
        )
    emit_stage("video", "completed", "百炼视频任务提交完成", 95, submitted_count=len(jobs))
    manifest_payload = {
        "story_path": story_path,
        "package_dir": str(output_dir),
        "jobs_path": str(jobs_path),
        "submitted_count": len(jobs),
        "shot_limit": shot_limit,
        "jobs": jobs,
    }
    manifest_uri = create_object_storage().put_text(
        f"drama-video/{output_dir.name}/manifest.json",
        json.dumps(manifest_payload, ensure_ascii=False),
    )

    return {
        "status": "submitted",
        "story_path": story_path,
        "package_dir": str(output_dir),
        "jobs_path": str(jobs_path),
        "manifest_uri": manifest_uri,
        "submitted_count": len(jobs),
        "shot_limit": shot_limit,
        "jobs": jobs,
    }


async def execute_video_run_in_background(
    dependencies,
    state,
    run_id: str,
    story_path: str,
    shot_limit: int,
    stage_drafts: dict[str, str] | None = None,
    project_id: str = "",
    *,
    payload_factory=create_video_tasks_payload,
):
    queue = state.video_events.setdefault(run_id, asyncio.Queue())
    loop = asyncio.get_event_loop()
    update_video_run(
        dependencies,
        run_id,
        {
            "story_path": story_path,
            "project_id": project_id,
            "shot_limit": shot_limit,
            "stage_drafts": dict(stage_drafts or {}),
            "status": "running",
        },
    )
    update_video_job(dependencies, run_id, {"status": "running", "error": ""})

    def emit_sync(stage: str, status: str, message: str, progress: int, **extra):
        asyncio.run_coroutine_threadsafe(queue.put({
            "type": "stage_update",
            "data": {
                "run_id": run_id,
                "stage": stage,
                "status": status,
                "message": message,
                "progress": progress,
                **extra,
            },
        }), loop)

    try:
        await queue.put({"type": "stage_update", "data": {
            "run_id": run_id,
            "stage": "start",
            "status": "running",
            "message": "短剧视频生产启动中...",
            "progress": 0,
        }})
        payload = await loop.run_in_executor(
            None,
            lambda: payload_factory(
                dependencies,
                story_path,
                shot_limit,
                stage_drafts=stage_drafts,
                emit=emit_sync,
            ),
        )
        await queue.put({"type": "complete", "data": {
            "run_id": run_id,
            **payload,
            "status": "completed",
            "message": "视频任务已提交",
            "progress": 100,
        }})
        update_video_run(
            dependencies,
            run_id,
            {
                "status": "completed",
                "story_path": story_path,
                "project_id": project_id,
                "shot_limit": shot_limit,
                "stage_drafts": dict(stage_drafts or {}),
                "submitted_count": int(payload.get("submitted_count") or 0),
                "jobs_path": str(payload.get("jobs_path") or ""),
                "package_dir": str(payload.get("package_dir") or ""),
                "error": "",
            },
        )
        update_video_job(
            dependencies,
            run_id,
            {"status": "completed", "result": payload, "error": ""},
        )
        register_video_assets_from_payload(dependencies, run_id, story_path, payload)
    except Exception as exc:
        await queue.put({"type": "complete", "data": {
            "run_id": run_id,
            "status": "failed",
            "message": str(exc),
            "progress": 0,
            "error": str(exc),
        }})
        update_video_run(
            dependencies,
            run_id,
            {
                "status": "failed",
                "story_path": story_path,
                "project_id": project_id,
                "shot_limit": shot_limit,
                "stage_drafts": dict(stage_drafts or {}),
                "error": str(exc),
            },
        )
        update_video_job(
            dependencies,
            run_id,
            {"status": "failed", "error": str(exc)},
        )
    finally:
        state.video_progress[run_id] = {"status": "done"}


def register_video_assets_from_payload(dependencies, run_id: str, story_path: str, payload: dict) -> int:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None:
        return 0
    run = repo.get_drama_video_run(run_id)
    project_id = getattr(run, "project_id", "") if run is not None else ""
    if not project_id:
        story = next((item for item in repo.list_stories() if item.body_path == story_path), None)
        project_id = getattr(story, "project_id", "") if story is not None else ""
    if not project_id:
        return 0

    saved = 0
    for job in payload.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        video_url = str(job.get("video_url") or "")
        if not video_url:
            continue
        asset_id = new_id("asset")
        repo.save_video_asset(
            VideoAsset(
                id=asset_id,
                project_id=project_id,
                run_id=run_id,
                kind="video",
                uri=video_url,
                content_type="video/mp4",
                provider=str(job.get("provider") or "bailian"),
                shot_id=str(job.get("shot_id") or ""),
                metadata={
                    "provider_job_id": str(job.get("provider_job_id") or ""),
                    "status": str(job.get("status") or ""),
                },
            )
        )
        saved += 1
    return saved


def export_project_package(
    dependencies,
    state,
    run_id: str,
    *,
    infrastructure_factory,
    app_root,
) -> dict:
    from fastapi import HTTPException

    spec = get_session_spec(dependencies, state, run_id)
    session = dependencies.workspace_repo.get_drama_session(run_id)
    if spec is None and session is None:
        raise HTTPException(404, "DeepAgent 会话未找到")
    if session is None:
        session = persist_session(dependencies, run_id, spec or {}, "started")
    versions = dependencies.workspace_repo.list_drama_stage_versions(run_id)
    structured_assets = {
        stage: normalize_stage_asset(stage, content)
        for stage, content in session.stage_drafts.items()
        if stage in DEEPAGENT_STAGES
    }
    payload = {
        "run_id": run_id,
        "story_path": session.story_path,
        "shot_limit": session.shot_limit,
        "status": session.status,
        "stage_drafts": session.stage_drafts,
        "structured_assets": structured_assets,
        "drafts": session.drafts,
        "confirmed_stages": session.confirmed_stages,
        "pending_stage": session.pending_stage,
        "video_run_id": session.video_run_id,
        "versions": [version.to_dict() for version in versions],
        "infrastructure": infrastructure_factory(dependencies),
        "exported_at": utc_now_iso(),
    }
    key = f"drama-projects/{run_id}/package.json"
    asset_store = create_asset_store(local_root=app_root() / "data" / "workspace" / "assets")
    asset = asset_store.put_text(
        key,
        json.dumps(payload, ensure_ascii=False, indent=2),
        content_type="application/json",
        metadata={"run_id": run_id, "kind": "drama_project_package"},
    )
    package = DramaProjectPackage(
        id=new_id("drama_pkg"),
        run_id=run_id,
        story_path=session.story_path,
        package_uri=asset.uri,
        stage_count=len(session.stage_drafts),
        version_count=len(versions),
        video_run_id=session.video_run_id,
        provider=session.provider,
        metadata={"asset_key": asset.key, "asset_backend": asset_store.backend},
    )
    dependencies.workspace_repo.save_drama_project_package(package)
    return {
        "package": package.to_dict(),
        "asset": asset.to_dict(),
        "payload": payload,
    }
