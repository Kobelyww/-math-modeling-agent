from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from langchain.agents.middleware import AgentMiddleware
except Exception:  # pragma: no cover
    class AgentMiddleware:  # type: ignore[no-redef]
        pass


@dataclass(frozen=True)
class StageDefinition:
    name: str
    tools: list[str]
    required_tools: list[str]


DEFAULT_STAGES = [
    StageDefinition("ingest_inputs", ["ingest_inputs"], ["ingest_inputs"]),
    StageDefinition("understand_problem", ["analyze_problem"], ["analyze_problem"]),
    StageDefinition("audit_data", ["audit_data"], ["audit_data"]),
    StageDefinition("retrieve_evidence", ["retrieve_evidence"], ["retrieve_evidence"]),
    StageDefinition("plan_modeling", ["plan_model"], ["plan_model"]),
    StageDefinition("run_experiments", ["run_experiment", "repair_code"], ["run_experiment"]),
    StageDefinition("draft_paper", ["draft_competition_paper"], ["draft_competition_paper"]),
    StageDefinition("review_and_revise", ["review_submission"], ["review_submission"]),
    StageDefinition("package_submission", ["package_submission"], ["package_submission"]),
    StageDefinition("done", [], []),
]


class CompetitionStageMiddleware(AgentMiddleware):
    def __init__(self, stages: list[StageDefinition] | None = None) -> None:
        super().__init__()
        self.stages = stages or DEFAULT_STAGES
        self.stage_index = 0
        self.tool_history: list[str] = []
        self.stage_results: dict[str, Any] = {}
        self.gate_failures: list[dict[str, Any]] = []

    @property
    def current_stage(self) -> str:
        return self.stages[self.stage_index].name

    def available_tools(self) -> list[str]:
        return list(self.stages[self.stage_index].tools)

    def validate_tool(self, tool_name: str) -> None:
        if tool_name not in self.available_tools():
            raise PermissionError(f"Tool {tool_name!r} is not available during stage {self.current_stage!r}")

    def record_tool_result(self, tool_name: str, result: Any) -> None:
        self.validate_tool(tool_name)
        self.tool_history.append(tool_name)
        self.stage_results[tool_name] = result
        self._advance_if_ready()

    def record_gate_result(self, gate_name: str, passed: bool, required_fixes: list[str] | None = None) -> None:
        if not passed:
            self.gate_failures.append(
                {
                    "gate_name": gate_name,
                    "stage": self.current_stage,
                    "required_fixes": required_fixes or [],
                }
            )

    def _advance_if_ready(self) -> None:
        stage = self.stages[self.stage_index]
        if all(name in self.tool_history for name in stage.required_tools):
            self.stage_index = min(self.stage_index + 1, len(self.stages) - 1)
