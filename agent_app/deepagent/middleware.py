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
    tools: tuple[str, ...]
    required_tools: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "tools", tuple(self.tools))
        object.__setattr__(self, "required_tools", tuple(self.required_tools))


DEFAULT_STAGES = (
    StageDefinition("ingest_inputs", ("ingest_inputs",), ("ingest_inputs",)),
    StageDefinition("understand_problem", ("analyze_problem",), ("analyze_problem",)),
    StageDefinition("audit_data", ("audit_data",), ("audit_data",)),
    StageDefinition("retrieve_evidence", ("retrieve_evidence",), ("retrieve_evidence",)),
    StageDefinition("plan_modeling", ("plan_model",), ("plan_model",)),
    StageDefinition("run_experiments", ("run_experiment", "repair_code"), ("run_experiment",)),
    StageDefinition("draft_paper", ("draft_competition_paper",), ("draft_competition_paper",)),
    StageDefinition("review_and_revise", ("review_submission",), ("review_submission",)),
    StageDefinition("package_submission", ("package_submission",), ("package_submission",)),
    StageDefinition("done", [], []),
)


class CompetitionStageMiddleware(AgentMiddleware):
    def __init__(self, stages: list[StageDefinition] | None = None) -> None:
        super().__init__()
        self.stages = self._normalize_stages(DEFAULT_STAGES if stages is None else stages)
        self.stage_index = 0
        self.tool_history: list[dict[str, Any]] = []
        self.completed_required_tools: dict[str, set[str]] = {stage.name: set() for stage in self.stages}
        self.stage_results: dict[str, dict[str, Any]] = {stage.name: {} for stage in self.stages}
        self.gate_failures: list[dict[str, Any]] = []
        self.unresolved_gate_failures: dict[str, set[str]] = {stage.name: set() for stage in self.stages}

    def _normalize_stages(self, stages: list[StageDefinition] | tuple[StageDefinition, ...]) -> tuple[StageDefinition, ...]:
        if not stages:
            raise ValueError("stages must include at least one stage")

        normalized = tuple(
            StageDefinition(stage.name, stage.tools, stage.required_tools)
            for stage in stages
        )
        self._validate_stages(normalized)
        return normalized

    def _validate_stages(self, stages: tuple[StageDefinition, ...]) -> None:
        seen_names: set[str] = set()
        for index, stage in enumerate(stages):
            stage_name = stage.name.strip()
            if not stage_name or stage_name in seen_names:
                raise ValueError("stage name must be nonblank and unique")
            seen_names.add(stage_name)

            missing_required = set(stage.required_tools) - set(stage.tools)
            if missing_required:
                raise ValueError(f"Stage {stage.name!r} has required tools outside stage tools")

            is_terminal = index == len(stages) - 1
            if is_terminal and (stage.tools or stage.required_tools):
                raise ValueError("terminal stage must have no tools and no required tools")
            if not is_terminal and not stage.required_tools:
                raise ValueError(f"Intermediate stage {stage.name!r} must define required tools")

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
        stage = self.stages[self.stage_index]
        self.tool_history.append(
            {
                "stage": stage.name,
                "tool_name": tool_name,
                "result": result,
            }
        )
        self.stage_results[stage.name][tool_name] = result
        if tool_name in stage.required_tools:
            self.completed_required_tools[stage.name].add(tool_name)
        self._advance_if_ready()

    def record_gate_result(self, gate_name: str, passed: bool, required_fixes: list[str] | None = None) -> None:
        stage_name = self.current_stage
        if not passed:
            self.unresolved_gate_failures[stage_name].add(gate_name)
            self.gate_failures.append(
                {
                    "gate_name": gate_name,
                    "stage": stage_name,
                    "required_fixes": required_fixes or [],
                }
            )
            return

        self.unresolved_gate_failures[stage_name].discard(gate_name)
        self._advance_if_ready()

    def _advance_if_ready(self) -> None:
        stage = self.stages[self.stage_index]
        if self.unresolved_gate_failures[stage.name]:
            return
        if all(name in self.completed_required_tools[stage.name] for name in stage.required_tools):
            self.stage_index = min(self.stage_index + 1, len(self.stages) - 1)
