from agent_app.domain.models import RunOptions
from agent_app.workflow_packs.cumcm.routing import (
    BENCHMARK_2024_B_ID,
    GENERIC_CUMCM_WORKFLOW,
    select_cumcm_route,
)


B_TEXT = (
    "2024 年 B 题 生产过程中的决策问题。"
    "问题1：抽样检测。问题2：检测拆解决策。问题3：多工序。问题4：不确定性。"
)


def test_production_route_is_generic_even_for_2024_b_text():
    route = select_cumcm_route(B_TEXT, RunOptions())

    assert route.workflow_type == GENERIC_CUMCM_WORKFLOW
    assert route.workflow_family == "cumcm"
    assert route.is_benchmark is False
    assert route.selected_benchmark_id == ""
    assert route.rejected_routes == ["cumcm_2024_b_production_decision"]
    assert "problem text is treated as production input" in route.reason


def test_explicit_benchmark_route_selects_2024_b_fixture():
    route = select_cumcm_route(
        B_TEXT,
        RunOptions(
            workflow_mode="benchmark",
            benchmark_id=BENCHMARK_2024_B_ID,
        ),
    )

    assert route.workflow_type == "cumcm_b_problem_benchmark_workflow"
    assert route.is_benchmark is True
    assert route.selected_benchmark_id == BENCHMARK_2024_B_ID
    assert route.rejected_routes == []


def test_unknown_benchmark_id_falls_back_to_generic_with_rejection_reason():
    route = select_cumcm_route(
        "A 题 城市交通预测问题。问题1：预测交通流。",
        RunOptions(workflow_mode="benchmark", benchmark_id="unknown_case"),
    )

    assert route.workflow_type == GENERIC_CUMCM_WORKFLOW
    assert route.is_benchmark is False
    assert "unknown_case" in route.rejected_routes
