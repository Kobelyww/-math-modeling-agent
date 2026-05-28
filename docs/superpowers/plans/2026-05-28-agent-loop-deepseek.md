# DeepSeek Agent Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `agent_app` default to a DeepSeek-backed conversation-driven agent loop instead of a fixed workflow.

**Architecture:** Add a focused `agent_app/agent_loop.py` module for structured decisions and fallback policy, then wire `Orchestrator.solve_agent_loop()` through existing agents, RAG, memory, and output finalization. Keep legacy workflow methods intact and update CLI/Web/GUI defaults to use `agent_loop`.

**Tech Stack:** Python, LangChain chat models, existing DeepSeek integration, pytest, FastAPI route helpers, Streamlit constants.

---

## Repository Ownership Note

The GitHub remote is `git@github.com:Kobelyww/-math-modeling-agent.git`. Do not push, open PRs, or run GitHub account-bound commands from a different account. Local commits are fine; any remote operation must be confirmed to use the `kobelyww`/`Kobelyww` repository ownership context first.

## File Structure

- Create `agent_app/agent_loop.py`: dataclasses and pure functions for coordinator decisions, loop trace, state, JSON parsing, fallback action selection, and result normalization helpers.
- Create `agent_app/tests/test_agent_loop.py`: unit tests for parsing, fallback policy, and stubbed `solve_agent_loop()`.
- Modify `agent_app/orchestrator.py`: import loop primitives, add coordinator decision prompt, add `solve_agent_loop()`, and keep legacy solve methods unchanged.
- Modify `agent_app/cli.py`: default mode becomes `agent_loop`, help text includes legacy modes, and `solve()` dispatches to `solve_agent_loop()`.
- Modify `agent_app/web/routes.py`: default API strategy becomes `agent_loop`, and route dispatch calls the new loop.
- Modify `agent_app/gui.py`: add `agent_loop` as the first/default collaboration strategy and dispatch to `solve_agent_loop()`.
- Modify `agent_app/README.md`: document the new default mode and legacy fallback modes.

## Task 1: Agent Loop Decision Primitives

**Files:**
- Create: `agent_app/agent_loop.py`
- Create: `agent_app/tests/test_agent_loop.py`

- [ ] **Step 1: Write the failing tests**

Add this test file:

```python
"""Tests for DeepSeek agent loop decision primitives."""

from __future__ import annotations

import pytest

from agent_app.agent_loop import (
    AgentLoopState,
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


def test_parse_coordinator_decision_rejects_unknown_action():
    with pytest.raises(ValueError, match="Unknown agent loop action"):
        parse_coordinator_decision('{"action": "teleport", "reason": "bad"}')


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py -v
```

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'agent_app.agent_loop'`.

- [ ] **Step 3: Implement the decision primitives**

Create `agent_app/agent_loop.py`:

```python
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

VALID_AGENT_LOOP_ACTIONS = {
    "explore",
    "model",
    "program",
    "debug",
    "write",
    "review",
    "synthesize",
    "ask_user",
    "final",
}

ACTION_TO_ROLE = {
    "model": "modeling",
    "program": "programming",
    "debug": "code_debugger",
    "write": "writing",
    "review": "reviewer",
    "synthesize": "synthesizer",
}


@dataclass(frozen=True)
class AgentLoopDecision:
    action: str
    reason: str = ""
    target_agent: str = ""
    instruction: str = ""


@dataclass
class AgentLoopTrace:
    step: int
    action: str
    role: str
    reason: str
    instruction: str
    output: str = ""


@dataclass
class AgentLoopState:
    question: str
    outputs: dict[str, str] = field(default_factory=dict)
    trace: list[AgentLoopTrace] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def record_output(self, role: str, content: str) -> None:
        self.outputs[role] = content

    def latest(self, role: str) -> str:
        return self.outputs.get(role, "")

    def has(self, role: str) -> bool:
        return bool(self.outputs.get(role, "").strip())

    def trace_text(self, max_chars: int = 6000) -> str:
        parts = []
        for item in self.trace:
            parts.append(
                f"[{item.step}] action={item.action} role={item.role}\n"
                f"reason={item.reason}\n"
                f"instruction={item.instruction}\n"
                f"output={item.output[:1200]}"
            )
        text = "\n\n".join(parts)
        return text[-max_chars:]


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return stripped


