"""Tests for fiction pipeline API routes."""
from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from zhihu_fiction.app.routes import pipeline as pipeline_routes
from zhihu_fiction.app.state import AppState


def make_pipeline_client(dependencies) -> TestClient:
    app = FastAPI()
    app.state.dependencies = dependencies
    app.state.runtime = AppState()
    app.include_router(pipeline_routes.router)
    return TestClient(app)


def test_trigger_run_parses_json_content_type_with_charset(monkeypatch):
    captured: dict = {}

    def fake_execute_pipeline(state, run_id, pipeline_factory, topic, genre, chapters):
        captured.update(
            {
                "state": state,
                "run_id": run_id,
                "pipeline_factory": pipeline_factory,
                "topic": topic,
                "genre": genre,
                "chapters": chapters,
            }
        )

        async def noop():
            return None

        return noop()

    monkeypatch.setattr(
        pipeline_routes,
        "execute_pipeline_in_background",
        fake_execute_pipeline,
    )

    client = make_pipeline_client(
        SimpleNamespace(create_pipeline=lambda: object(), scheduler_pipeline=None)
    )
    response = client.post(
        "/api/run",
        content=json.dumps(
            {"topic": "  城市异味事件  ", "genre": "  悬疑  ", "chapters": 3},
            ensure_ascii=False,
        ),
        headers={"content-type": "Application/JSON; charset=utf-8"},
    )

    assert response.status_code == 200
    assert captured["topic"] == "城市异味事件"
    assert captured["genre"] == "悬疑"
    assert captured["chapters"] == 3


def test_continue_chapter_parses_json_content_type_with_charset():
    captured: dict = {}

    class FakePipeline:
        def continue_chapter(self, topic, genre, existing_story, chapter_count):
            captured.update(
                {
                    "topic": topic,
                    "genre": genre,
                    "existing_story": existing_story,
                    "chapter_count": chapter_count,
                }
            )
            return SimpleNamespace(published_url="/tmp/story.md")

    client = make_pipeline_client(
        SimpleNamespace(create_pipeline=FakePipeline, scheduler_pipeline=None)
    )
    response = client.post(
        "/api/run/continue",
        content=json.dumps(
            {
                "topic": "城市异味事件",
                "genre": "现实悬疑",
                "existing_story": "第一章内容",
                "chapter_count": 2,
            },
            ensure_ascii=False,
        ),
        headers={"content-type": "application/json; charset=utf-8"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "path": "/tmp/story.md"}
    assert captured == {
        "topic": "城市异味事件",
        "genre": "现实悬疑",
        "existing_story": "第一章内容",
        "chapter_count": 2,
    }


def test_start_scheduler_parses_json_content_type_with_charset():
    captured: dict = {}

    class FakePipeline:
        def run_scheduled(self, interval_minutes):
            captured["interval_minutes"] = interval_minutes

    deps = SimpleNamespace(create_pipeline=FakePipeline, scheduler_pipeline=None)
    client = make_pipeline_client(deps)
    response = client.post(
        "/api/scheduler/start",
        content=json.dumps({"interval": 15}, ensure_ascii=False),
        headers={"content-type": "application/json; charset=utf-8"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "started", "interval": 15}
    assert captured == {"interval_minutes": 15}
    assert isinstance(deps.scheduler_pipeline, FakePipeline)
