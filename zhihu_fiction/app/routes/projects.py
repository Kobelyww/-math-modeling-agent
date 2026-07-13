"""Project workspace API routes."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ...drama.stage_assets import estimate_video_cost
from ...workspace.models import (
    CostLedgerEntry,
    REVIEW_STATUSES,
    REVIEW_TARGET_KINDS,
    ProjectRelease,
    Review,
    new_id,
)
from ..request_parsing import json_body, require_stripped

router = APIRouter()

PACKAGE_READY_STAGES = ("script", "style", "plot", "character_refs", "storyboard")


@router.get("/api/projects")
async def list_projects(req: Request):
    repo = req.app.state.dependencies.workspace_repo
    return {"projects": [project.to_dict() for project in repo.list_projects()]}


@router.get("/api/projects/{project_id}")
async def get_project_workspace(req: Request, project_id: str):
    repo = req.app.state.dependencies.workspace_repo
    project = repo.get_project(project_id)
    if project is None:
        raise _not_found()
    return _workspace_payload(repo, project_id, project)


@router.get("/api/projects/{project_id}/release/package/download")
async def download_project_release_package(req: Request, project_id: str):
    repo = req.app.state.dependencies.workspace_repo
    project = repo.get_project(project_id)
    if project is None:
        raise _not_found()
    package = _project_release_package_record(repo, project_id)
    if package is None:
        raise HTTPException(status_code=404, detail="release package not found")
    package_path = _local_package_asset_path(repo, package)
    if package_path is None:
        raise HTTPException(status_code=409, detail="release package is not locally downloadable")
    return FileResponse(
        package_path,
        media_type="application/json",
        filename=f"{project_id}_release_package.json",
    )


@router.post("/api/projects/{project_id}/release/confirm")
async def confirm_project_release(req: Request, project_id: str):
    repo = req.app.state.dependencies.workspace_repo
    project = repo.get_project(project_id)
    if project is None:
        raise _not_found()
    package = _project_release_package_record(repo, project_id)
    if package is None:
        raise HTTPException(status_code=404, detail="release package not found")
    existing_release = repo.get_project_release_for_package(project_id, package.id)
    if existing_release is not None:
        if package.status != "confirmed":
            package = repo.update_drama_project_package(package.id, {"status": "confirmed"})
        existing_payload = _workspace_payload(repo, project_id, project)
        _ensure_release_cost_ledger_entry(repo, project_id, existing_release, existing_payload)
        return _release_confirmation_payload(repo, project_id, project, package, existing_release)

    current_payload = _workspace_payload(repo, project_id, project)
    current_manifest = current_payload["release_manifest"]
    if not current_manifest.get("release_ready"):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "release is blocked",
                "release_blockers": current_manifest.get("release_blockers") or [],
            },
        )
    confirmed = repo.update_drama_project_package(package.id, {"status": "confirmed"})
    confirmed_payload = _workspace_payload(repo, project_id, project)
    release = repo.save_project_release(ProjectRelease(
        id=new_id("release"),
        project_id=project_id,
        package_id=confirmed.id,
        run_id=confirmed.run_id,
        status="confirmed",
        reviewer="human",
        metadata=_release_audit_metadata(confirmed_payload),
    ))
    _ensure_release_cost_ledger_entry(repo, project_id, release, confirmed_payload)
    return _release_confirmation_payload(repo, project_id, project, confirmed, release)


def _release_confirmation_payload(repo, project_id: str, project, package, release: ProjectRelease) -> dict:
    payload = _workspace_payload(repo, project_id, project)
    final_metadata = _release_audit_metadata(payload)
    if release.metadata != final_metadata:
        release = repo.save_project_release(ProjectRelease(
            id=release.id,
            project_id=release.project_id,
            package_id=release.package_id,
            run_id=release.run_id,
            status=release.status,
            reviewer=release.reviewer,
            created_at=release.created_at,
            metadata=final_metadata,
        ))
        payload = _workspace_payload(repo, project_id, project)
    payload["release_confirmation"] = {
        "project_id": project_id,
        "package_id": package.id,
        "run_id": package.run_id,
        "status": package.status,
        "release_id": release.id,
    }
    payload["cost_ledger"] = [
        entry.to_dict()
        for entry in repo.list_cost_ledger_entries(project_id=project_id, release_id=release.id)
    ]
    return payload


@router.get("/api/projects/{project_id}/release/history/{release_id}")
async def get_project_release_audit_detail(req: Request, project_id: str, release_id: str):
    repo = req.app.state.dependencies.workspace_repo
    project = repo.get_project(project_id)
    if project is None:
        raise _not_found()
    release = repo.get_project_release(release_id)
    if release is None or release.project_id != project_id:
        raise HTTPException(status_code=404, detail="release not found")
    package = repo.get_drama_project_package(release.package_id)
    metadata = release.metadata if isinstance(release.metadata, dict) else {}
    manifest_snapshot = metadata.get("manifest_snapshot") or {}
    package_snapshot = metadata.get("package_snapshot") or {}
    review_summary = metadata.get("review_summary") or {}
    cost_ledger = repo.list_cost_ledger_entries(project_id=project_id, release_id=release.id)
    return {
        "project": project.to_dict(),
        "release": release.to_dict(),
        "package": _project_package_payload(repo, package) if package is not None else None,
        "manifest_snapshot": manifest_snapshot,
        "package_snapshot": package_snapshot,
        "review_summary": review_summary,
        "cost_ledger": [entry.to_dict() for entry in cost_ledger],
        "cost_ledger_summary": _cost_ledger_summary(cost_ledger),
        "integrity": _project_release_integrity(repo, release, package, package_snapshot),
    }


@router.post("/api/projects/{project_id}/assets/reviews")
async def create_project_asset_review(req: Request, project_id: str):
    repo = req.app.state.dependencies.workspace_repo
    project = repo.get_project(project_id)
    if project is None:
        raise _not_found()

    body = await json_body(req)
    target_kind = require_stripped(body, "target_kind")
    target_id = require_stripped(body, "target_id")
    decision = require_stripped(body, "decision")
    comment = str(body.get("comment") or "").strip()
    metadata = body.get("metadata") or {}

    if target_kind not in REVIEW_TARGET_KINDS:
        raise HTTPException(status_code=400, detail="invalid review target kind")
    if decision not in REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail="invalid review decision")
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="metadata must be an object")
    metadata = {**metadata, "source": "project_asset_dialog"}

    assets = repo.project_assets(project_id)
    if not any(
        asset.get("review_target_kind") == target_kind and asset.get("id") == target_id
        for asset in assets
    ):
        raise HTTPException(status_code=404, detail="asset not found")

    review = repo.save_review(Review(
        id=new_id("review"),
        project_id=project_id,
        target_kind=target_kind,
        target_id=target_id,
        reviewer=str(body.get("reviewer") or "human").strip() or "human",
        decision=decision,
        comment=comment,
        metadata=metadata,
    ))
    rework_request = _create_rework_request(
        repo,
        project_id,
        review,
        assets,
    )
    payload = _workspace_payload(repo, project_id, project)
    payload["review"] = review.to_dict()
    if rework_request is not None:
        payload["rework_request"] = rework_request
    return payload


def _workspace_payload(repo, project_id: str, project) -> dict:
    stories = [story.to_dict() for story in repo.list_stories(project_id)]
    video_assets = [asset.to_dict() for asset in repo.list_video_assets(project_id)]
    assets = repo.project_assets(project_id)
    assets_summary = repo.project_asset_summary(project_id)
    drama_sessions = _project_drama_sessions(repo, project_id)
    rework_requests = _project_rework_requests(repo, project_id)
    consistency_profiles = [
        profile.to_dict() for profile in repo.list_consistency_profiles(project_id)
    ]
    production_status = _project_production_status(
        repo,
        stories,
        assets,
        assets_summary,
        drama_sessions,
        rework_requests,
    )
    stage_summary = _project_stage_summary(drama_sessions)
    return {
        "project": project.to_dict(),
        "stories": stories,
        "video_assets": video_assets,
        "assets": assets,
        "assets_summary": assets_summary,
        "drama_sessions": drama_sessions,
        "production_status": production_status,
        "stage_summary": stage_summary,
        "next_action": _project_stage_next_action(stage_summary),
        "release_manifest": _project_release_manifest(
            project,
            stories,
            assets_summary,
            drama_sessions,
            production_status,
        ),
        "release_history": [
            release.to_dict() for release in repo.list_project_releases(project_id)
        ],
        "operation_logs": [
            log.to_dict() for log in repo.list_operation_logs(project_id)
        ],
        "consistency_profiles": consistency_profiles,
        "latest_consistency_profile": (
            consistency_profiles[0] if consistency_profiles else None
        ),
        "rework_requests": rework_requests,
        "reviews": [review.to_dict() for review in repo.list_reviews(project_id)],
    }


def _project_stage_summary(drama_sessions: list[dict]) -> dict:
    if not drama_sessions:
        return {"pending_stage": "", "status": "not_started", "session_id": ""}
    session = drama_sessions[0]
    status = str(session.get("status") or "")
    pending_stage = str(session.get("pending_stage") or "")
    if not pending_stage and status == "ready_for_next_stage":
        pending_stage = _next_project_stage(session)
    return {
        "pending_stage": pending_stage,
        "status": status,
        "session_id": str(session.get("id") or ""),
    }


def _project_stage_next_action(stage_summary: dict) -> dict:
    status = stage_summary.get("status") or ""
    stage = stage_summary.get("pending_stage") or ""
    session_id = stage_summary.get("session_id") or ""
    if status == "awaiting_confirmation" and stage and session_id:
        return {
            "kind": "confirm_stage",
            "label": f"确认 {stage} 阶段",
            "target_id": session_id,
            "stage": stage,
        }
    if status == "ready_for_next_stage" and stage and session_id:
        return {
            "kind": "generate_stage",
            "label": f"生成 {stage} 阶段",
            "target_id": session_id,
            "stage": stage,
        }
    if status in {"generating", "running"}:
        return {
            "kind": "wait",
            "label": "等待生成完成",
            "target_id": session_id,
            "stage": stage,
        }
    return {
        "kind": "none",
        "label": "暂无待处理动作",
        "target_id": session_id,
        "stage": stage,
    }


def _create_rework_request(repo, project_id: str, review: Review, assets: list[dict]) -> dict | None:
    if review.decision != "changes_requested" or review.target_kind != "stage_version":
        return None
    asset = next(
        (
            item for item in assets
            if item.get("review_target_kind") == review.target_kind and item.get("id") == review.target_id
        ),
        None,
    )
    if asset is None:
        return None

    record = asset.get("record") or {}
    run_id = str(record.get("run_id") or "")
    stage = str(record.get("stage") or "")
    if not run_id or not stage:
        return None

    session = repo.get_drama_session(run_id)
    if session is None:
        return None

    instruction = str(review.metadata.get("agent_instruction") or review.comment or "").strip()
    request = {
        "review_id": review.id,
        "project_id": project_id,
        "run_id": run_id,
        "stage": stage,
        "target_kind": review.target_kind,
        "target_id": review.target_id,
        "instruction": instruction,
        "comment": review.comment,
        "status": "requested",
    }
    requests = [
        item for item in session.rework_requests
        if item.get("review_id") != review.id
    ]
    requests.append(request)
    repo.update_drama_session(run_id, {"rework_requests": requests})
    return request


def _project_production_status(
    repo,
    stories: list[dict],
    assets: list[dict],
    assets_summary: dict,
    drama_sessions: list[dict],
    rework_requests: list[dict],
) -> dict:
    pending_rework = [
        request for request in rework_requests
        if request.get("status") == "requested"
    ]
    export_ready_sessions = [
        session for session in drama_sessions
        if session.get("can_export_package")
    ]
    packaged_sessions = [
        session for session in drama_sessions
        if session.get("latest_package") is not None
    ]
    latest_session = drama_sessions[0] if drama_sessions else None
    recommended_session = _recommended_drama_session(
        drama_sessions,
        pending_rework,
        export_ready_sessions,
    )
    next_action, next_action_label = _project_next_action(
        bool(stories),
        bool(drama_sessions),
        pending_rework,
        export_ready_sessions,
    )
    release_blockers = _project_release_blockers(
        bool(stories),
        packaged_sessions,
        len(pending_rework),
        int(assets_summary.get("awaiting_review") or 0),
        int(assets_summary.get("needs_changes") or 0),
    )
    release_package = _release_package_for_manifest(drama_sessions)
    cost_guardrail = _project_release_cost_guardrail(repo, release_package)
    if release_package is not None and cost_guardrail["configured"] and not cost_guardrail["within_budget"]:
        release_blockers.append({"code": "budget_exceeded", "label": "预算不足", "count": 1})
    release_action = "ready_to_release" if not release_blockers else ""
    release_action_label = "可以发布" if release_action else ""
    return {
        "story_count": len(stories),
        "drama_session_count": len(drama_sessions),
        "asset_count": len(assets),
        "awaiting_review_count": int(assets_summary.get("awaiting_review") or 0),
        "pending_rework_count": len(pending_rework),
        "export_ready_count": len(export_ready_sessions),
        "exported_package_count": len(packaged_sessions),
        "latest_session_id": str((latest_session or {}).get("id") or ""),
        "recommended_run_id": str((recommended_session or {}).get("id") or ""),
        "next_action": next_action,
        "next_action_label": next_action_label,
        "next_stage": _next_project_stage(recommended_session),
        "release_ready": not release_blockers,
        "release_action": release_action,
        "release_action_label": release_action_label,
        "release_blockers": release_blockers,
        "cost_guardrail": cost_guardrail,
    }


def _project_release_manifest(
    project,
    stories: list[dict],
    assets_summary: dict,
    drama_sessions: list[dict],
    production_status: dict,
) -> dict:
    release_package = _release_package_for_manifest(drama_sessions)
    return {
        "project": {
            "id": project.id,
            "title": project.title,
            "source": project.source,
        },
        "release_ready": bool(production_status.get("release_ready")),
        "release_action": str(production_status.get("release_action") or ""),
        "release_action_label": str(production_status.get("release_action_label") or ""),
        "release_blockers": production_status.get("release_blockers") or [],
        "cost_guardrail": production_status.get("cost_guardrail") or {},
        "story_count": len(stories),
        "asset_summary": assets_summary,
        "recommended_run_id": str(production_status.get("recommended_run_id") or ""),
        "latest_session_id": str(production_status.get("latest_session_id") or ""),
        "release_package_run_id": str((release_package or {}).get("run_id") or ""),
        "release_package": release_package,
        "delivery_actions": _project_release_delivery_actions(
            project.id,
            release_package,
            bool(production_status.get("release_ready")),
        ),
    }


def _project_release_delivery_actions(
    project_id: str,
    release_package: dict | None,
    release_ready: bool,
) -> dict:
    can_download = _release_package_is_local(release_package)
    return {
        "download_url": f"/api/projects/{project_id}/release/package/download",
        "confirm_url": f"/api/projects/{project_id}/release/confirm",
        "can_download": can_download,
        "can_confirm": release_ready and release_package is not None,
    }


def _project_release_cost_guardrail(repo, release_package: dict | None) -> dict:
    shot_count = _release_package_shot_count(release_package)
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


def _ensure_release_cost_ledger_entry(repo, project_id: str, release: ProjectRelease, workspace_payload: dict):
    existing = repo.get_cost_ledger_entry_for_release(release.id, "project_release_confirm")
    if existing is not None:
        return existing
    cost_guardrail = (workspace_payload.get("release_manifest") or {}).get("cost_guardrail") or {}
    estimate = cost_guardrail.get("estimate") if isinstance(cost_guardrail.get("estimate"), dict) else {}
    amount = _safe_money(estimate.get("estimated_total_cny"))
    return repo.save_cost_ledger_entry(CostLedgerEntry(
        id=new_id("cost"),
        project_id=project_id,
        release_id=release.id,
        package_id=release.package_id,
        run_id=release.run_id,
        source="project_release_confirm",
        amount_cny=amount,
        currency="CNY",
        estimated=True,
        metadata={
            "billable_stage": str(cost_guardrail.get("billable_stage") or "video"),
            "estimate": estimate,
        },
    ))


def _cost_ledger_summary(entries: list[CostLedgerEntry]) -> dict:
    estimated_total = round(sum(
        float(entry.amount_cny or 0.0)
        for entry in entries
        if entry.estimated
    ), 2)
    actual_total = round(sum(
        float(entry.amount_cny or 0.0)
        for entry in entries
        if not entry.estimated
    ), 2)
    return {
        "currency": "CNY",
        "entry_count": len(entries),
        "estimated_total_cny": estimated_total,
        "actual_total_cny": actual_total,
        "total_cny": round(estimated_total + actual_total, 2),
    }


def _release_package_shot_count(release_package: dict | None) -> int:
    if not isinstance(release_package, dict):
        return 0
    package_summary = release_package.get("package_summary") if isinstance(
        release_package.get("package_summary"),
        dict,
    ) else {}
    for key in ("shot_count", "shot_limit", "stage_count"):
        count = _safe_int(package_summary.get(key))
        if count:
            return count
    for key in ("shot_count", "shot_limit", "stage_count"):
        count = _safe_int(release_package.get(key))
        if count:
            return count
    return 0


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _optional_float_env(name: str) -> float | None:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _release_package_is_local(release_package: dict | None) -> bool:
    if not isinstance(release_package, dict):
        return False
    package_summary = release_package.get("package_summary") or {}
    if package_summary.get("available") is not True:
        return False
    metadata = release_package.get("metadata") or {}
    backend = str(metadata.get("asset_backend") or "").strip().lower()
    asset_key = str(metadata.get("asset_key") or "").strip()
    return bool(asset_key) and (not backend or backend == "local")


def _release_audit_metadata(workspace_payload: dict) -> dict:
    manifest = workspace_payload.get("release_manifest") or {}
    return {
        "source": "project_release_confirm",
        "manifest_snapshot": manifest,
        "package_snapshot": manifest.get("release_package") or {},
        "review_summary": (workspace_payload.get("assets_summary") or {}).get("review") or {},
    }


def _release_package_for_manifest(drama_sessions: list[dict]) -> dict | None:
    packages = [
        session.get("latest_package")
        for session in drama_sessions
        if isinstance(session.get("latest_package"), dict)
    ]
    if not packages:
        return None
    return sorted(
        packages,
        key=lambda package: _parse_release_package_created_at(package.get("created_at")),
        reverse=True,
    )[0]


def _parse_release_package_created_at(value) -> datetime:
    if not isinstance(value, str) or not value.strip():
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _recommended_drama_session(
    drama_sessions: list[dict],
    pending_rework: list[dict],
    export_ready_sessions: list[dict],
) -> dict | None:
    if pending_rework:
        run_id = str(pending_rework[0].get("run_id") or "")
        session = _find_session(drama_sessions, run_id)
        if session is not None:
            return session
    if export_ready_sessions:
        return export_ready_sessions[0]
    for session in drama_sessions:
        if session.get("latest_package") is None:
            return session
    return drama_sessions[0] if drama_sessions else None


def _find_session(drama_sessions: list[dict], run_id: str) -> dict | None:
    if not run_id:
        return None
    return next(
        (session for session in drama_sessions if session.get("id") == run_id),
        None,
    )


def _project_next_action(
    has_stories: bool,
    has_sessions: bool,
    pending_rework: list[dict],
    export_ready_sessions: list[dict],
) -> tuple[str, str]:
    if pending_rework:
        return "resolve_rework", "处理返工请求"
    if export_ready_sessions:
        return "export_package", "导出短剧项目包"
    if has_sessions:
        return "continue_drama", "继续短剧生产"
    if has_stories:
        return "start_drama", "开始短剧生产"
    return "create_story", "先生成小说"


def _project_release_blockers(
    has_stories: bool,
    packaged_sessions: list[dict],
    pending_rework_count: int,
    awaiting_review_count: int,
    needs_changes_count: int,
) -> list[dict]:
    blockers: list[dict] = []
    if not has_stories:
        blockers.append({"code": "missing_story", "label": "缺少小说作品", "count": 1})
    if not packaged_sessions:
        blockers.append({"code": "missing_package", "label": "缺少短剧项目包", "count": 1})
    if pending_rework_count:
        blockers.append({
            "code": "pending_rework",
            "label": "存在待处理返工",
            "count": pending_rework_count,
        })
    if awaiting_review_count:
        blockers.append({
            "code": "awaiting_review",
            "label": "存在待审核资产",
            "count": awaiting_review_count,
        })
    if needs_changes_count:
        blockers.append({
            "code": "needs_changes",
            "label": "存在需修改或已驳回资产",
            "count": needs_changes_count,
        })
    return blockers


def _next_project_stage(session: dict | None) -> str:
    if not session:
        return ""
    pending_stage = str(session.get("pending_stage") or "").strip()
    if pending_stage:
        return pending_stage
    confirmed = set(session.get("confirmed_stages") or [])
    for stage in PACKAGE_READY_STAGES:
        if stage not in confirmed:
            return stage
    return "video"


def _project_rework_requests(repo, project_id: str) -> list[dict]:
    requests: list[dict] = []
    project_story_paths = _project_story_paths(repo, project_id)
    for session in repo.list_drama_sessions():
        if not _session_belongs_to_project(session, project_id, project_story_paths):
            continue
        for request in session.rework_requests:
            item = dict(request)
            item.setdefault("project_id", project_id)
            item["run_id"] = session.id
            completed_version = _completed_rework_stage_version(repo, item)
            if completed_version is not None:
                item["completed_stage_version"] = completed_version.to_dict()
            requests.append(item)
    return requests


def _project_drama_sessions(repo, project_id: str) -> list[dict]:
    sessions: list[dict] = []
    project_story_paths = _project_story_paths(repo, project_id)
    packages_by_run: dict[str, list] = {}
    for package in repo.list_drama_project_packages():
        packages_by_run.setdefault(package.run_id, []).append(package)

    for session in repo.list_drama_sessions():
        if not _session_belongs_to_project(session, project_id, project_story_paths):
            continue
        versions = repo.list_drama_stage_versions(session.id)
        packages = packages_by_run.get(session.id, [])
        latest_package = _latest_project_package(packages)
        latest_package_payload = _project_package_payload(repo, latest_package)
        item = session.to_dict()
        item.update({
            "stage_version_count": len(versions),
            "confirmed_stage_count": len([
                stage for stage in PACKAGE_READY_STAGES
                if stage in session.confirmed_stages
            ]),
            "latest_package": latest_package_payload,
            "package_count": len(packages),
            "can_export_package": (
                latest_package is None
                and all(stage in session.confirmed_stages for stage in PACKAGE_READY_STAGES)
            ),
        })
        sessions.append(item)
    return sessions


def _latest_project_package(packages: list) -> object | None:
    if not packages:
        return None
    return sorted(
        packages,
        key=lambda package: _parse_release_package_created_at(getattr(package, "created_at", None)),
        reverse=True,
    )[0]


def _project_release_package_record(repo, project_id: str):
    project_story_paths = _project_story_paths(repo, project_id)
    packages = []
    for session in repo.list_drama_sessions():
        if not _session_belongs_to_project(session, project_id, project_story_paths):
            continue
        packages.extend(repo.list_drama_project_packages(session.id))
    return _latest_project_package(packages)


def _project_package_payload(repo, package) -> dict | None:
    if package is None:
        return None
    payload = package.to_dict()
    payload["package_summary"] = _read_project_package_summary(repo, package)
    return payload


def _project_release_integrity(repo, release: ProjectRelease, package, package_snapshot: dict) -> dict:
    checks: list[dict] = []
    checks.append(_integrity_check(
        "package_record",
        "项目包记录",
        "passed" if package is not None else "failed",
        "package record found" if package is not None else "package record missing",
    ))

    package_summary = _read_project_package_summary(repo, package) if package is not None else None
    if package_summary is None:
        checks.append(_integrity_check("package_asset", "项目包文件", "failed", "package record missing"))
    elif package_summary.get("available") is True:
        checks.append(_integrity_check("package_asset", "项目包文件", "passed", "package asset readable"))
    else:
        checks.append(_integrity_check(
            "package_asset",
            "项目包文件",
            "failed",
            str(package_summary.get("reason") or "package asset unavailable"),
        ))

    if isinstance(package_snapshot, dict) and package_snapshot:
        snapshot_matches = package is not None and _package_snapshot_matches(package_snapshot, package)
        checks.append(_integrity_check(
            "package_snapshot",
            "确认快照",
            "passed" if snapshot_matches else "failed",
            "snapshot matches package" if snapshot_matches else "snapshot package mismatch",
        ))
    else:
        checks.append(_integrity_check("package_snapshot", "确认快照", "warning", "package snapshot missing"))

    run_matches = package is not None and release.run_id == package.run_id
    checks.append(_integrity_check(
        "run_consistency",
        "Run 一致性",
        "passed" if run_matches else "failed",
        "release run matches package" if run_matches else "release run does not match package",
    ))

    stage_count = int(getattr(package, "stage_count", 0) or 0) if package is not None else 0
    version_count = int(getattr(package, "version_count", 0) or 0) if package is not None else 0
    stage_ready = stage_count >= len(PACKAGE_READY_STAGES) and version_count >= len(PACKAGE_READY_STAGES)
    checks.append(_integrity_check(
        "stage_coverage",
        "阶段覆盖",
        "passed" if stage_ready else "failed",
        (
            f"package covers {stage_count} stages and {version_count} versions"
            if stage_ready
            else f"package only covers {stage_count} stages and {version_count} versions"
        ),
    ))

    summary = {
        "passed": len([check for check in checks if check["status"] == "passed"]),
        "failed": len([check for check in checks if check["status"] == "failed"]),
        "warning": len([check for check in checks if check["status"] == "warning"]),
    }
    if summary["failed"]:
        status = "failed"
    elif summary["warning"]:
        status = "warning"
    else:
        status = "passed"
    return {
        "status": status,
        "summary": summary,
        "checks": checks,
    }


def _package_snapshot_matches(package_snapshot: dict, package) -> bool:
    fields = ("id", "run_id", "stage_count", "version_count")
    package_payload = package.to_dict()
    for field in fields:
        if field not in package_snapshot:
            continue
        if str(package_snapshot.get(field) or "") != str(package_payload.get(field) or ""):
            return False
    return str(package_snapshot.get("id") or "") == package.id


def _integrity_check(code: str, label: str, status: str, message: str) -> dict:
    return {
        "code": code,
        "label": label,
        "status": status,
        "message": message,
    }


def _read_project_package_summary(repo, package) -> dict:
    metadata = package.metadata if isinstance(package.metadata, dict) else {}
    backend = str(metadata.get("asset_backend") or "").strip().lower()
    asset_key = str(metadata.get("asset_key") or "").strip()
    if backend and backend != "local":
        return {"available": False, "reason": "package asset is not local"}
    if not asset_key:
        return {"available": False, "reason": "package asset key is missing"}

    package_path = _safe_package_asset_path(repo, asset_key)
    if package_path is None:
        return {"available": False, "reason": "package asset key is invalid"}
    try:
        data = json.loads(package_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"available": False, "reason": "package asset not found"}
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {"available": False, "reason": "package asset is unreadable"}
    if not isinstance(data, dict):
        return {"available": False, "reason": "package payload is invalid"}

    return {
        "available": True,
        "run_id": str(data.get("run_id") or package.run_id),
        "story_path": str(data.get("story_path") or package.story_path),
        "shot_count": _package_payload_shot_count(data),
        "shot_limit": _safe_int(data.get("shot_limit")),
        "status": str(data.get("status") or ""),
        "stage_count": _dict_len(data.get("stage_drafts")),
        "structured_asset_count": _dict_len(data.get("structured_assets")),
        "confirmed_stage_count": _list_len(data.get("confirmed_stages")),
        "version_count": _list_len(data.get("versions")),
        "video_run_id": str(data.get("video_run_id") or package.video_run_id),
        "exported_at": str(data.get("exported_at") or ""),
    }


def _package_payload_shot_count(data: dict) -> int:
    structured_assets = data.get("structured_assets") if isinstance(data.get("structured_assets"), dict) else {}
    storyboard = structured_assets.get("storyboard") if isinstance(structured_assets.get("storyboard"), dict) else {}
    shots = storyboard.get("shots")
    if isinstance(shots, list):
        return len(shots)
    stage_drafts = data.get("stage_drafts") if isinstance(data.get("stage_drafts"), dict) else {}
    storyboard_draft = stage_drafts.get("storyboard") if isinstance(stage_drafts.get("storyboard"), dict) else {}
    draft_shots = storyboard_draft.get("shots")
    if isinstance(draft_shots, list):
        return len(draft_shots)
    return 0


def _safe_package_asset_path(repo, asset_key: str):
    root = (repo.root / "assets").resolve()
    try:
        path = (root / asset_key).resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        return None
    return path


def _local_package_asset_path(repo, package):
    metadata = package.metadata or {}
    backend = str(metadata.get("asset_backend") or "").strip().lower()
    if backend and backend != "local":
        return None
    asset_key = str(metadata.get("asset_key") or "").strip()
    if not asset_key:
        return None
    package_path = _safe_package_asset_path(repo, asset_key)
    if package_path is None or not package_path.is_file():
        return None
    return package_path


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_money(value) -> float:
    try:
        return round(float(value or 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


def _dict_len(value) -> int:
    return len(value) if isinstance(value, dict) else 0


def _list_len(value) -> int:
    return len(value) if isinstance(value, list) else 0


def _project_story_paths(repo, project_id: str) -> set[str]:
    return {
        story.body_path
        for story in repo.list_stories(project_id)
    }


def _session_belongs_to_project(session, project_id: str, project_story_paths: set[str]) -> bool:
    return session.project_id == project_id or (
        not session.project_id and session.story_path in project_story_paths
    )


def _completed_rework_stage_version(repo, request: dict):
    version_id = str(request.get("completed_stage_version_id") or "").strip()
    if not version_id:
        return None
    run_id = str(request.get("run_id") or "").strip()
    stage = str(request.get("stage") or "").strip() or None
    if not run_id:
        return None
    for version in repo.list_drama_stage_versions(run_id, stage=stage):
        if version.id == version_id:
            return version
    return None


@router.get("/api/projects/{project_id}/timeline")
async def get_project_timeline(req: Request, project_id: str):
    repo = req.app.state.dependencies.workspace_repo
    project = repo.get_project(project_id)
    if project is None:
        raise _not_found()
    return {
        "project_id": project_id,
        "timeline": repo.project_timeline(project_id),
    }


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="project not found")
