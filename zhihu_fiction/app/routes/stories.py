"""Story listing and loading routes."""
from __future__ import annotations

from fastapi import APIRouter

from ..services.story_library import (
    extract_web_story_body,
    list_story_dirs,
    safe_story_file,
    story_result_from_file,
)

router = APIRouter()


@router.get("/api/stories")
async def list_stories():
    return list_story_dirs()


@router.get("/api/stories/{story_path:path}")
async def get_story(story_path: str):
    full_path = safe_story_file(story_path)
    return {"path": story_path, "content": full_path.read_text(encoding="utf-8")}
