"""API tests for workspace routes."""
import importlib
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from zhihu_fiction.workspace.models import StoryTask
from zhihu_fiction.workspace.repositories import WorkspaceRepository
from zhihu_fiction.workspace.services import WorkspaceService
from zhihu_fiction.workspace_routes import create_workspace_router


class FakeExporter:
    def __init__(self, package_dir: Path) -> None:
        self.package_dir = package_dir

    def export(self, result, platforms=None):
        return {platforms[0]: self.package_dir}


class FakeQueue:
    def __init__(self, service: WorkspaceService) -> None:
        self.service = service
        self.kick_count = 0

    def kick(self) -> bool:
        self.kick_count += 1
        return True

    def retry(self, task_id: str):
        task = self.service.repo.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status != "failed":
            raise ValueError("Only failed tasks can be retried")
        return self.service.repo.update_task(
            task_id,
            {"status": "queued", "retry_count": 1},
        )

    def cancel(self, task_id: str):
        return self.service.repo.update_task(task_id, {"status": "canceled"})


def _client(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    queue = FakeQueue(service)
    package_dir = tmp_path / "fake_export"

    def exporter_factory():
        return FakeExporter(package_dir)

    app = FastAPI()
    app.include_router(create_workspace_router(service, queue, exporter_factory))
    return TestClient(app), service, queue


def test_material_manual_endpoint(tmp_path):
    client, _, _ = _client(tmp_path)

    response = client.post(
        "/api/workspace/materials/manual",
        json={"title": "人工素材", "content": "正文"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "人工素材"


def test_material_patch_rejects_unsafe_fields(tmp_path):
    client, service, _ = _client(tmp_path)
    material = service.create_manual_material("素材", content="正文")

    response = client.patch(
        f"/api/workspace/materials/{material.id}",
        json={"id": "mat_hijack"},
    )

    assert response.status_code == 422
    assert service.repo.get_material(material.id) is not None
    assert service.repo.get_material("mat_hijack") is None


def test_topic_card_to_task_flow(tmp_path):
    client, _, queue = _client(tmp_path)
    material = client.post(
        "/api/workspace/materials/manual",
        json={"title": "素材", "content": "正文"},
    ).json()
    card = client.post(
        "/api/workspace/topic-cards",
        json={
            "title": "选题",
            "source_material_ids": [material["id"]],
            "genre": "悬疑",
            "platform": "zhihu",
        },
    ).json()

    approved = client.post(f"/api/workspace/topic-cards/{card['id']}/approve")
    response = client.post(
        f"/api/workspace/topic-cards/{card['id']}/create-task",
        json={"chapters": 2, "mode": "full", "priority": 3},
    )

    assert approved.status_code == 200
    assert response.status_code == 200
    task = response.json()
    assert task["status"] == "queued"
    assert task["chapters"] == 2
    assert queue.kick_count == 1


def test_topic_card_patch_rejects_status_and_source_material_changes(tmp_path):
    client, service, _ = _client(tmp_path)
    card = service.create_topic_card("选题")

    status_response = client.patch(
        f"/api/workspace/topic-cards/{card.id}",
        json={"status": "approved"},
    )
    sources_response = client.patch(
        f"/api/workspace/topic-cards/{card.id}",
        json={"source_material_ids": ["mat_1"]},
    )

    assert status_response.status_code == 422
    assert sources_response.status_code == 422
    assert service.repo.get_topic_card(card.id).status == "draft"
    assert service.repo.get_topic_card(card.id).source_material_ids == []


def test_create_task_from_unapproved_card_returns_409(tmp_path):
    client, _, _ = _client(tmp_path)
    card = client.post(
        "/api/workspace/topic-cards",
        json={"title": "草稿选题"},
    ).json()

    response = client.post(f"/api/workspace/topic-cards/{card['id']}/create-task")

    assert response.status_code == 409


def test_create_task_from_unapproved_card_does_not_kick_queue(tmp_path):
    client, _, queue = _client(tmp_path)
    card = client.post(
        "/api/workspace/topic-cards",
        json={"title": "草稿选题"},
    ).json()

    response = client.post(f"/api/workspace/topic-cards/{card['id']}/create-task")

    assert response.status_code == 409
    assert queue.kick_count == 0


def test_draft_update_ready_and_package_generation(tmp_path):
    client, service, _ = _client(tmp_path)
    task = service.repo.save_task(
        StoryTask(
            id="task_1",
            topic_card_id="card_1",
            topic="待审选题",
            genre="悬疑",
            status="needs_review",
        )
    )
    service.create_review_draft_from_result(task, Path("story.md"), "初稿正文", {})

    draft_response = client.patch(
        f"/api/workspace/drafts/{task.id}",
        json={
            "title": "新标题",
            "synopsis": "新简介",
            "tags": ["悬疑", "反转"],
            "body": "定稿正文",
            "editor_notes": "可以发布",
        },
    )
    ready_response = client.post(f"/api/workspace/drafts/{task.id}/ready")
    package_response = client.post(
        "/api/workspace/packages/generate",
        json={"task_id": task.id, "platform": "zhihu"},
    )

    assert draft_response.status_code == 200
    assert ready_response.status_code == 200
    assert package_response.status_code == 200
    assert package_response.json()["platform"] == "zhihu"


def test_draft_patch_rejects_explicit_null(tmp_path):
    client, service, _ = _client(tmp_path)
    task = service.repo.save_task(
        StoryTask(
            id="task_1",
            topic_card_id="card_1",
            topic="待审选题",
            genre="悬疑",
            status="needs_review",
        )
    )
    service.create_review_draft_from_result(task, Path("story.md"), "初稿正文", {})
    service.update_review_draft(task.id, {"tags": ["悬疑"]})

    response = client.patch(
        f"/api/workspace/drafts/{task.id}",
        json={"tags": None},
    )

    assert response.status_code == 422
    assert service.repo.get_review_draft(task.id).tags == ["悬疑"]


def test_mark_draft_ready_returns_specific_missing_resource_errors(tmp_path):
    client, service, _ = _client(tmp_path)

    missing_task_response = client.post("/api/workspace/drafts/task_missing/ready")

    task = service.repo.save_task(
        StoryTask(
            id="task_without_draft",
            topic_card_id="card_1",
            topic="无草稿任务",
            genre="悬疑",
            status="needs_review",
        )
    )
    missing_draft_response = client.post(f"/api/workspace/drafts/{task.id}/ready")

    assert missing_task_response.status_code == 404
    assert missing_task_response.json()["detail"] == "task not found"
    assert missing_draft_response.status_code == 404
    assert missing_draft_response.json()["detail"] == "draft not found"


def test_generate_package_returns_specific_missing_resource_errors(tmp_path):
    client, service, _ = _client(tmp_path)

    missing_task_response = client.post(
        "/api/workspace/packages/generate",
        json={"task_id": "task_missing", "platform": "zhihu"},
    )

    task = service.repo.save_task(
        StoryTask(
            id="task_without_draft",
            topic_card_id="card_1",
            topic="无草稿任务",
            genre="悬疑",
            status="approved",
        )
    )
    missing_draft_response = client.post(
        "/api/workspace/packages/generate",
        json={"task_id": task.id, "platform": "zhihu"},
    )

    assert missing_task_response.status_code == 404
    assert missing_task_response.json()["detail"] == "task not found"
    assert missing_draft_response.status_code == 404
    assert missing_draft_response.json()["detail"] == "draft not found"


def test_retry_failed_task_kicks_queue(tmp_path):
    client, service, queue = _client(tmp_path)
    task = service.repo.save_task(
        StoryTask(
            id="task_failed",
            topic_card_id="card_1",
            topic="失败任务",
            genre="悬疑",
            status="failed",
        )
    )

    response = client.post(f"/api/workspace/tasks/{task.id}/retry")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["retry_count"] == 1
    assert queue.kick_count == 1


def test_retry_non_failed_task_returns_409_and_does_not_kick(tmp_path):
    client, service, queue = _client(tmp_path)
    task = service.repo.save_task(
        StoryTask(
            id="task_queued",
            topic_card_id="card_1",
            topic="排队任务",
            genre="悬疑",
            status="queued",
        )
    )

    response = client.post(f"/api/workspace/tasks/{task.id}/retry")

    assert response.status_code == 409
    assert service.repo.get_task(task.id).status == "queued"
    assert queue.kick_count == 0


def test_server_mounts_workspace_and_keeps_legacy_routes(tmp_path, monkeypatch):
    from zhihu_fiction.workspace import repositories

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(repositories, "WORKSPACE_DIR", tmp_path / "server_workspace")
    if "zhihu_fiction.server" in sys.modules:
        server = importlib.reload(sys.modules["zhihu_fiction.server"])
    else:
        server = importlib.import_module("zhihu_fiction.server")

    paths = {route.path for route in server.app.routes}

    assert "/api/workspace/materials" in paths
    assert "/api/run" in paths
