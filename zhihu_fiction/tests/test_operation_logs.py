"""Tests for operation log workspace model contracts."""
from __future__ import annotations

import pytest

from zhihu_fiction.workspace.models import OperationLog


def test_operation_log_round_trips_actor_target_and_metadata():
    log = OperationLog(
        id="op_1",
        project_id="project_1",
        action="generate_stage",
        actor="planner_agent",
        target_kind="stage_version",
        target_id="version_1",
        session_id="deepagent_1",
        run_id="run_1",
        message="generated script draft",
        created_at="2026-06-15T10:00:00+00:00",
        metadata={"stage": "script", "attempt": 2},
    )

    payload = log.to_dict()
    restored = OperationLog.from_dict(payload)

    assert payload == {
        "id": "op_1",
        "project_id": "project_1",
        "action": "generate_stage",
        "actor": "planner_agent",
        "target_kind": "stage_version",
        "target_id": "version_1",
        "session_id": "deepagent_1",
        "run_id": "run_1",
        "message": "generated script draft",
        "created_at": "2026-06-15T10:00:00+00:00",
        "metadata": {"stage": "script", "attempt": 2},
    }
    assert restored == log


@pytest.mark.parametrize(
    "field, value",
    [
        ("project_id", ""),
        ("actor", ""),
        ("target_id", ""),
    ],
)
def test_operation_log_requires_project_actor_and_target(field, value):
    kwargs = {
        "id": "op_1",
        "project_id": "project_1",
        "action": "start_session",
        "actor": "human",
        "target_kind": "drama_session",
        "target_id": "deepagent_1",
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        OperationLog(**kwargs)


@pytest.mark.parametrize(
    "field, value",
    [
        ("action", "unknown_action"),
        ("target_kind", "unknown_target"),
    ],
)
def test_operation_log_validates_action_and_target_kind(field, value):
    kwargs = {
        "id": "op_1",
        "project_id": "project_1",
        "action": "start_session",
        "actor": "human",
        "target_kind": "drama_session",
        "target_id": "deepagent_1",
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        OperationLog(**kwargs)
