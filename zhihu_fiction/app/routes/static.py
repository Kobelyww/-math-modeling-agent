"""Static workbench routes."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ...core.config import APP_ROOT

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index():
    static_file = APP_ROOT / "static" / "index.html"
    if not static_file.exists():
        return HTMLResponse(
            "<h2>index.html not found. Create static/index.html first.</h2>",
            status_code=404,
        )
    return HTMLResponse(static_file.read_text(encoding="utf-8"))


@router.get("/video", response_class=HTMLResponse)
async def video_workspace():
    static_file = APP_ROOT / "static" / "video.html"
    if not static_file.exists():
        return HTMLResponse(
            "<h2>video.html not found. Create static/video.html first.</h2>",
            status_code=404,
        )
    return HTMLResponse(static_file.read_text(encoding="utf-8"))