def parse_coordinator_decision(text: str) -> AgentLoopDecision:
    try:
        payload: Any = json.loads(_extract_json_object(text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid coordinator decision JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Coordinator decision must be a JSON object")

    action = str(payload.get("action", "")).strip().lower()
    if action not in VALID_AGENT_LOOP_ACTIONS:
        raise ValueError(f"Unknown agent loop action: {action}")

    return AgentLoopDecision(
        action=action,
        reason=str(payload.get("reason", "")).strip(),
        target_agent=str(payload.get("target_agent", "")).strip(),
        instruction=str(payload.get("instruction", "")).strip(),
    )


def fallback_next_decision(state: AgentLoopState) -> AgentLoopDecision:
    if not state.has("modeling"):
        return AgentLoopDecision("model", "No modeling output exists yet.", "modeler")
    if not state.has("programming"):
        return AgentLoopDecision("program", "No programming output exists yet.", "programmer")
    if not state.has("code_debugger"):
        return AgentLoopDecision("debug", "Programming output has not been reviewed.", "code_debugger")
    if not state.has("writing"):
        return AgentLoopDecision("write", "No paper writing output exists yet.", "writer")
    if not state.has("synthesizer"):
        return AgentLoopDecision("synthesize", "Deliverables need final synthesis.", "synthesizer")
    return AgentLoopDecision("final", "All core deliverables are available.", "synthesizer")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py -v
```

Expected: PASS for all 4 tests.

- [ ] **Step 5: Commit**

Run:

```bash
git add agent_app/agent_loop.py agent_app/tests/test_agent_loop.py
git commit -m "feat: add agent loop decision primitives"
```

## Task 2: Orchestrator Agent Loop

**Files:**
- Modify: `agent_app/orchestrator.py`
- Modify: `agent_app/tests/test_agent_loop.py`

- [ ] **Step 1: Add a failing orchestrator test**

Append this test to `agent_app/tests/test_agent_loop.py`:

```python
from agent_app.agent_loop import AgentLoopDecision
from agent_app.memory import SharedMemory
from agent_app.orchestrator import Orchestrator, WorkflowResult


class StubAgent:
    def __init__(self, role: str, output: str):
        self.role = role
        self.output = output
        self.last_usage = {"prompt_tokens": 1, "completion_tokens": 1}


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

    decisions = iter(
        [
            AgentLoopDecision("model", "Need a model", "modeler", "model now"),
            AgentLoopDecision("program", "Need code", "programmer", "code now"),
            AgentLoopDecision("debug", "Check code", "code_debugger", "debug now"),
            AgentLoopDecision("write", "Need paper", "writer", "write now"),
            AgentLoopDecision("synthesize", "Wrap up", "synthesizer", "summarize now"),
            AgentLoopDecision("final", "Done", "synthesizer", ""),
        ]
    )

    monkeypatch.setattr(orch, "_rag_context", lambda question, top_k=6: "rag context")
    monkeypatch.setattr(orch, "_get_stm", lambda memory=None: memory or SharedMemory())
    monkeypatch.setattr(orch, "_get_stm_context", lambda mem, max_tokens=3000, compressed_only=False: "")
    monkeypatch.setattr(orch, "_decide_agent_loop_next", lambda state, rag_ctx, max_steps: next(decisions))
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py::test_solve_agent_loop_runs_stubbed_dynamic_steps -v
```

Expected: FAIL with `AttributeError: 'Orchestrator' object has no attribute 'solve_agent_loop'`.

- [ ] **Step 3: Add result trace field and loop imports**

In `agent_app/orchestrator.py`, add the import near existing imports:

```python
from .agent_loop import (
    ACTION_TO_ROLE,
    AgentLoopDecision,
    AgentLoopState,
    AgentLoopTrace,
    fallback_next_decision,
    parse_coordinator_decision,
)
```

Add this field to `WorkflowResult`:

```python
    agent_loop_trace: list[AgentLoopTrace] = field(default_factory=list)
```

Add trace serialization inside `WorkflowResult.to_dict()`:

```python
            "agent_loop_trace": [
                {
                    "step": item.step,
                    "action": item.action,
                    "role": item.role,
                    "reason": item.reason,
                    "instruction": item.instruction,
                    "output": item.output,
                }
                for item in self.agent_loop_trace
            ],
```

- [ ] **Step 4: Add coordinator decision helpers to `Orchestrator`**

Add these methods before the existing strategy methods:

```python
    def _build_agent_loop_decision_prompt(
        self,
        state: AgentLoopState,
        rag_ctx: str,
        max_steps: int,
    ) -> str:
        available = ", ".join([
            "explore", "model", "program", "debug", "write",
            "review", "synthesize", "ask_user", "final",
        ])
        return (
            "You are the coordinator for a math-modeling agent loop. "
            "Choose exactly one next action based on the current state. "
            "Return only JSON with keys: action, reason, target_agent, instruction.\n\n"
            f"Available actions: {available}\n"
            f"Question:\n{state.question}\n\n"
            f"RAG context:\n{rag_ctx[:4000]}\n\n"
            f"Existing outputs:\n"
            f"- modeling: {'yes' if state.has('modeling') else 'no'}\n"
            f"- programming: {'yes' if state.has('programming') else 'no'}\n"
            f"- code_debugger: {'yes' if state.has('code_debugger') else 'no'}\n"
            f"- writing: {'yes' if state.has('writing') else 'no'}\n"
            f"- synthesizer: {'yes' if state.has('synthesizer') else 'no'}\n\n"
            f"Recent trace:\n{state.trace_text()}\n\n"
            f"Step budget: {len(state.trace)}/{max_steps}\n"
            "Prefer making progress with specialist agents. Use ask_user only if the task "
            "cannot proceed without missing user data. Use final only after synthesis exists."
        )

    def _decide_agent_loop_next(
        self,
        state: AgentLoopState,
        rag_ctx: str,
        max_steps: int,
    ) -> AgentLoopDecision:
        prompt = self._build_agent_loop_decision_prompt(state, rag_ctx, max_steps)
        try:
            raw = self.synthesizer.invoke(prompt)
            decision = parse_coordinator_decision(raw)
        except Exception as exc:
            state.errors.append(f"[agent_loop_decision] {exc}")
            return fallback_next_decision(state)

        if decision.action == "final" and not state.has("synthesizer"):
            return fallback_next_decision(state)
        return decision
```

- [ ] **Step 5: Add `solve_agent_loop()`**

Add this method before `solve_with_plan()`:

```python
    def solve_agent_loop(
        self,
        question: str,
        top_k: int = 6,
        memory: SharedMemory | None = None,
        max_steps: int = 10,
        enable_data_engineer: bool = False,
        conditions: list[BaseCondition] | None = None,
    ) -> WorkflowResult:
        del enable_data_engineer
        mem = self._get_stm(memory)
        rag_ctx = self._rag_context(question, top_k)
        errors: list[str] = []
        token_budget = TokenBudgetCondition(max_total_tokens=200000)
        timeout = TimeoutCondition(timeout_seconds=600.0)
        timeout.start()
        started_at = time_module.monotonic()
        state = AgentLoopState(question=question)

        active_conditions: list[BaseCondition] = [token_budget, timeout]
        if conditions:
            active_conditions.extend(conditions)

        for step in range(1, max_steps + 1):
            stop_reason = self._check_conditions(active_conditions, mem, step, timeout.elapsed)
            if stop_reason:
                errors.append(stop_reason)
                break

            decision = self._decide_agent_loop_next(state, rag_ctx, max_steps)
            if decision.action == "final":
                break
            if decision.action == "ask_user":
                state.record_output("synthesizer", decision.instruction or decision.reason)
                break

            role = ACTION_TO_ROLE.get(decision.action, "")
            output = ""

            if decision.action == "explore":
                output = self._rag_context(question, top_k)
                role = "explore"
                self._post(mem, role, output, token_budget=token_budget)
            elif decision.action == "model":
                output = self._safe_invoke(
                    self.modeler,
                    self._build_prompt(
                        question,
                        self._get_stm_context(mem, compressed_only=True),
                        rag_ctx,
                        {"Coordinator instruction": decision.instruction},
                        agent_role="modeler",
                        inject_skills=True,
                    ),
                    "modeling",
                    mem,
                    errors,
                    token_budget=token_budget,
                )
            elif decision.action == "program":
                output = self._safe_invoke(
                    self.programmer,
                    self._build_prompt(
                        question,
                        self._get_stm_context(mem, compressed_only=True),
                        rag_ctx,
                        {
                            "Coordinator instruction": decision.instruction,
                            "Modeling output": state.latest("modeling"),
                        },
                        agent_role="programmer",
                        inject_skills=True,
                    ),
                    "programming",
                    mem,
                    errors,
                    triggered_by="modeling",
                    token_budget=token_budget,
                )
            elif decision.action == "debug":
                output = self._safe_invoke(
                    self.code_debugger,
                    self._build_prompt(
                        question,
                        self._get_stm_context(mem, compressed_only=True),
                        "",
                        {
                            "Coordinator instruction": decision.instruction,
                            "Programming output": state.latest("programming")[:4000],
                        },
                        agent_role="code_debugger",
                        inject_skills=True,
                    ),
                    "code_debugger",
                    mem,
                    errors,
                    triggered_by="programming",
                    token_budget=token_budget,
                )
            elif decision.action == "write":
                output = self._safe_invoke(
                    self.writer,
                    self._build_prompt(
                        question,
                        self._get_stm_context(mem, compressed_only=True),
                        rag_ctx,
                        {
                            "Coordinator instruction": decision.instruction,
                            "Modeling output": state.latest("modeling"),
                            "Programming output": state.latest("programming"),
                            "Code review": state.latest("code_debugger"),
                        },
                        agent_role="writer",
                        inject_skills=True,
                    ),
                    "writing",
                    mem,
                    errors,
                    triggered_by="code_debugger",
                    token_budget=token_budget,
                )
            elif decision.action == "review":
                target = decision.target_agent or "latest"
                target_output = state.latest("writing") or state.latest("programming") or state.latest("modeling")
                output = self.reviewer.review(target, target_output, question)
                self._post(mem, "reviewer", output, triggered_by=target, token_budget=token_budget)
                role = "reviewer"
            elif decision.action == "synthesize":
                output = self._safe_invoke(
                    self.synthesizer,
                    self._build_prompt(
                        question,
                        self._get_stm_context(mem, compressed_only=True),
                        "",
                        {
                            "Coordinator instruction": decision.instruction,
                            "Modeling output": state.latest("modeling"),
                            "Programming output": state.latest("programming"),
                            "Code review": state.latest("code_debugger"),
                            "Writing output": state.latest("writing"),
                        },
                        agent_role="synthesizer",
                        inject_skills=True,
                    ),
                    "synthesizer",
                    mem,
                    errors,
                    triggered_by="writing",
                    token_budget=token_budget,
                )
            else:
                errors.append(f"Unknown agent loop action: {decision.action}")
                continue

            state.record_output(role, output)
            state.trace.append(
                AgentLoopTrace(
                    step=step,
                    action=decision.action,
                    role=role,
                    reason=decision.reason,
                    instruction=decision.instruction,
                    output=output,
                )
            )
            mem.advance_round()

        if not state.has("synthesizer"):
            fallback_summary = (
                "Agent loop stopped before final synthesis.\n\n"
                f"Modeling:\n{state.latest('modeling')}\n\n"
                f"Programming:\n{state.latest('programming')}\n\n"
                f"Writing:\n{state.latest('writing')}"
            )
            state.record_output("synthesizer", fallback_summary)

        self._maybe_archive(question, state.latest("synthesizer"))
        self._reset_conditions(active_conditions)

        programming = state.latest("programming")
        if state.has("code_debugger"):
            programming = f"{programming}\n\n## Code Review\n\n{state.latest('code_debugger')}".strip()

        return self._finalize_workflow(WorkflowResult(
            question=question,
            modeling=StageResult("建模智能体", state.latest("modeling")),
            programming=StageResult("编程智能体", programming),
            writing=StageResult("写作智能体", state.latest("writing")),
            synthesis=state.latest("synthesizer"),
            memory=mem,
            errors=[*errors, *state.errors],
            total_prompt_tokens=token_budget.accumulated,
            total_completion_tokens=0,
            elapsed_seconds=time_module.monotonic() - started_at,
            agent_loop_trace=state.trace,
        ))
```

- [ ] **Step 6: Run the orchestrator test to verify it passes**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py::test_solve_agent_loop_runs_stubbed_dynamic_steps -v
```

Expected: PASS.

- [ ] **Step 7: Run all agent loop tests**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py -v
```

Expected: PASS for all tests in the file.

- [ ] **Step 8: Commit**

Run:

```bash
git add agent_app/orchestrator.py agent_app/tests/test_agent_loop.py
git commit -m "feat: add DeepSeek agent loop orchestrator"
```

## Task 3: CLI Default Mode

**Files:**
- Modify: `agent_app/cli.py`
- Modify: `agent_app/tests/test_agent_loop.py`

- [ ] **Step 1: Add failing CLI tests**

Append this to `agent_app/tests/test_agent_loop.py`:

```python
def test_cli_default_mode_constant_is_agent_loop():
    from agent_app.cli import DEFAULT_ORCHESTRATOR_MODE

    assert DEFAULT_ORCHESTRATOR_MODE == "agent_loop"


def test_cli_solve_dispatches_agent_loop(monkeypatch):
    from agent_app.cli import CLI
    from agent_app.orchestrator import StageResult, WorkflowResult

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
    monkeypatch.setattr(cli, "_print_result", lambda result: called.setdefault("printed", result.synthesis))

    cli.solve("traffic task")

    assert called["question"] == "traffic task"
    assert called["printed"] == "s"
```

- [ ] **Step 2: Run the CLI tests to verify they fail**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py::test_cli_default_mode_constant_is_agent_loop agent_app/tests/test_agent_loop.py::test_cli_solve_dispatches_agent_loop -v
```

Expected: FAIL because `DEFAULT_ORCHESTRATOR_MODE` is not defined or `agent_loop` is not dispatched.

- [ ] **Step 3: Update CLI constants, help, and dispatch**

In `agent_app/cli.py`, add after the help strings:

```python
DEFAULT_ORCHESTRATOR_MODE = "agent_loop"
LEGACY_ORCHESTRATOR_MODES = ("plan", "explore", "sequential", "review", "parallel")
ORCHESTRATOR_MODES = (DEFAULT_ORCHESTRATOR_MODE, *LEGACY_ORCHESTRATOR_MODES)
```

Update help text mode list to include:

```text
  1. agent_loop   - 对话驱动 Agent Loop（默认，动态选择下一步）
  2. plan         - 规划先行（legacy）
  3. explore      - 先探索后求解（legacy）
  4. sequential   - 串行流水线（legacy）
  5. review       - 深度反思（legacy）
  6. parallel     - 快速并行（legacy）
```

Change CLI initialization:

```python
        self.mode: str = DEFAULT_ORCHESTRATOR_MODE
```

Change `solve()` dispatch so the first branch is:

```python
        if self.mode == "agent_loop":
            result = self.orchestrator.solve_agent_loop(question)
        elif self.mode == "plan":
            result = self.orchestrator.solve_with_plan(question)
```

Change `/mode` validation:

```python
                if new_mode in ORCHESTRATOR_MODES:
                    self.mode = new_mode
                    print(f"已切换到 {new_mode} 模式。")
                else:
                    print(f"无效模式。可选: {' / '.join(ORCHESTRATOR_MODES)}")
```

- [ ] **Step 4: Run the CLI tests to verify they pass**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py::test_cli_default_mode_constant_is_agent_loop agent_app/tests/test_agent_loop.py::test_cli_solve_dispatches_agent_loop -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add agent_app/cli.py agent_app/tests/test_agent_loop.py
git commit -m "feat: make agent loop the CLI default"
```

## Task 4: Web and GUI Strategy Defaults

**Files:**
- Modify: `agent_app/web/routes.py`
- Modify: `agent_app/gui.py`
- Modify: `agent_app/tests/test_agent_loop.py`

- [ ] **Step 1: Add failing route and GUI tests**

Append this to `agent_app/tests/test_agent_loop.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py::test_web_default_strategy_is_agent_loop agent_app/tests/test_agent_loop.py::test_web_solver_selector_supports_agent_loop agent_app/tests/test_agent_loop.py::test_gui_default_mode_is_agent_loop -v
```

Expected: FAIL because the constants and selector are missing.

- [ ] **Step 3: Update Web route strategy dispatch**

In `agent_app/web/routes.py`, add near router setup:

```python
DEFAULT_SOLVE_STRATEGY = "agent_loop"
```

Add this helper before `solve()`:

```python
def _select_solver_for_strategy(orch: Orchestrator, strategy: str):
    if strategy == "agent_loop":
        return orch.solve_agent_loop
    if strategy == "review":
        return orch.solve_with_review_stream
    if strategy == "parallel":
        return orch.solve_parallel_stream
    return orch.solve_stream
```

Change the API default:

```python
    strategy = data.get("strategy", DEFAULT_SOLVE_STRATEGY)
```

Change `_run_solve()` dispatch to use the helper. Keep callbacks for legacy stream methods and run `solve_agent_loop` without per-stage token callbacks:

```python
        solver = _select_solver_for_strategy(_orch, strategy)
        if strategy == "agent_loop":
            result = await asyncio.wait_for(
                asyncio.to_thread(solver, question, top_k=top_k),
                timeout=SOLVE_TASK_TIMEOUT,
            )
        elif strategy == "review":
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    solver,
                    question, top_k=top_k,
                    on_modeling_token=on_m, on_programming_token=on_p,
                    on_writing_token=on_w, on_synthesis_token=on_s,
                ),
                timeout=SOLVE_TASK_TIMEOUT,
            )
        elif strategy == "parallel":
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    solver,
                    question, top_k=top_k,
                    on_modeling_token=on_m, on_programming_token=on_p,
                    on_writing_token=on_w, on_synthesis_token=on_s,
                ),
                timeout=SOLVE_TASK_TIMEOUT,
            )
        else:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    solver,
                    question, top_k=top_k,
                    on_modeling_token=on_m, on_programming_token=on_p,
                    on_writing_token=on_w, on_synthesis_token=on_s,
                ),
                timeout=SOLVE_TASK_TIMEOUT,
            )
