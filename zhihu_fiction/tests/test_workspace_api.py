"""API tests for workspace routes."""
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


def test_create_task_from_unapproved_card_returns_409(tmp_path):
    client, _, _ = _client(tmp_path)
    card = client.post(
        "/api/workspace/topic-cards",
        json={"title": "草稿选题"},
    ).json()

    response = client.post(f"/api/workspace/topic-cards/{card['id']}/create-task")

    assert response.status_code == 409


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
