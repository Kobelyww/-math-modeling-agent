"""Release artifact contract tests."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def test_gitignore_excludes_runtime_secrets_and_generated_data():
    text = Path(".gitignore").read_text(encoding="utf-8")

    required_patterns = [
        ".env",
        ".env.*",
        "!*.env.example",
        "!*.env.production.example",
        "zhihu_fiction/data/auth/",
        "zhihu_fiction/data/workspace/",
        "zhihu_fiction/data/objects/",
        "zhihu_fiction/output/",
        "__pycache__/",
        "*.py[cod]",
    ]
    for pattern in required_patterns:
        assert pattern in text


def test_release_checklist_exists_and_covers_publish_gates():
    text = Path("docs/release/RELEASE_CHECKLIST.md").read_text(encoding="utf-8")

    for phrase in [
        "Secrets are not committed",
        "Production auth is enabled",
        "CORS origins are restricted",
        "Video cost guardrails are configured",
        "Health checks pass",
        "CI is green",
    ]:
        assert phrase in text


def test_release_checklist_documents_industrial_v1_gates():
    checklist = Path("zhihu_fiction/RELEASE_CHECKLIST.md").read_text(encoding="utf-8")

    assert "SQLite" in checklist
    assert "一致性" in checklist
    assert "成本确认" in checklist
    assert "服务重启恢复" in checklist
    assert "Web QA" in checklist


def test_env_example_documents_local_production_settings():
    env_example = Path("zhihu_fiction/.env.example").read_text(encoding="utf-8")

    assert "ZH_WORKSPACE_BACKEND=sqlite" in env_example
    assert "ZH_WORKSPACE_SQLITE_PATH" in env_example
    assert "ZH_OBJECT_STORAGE_BACKEND" in env_example
    assert "ZH_DAILY_BUDGET_CNY" in env_example
    assert "EMBEDDING_API_KEY" in env_example


def test_readme_documents_local_single_machine_production_mode():
    readme = Path("zhihu_fiction/README.md").read_text(encoding="utf-8")

    assert "## 本地单机生产模式" in readme
    assert "V1 推荐使用 SQLite 作为工作台主存储" in readme
    assert "默认本地单机模式使用本地内存队列、本地文件对象存储、SQLite workspace 持久化" in readme
    assert "http://127.0.0.1:8000/video" in readme
    assert "视频生成前会展示成本估算并要求人工确认" in readme
    assert "默认使用 `zhihu_fiction/data/workspace/` 下的 JSONL/JSON 文件存储" not in readme


def test_docker_release_artifacts_exist_and_wire_services():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path("zhihu_fiction/.env.production.example").read_text(encoding="utf-8")

    assert "ARG PYTHON_IMAGE=python:3.13-slim" in dockerfile
    assert "FROM ${PYTHON_IMAGE}" in dockerfile
    assert "uvicorn" in dockerfile
    assert "zhihu_fiction.server:app" in dockerfile
    assert "ZH_COMPOSE_ENV_FILE=zhihu_fiction/.env.production.example" in env_example
    assert "PYTHON_IMAGE=python:3.13-slim" in env_example
    assert "ZH_WEB_PORT=8000" in env_example
    assert "ZH_REDIS_PORT=6379" in env_example
    assert "ZH_MINIO_API_PORT=9000" in env_example
    assert "ZH_MINIO_CONSOLE_PORT=9001" in env_example
    assert "${ZH_COMPOSE_ENV_FILE:-zhihu_fiction/.env.production.example}" in compose
    assert "PYTHON_IMAGE: ${PYTHON_IMAGE:-python:3.13-slim}" in compose
    assert "${ZH_WEB_PORT:-8000}:8000" in compose
    assert "${ZH_REDIS_PORT:-6379}:6379" in compose
    assert "${ZH_MINIO_API_PORT:-9000}:9000" in compose
    assert "${ZH_MINIO_CONSOLE_PORT:-9001}:9001" in compose
    assert "video-worker:" in compose
    assert "zhihu_fiction.app.services.drama_video_worker" in compose
    assert "redis:" in compose
    assert "minio:" in compose
    assert "ZH_APP_ENV=production" in compose
    assert "ZH_REQUIRE_AUTH=true" in env_example
    assert "ZH_WEB_API_TOKEN=" in env_example
    assert "DASHSCOPE_API_KEY=" in env_example


def test_compose_env_file_overrides_release_recovery_knobs(tmp_path):
    if shutil.which("docker") is None:
        return

    env_file = tmp_path / "compose.env"
    env_file.write_text(
        "\n".join(
            [
                "ZH_COMPOSE_ENV_FILE=zhihu_fiction/.env.production.example",
                "PYTHON_IMAGE=python:3.14-slim",
                "ZH_WEB_PORT=18000",
                "ZH_REDIS_PORT=36379",
                "ZH_MINIO_API_PORT=39000",
                "ZH_MINIO_CONSOLE_PORT=39001",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["docker", "compose", "--env-file", str(env_file), "config", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    compose = json.loads(result.stdout)
    services = compose["services"]

    assert services["web"]["build"]["args"]["PYTHON_IMAGE"] == "python:3.14-slim"
    assert services["video-worker"]["build"]["args"]["PYTHON_IMAGE"] == "python:3.14-slim"
    assert services["web"]["ports"] == [
        {"mode": "ingress", "target": 8000, "published": "18000", "protocol": "tcp"}
    ]
    assert services["redis"]["ports"] == [
        {"mode": "ingress", "target": 6379, "published": "36379", "protocol": "tcp"}
    ]
    assert services["minio"]["ports"] == [
        {"mode": "ingress", "target": 9000, "published": "39000", "protocol": "tcp"},
        {"mode": "ingress", "target": 9001, "published": "39001", "protocol": "tcp"},
    ]


def test_deployment_docs_explain_compose_interpolation_contract():
    deployment = Path("docs/release/DEPLOYMENT.md").read_text(encoding="utf-8")

    assert "docker compose --env-file zhihu_fiction/.env.production.local up --build" in deployment
    assert "Compose interpolation" in deployment
    assert "curl http://127.0.0.1:${ZH_WEB_PORT:-8000}/health" in deployment
    assert "http://127.0.0.1:${ZH_WEB_PORT:-8000}/api/drama-video/infrastructure" in deployment


def test_ci_workflow_runs_zhihu_fiction_tests():
    text = Path(".github/workflows/zhihu-fiction-ci.yml").read_text(encoding="utf-8")

    assert "python -m pytest zhihu_fiction/tests" in text
    assert "test_release_artifacts.py" in text
    assert "actions/setup-python" in text
