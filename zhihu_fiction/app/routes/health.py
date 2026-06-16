"""Health and readiness routes."""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "app": "zhihu_fiction"}


@router.get("/ready")
async def ready(req: Request):
    deps = req.app.state.dependencies
    status = deps.infrastructure_status()
    return {"status": "ready", **status}
