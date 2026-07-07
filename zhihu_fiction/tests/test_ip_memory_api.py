from pathlib import Path
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from zhihu_fiction.app.factory import create_app
from zhihu_fiction.ip_memory.repository import IPMemoryRepository


class Deps:
    def __init__(self, tmp_path: Path):
        from zhihu_fiction.app.dependencies import AppDependencies
        base = AppDependencies()
        self.__dict__.update(base.__dict__)
        self.ip_memory_repo = IPMemoryRepository(tmp_path / "ip_memory")


@pytest.fixture
def isolated_story_roots(monkeypatch, tmp_path: Path):
    app_root = tmp_path / "app"
    output_dir = app_root / "output"
    output_dir.mkdir(parents=True)
    monkeypatch.setitem(
        sys.modules,
        "zhihu_fiction.server",
        SimpleNamespace(APP_ROOT=app_root, OUTPUT_DIR=output_dir),
    )
    return app_root, output_dir


def test_extract_and_read_ip_memory_api(tmp_path: Path, isolated_story_roots):
    app_root, output_dir = isolated_story_roots
    story_dir = output_dir / "demo"
    story_dir.mkdir()
    story = story_dir / "小说正文.md"
    story.write_text("# 雨夜归来\n\n> 题材：复仇爽文\n\n林晚在山西运城醒来，带着录音证据归来。", encoding="utf-8")
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    extracted = client.post(
        "/api/ip-memory/story-rain/extract",
        json={
            "title": "雨夜归来",
            "genre": "复仇爽文",
            "story_path": str(story.relative_to(app_root)),
        },
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


def test_extract_ip_memory_api_returns_404_for_missing_story_path(
    tmp_path: Path,
    isolated_story_roots,
):
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/ip-memory/project-a/extract",
        json={"story_path": "output/missing/小说正文.md"},
    )

    assert response.status_code == 404


def test_extract_ip_memory_api_rejects_path_traversal(tmp_path: Path, isolated_story_roots):
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/ip-memory/project-a/extract",
        json={"story_path": "../secret.md"},
    )

    assert response.status_code == 400


def test_extract_ip_memory_api_rejects_absolute_path_outside_app_root(
    tmp_path: Path,
    isolated_story_roots,
):
    outside_story = tmp_path / "outside.md"
    outside_story.write_text("不应读取的外部正文", encoding="utf-8")
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/ip-memory/project-a/extract",
        json={"story_path": str(outside_story)},
    )

    assert response.status_code == 400
    assert "不应读取的外部正文" not in response.text


def test_extract_ip_memory_api_does_not_expand_tilde_story_path(
    monkeypatch,
    tmp_path: Path,
    isolated_story_roots,
):
    fake_home = tmp_path / "home"
    ssh_dir = fake_home / ".ssh"
    ssh_dir.mkdir(parents=True)
    private_key = ssh_dir / "id_rsa"
    private_key.write_text("FAKE PRIVATE KEY CONTENT", encoding="utf-8")
    monkeypatch.setenv("HOME", str(fake_home))
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/ip-memory/project-a/extract",
        json={"story_path": "~/.ssh/id_rsa"},
    )

    assert response.status_code in {400, 404}
    assert "FAKE PRIVATE KEY CONTENT" not in response.text


def test_patch_ip_memory_api_rejects_malformed_payload(tmp_path: Path):
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/ip-memory/project-a/patch",
        json={"world_facts": "not-a-list"},
    )

    assert response.status_code == 400


@pytest.mark.parametrize("payload", [[], "bad"])
def test_patch_ip_memory_api_rejects_non_object_json_payload(tmp_path: Path, payload):
    app = create_app(dependencies=Deps(tmp_path))
    client = TestClient(app)

    response = client.post("/api/ip-memory/project-a/patch", json=payload)

    assert response.status_code == 400
