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


def test_repeated_tool_names_are_completed_per_stage():
    middleware = CompetitionStageMiddleware(
        stages=[
            StageDefinition("inspect_a", ["inspect"], ["inspect"]),
            StageDefinition("inspect_b", ["repair", "inspect"], ["inspect"]),
            StageDefinition("done", [], []),
        ]
    )

    middleware.record_tool_result("inspect", {"stage": "a"})
    assert middleware.current_stage == "inspect_b"

    middleware.record_tool_result("repair", {"stage": "b", "repair": True})
    assert middleware.current_stage == "inspect_b"

    middleware.record_tool_result("inspect", {"stage": "b"})
    assert middleware.current_stage == "done"


def test_repeated_tool_results_are_stage_scoped():
    middleware = CompetitionStageMiddleware(
        stages=[
            StageDefinition("inspect_a", ["inspect"], ["inspect"]),
            StageDefinition("inspect_b", ["inspect"], ["inspect"]),
            StageDefinition("done", [], []),
        ]
    )

    middleware.record_tool_result("inspect", {"stage": "a"})
    middleware.record_tool_result("inspect", {"stage": "b"})

    assert middleware.stage_results["inspect_a"]["inspect"] == {"stage": "a"}
    assert middleware.stage_results["inspect_b"]["inspect"] == {"stage": "b"}


def test_empty_stage_list_raises_value_error():
    with pytest.raises(ValueError, match="at least one"):
        CompetitionStageMiddleware(stages=[])


def test_required_tool_not_in_stage_tools_raises_value_error():
    with pytest.raises(ValueError, match="required tools"):
        CompetitionStageMiddleware(
            stages=[
                StageDefinition("inspect", ["inspect"], ["missing"]),
                StageDefinition("done", [], []),
            ]
        )


@pytest.mark.parametrize(
    "stages",
    [
        [StageDefinition("", ["inspect"], ["inspect"]), StageDefinition("done", [], [])],
        [StageDefinition("inspect", ["inspect"], ["inspect"]), StageDefinition("inspect", [], [])],
    ],
)
def test_blank_or_duplicate_stage_name_raises_value_error(stages):
    with pytest.raises(ValueError, match="stage name"):
        CompetitionStageMiddleware(stages=stages)


def test_gate_failure_blocks_advancement_until_same_gate_passes():
    middleware = CompetitionStageMiddleware(
        stages=[
            StageDefinition("inspect", ["inspect"], ["inspect"]),
            StageDefinition("done", [], []),
        ]
    )

    middleware.record_gate_result("input", passed=False, required_fixes=["missing manifest"])
    middleware.record_tool_result("inspect", {"stage": "blocked"})
    assert middleware.current_stage == "inspect"

    middleware.record_gate_result("input", passed=True)
    assert middleware.current_stage == "done"


def test_default_stage_definitions_are_isolated_between_instances():
    first = CompetitionStageMiddleware()
    second = CompetitionStageMiddleware()

    assert isinstance(first.stages, tuple)
    assert isinstance(first.stages[0].tools, tuple)
    assert first.stages is not second.stages
    assert first.stages[0] is not second.stages[0]
