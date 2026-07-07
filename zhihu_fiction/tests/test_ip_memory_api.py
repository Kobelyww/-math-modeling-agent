from pathlib import Path

from fastapi.testclient import TestClient

from zhihu_fiction.app.factory import create_app
from zhihu_fiction.ip_memory.repository import IPMemoryRepository


class Deps:
    def __init__(self, tmp_path: Path):
        from zhihu_fiction.app.dependencies import AppDependencies
        base = AppDependencies()
        self.__dict__.update(base.__dict__)
        self.ip_memory_repo = IPMemoryRepository(tmp_path / "ip_memory")


def test_extract_and_read_ip_memory_api(tmp_path: Path):
    story = tmp_path / "story.md"
    story.write_text("# 雨夜归来\n\n> 题材：复仇爽文\n\n林晚在山西运城醒来，带着录音证据归来。", encoding="utf-8")
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    extracted = client.post(
        "/api/ip-memory/story-rain/extract",
        json={"title": "雨夜归来", "genre": "复仇爽文", "story_path": str(story)},
    )

    assert extracted.status_code == 200
    assert extracted.json()["memory"]["story_bible"]["title"] == "雨夜归来"

    loaded = client.get("/api/ip-memory/story-rain")
    assert loaded.status_code == 200
    assert loaded.json()["memory"]["project_id"] == "story-rain"


def test_patch_ip_memory_api(tmp_path: Path):
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/ip-memory/project-a/patch",
        json={"world_facts": [{"id": "fact_manual", "text": "人工确认的事实", "category": "manual"}]},
    )

    assert response.status_code == 200
    assert response.json()["memory"]["world_facts"][0]["text"] == "人工确认的事实"


def test_read_ip_memory_api_returns_404_for_missing_project(tmp_path: Path):
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    response = client.get("/api/ip-memory/missing-project")

    assert response.status_code == 404


def test_extract_ip_memory_api_rejects_missing_story_text(tmp_path: Path):
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/ip-memory/project-a/extract",
        json={"title": "无正文"},
    )

    assert response.status_code == 400


def test_extract_ip_memory_api_returns_404_for_missing_story_path(tmp_path: Path):
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/ip-memory/project-a/extract",
        json={"story_path": str(tmp_path / "missing.md")},
    )

    assert response.status_code == 404


def test_patch_ip_memory_api_rejects_malformed_payload(tmp_path: Path):
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/ip-memory/project-a/patch",
        json={"world_facts": "not-a-list"},
    )

    assert response.status_code == 400
