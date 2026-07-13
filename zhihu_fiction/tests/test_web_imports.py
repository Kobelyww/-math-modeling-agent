from __future__ import annotations

import importlib


def test_web_modules_expose_existing_fastapi_app_api() -> None:
    from zhihu_fiction.app import dependencies as legacy_dependencies
    from zhihu_fiction.app import factory as legacy_factory
    from zhihu_fiction.app import request_parsing as legacy_request_parsing
    from zhihu_fiction.app import security as legacy_security
    from zhihu_fiction.app import settings as legacy_settings
    from zhihu_fiction.app import sse as legacy_sse
    from zhihu_fiction.app import state as legacy_state
    from zhihu_fiction.web import dependencies, factory, request_parsing, security, settings, sse, state

    assert factory.create_app is legacy_factory.create_app
    assert factory.TimingMiddleware is legacy_factory.TimingMiddleware
    assert dependencies.AppDependencies is legacy_dependencies.AppDependencies
    assert settings.WebSettings is legacy_settings.WebSettings
    assert settings.load_web_settings is legacy_settings.load_web_settings
    assert security.install_security is legacy_security.install_security
    assert sse.queue_streaming_response is legacy_sse.queue_streaming_response
    assert state.AppState is legacy_state.AppState
    assert request_parsing.require_stripped is legacy_request_parsing.require_stripped


def test_web_route_modules_are_importable_from_target_namespace() -> None:
    route_names = [
        "costs",
        "drama_video",
        "health",
        "ip_memory",
        "pipeline",
        "projects",
        "static",
        "stories",
        "tasks",
    ]

    for name in route_names:
        target = importlib.import_module(f"zhihu_fiction.web.routes.{name}")
        legacy = importlib.import_module(f"zhihu_fiction.app.routes.{name}")
        assert target.router is legacy.router


def test_web_service_modules_are_importable_from_target_namespace() -> None:
    service_names = [
        "drama_video_deepagent_flow",
        "drama_video_execution",
        "drama_video_jobs",
        "drama_video_queue",
        "drama_video_recovery",
        "drama_video_runtime",
        "drama_video_sessions",
        "drama_video_stage_generation",
        "drama_video_worker",
        "infrastructure",
        "object_storage",
        "pipeline_runtime",
        "story_library",
    ]

    for name in service_names:
        target = importlib.import_module(f"zhihu_fiction.web.services.{name}")
        legacy = importlib.import_module(f"zhihu_fiction.app.services.{name}")
        assert target is legacy
