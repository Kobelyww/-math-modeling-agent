"""IP memory API routes."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Request

from ...config import APP_ROOT
from ...ip_memory.extraction import extract_ip_memory_from_story
from ...ip_memory.rendering import render_memory_context
from ...ip_memory.repository import IPMemoryRepository
from ..request_parsing import json_body, stripped_or_none
from ..services.story_library import safe_story_file

router = APIRouter()


@router.get("/api/ip-memory/{project_id}")
async def get_ip_memory(req: Request, project_id: str):
    repo = _ip_memory_repo(req)
    memory = repo.load(project_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="ip memory not found")
    return _memory_response(memory)


@router.post("/api/ip-memory/{project_id}/extract")
async def extract_ip_memory(req: Request, project_id: str):
    body = await json_body(req)
    story_text, story_ref = _story_text_from_request(body)
    if not story_text.strip():
        raise HTTPException(status_code=400, detail="story_path or story_text is required")

    repo = _ip_memory_repo(req)
    prior = repo.load(project_id)
    memory = extract_ip_memory_from_story(
        project_id=project_id,
        title=stripped_or_none(body, "title") or "",
        genre=stripped_or_none(body, "genre") or "",
        story_text=story_text,
        story_ref=story_ref,
        prior=prior,
    )
    saved = repo.save(memory, patch_note=f"extract_ip_memory:{story_ref or 'inline'}")
    return _memory_response(saved)


@router.post("/api/ip-memory/{project_id}/patch")
async def patch_ip_memory(req: Request, project_id: str):
    body = await _patch_json_body(req)
    repo = _ip_memory_repo(req)
    try:
        memory = repo.apply_patch(project_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _memory_response(memory)


def _ip_memory_repo(req: Request) -> IPMemoryRepository:
    deps = getattr(req.app.state, "dependencies", None)
    if deps is None:
        deps = SimpleNamespace()
        req.app.state.dependencies = deps

    repo = getattr(deps, "ip_memory_repo", None)
    if repo is None:
        repo = IPMemoryRepository(APP_ROOT / "data" / "ip_memory")
        setattr(deps, "ip_memory_repo", repo)
    return repo


def _story_text_from_request(body: dict) -> tuple[str, str]:
    story_path = stripped_or_none(body, "story_path")
    if story_path is not None:
        path = safe_story_file(story_path)
        return path.read_text(encoding="utf-8"), str(path)

    story_text = stripped_or_none(body, "story_text")
    if story_text is None:
        return "", ""
    return story_text, "inline"


async def _patch_json_body(req: Request) -> dict:
    content_type = req.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        raise HTTPException(status_code=400, detail="patch payload must be a JSON object")

    try:
        body = await req.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="patch payload must be valid JSON") from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="patch payload must be a JSON object")
    return body


def _memory_response(memory) -> dict:
    context = render_memory_context(memory)
    return {
        "project_id": memory.project_id,
        "memory": memory.to_dict(),
        "context": context,
        "rendered_context": context,
    }
