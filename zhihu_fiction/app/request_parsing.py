"""Shared request parsing helpers for route modules."""
from __future__ import annotations

from fastapi import HTTPException


async def json_body(request) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        return {}
    body = await request.json()
    return body if isinstance(body, dict) else {}


def stripped_or_none(body: dict, field: str) -> str | None:
    value = body.get(field)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def require_stripped(body: dict, field: str, *, message: str | None = None) -> str:
    value = stripped_or_none(body, field)
    if value is None:
        raise HTTPException(400, message or f"{field} is required")
    return value
