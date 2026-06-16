"""Shared Server-Sent Events helpers."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
HEARTBEAT_EVENT = "event: heartbeat\ndata: \n\n"


def format_sse_event(event_name: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_name}\ndata: {payload}\n\n"


async def stream_queue_events(
    queue: asyncio.Queue,
    *,
    event_types: tuple[str, ...],
    heartbeat_seconds: float = 15,
) -> AsyncIterator[str]:
    allowed_events = set(event_types) | {"complete"}
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
        except asyncio.TimeoutError:
            yield HEARTBEAT_EVENT
            continue

        event_type = event.get("type")
        if event_type not in allowed_events:
            continue

        yield format_sse_event(event_type, event.get("data") or {})
        if event_type == "complete":
            break


def queue_streaming_response(
    queue: asyncio.Queue,
    *,
    event_types: tuple[str, ...],
) -> StreamingResponse:
    return StreamingResponse(
        stream_queue_events(queue, event_types=event_types),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
