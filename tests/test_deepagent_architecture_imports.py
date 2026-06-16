from __future__ import annotations

import importlib
from pathlib import Path


def test_deepagent_dependency_declared_in_project_files():
    root = Path(__file__).resolve().parents[2]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (root / "agent_app" / "requirements.txt").read_text(encoding="utf-8")

    assert '"deepagents>=0.5.0"' in pyproject
    assert "deepagents>=0.5.0" in {
        line.strip() for line in requirements.splitlines()
    }


def test_tools_package_keeps_legacy_exports():
    tools = importlib.import_module("agent_app.tools")

    for name in [
        "python_exec",
        "latex_compile",
        "read_csv_info",
        "TOOLS",
        "TOOLS_FULL",
    ]:
        assert hasattr(tools, name)


def test_new_architecture_packages_import():
    for module_name in [
        "agent_app.domain",
        "agent_app.infra",
        "agent_app.services",
        "agent_app.evaluators",
        "agent_app.deepagent",
        "agent_app.workflows",
        "agent_app.interfaces",
    ]:
        assert importlib.import_module(module_name) is not None
