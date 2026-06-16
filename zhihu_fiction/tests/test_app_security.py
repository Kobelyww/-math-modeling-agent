"""Tests for production API security middleware."""
from __future__ import annotations

from fastapi.testclient import TestClient

from zhihu_fiction.app.dependencies import AppDependencies
from zhihu_fiction.app.factory import create_app
from zhihu_fiction.app.settings import WebSettings


def make_app(require_auth: bool = True) -> TestClient:
    deps = AppDependencies(
        web_settings=WebSettings(
            app_env="production",
            cors_origins=["https://studio.example.com"],
            require_auth=require_auth,
            web_api_token="token-123",
            expose_error_details=False,
        )
    )
    return TestClient(create_app(dependencies=deps))


def test_production_api_requires_token():
    client = make_app(require_auth=True)

    response = client.get("/api/drama-video/infrastructure")

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


def test_production_api_accepts_bearer_token():
    client = make_app(require_auth=True)

    response = client.get(
        "/api/drama-video/infrastructure",
        headers={"Authorization": "Bearer token-123"},
    )

    assert response.status_code == 200
    assert response.json()["video_provider"] == "bailian"


def test_health_is_public_even_when_auth_required():
    client = make_app(require_auth=True)

    response = client.get("/health")

    assert response.status_code == 200


def test_auth_can_be_disabled_for_development():
    client = make_app(require_auth=False)

    response = client.get("/api/drama-video/infrastructure")

    assert response.status_code == 200


def test_production_exception_handler_hides_internal_details():
    deps = AppDependencies(
        web_settings=WebSettings(
            app_env="production",
            cors_origins=["https://studio.example.com"],
            require_auth=False,
            web_api_token="",
            expose_error_details=False,
        )
    )
    app = create_app(dependencies=deps)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret stack detail")

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"error": "Internal Server Error", "path": "/boom"}
