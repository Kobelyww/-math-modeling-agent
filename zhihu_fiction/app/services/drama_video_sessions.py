"""DeepAgent short-drama session persistence helpers."""
from __future__ import annotations

import os
import re

from ...workspace.models import (
    ConsistencyProfile,
    DramaProjectSession,
    DramaStageVersion,
    OperationLog,
    new_id,
    utc_now_iso,
)


def session_to_spec(session: DramaProjectSession) -> dict:
    return {
        "story_path": session.story_path,
        "project_id": session.project_id,
        "shot_limit": session.shot_limit,
        "stage_drafts": dict(session.stage_drafts),
        "drafts": dict(session.drafts),
        "confirmed_stages": list(session.confirmed_stages),
        "pending_stage": session.pending_stage or None,
        "video_run_id": session.video_run_id,
        "rework_requests": list(session.rework_requests),
    }


def persist_session(
    dependencies,
    run_id: str,
    spec: dict,
    status: str,
    error: str = "",
) -> DramaProjectSession:
    existing = dependencies.workspace_repo.get_drama_session(run_id)
    created_at = existing.created_at if existing is not None else utc_now_iso()
    session = DramaProjectSession(
        id=run_id,
        story_path=spec.get("story_path", ""),
        project_id=spec.get("project_id", ""),
        shot_limit=int(spec.get("shot_limit") or 1),
        stage_drafts=dict(spec.get("stage_drafts") or {}),
        drafts=dict(spec.get("drafts") or {}),
        confirmed_stages=list(spec.get("confirmed_stages") or []),
        pending_stage=spec.get("pending_stage") or "",
        video_run_id=spec.get("video_run_id") or "",
        rework_requests=list(spec.get("rework_requests") or []),
        provider=os.getenv("ZH_VIDEO_PROVIDER", "bailian"),
        model="deepseek-v4-pro",
        status=status,
        created_at=created_at,
        updated_at=utc_now_iso(),
        error=error,
    )
    dependencies.workspace_repo.save_drama_session(session)
    return session


def store_session_spec(
    dependencies,
    state,
    run_id: str,
    spec: dict,
    status: str,
    error: str = "",
) -> DramaProjectSession:
    state.video_deepagent_specs[run_id] = spec
    return persist_session(dependencies, run_id, spec, status, error=error)


def record_operation_log(
    dependencies,
    project_id: str,
    actor: str,
    action: str,
    target_kind: str,
    target_id: str,
    message: str = "",
    metadata: dict | None = None,
) -> OperationLog | None:
    if not project_id:
        return None
    log = OperationLog(
        id=new_id("op"),
        project_id=project_id,
        action=action,
        actor=actor,
        target_kind=target_kind,
        target_id=target_id,
        session_id=target_id if target_kind == "drama_session" else "",
        run_id=str((metadata or {}).get("run_id") or ""),
        message=message,
        created_at=utc_now_iso(),
        metadata=dict(metadata or {}),
    )
    return dependencies.workspace_repo.save_operation_log(log)


def update_consistency_profile_from_stage(
    dependencies,
    run_id: str,
    stage: str,
    content: str,
    version: DramaStageVersion,
) -> ConsistencyProfile | None:
    project_id = version.project_id
    if not project_id:
        return None

    existing = dependencies.workspace_repo.latest_consistency_profile_for_session(run_id)
    extracted = _extract_consistency_fragments(stage, content)
    if existing is None:
        profile = ConsistencyProfile(
            id=new_id("consistency"),
            project_id=project_id,
            session_id=run_id,
            created_at=utc_now_iso(),
        )
    else:
        profile = existing

    source_version_ids = _append_unique(profile.source_version_ids, version.id)
    characters = _merge_dict_items(profile.characters, extracted["characters"], "name")
    world_facts = _merge_dict_items(profile.world_facts, extracted["world_facts"], "text")
    narrative_constraints = _merge_text_items(
        profile.narrative_constraints,
        extracted["narrative_constraints"],
    )
    visual_style = _merge_visual_style(profile.visual_style, extracted["visual_style"])
    asset_bindings = _merge_asset_bindings(
        profile.asset_bindings,
        extracted["asset_bindings"],
    )

    updated = ConsistencyProfile(
        id=profile.id,
        project_id=project_id,
        session_id=run_id,
        source_version_ids=source_version_ids,
        characters=characters,
        world_facts=world_facts,
        visual_style=visual_style,
        narrative_constraints=narrative_constraints,
        asset_bindings=asset_bindings,
        created_at=profile.created_at,
        updated_at=utc_now_iso(),
    )
    return dependencies.workspace_repo.save_consistency_profile(updated)


def record_stage_version(
    dependencies,
    run_id: str,
    stage: str,
    content: str,
    event: str,
    *,
    project_id: str = "",
    human_feedback: str = "",
    metadata: dict | None = None,
    ) -> DramaStageVersion:
    if not project_id:
        session = dependencies.workspace_repo.get_drama_session(run_id)
        project_id = getattr(session, "project_id", "") if session is not None else ""
    version = DramaStageVersion(
        id=new_id("drama_ver"),
        run_id=run_id,
        project_id=project_id,
        stage=stage,
        content=content[:20000],
        event=event,
        human_feedback=human_feedback,
        model="deepseek-v4-pro",
        agent="deepagent",
        metadata=dict(metadata or {}),
    )
    return dependencies.workspace_repo.save_drama_stage_version(version)


