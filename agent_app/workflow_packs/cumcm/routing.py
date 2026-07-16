from __future__ import annotations

from dataclasses import dataclass, field

from agent_app.domain.models import RunOptions


GENERIC_CUMCM_WORKFLOW = "generic_cumcm_contract_workflow"
BENCHMARK_2024_B_ID = "cumcm_2024_b_production_decision"


@dataclass(frozen=True)
class CumcmRoute:
    workflow_family: str
    workflow_type: str
    is_benchmark: bool = False
    selected_benchmark_id: str = ""
    rejected_routes: list[str] = field(default_factory=list)
    reason: str = ""


def select_cumcm_route(problem_text: str, options: RunOptions | None = None) -> CumcmRoute:
    selected_options = options or RunOptions()
    if selected_options.workflow_mode == "benchmark":
        if selected_options.benchmark_id == BENCHMARK_2024_B_ID:
            return CumcmRoute(
                workflow_family="cumcm",
                workflow_type="cumcm_b_problem_benchmark_workflow",
                is_benchmark=True,
                selected_benchmark_id=BENCHMARK_2024_B_ID,
                reason="explicit benchmark mode selected the 2024 B fixture",
            )
        rejected = [selected_options.benchmark_id] if selected_options.benchmark_id else ["missing_benchmark_id"]
        return CumcmRoute(
            workflow_family="cumcm",
            workflow_type=GENERIC_CUMCM_WORKFLOW,
            rejected_routes=rejected,
            reason="benchmark mode was requested but no registered benchmark matched",
        )

    rejected_routes = [BENCHMARK_2024_B_ID] if _looks_like_2024_b_text(problem_text) else []
    return CumcmRoute(
        workflow_family="cumcm",
        workflow_type=GENERIC_CUMCM_WORKFLOW,
        rejected_routes=rejected_routes,
        reason="problem text is treated as production input; benchmark routes require explicit options",
    )


def _looks_like_2024_b_text(problem_text: str) -> bool:
    return all(token in problem_text for token in ("生产过程中的决策问题", "抽样", "拆解"))
