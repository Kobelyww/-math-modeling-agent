"""Tests for DeepSeek agent loop decision primitives."""

from __future__ import annotations

import pytest

from agent_app.agent_loop import (
    ACTION_TO_ROLE,
    AgentLoopDecision,
    AgentLoopState,
    AgentLoopTrace,
    VALID_AGENT_LOOP_ACTIONS,
    parse_coordinator_decision,
    fallback_next_decision,
)
from agent_app.conditions import TokenBudgetCondition
from agent_app.memory import SharedMemory
from agent_app.orchestrator import Orchestrator, StageResult, WorkflowResult


class StubAgent:
    def __init__(self, role: str, output: str):
        self.role = role
        self.output = output
        self.last_usage = {"prompt_tokens": 1, "completion_tokens": 1}


def test_parse_coordinator_decision_accepts_json_object():
    decision = parse_coordinator_decision(
        '{"action": "model", "reason": "Need a mathematical formulation", '
        '"target_agent": "modeler", "instruction": "Build variables and constraints"}'
    )

    assert decision.action == "model"
    assert decision.target_agent == "modeler"
    assert "mathematical" in decision.reason
    assert "constraints" in decision.instruction


def test_action_to_role_covers_routed_valid_actions():
    routed_actions = VALID_AGENT_LOOP_ACTIONS - {"ask_user", "final"}

    assert routed_actions <= ACTION_TO_ROLE.keys()
    assert ACTION_TO_ROLE["explore"] == "explore"


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


def test_parse_coordinator_decision_accepts_bare_json_with_trailing_braces():
    decision = parse_coordinator_decision(
        '{"action": "review", "reason": "Check the result"} trailing {not json}'
    )

    assert decision.action == "review"
    assert decision.reason == "Check the result"


def test_parse_coordinator_decision_accepts_fence_with_space_before_label():
    decision = parse_coordinator_decision(
        "``` json\n"
        '{"action": "synthesize", "reason": "Summarize deliverables"}'
        "\n```"
    )

    assert decision.action == "synthesize"
    assert decision.reason == "Summarize deliverables"


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


def test_solve_agent_loop_runs_stubbed_dynamic_steps(monkeypatch):
    orch = Orchestrator.__new__(Orchestrator)
    orch.memory = None
    orch.rag = None
    orch.modeler = StubAgent("modeler", "model output")
    orch.programmer = StubAgent("programmer", "program output")
    orch.code_debugger = StubAgent("code_debugger", "debug output")
    orch.writer = StubAgent("writer", "writing output")
    orch.reviewer = StubAgent("reviewer", "review output")
    orch.synthesizer = StubAgent("synthesizer", "synthesis output")
    orch.data_engineer = StubAgent("data_engineer", "data output")
    orch.planner = StubAgent("planner", "planner output")

    decisions = iter([
        AgentLoopDecision("model", "Need a model", "modeler", "model now"),
        AgentLoopDecision("program", "Need code", "programmer", "code now"),
        AgentLoopDecision("debug", "Check code", "code_debugger", "debug now"),
        AgentLoopDecision("write", "Need paper", "writer", "write now"),
        AgentLoopDecision("synthesize", "Wrap up", "synthesizer", "summarize now"),
        AgentLoopDecision("final", "Done", "synthesizer", ""),
    ])

    monkeypatch.setattr(orch, "_rag_context", lambda question, top_k=6: "rag context")
    monkeypatch.setattr(orch, "_get_stm", lambda memory=None: memory or SharedMemory())
    monkeypatch.setattr(orch, "_get_stm_context", lambda mem, max_tokens=3000, compressed_only=False: "")
    monkeypatch.setattr(
        orch,
        "_decide_agent_loop_next",
        lambda state, rag_ctx, max_steps, **kwargs: next(decisions),
        raising=False,
    )
    monkeypatch.setattr(orch, "_finalize_workflow", lambda result: result)
    monkeypatch.setattr(orch, "_maybe_archive", lambda question, result_summary: None)

    def fake_safe_invoke(agent, prompt, role_label, stm, errors, **kwargs):
        output = agent.output
        stm.post(role_label, output)
        return output

    monkeypatch.setattr(orch, "_safe_invoke", fake_safe_invoke)

    result = orch.solve_agent_loop("build a traffic model", max_steps=8)

    assert isinstance(result, WorkflowResult)
    assert result.modeling.content == "model output"
    assert result.programming.content == "program output\n\n## Code Review\n\ndebug output"
    assert result.writing.content == "writing output"
    assert result.synthesis == "synthesis output"
    assert len(result.agent_loop_trace) == 5