def _extract_consistency_fragments(stage: str, content: str) -> dict:
    characters = [
        {"name": name, "source_stage": stage}
        for name in _extract_labeled_items(content, ("角色", "人物", "主角", "女主", "男主"))
    ]
    world_facts = [
        {"text": fact, "source_stage": stage}
        for fact in _extract_labeled_items(content, ("地点", "场景", "背景", "世界观", "时间"))
    ]
    narrative_constraints = _extract_labeled_items(content, ("限制", "约束", "禁忌", "必须"))
    narrative_constraints.extend(_extract_negative_constraints(content))

    visual_style = {}
    for value in _extract_labeled_items(content, ("风格", "视觉", "色彩", "镜头")):
        visual_style.setdefault("notes", [])
        visual_style["notes"].append(value)

    asset_bindings = {}
    if stage == "character_refs":
        for character in characters:
            asset_bindings.setdefault(character["name"], [])
            asset_bindings[character["name"]].append({"source_stage": stage, "prompt": content[:500]})

    return {
        "characters": characters,
        "world_facts": world_facts,
        "visual_style": visual_style,
        "narrative_constraints": _dedupe_text(narrative_constraints),
        "asset_bindings": asset_bindings,
    }


def _extract_labeled_items(content: str, labels: tuple[str, ...]) -> list[str]:
    items: list[str] = []
    label_pattern = "|".join(re.escape(label) for label in labels)
    for match in re.finditer(
        rf"(?:{label_pattern})\s*[:：]\s*([^。\n；;]+)",
        content,
    ):
        items.extend(_split_compact_items(match.group(1)))
    return _dedupe_text(items)


def _extract_negative_constraints(content: str) -> list[str]:
    constraints: list[str] = []
    for match in re.finditer(r"([^。\n；;]*不能[^。\n；;]*)", content):
        value = match.group(1).strip(" ，,。；;")
        if ":" in value or "：" in value:
            value = re.split(r"[:：]", value)[-1].strip(" ，,。；;")
        constraints.append(value)
    return _dedupe_text(constraints)


def _split_compact_items(value: str) -> list[str]:
    return [
        item.strip(" ，,、。；;")
        for item in re.split(r"[、,，/；;]", value)
        if item.strip(" ，,、。；;")
    ]


def _append_unique(items: list[str], value: str) -> list[str]:
    merged = list(items)
    if value and value not in merged:
        merged.append(value)
    return merged


def _merge_text_items(existing: list[str], additions: list[str]) -> list[str]:
    merged = list(existing)
    for item in additions:
        if item and item not in merged:
            merged.append(item)
    return merged


def _merge_dict_items(existing: list[dict], additions: list[dict], key: str) -> list[dict]:
    merged = list(existing)
    seen = {str(item.get(key) or "") for item in merged}
    for item in additions:
        value = str(item.get(key) or "")
        if value and value not in seen:
            merged.append(item)
            seen.add(value)
    return merged


def _merge_visual_style(existing: dict, additions: dict) -> dict:
    merged = dict(existing)
    if "notes" in additions:
        merged["notes"] = _merge_text_items(
            list(merged.get("notes") or []),
            list(additions.get("notes") or []),
        )
    for key, value in additions.items():
        if key != "notes":
            merged[key] = value
    return merged


def _merge_asset_bindings(existing: dict, additions: dict) -> dict:
    merged = dict(existing)
    for key, value in additions.items():
        if key not in merged:
            merged[key] = value
            continue
        merged[key] = _merge_asset_binding_value(merged[key], value)
    return merged


def _merge_asset_binding_value(existing, addition):
    addition_items = addition if isinstance(addition, list) else [addition]
    if isinstance(existing, dict):
        merged = dict(existing)
        merged["generated_refs"] = _merge_list_items(
            list(merged.get("generated_refs") or []),
            addition_items,
        )
        return merged
    if isinstance(existing, list):
        return _merge_list_items(existing, addition_items)
    return {
        "legacy_value": existing,
        "generated_refs": _merge_list_items([], addition_items),
    }


def _merge_list_items(existing: list, additions: list) -> list:
    merged = list(existing)
    for item in additions:
        if item not in merged:
            merged.append(item)
    return merged


def _dedupe_text(items: list[str]) -> list[str]:
    merged: list[str] = []
    for item in items:
        value = item.strip()
        if value and value not in merged:
            merged.append(value)
    return merged


def get_session_spec(dependencies, state, run_id: str) -> dict | None:
    spec = state.video_deepagent_specs.get(run_id)
    if spec is not None:
        return spec
    session = dependencies.workspace_repo.get_drama_session(run_id)
    if session is None:
        return None
    spec = session_to_spec(session)
    state.video_deepagent_specs[run_id] = spec
    return spec
