from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_app.domain.models import ArtifactRef, RunSpec, RunStage, RunStatus
from agent_app.services.artifact_service import ArtifactService
from agent_app.services.run_store import RunStore


def test_run_store_creates_traceable_run_directory(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="优化配送路径"))

    assert state.run_id.startswith("run_")
    assert (tmp_path / state.run_id).is_dir()
    assert (tmp_path / state.run_id / "run.json").exists()

    payload = json.loads((tmp_path / state.run_id / "run.json").read_text(encoding="utf-8"))
    assert payload["spec"]["question"] == "优化配送路径"
    assert payload["status"] == "pending"


def test_run_store_persists_stage_status_and_artifacts(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="预测销量"))
    state.stage = RunStage.AUDIT_DATA
    state.status = RunStatus.RUNNING
    state.artifacts.append(ArtifactRef(name="audit", path=Path("data_audit.md"), kind="markdown"))

    store.save_state(state)
    restored = store.load_state(state.run_id)

    assert restored.stage == RunStage.AUDIT_DATA
    assert restored.status == RunStatus.RUNNING
    assert restored.artifacts[0].path == Path("data_audit.md")


def test_artifact_service_writes_inside_run_directory(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="分析"))
    artifacts = ArtifactService(store.run_dir(state.run_id))

    path = artifacts.write_text("notes/problem.md", "# Problem\n")

    assert path == store.run_dir(state.run_id) / "notes" / "problem.md"
    assert path.read_text(encoding="utf-8") == "# Problem\n"


def test_artifact_service_rejects_path_traversal(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="分析"))
    artifacts = ArtifactService(store.run_dir(state.run_id))

    with pytest.raises(ValueError, match="outside run directory"):
        artifacts.write_text("../escape.md", "bad")
