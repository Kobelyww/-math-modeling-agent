"""Health and readiness endpoint tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from zhihu_fiction.app.dependencies import AppDependencies
from zhihu_fiction.app.factory import create_app
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def test_health_endpoint_is_minimal(tmp_path):
    deps = AppDependencies(workspace_repo=WorkspaceRepository(tmp_path / "workspace"))
    client = TestClient(create_app(dependencies=deps))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["app"] == "zhihu_fiction"


def test_ready_endpoint_reports_backends_without_secrets(tmp_path):
    deps = AppDependencies(workspace_repo=WorkspaceRepository(tmp_path / "workspace"))
    client = TestClient(create_app(dependencies=deps))

    response = client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["workspace_backend"] in {"jsonl", "sqlite"}
    assert data["queue_backend"] in {"local", "redis"}
    assert data["video_provider"] == "bailian"
    assert data["app_env"] == "development"
    assert data["auth_required"] is False
    assert data["cors_mode"] == "wildcard"
    assert "api_key" not in str(data).lower()
    assert "token" not in str(data).lower()
