from pathlib import Path

from agent_app.workflow_packs.cumcm.contracts import (
    LIBRARY_BY_TYPE,
    SolverMode,
    build_generic_cumcm_contract_bundle,
)
from agent_app.domain.contracts import SubproblemType


def test_generic_contract_bundle_matches_dynamic_subproblem_count():
    text = (
        "A 题 城市交通治理。"
        "问题1：预测未来七天各路段交通流量。"
        "问题2：在道路容量约束下优化信号灯配时。"
        "问题3：评价方案在容量扰动下的稳健性。"
    )

    bundle = build_generic_cumcm_contract_bundle(
        problem_text=text,
        source_text_path=Path("question.md"),
        tables=[],
        figures=[],
        data_files=[Path("inputs/data/traffic.csv")],
    )

    assert bundle.problem_contract.title.startswith("A 题")
    assert [item.subproblem_id for item in bundle.problem_contract.subproblems] == ["q1", "q2", "q3"]
    assert [item.subproblem_id for item in bundle.model_contracts] == ["q1", "q2", "q3"]
    assert [item.subproblem_id for item in bundle.experiment_contracts] == ["q1", "q2", "q3"]
    assert bundle.solver_strategies["q1"].mode in {SolverMode.LIBRARY_SOLVER, SolverMode.GENERATED_SOLVER}
    assert bundle.solver_strategies["q2"].primary_type == "optimization"


def test_generic_contract_bundle_has_experiment_to_conclusion_links():
    bundle = build_generic_cumcm_contract_bundle(
        problem_text="问题1：建立评价指标体系并排序。",
        source_text_path=Path("question.md"),
        tables=[],
        figures=[],
        data_files=[],
    )

    model = bundle.model_contracts[0]
    experiment = bundle.experiment_contracts[0]

    assert model.result_files == ["results/q1_result.csv"]
    assert model.experiment_to_claim_links == ["results/q1_result.csv -> claim_q1_result"]
    assert experiment.output_schemas["results/q1_result.csv"] == [
        "subproblem_id",
        "problem_type",
        "model",
        "solver_mode",
        "status",
    ]


def test_solver_strategy_libraries_do_not_mutate_global_registry():
    bundle = build_generic_cumcm_contract_bundle(
        problem_text="问题1：预测未来七天交通流量。",
        source_text_path=Path("question.md"),
        tables=[],
        figures=[],
        data_files=[Path("inputs/data/traffic.csv")],
    )

    bundle.solver_strategies["q1"].libraries.append("mutated")

    assert LIBRARY_BY_TYPE[SubproblemType.PREDICTION] == ["pandas", "sklearn"]
    later_bundle = build_generic_cumcm_contract_bundle(
        problem_text="问题1：预测未来七天交通流量。",
        source_text_path=Path("question.md"),
        tables=[],
        figures=[],
        data_files=[Path("inputs/data/traffic.csv")],
    )
    assert later_bundle.solver_strategies["q1"].libraries == ["pandas", "sklearn"]


def test_experiment_input_files_are_not_aliased_to_caller_data_files():
    data_files = [Path("inputs/data/traffic.csv")]

    bundle = build_generic_cumcm_contract_bundle(
        problem_text="问题1：预测未来七天交通流量。",
        source_text_path=Path("question.md"),
        tables=[],
        figures=[],
        data_files=data_files,
    )

    data_files.append(Path("inputs/data/late.csv"))

    assert bundle.experiment_contracts[0].input_files == [Path("inputs/data/traffic.csv")]