```

- [ ] **Step 4: Update GUI strategy list and dispatch**

In `agent_app/gui.py`, add near path constants:

```python
COLLABORATION_MODES = ["agent_loop", "sequential", "review", "parallel"]
```

Change the sidebar selectbox to use this constant:

```python
        options=COLLABORATION_MODES,
        format_func=lambda m: {
            "agent_loop": "Agent Loop（动态对话驱动）",
            "sequential": "串行流水线",
            "review": "深度反思",
            "parallel": "快速并行",
        }.get(m, m),
```

Change the non-streaming dispatch:

```python
            if mode == "agent_loop":
                result = orch.solve_agent_loop(question, top_k=top_k)
            elif mode == "sequential":
                result = orch.solve_sequential(question, top_k=top_k)
            elif mode == "review":
                result = orch.solve_with_review(question, top_k=top_k, max_review_rounds=review_rounds)
            else:
                result = orch.solve_parallel(question, top_k=top_k)
```

- [ ] **Step 5: Run the route and GUI tests to verify they pass**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py::test_web_default_strategy_is_agent_loop agent_app/tests/test_agent_loop.py::test_web_solver_selector_supports_agent_loop agent_app/tests/test_agent_loop.py::test_gui_default_mode_is_agent_loop -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add agent_app/web/routes.py agent_app/gui.py agent_app/tests/test_agent_loop.py
git commit -m "feat: default web and GUI to agent loop"
```

