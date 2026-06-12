"""Release artifact contract tests."""
from __future__ import annotations

from pathlib import Path


def test_gitignore_excludes_runtime_secrets_and_generated_data():
    text = Path(".gitignore").read_text(encoding="utf-8")

    required_patterns = [
        ".env",
        ".env.*",
        "!*.env.example",
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
