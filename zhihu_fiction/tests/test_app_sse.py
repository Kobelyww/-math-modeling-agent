"""Tests for shared Server-Sent Events helpers."""
from __future__ import annotations

import asyncio

from zhihu_fiction.app.sse import format_sse_event, stream_queue_events


def test_format_sse_event_serializes_json_payload_without_ascii_escape():
    text = format_sse_event("stage_update", {"stage": "script", "message": "短剧启动"})

    assert text == 'event: stage_update\ndata: {"stage": "script", "message": "短剧启动"}\n\n'


def test_stream_queue_events_yields_known_events_and_stops_on_complete():
    async def collect_events():
        queue = asyncio.Queue()
        await queue.put({"type": "stage_update", "data": {"progress": 10}})
        await queue.put({"type": "agent_event", "data": {"name": "writer"}})
        await queue.put({"type": "complete", "data": {"status": "completed"}})

        events = []
        async for event in stream_queue_events(queue, event_types=("stage_update", "agent_event")):
            events.append(event)
        return events

    events = asyncio.run(collect_events())

    assert events == [
        'event: stage_update\ndata: {"progress": 10}\n\n',
        'event: agent_event\ndata: {"name": "writer"}\n\n',
        'event: complete\ndata: {"status": "completed"}\n\n',
    ]


def test_stream_queue_events_yields_heartbeat_on_timeout():
    async def next_event():
        queue = asyncio.Queue()
        stream = stream_queue_events(queue, event_types=("stage_update",), heartbeat_seconds=0.01)
        try:
            return await anext(stream)
        finally:
            await stream.aclose()

    event = asyncio.run(next_event())
    assert event == "event: heartbeat\ndata: \n\n"