## Task 5: Documentation and Regression Verification

**Files:**
- Modify: `agent_app/README.md`

- [ ] **Step 1: Update README command docs**

In `agent_app/README.md`, change the CLI mode table so it includes:

```markdown
| `/mode <模式>` | 切换策略：`agent_loop` / `plan` / `explore` / `sequential` / `review` / `parallel` |
```

Change the collaboration strategies table so `agent_loop` is first:

```markdown
| **Agent Loop** | `agent_loop` | 协调者根据上下文动态选择探索、建模、编程、调试、写作、评审或总结 | 默认模式，适合开放式任务 |
| **规划先行** | `plan` | Plan→Execute→Synthesize | 需要显式计划审阅 |
| **串行流水线** | `sequential` | 建模→编程→写作→总控 | legacy 稳定路径 |
| **深度反思** | `review` | 每阶段输出后评审专家审核修改 | 追求方案质量 |
| **快速并行** | `parallel` | 建模先行，编程+写作并行 | 时间紧迫，追求速度 |
```

Add this programming example:

```python
# 默认 Agent Loop：动态决定下一步，而不是固定流水线
result = orch.solve_agent_loop("建立交通流优化模型")
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py agent_app/tests/test_orchestrator_tools.py -v
```

Expected: PASS.

- [ ] **Step 3: Run broader existing tests**

Run:

```bash
pytest agent_app/tests/test_core.py agent_app/tests/test_memory.py -v
```

Expected: PASS. If unrelated pre-existing failures appear, record the exact failing tests and error messages before final response.

- [ ] **Step 4: Commit**

Run:

```bash
git add agent_app/README.md
git commit -m "docs: document DeepSeek agent loop default"
```

## Final Verification

- [ ] Run:

```bash
pytest agent_app/tests -v
```

Expected: PASS for all `agent_app` tests, or a clearly documented list of pre-existing failures not caused by this change.

- [ ] Run:

```bash
git status --short
```

Expected: only unrelated pre-existing workspace changes remain, or a clean worktree for files touched by this plan.
