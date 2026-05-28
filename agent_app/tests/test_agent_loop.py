"""Tests for DeepSeek agent loop decision primitives."""

from __future__ import annotations

import pytest

from agent_app.agent_loop import (
    AgentLoopState,
    AgentLoopTrace,
    parse_coordinator_decision,
    fallback_next_decision,
)


def test_parse_coordinator_decision_accepts_json_object():
    decision = parse_coordinator_decision(
        '{"action": "model", "reason": "Need a mathematical formulation", '
        '"target_agent": "modeler", "instruction": "Build variables and constraints"}'
    )

    assert decision.action == "model"
    assert decision.target_agent == "modeler"
    assert "mathematical" in decision.reason
    assert "constraints" in decision.instruction


def test_parse_coordinator_decision_extracts_json_from_markdown():
    decision = parse_coordinator_decision(
        "I will choose this:\n```json\n"
        '{"action": "program", "reason": "Model is ready"}'
        "\n```"
    )

    assert decision.action == "program"
    assert decision.reason == "Model is ready"


def test_parse_coordinator_decision_cleans_null_optional_fields():
    decision = parse_coordinator_decision(
        '{"action": "ask_user", "reason": null, '
        '"target_agent": null, "instruction": null}'
    )

    assert decision.reason == ""
    assert decision.target_agent == ""
    assert decision.instruction == ""


def test_parse_coordinator_decision_accepts_uppercase_fence_with_trailing_braces():
    decision = parse_coordinator_decision(
        "Decision follows:\n```JSON\n"
        '{"action": "review", "reason": "Check the result"}'
        "\n```\nTrailing prose can contain braces like {not json}."
    )

    assert decision.action == "review"
    assert decision.reason == "Check the result"


def test_parse_coordinator_decision_rejects_unknown_action():
    with pytest.raises(ValueError, match="Unknown agent loop action"):
        parse_coordinator_decision('{"action": "teleport", "reason": "bad"}')


def test_trace_text_returns_empty_string_for_zero_max_chars():
    state = AgentLoopState(
        question="optimize traffic",
        trace=[
            AgentLoopTrace(
                step=1,
                action="model",
                role="modeling",
                reason="Need model",
                instruction="Build model",
                output="model output",
            )
        ],
    )

    assert state.trace_text(max_chars=0) == ""


def test_fallback_next_decision_progresses_through_missing_outputs():
    state = AgentLoopState(question="optimize traffic")
    assert fallback_next_decision(state).action == "model"

    state.record_output("modeling", "model output")
    assert fallback_next_decision(state).action == "program"

    state.record_output("programming", "code output")
    assert fallback_next_decision(state).action == "debug"

    state.record_output("code_debugger", "debug output")
    assert fallback_next_decision(state).action == "write"

    state.record_output("writing", "paper output")
    assert fallback_next_decision(state).action == "synthesize"

    state.record_output("synthesizer", "final summary")
    assert fallback_next_decision(state).action == "final"