def test_decide_agent_loop_next_counts_coordinator_usage():
    class CoordinatorStub:
        last_usage = {"prompt_tokens": 11, "completion_tokens": 7}

        def invoke(self, prompt):
            return '{"action": "model", "reason": "Need model"}'

    orch = Orchestrator.__new__(Orchestrator)
    orch.synthesizer = CoordinatorStub()
    state = AgentLoopState(question="build a model")
    budget = TokenBudgetCondition(max_total_tokens=100)

    decision = orch._decide_agent_loop_next(state, "rag", 4, token_budget=budget)

    assert decision.action == "model"
    assert budget.accumulated == 18
    assert state.errors == []


def test_decide_agent_loop_next_records_fallback_error():
    class BrokenCoordinatorStub:
        last_usage = {"prompt_tokens": 5, "completion_tokens": 0}

        def invoke(self, prompt):
            return "not json"

    orch = Orchestrator.__new__(Orchestrator)
    orch.synthesizer = BrokenCoordinatorStub()
    state = AgentLoopState(question="build a model")
    budget = TokenBudgetCondition(max_total_tokens=100)

    decision = orch._decide_agent_loop_next(state, "rag", 4, token_budget=budget)

    assert decision.action == "model"
    assert budget.accumulated == 5
    assert state.errors
    assert "agent_loop_decision" in state.errors[0]


def test_cli_default_mode_constant_is_agent_loop():
    from agent_app.cli import DEFAULT_ORCHESTRATOR_MODE

    assert DEFAULT_ORCHESTRATOR_MODE == "agent_loop"


def test_cli_solve_dispatches_agent_loop(monkeypatch):
    from agent_app.cli import CLI

    cli = CLI.__new__(CLI)
    cli.mode = "agent_loop"
    called = {}

    class FakeOrchestrator:
        def solve_agent_loop(self, question):
            called["question"] = question
            return WorkflowResult(
                question=question,
                modeling=StageResult("model", "m"),
                programming=StageResult("program", "p"),
                writing=StageResult("write", "w"),
                synthesis="s",
            )

    cli.orchestrator = FakeOrchestrator()
    monkeypatch.setattr(
        cli,
        "_print_result",
        lambda result: called.setdefault("printed", result.synthesis),
    )

    cli.solve("traffic task")

    assert called["question"] == "traffic task"
    assert called["printed"] == "s"


def test_web_default_strategy_is_agent_loop():
    from agent_app.web.routes import DEFAULT_SOLVE_STRATEGY

    assert DEFAULT_SOLVE_STRATEGY == "agent_loop"


def test_web_solver_selector_supports_agent_loop():
    from agent_app.web.routes import _select_solver_for_strategy

    class FakeOrchestrator:
        def solve_agent_loop(self):
            return "agent_loop"

        def solve_stream(self):
            return "stream"

        def solve_with_review_stream(self):
            return "review"

        def solve_parallel_stream(self):
            return "parallel"

    solver = _select_solver_for_strategy(FakeOrchestrator(), "agent_loop")

    assert solver.__name__ == "solve_agent_loop"


def test_gui_default_mode_is_agent_loop():
    from agent_app.gui import COLLABORATION_MODES

    assert COLLABORATION_MODES[0] == "agent_loop"
