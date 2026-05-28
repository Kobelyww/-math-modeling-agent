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
