from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from agent_app.domain.contracts import ExperimentContract, ModelContract, ProblemContract, SubproblemContract, SubproblemType
from agent_app.workflow_packs.cumcm.problem_builder import build_cumcm_problem_contract


class SolverMode(str, Enum):
    TEMPLATE_SOLVER = "template_solver"
    GENERATED_SOLVER = "generated_solver"
    LIBRARY_SOLVER = "library_solver"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


@dataclass(frozen=True)
class SolverStrategyDecision:
    subproblem_id: str
    primary_type: str
    mode: SolverMode
    libraries: list[str]
    reason: str


@dataclass(frozen=True)
class CumcmContractBundle:
    problem_contract: ProblemContract
    model_contracts: list[ModelContract]
    experiment_contracts: list[ExperimentContract]
    solver_strategies: dict[str, SolverStrategyDecision]


LIBRARY_BY_TYPE: dict[SubproblemType, list[str]] = {
    SubproblemType.PREDICTION: ["pandas", "sklearn"],
    SubproblemType.OPTIMIZATION: ["scipy", "pulp", "cvxpy"],
    SubproblemType.MULTI_OBJECTIVE_DECISION: ["pandas", "numpy"],
    SubproblemType.EVALUATION: ["pandas", "numpy"],
    SubproblemType.STATISTICS: ["scipy", "statsmodels"],
    SubproblemType.SAMPLING_TEST: ["scipy"],
    SubproblemType.SIMULATION: ["numpy"],
    SubproblemType.GRAPH_NETWORK: ["networkx"],
    SubproblemType.OPERATIONS_RESEARCH: ["scipy", "pulp"],
    SubproblemType.DATA_MINING: ["sklearn", "pandas"],
}
TEMPLATE_SOLVER_TYPES = {
    SubproblemType.SAMPLING_TEST,
    SubproblemType.EVALUATION,
    SubproblemType.STATISTICS,
}
GENERIC_OUTPUT_SCHEMA = [
    "subproblem_id",
    "problem_type",
    "model",
    "solver_mode",
    "status",
]


def build_generic_cumcm_contract_bundle(
    problem_text: str,
    source_text_path: Path,
    tables: list[dict],
    figures: list[dict],
    data_files: list[Path],
) -> CumcmContractBundle:
    problem_contract = build_cumcm_problem_contract(
        problem_text=problem_text,
        source_text_path=source_text_path,
        tables=tables,
        figures=figures,
    )
    solver_strategies = {
        subproblem.subproblem_id: select_solver_strategy(subproblem, data_files)
        for subproblem in problem_contract.subproblems
    }

    return CumcmContractBundle(
        problem_contract=problem_contract,
        model_contracts=[
            _build_model_contract(subproblem, solver_strategies[subproblem.subproblem_id])
            for subproblem in problem_contract.subproblems
        ],
        experiment_contracts=[
            _build_experiment_contract(subproblem, solver_strategies[subproblem.subproblem_id], data_files)
            for subproblem in problem_contract.subproblems
        ],
        solver_strategies=solver_strategies,
    )


def select_solver_strategy(subproblem: SubproblemContract, data_files: list[Path]) -> SolverStrategyDecision:
    libraries = list(LIBRARY_BY_TYPE.get(subproblem.primary_type, []))
    if libraries and data_files:
        return SolverStrategyDecision(
            subproblem_id=subproblem.subproblem_id,
            primary_type=subproblem.primary_type.value,
            mode=SolverMode.LIBRARY_SOLVER,
            libraries=libraries,
            reason="recognized problem type has supported libraries and input data files are available",
        )
    if subproblem.primary_type in TEMPLATE_SOLVER_TYPES:
        return SolverStrategyDecision(
            subproblem_id=subproblem.subproblem_id,
            primary_type=subproblem.primary_type.value,
            mode=SolverMode.TEMPLATE_SOLVER,
            libraries=libraries,
            reason="recognized problem type can use a deterministic CUMCM template solver",
        )
    return SolverStrategyDecision(
        subproblem_id=subproblem.subproblem_id,
        primary_type=subproblem.primary_type.value,
        mode=SolverMode.GENERATED_SOLVER,
        libraries=libraries,
        reason="no deterministic template applies; generate a solver from the contracts",
    )


def _build_model_contract(subproblem: SubproblemContract, strategy: SolverStrategyDecision) -> ModelContract:
    result_file = _result_file_for(subproblem)
    return ModelContract(
        subproblem_id=subproblem.subproblem_id,
        variables={"decision_variables": "defined by the generated solver for this subproblem"},
        parameters={"problem_type": strategy.primary_type},
        parameter_sources={"problem_type": "CUMCM subproblem recognizer"},
        assumptions=["Model assumptions must be stated and validated before final paper packaging."],
        objective_functions=[f"solve {subproblem.subproblem_id} as a {strategy.primary_type} task"],
        constraints=["respect problem statement constraints and available data schemas"],
        algorithm=f"{strategy.mode.value} using {', '.join(strategy.libraries) if strategy.libraries else 'generated Python'}",
        limitations=["Generic contract requires solver output validation before claims are promoted."],
        result_files=[result_file],
        experiment_to_claim_links=[f"{result_file} -> claim_{subproblem.subproblem_id}_result"],
    )


def _build_experiment_contract(
    subproblem: SubproblemContract,
    strategy: SolverStrategyDecision,
    data_files: list[Path],
) -> ExperimentContract:
    result_file = _result_file_for(subproblem)
    return ExperimentContract(
        subproblem_id=subproblem.subproblem_id,
        entrypoint=Path("code/solve.py"),
        input_files=list(data_files),
        output_schemas={result_file: GENERIC_OUTPUT_SCHEMA.copy()},
        validation_checks=["non_empty_csv", "schema_matches_contract"],
        rerun_conditions=[f"solver_strategy={strategy.mode.value}", "problem_contract_changed"],
    )


def _result_file_for(subproblem: SubproblemContract) -> str:
    if subproblem.expected_outputs:
        return subproblem.expected_outputs[0]
    return f"results/{subproblem.subproblem_id}_result.csv"
