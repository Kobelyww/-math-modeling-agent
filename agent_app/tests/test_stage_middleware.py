from __future__ import annotations

import pytest

from agent_app.deepagent.middleware import CompetitionStageMiddleware, StageDefinition


def test_stage_middleware_exposes_initial_tools():
    middleware = CompetitionStageMiddleware()

    assert middleware.current_stage == "ingest_inputs"
    assert middleware.available_tools() == ["ingest_inputs"]


def test_stage_middleware_advances_after_required_tool():
    middleware = CompetitionStageMiddleware()

    middleware.record_tool_result("ingest_inputs", {"inputs_manifest": {}})

    assert middleware.current_stage == "understand_problem"
    assert middleware.available_tools() == ["analyze_problem"]


def test_stage_middleware_rejects_tool_outside_current_stage():
    middleware = CompetitionStageMiddleware()

    with pytest.raises(PermissionError, match="not available"):
        middleware.validate_tool("run_experiment")


def test_stage_middleware_can_mark_gate_failure_without_advancing():
    middleware = CompetitionStageMiddleware()
    middleware.record_gate_result("input", passed=False, required_fixes=["缺少输入清单"])

    assert middleware.current_stage == "ingest_inputs"
    assert middleware.gate_failures[-1]["gate_name"] == "input"


def test_custom_stage_definition_supports_repair_tool():
    middleware = CompetitionStageMiddleware(
        stages=[
            StageDefinition("run_experiments", ["run_experiment", "repair_code"], ["run_experiment"]),
            StageDefinition("done", [], []),
        ]
    )

    assert middleware.available_tools() == ["run_experiment", "repair_code"]
    middleware.record_tool_result("run_experiment", {"experiment_result": {"execution_status": "success"}})
    assert middleware.current_stage == "done"
