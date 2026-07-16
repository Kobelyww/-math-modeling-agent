# Generic CUMCM Contract Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current B-problem production branch with a generic CUMCM contract workflow, while preserving the 2024 B problem as an explicit benchmark fixture.

**Architecture:** Production runs always enter `generic_cumcm_contract_workflow`: dynamic subproblem recognition, model-family routing, solver-strategy selection, contract writing, trace writing, claim-aware section writing, and stricter gates. The 2024 B deterministic solver moves under a benchmark namespace and can only run when `RunOptions.workflow_mode == "benchmark"` and `RunOptions.benchmark_id == "cumcm_2024_b_production_decision"`.

**Tech Stack:** Python dataclasses, LangChain tools, pytest, existing `RunStore`, `ContractStore`, `ProblemContract`, `ModelContract`, `ExperimentContract`, and `QualityReport`.

---

## Source Spec

Implement against `docs/superpowers/specs/2026-07-15-generic-cumcm-contract-workflow-design.md`.

The production rule is strict:

- Do not route user runs by contest letter, year, exact title, or the phrase `生产过程中的决策问题`.
- Do keep the 2024 B deterministic solver as a benchmark and regression suite.
- Do save observable trace files under `trace/`.
- Do reject internal context leakage and thin paper drafts before packaging.

## File Structure

Create or modify these files:

- Modify `agent_app/domain/models.py`
  - Add explicit workflow mode fields to `RunOptions`.
- Create `agent_app/workflow_packs/cumcm/routing.py`
  - Own production vs benchmark route selection.
- Create `agent_app/workflow_packs/cumcm/contracts.py`
  - Build generic CUMCM contract bundles and solver strategy decisions.
- Create `agent_app/workflow_packs/cumcm/benchmarks/__init__.py`
  - Benchmark namespace marker.
- Move `agent_app/workflow_packs/cumcm/templates/production_decision.py`
  - New location: `agent_app/workflow_packs/cumcm/benchmarks/y2024_b_production_decision.py`.
- Move `agent_app/workflow_packs/cumcm/templates/production_decision_solver.py`
  - New location: `agent_app/workflow_packs/cumcm/benchmarks/y2024_b_production_decision_solver.py`.
- Modify `agent_app/workflow_packs/cumcm/templates/production_decision.py`
  - Keep a compatibility re-export only.
- Modify `agent_app/workflow_packs/cumcm/templates/production_decision_solver.py`
  - Keep a compatibility re-export only.
- Create `agent_app/services/run_trace.py`
  - Write redacted routing, prompt, LLM output, event, and gate traces.
- Modify `agent_app/services/claim_map.py`
  - Add generic claim building and locators.
- Modify `agent_app/services/section_writer.py`
  - Write reviewable user-facing sections from claims; no internal context in final sections.
- Modify `agent_app/evaluators/claim_gate.py`
  - Require evidence locators.
- Modify `agent_app/evaluators/paper_gate.py`
  - Reject internal workflow leakage and thin sections.
- Modify `agent_app/evaluators/submission_gate.py`
  - Block package when upstream gates are failed or stale.
- Modify `agent_app/tools/competition.py`
  - Use generic routing in `analyze_problem`, `plan_model`, `run_experiment`, and `draft_competition_paper`.
  - Use benchmark route only when explicitly requested.
- Add tests:
  - `agent_app/tests/test_cumcm_workflow_routing.py`
  - `agent_app/tests/test_cumcm_contract_bundle.py`
  - `agent_app/tests/test_run_trace.py`
  - `agent_app/tests/test_generic_cumcm_workflow.py`
  - Update `agent_app/tests/test_b_problem_solver.py`
  - Update `agent_app/tests/test_deepagent_tools.py`
  - Update `agent_app/tests/test_claim_gate.py`
  - Update `agent_app/tests/test_quality_gates.py`

## Task 1: Add Explicit CUMCM Routing

**Files:**
- Modify: `agent_app/domain/models.py`
- Create: `agent_app/workflow_packs/cumcm/routing.py`
- Test: `agent_app/tests/test_cumcm_workflow_routing.py`

- [ ] **Step 1: Write the failing routing tests**

```python
# agent_app/tests/test_cumcm_workflow_routing.py
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
```

- [ ] **Step 2: Run the routing tests and confirm they fail**

Run:

```bash
pytest agent_app/tests/test_cumcm_workflow_routing.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'agent_app.workflow_packs.cumcm.routing'
```

- [ ] **Step 3: Add workflow options to `RunOptions`**

Change `agent_app/domain/models.py`:

```python
@dataclass
class RunOptions:
    top_k: int = 6
    max_repair_attempts: int = 2
    compile_pdf: bool = True
    allow_online_search: bool = False
    workflow_mode: str = "production"
    benchmark_id: str = ""
```

- [ ] **Step 4: Create the routing module**

```python
# agent_app/workflow_packs/cumcm/routing.py
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
```

- [ ] **Step 5: Verify routing and serialization**

Run:

```bash
pytest agent_app/tests/test_cumcm_workflow_routing.py agent_app/tests/test_domain_models.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Spec review**

Confirm:

- Production route is `generic_cumcm_contract_workflow`.
- Explicit benchmark mode is the only route to the 2024 B fixture.
- No tool path has changed yet.

- [ ] **Step 7: Quality review**

Check:

- `RunOptions` remains backward-compatible because new fields have defaults.
- `CumcmRoute` has no dependency on tool internals.
- Route reason is saved as data, not hidden in logs.

- [ ] **Step 8: Commit**

```bash
git add agent_app/domain/models.py agent_app/workflow_packs/cumcm/routing.py agent_app/tests/test_cumcm_workflow_routing.py
git commit -m "feat: add explicit cumcm workflow routing"
```

## Task 2: Move 2024 B Into Benchmark Namespace

**Files:**
- Create: `agent_app/workflow_packs/cumcm/benchmarks/__init__.py`
- Move: `agent_app/workflow_packs/cumcm/templates/production_decision.py`
- Move: `agent_app/workflow_packs/cumcm/templates/production_decision_solver.py`
- Modify: `agent_app/workflow_packs/cumcm/templates/production_decision.py`
- Modify: `agent_app/workflow_packs/cumcm/templates/production_decision_solver.py`
- Modify: `agent_app/tests/test_b_problem_solver.py`

- [ ] **Step 1: Write the benchmark namespace test changes**

Update imports in `agent_app/tests/test_b_problem_solver.py`:

```python
from agent_app.workflow_packs.cumcm.benchmarks.y2024_b_production_decision import (
    build_b_problem_experiment_contracts,
    build_b_problem_model_contracts,
    is_b_problem,
)
from agent_app.workflow_packs.cumcm.benchmarks.y2024_b_production_decision_solver import run_b_problem_solver
```

Add this test to the same file:

```python
def test_b_problem_solver_is_imported_from_benchmark_namespace():
    assert run_b_problem_solver.__module__.endswith("benchmarks.y2024_b_production_decision_solver")
```

- [ ] **Step 2: Run the benchmark tests and confirm they fail**

Run:

```bash
pytest agent_app/tests/test_b_problem_solver.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'agent_app.workflow_packs.cumcm.benchmarks'
```

- [ ] **Step 3: Move benchmark files with git**

Run:

```bash
mkdir -p agent_app/workflow_packs/cumcm/benchmarks
git mv agent_app/workflow_packs/cumcm/templates/production_decision.py agent_app/workflow_packs/cumcm/benchmarks/y2024_b_production_decision.py
git mv agent_app/workflow_packs/cumcm/templates/production_decision_solver.py agent_app/workflow_packs/cumcm/benchmarks/y2024_b_production_decision_solver.py
```

- [ ] **Step 4: Add namespace marker**

```python
# agent_app/workflow_packs/cumcm/benchmarks/__init__.py
"""Benchmark fixtures for CUMCM workflow regression tests."""
```

- [ ] **Step 5: Recreate compatibility re-export modules**

```python
# agent_app/workflow_packs/cumcm/templates/production_decision.py
from agent_app.workflow_packs.cumcm.benchmarks.y2024_b_production_decision import (
    build_b_problem_experiment_contracts,
    build_b_problem_model_contracts,
    is_b_problem,
)

__all__ = [
    "build_b_problem_experiment_contracts",
    "build_b_problem_model_contracts",
    "is_b_problem",
]
```

```python
# agent_app/workflow_packs/cumcm/templates/production_decision_solver.py
from agent_app.workflow_packs.cumcm.benchmarks.y2024_b_production_decision_solver import (
    SolverResult,
    run_b_problem_solver,
)

__all__ = ["SolverResult", "run_b_problem_solver"]
```

- [ ] **Step 6: Verify benchmark imports**

Run:

```bash
pytest agent_app/tests/test_b_problem_solver.py -q
```

Expected:

```text
passed
```

- [ ] **Step 7: Spec review**

Confirm:

- 2024 B code now lives under `benchmarks`.
- Old imports remain compatibility wrappers only.
- No production routing uses the compatibility wrapper as the primary route.

- [ ] **Step 8: Quality review**

Check:

- `git status --short` shows the moves as renames plus wrapper files.
- No copied duplicate solver implementation remains in `templates`.

- [ ] **Step 9: Commit**

```bash
git add agent_app/workflow_packs/cumcm/benchmarks agent_app/workflow_packs/cumcm/templates/production_decision.py agent_app/workflow_packs/cumcm/templates/production_decision_solver.py agent_app/tests/test_b_problem_solver.py
git commit -m "refactor: move cumcm b solver to benchmark namespace"
```

## Task 3: Build Generic Contract Bundles And Solver Strategies

**Files:**
- Create: `agent_app/workflow_packs/cumcm/contracts.py`
- Test: `agent_app/tests/test_cumcm_contract_bundle.py`

- [ ] **Step 1: Write failing contract bundle tests**

```python
# agent_app/tests/test_cumcm_contract_bundle.py
from pathlib import Path

from agent_app.workflow_packs.cumcm.contracts import (
    SolverMode,
    build_generic_cumcm_contract_bundle,
)


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
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```bash
pytest agent_app/tests/test_cumcm_contract_bundle.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'agent_app.workflow_packs.cumcm.contracts'
```

- [ ] **Step 3: Implement generic contract bundle builder**

```python
# agent_app/workflow_packs/cumcm/contracts.py
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


def build_generic_cumcm_contract_bundle(
    problem_text: str,
    source_text_path: Path,
    tables: list[dict],
    figures: list[dict],
    data_files: list[Path],
) -> CumcmContractBundle:
    problem_contract = build_cumcm_problem_contract(
        problem_text,
        source_text_path=source_text_path,
        tables=tables,
        figures=figures,
    )
    strategies = {
        subproblem.subproblem_id: select_solver_strategy(subproblem, data_files=data_files)
        for subproblem in problem_contract.subproblems
    }
    model_contracts = [
        _model_contract_for_subproblem(subproblem, strategies[subproblem.subproblem_id])
        for subproblem in problem_contract.subproblems
    ]
    experiment_contracts = [
        _experiment_contract_for_subproblem(subproblem, strategies[subproblem.subproblem_id])
        for subproblem in problem_contract.subproblems
    ]
    return CumcmContractBundle(
        problem_contract=problem_contract,
        model_contracts=model_contracts,
        experiment_contracts=experiment_contracts,
        solver_strategies=strategies,
    )


def select_solver_strategy(subproblem: SubproblemContract, data_files: list[Path]) -> SolverStrategyDecision:
    libraries = LIBRARY_BY_TYPE.get(subproblem.primary_type, [])
    if libraries and data_files:
        return SolverStrategyDecision(
            subproblem_id=subproblem.subproblem_id,
            primary_type=subproblem.primary_type.value,
            mode=SolverMode.LIBRARY_SOLVER,
            libraries=libraries,
            reason="typed subproblem has data files and a known library family",
        )
    if subproblem.primary_type in {SubproblemType.SAMPLING_TEST, SubproblemType.EVALUATION, SubproblemType.STATISTICS}:
        return SolverStrategyDecision(
            subproblem_id=subproblem.subproblem_id,
            primary_type=subproblem.primary_type.value,
            mode=SolverMode.TEMPLATE_SOLVER,
            libraries=libraries,
            reason="typed subproblem can run a deterministic template solver",
        )
    return SolverStrategyDecision(
        subproblem_id=subproblem.subproblem_id,
        primary_type=subproblem.primary_type.value,
        mode=SolverMode.GENERATED_SOLVER,
        libraries=libraries,
        reason="subproblem requires generated solver code from the model contract",
    )


def _model_contract_for_subproblem(
    subproblem: SubproblemContract,
    strategy: SolverStrategyDecision,
) -> ModelContract:
    result_file = subproblem.expected_outputs[0] if subproblem.expected_outputs else f"results/{subproblem.subproblem_id}_result.csv"
    return ModelContract(
        subproblem_id=subproblem.subproblem_id,
        variables={"x": "decision, prediction, evaluation, or state variables identified from the subproblem text"},
        parameters={"theta": "parameters extracted from question text, tables, figures, and input data"},
        parameter_sources={"theta": "problem_contract.source_text_path and registered input assets"},
        assumptions=[
            "Each subproblem is solved with only the inputs declared in its contract.",
            "Claims are written only after result files pass gate checks.",
        ],
        objective_functions=[_objective_for_type(subproblem.primary_type)],
        constraints=[_constraint_for_type(subproblem.primary_type)],
        algorithm=f"{strategy.mode.value} using {', '.join(strategy.libraries) if strategy.libraries else 'typed Python code'}",
        formulas=[_formula_hint_for_type(subproblem.primary_type)],
        limitations=["Generic contract describes the minimum auditable solve path; strong claims require stronger result evidence."],
        result_files=[result_file],
        experiment_to_claim_links=[f"{result_file} -> claim_{subproblem.subproblem_id}_result"],
    )


def _experiment_contract_for_subproblem(
    subproblem: SubproblemContract,
    strategy: SolverStrategyDecision,
) -> ExperimentContract:
    result_file = subproblem.expected_outputs[0] if subproblem.expected_outputs else f"results/{subproblem.subproblem_id}_result.csv"
    return ExperimentContract(
        subproblem_id=subproblem.subproblem_id,
        entrypoint=Path("code/solve.py"),
        output_schemas={
            result_file: ["subproblem_id", "problem_type", "model", "solver_mode", "status"],
        },
        validation_checks=[
            "non_empty_csv",
            "has_subproblem_id",
            "has_solver_mode",
            "experiment_to_conclusion_link_present",
        ],
    )


def _objective_for_type(problem_type: SubproblemType) -> str:
    return {
        SubproblemType.OPTIMIZATION: "optimize the declared objective under extracted constraints",
        SubproblemType.PREDICTION: "minimize validation error on the declared target",
        SubproblemType.EVALUATION: "produce a justified ranking or score table",
        SubproblemType.SAMPLING_TEST: "satisfy confidence and risk constraints with minimal sampling burden",
        SubproblemType.STATISTICS: "estimate uncertainty and explain how it limits conclusions",
    }.get(problem_type, "produce a reproducible result that directly supports the subproblem conclusion")


def _constraint_for_type(problem_type: SubproblemType) -> str:
    return {
        SubproblemType.OPTIMIZATION: "decision variables must satisfy feasibility constraints from the problem text",
        SubproblemType.PREDICTION: "train and validation splits must avoid target leakage",
        SubproblemType.EVALUATION: "indicator weights and normalization must be reported",
        SubproblemType.SAMPLING_TEST: "risk probabilities must be explicit",
    }.get(problem_type, "inputs, assumptions, and output schema must match the contract")


def _formula_hint_for_type(problem_type: SubproblemType) -> str:
    return {
        SubproblemType.OPTIMIZATION: "argmax/min f(x; theta) subject to g(x; theta) <= 0",
        SubproblemType.PREDICTION: "y_hat = f(X; theta), evaluate error(y, y_hat)",
        SubproblemType.EVALUATION: "score_i = sum_j w_j normalized(x_ij)",
        SubproblemType.SAMPLING_TEST: "P(decision error | p, n, k) <= alpha",
        SubproblemType.STATISTICS: "theta in [lower, upper] with stated confidence",
    }.get(problem_type, "result = solver(input_contract)")
```

- [ ] **Step 4: Verify contract bundle tests**

Run:

```bash
pytest agent_app/tests/test_cumcm_contract_bundle.py agent_app/tests/test_cumcm_problem_builder.py agent_app/tests/test_cumcm_recognizer.py -q
```

Expected:

```text
passed
```

- [ ] **Step 5: Spec review**

Confirm:

- Every subproblem gets `ProblemContract`, `ModelContract`, `ExperimentContract`, and solver strategy.
- Solver strategy is selected by subproblem type and asset availability.
- No B-problem branch is used in generic bundle creation.

- [ ] **Step 6: Quality review**

Check:

- The new module has no file writes.
- Model contracts contain experiment-to-conclusion links.
- Strategy decisions are serializable through `to_json_dict`.

- [ ] **Step 7: Commit**

```bash
git add agent_app/workflow_packs/cumcm/contracts.py agent_app/tests/test_cumcm_contract_bundle.py
git commit -m "feat: build generic cumcm contract bundles"
```

## Task 4: Add Observable Run Trace Writer

**Files:**
- Create: `agent_app/services/run_trace.py`
- Test: `agent_app/tests/test_run_trace.py`

- [ ] **Step 1: Write failing trace tests**

```python
# agent_app/tests/test_run_trace.py
import json

from agent_app.services.run_trace import RunTraceWriter


def test_trace_writer_saves_routing_and_redacts_secrets(tmp_path):
    writer = RunTraceWriter(tmp_path)

    path = writer.write_json(
        "routing_decision.json",
        {
            "route": "generic_cumcm_contract_workflow",
            "api_key": "sk-secret-value",
            "nested": {"authorization": "Bearer token-value"},
        },
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["route"] == "generic_cumcm_contract_workflow"
    assert payload["api_key"] == "[REDACTED]"
    assert payload["nested"]["authorization"] == "[REDACTED]"


def test_trace_writer_appends_stage_events(tmp_path):
    writer = RunTraceWriter(tmp_path)

    writer.append_event("plan_model", {"status": "started"})
    writer.append_event("plan_model", {"status": "completed"})

    lines = (tmp_path / "trace" / "stage_events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["stage"] == "plan_model"
    assert json.loads(lines[1])["payload"]["status"] == "completed"
```

- [ ] **Step 2: Run trace tests and confirm they fail**

Run:

```bash
pytest agent_app/tests/test_run_trace.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'agent_app.services.run_trace'
```

- [ ] **Step 3: Implement trace writer**

```python
# agent_app/services/run_trace.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


SECRET_KEYS = {"api_key", "apikey", "authorization", "token", "access_token", "secret"}


class RunTraceWriter:
    def __init__(self, run_dir: Path | str) -> None:
        self.run_dir = Path(run_dir)
        self.trace_dir = self.run_dir / "trace"

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> Path:
        path = self.trace_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_redact(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def write_text(self, relative_path: str, content: str) -> Path:
        path = self.trace_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_redact_text(content), encoding="utf-8")
        return path

    def append_event(self, stage: str, payload: dict[str, Any]) -> Path:
        path = self.trace_dir / "stage_events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "created_at": datetime.now().replace(microsecond=0).isoformat(),
            "stage": stage,
            "payload": _redact(payload),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return path

    def write_prompt(self, stage: str, role: str, model: str, messages: list[dict[str, str]], output_schema: dict[str, Any] | None = None) -> Path:
        return self.write_json(
            f"prompts/{stage}.json",
            {
                "stage": stage,
                "role": role,
                "model": model,
                "messages": messages,
                "output_schema": output_schema or {},
            },
        )

    def write_llm_output(self, stage: str, content: str) -> Path:
        suffix = ".json" if content.strip().startswith("{") else ".md"
        return self.write_text(f"llm_outputs/{stage}{suffix}", content)

    def write_gate_report(self, gate_name: str, report: dict[str, Any]) -> Path:
        return self.write_json(f"gate_reports/{gate_name}.json", report)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SECRET_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(content: str) -> str:
    if "sk-" not in content and "Bearer " not in content:
        return content
    tokens = []
    for token in content.split():
        if token.startswith("sk-") or token.startswith("Bearer"):
            tokens.append("[REDACTED]")
        else:
            tokens.append(token)
    return " ".join(tokens)
```

- [ ] **Step 4: Verify trace tests**

Run:

```bash
pytest agent_app/tests/test_run_trace.py -q
```

Expected:

```text
passed
```

- [ ] **Step 5: Spec review**

Confirm trace writer supports:

- `trace/routing_decision.json`
- `trace/stage_events.jsonl`
- `trace/prompts/*.json`
- `trace/llm_outputs/*`
- `trace/gate_reports/*.json`

- [ ] **Step 6: Quality review**

Check:

- Secrets are redacted recursively.
- Trace writer does not depend on LangChain.
- Text redaction is deterministic.

- [ ] **Step 7: Commit**

```bash
git add agent_app/services/run_trace.py agent_app/tests/test_run_trace.py
git commit -m "feat: add redacted run trace writer"
```

## Task 5: Wire Generic Route Into `analyze_problem` And `plan_model`

**Files:**
- Modify: `agent_app/tools/competition.py`
- Modify: `agent_app/tests/test_deepagent_tools.py`
- Test: `agent_app/tests/test_generic_cumcm_workflow.py`

- [ ] **Step 1: Write failing production-route tests**

```python
# agent_app/tests/test_generic_cumcm_workflow.py
import json

from agent_app.domain.models import RunOptions, RunSpec
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools
from agent_app.workflow_packs.cumcm.routing import BENCHMARK_2024_B_ID


B_TEXT = (
    "2024 年 B 题 生产过程中的决策问题。"
    "问题1：抽样检测。问题2：检测拆解决策。问题3：多工序。问题4：不确定性。"
)


def _tools_for_question(tmp_path, question, options=None):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question=question, options=options or RunOptions()))
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}
    return store, state, tools


def test_production_b_text_uses_generic_workflow_and_generic_contracts(tmp_path):
    store, state, tools = _tools_for_question(tmp_path, B_TEXT)

    problem = tools["analyze_problem"].invoke({"run_id": state.run_id, "question": B_TEXT})
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )

    run_dir = store.run_dir(state.run_id)
    route = json.loads((run_dir / "trace" / "routing_decision.json").read_text(encoding="utf-8"))

    assert plan["modeling_plan"]["workflow_type"] == "generic_cumcm_contract_workflow"
    assert route["workflow_type"] == "generic_cumcm_contract_workflow"
    assert "cumcm_2024_b_production_decision" in route["rejected_routes"]
    assert (run_dir / "contracts" / "problem_contract.json").exists()
    assert not (run_dir / "results" / "q2_table1_decisions.csv").exists()


def test_explicit_benchmark_mode_uses_b_fixture_contracts(tmp_path):
    options = RunOptions(workflow_mode="benchmark", benchmark_id=BENCHMARK_2024_B_ID)
    store, state, tools = _tools_for_question(tmp_path, B_TEXT, options=options)

    problem = tools["analyze_problem"].invoke({"run_id": state.run_id, "question": B_TEXT})
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )

    assert plan["modeling_plan"]["workflow_type"] == "cumcm_b_problem_benchmark_workflow"
    assert (store.run_dir(state.run_id) / "contracts" / "models" / "q4.json").exists()
```

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
pytest agent_app/tests/test_generic_cumcm_workflow.py -q
```

Expected:

```text
assert 'cumcm_b_problem_contract_workflow' == 'generic_cumcm_contract_workflow'
```

- [ ] **Step 3: Update imports in `competition.py`**

Replace benchmark imports:

```python
from agent_app.services.run_trace import RunTraceWriter
from agent_app.workflow_packs.cumcm.benchmarks.y2024_b_production_decision import (
    build_b_problem_experiment_contracts,
    build_b_problem_model_contracts,
)
from agent_app.workflow_packs.cumcm.benchmarks.y2024_b_production_decision_solver import run_b_problem_solver
from agent_app.workflow_packs.cumcm.contracts import build_generic_cumcm_contract_bundle
from agent_app.workflow_packs.cumcm.routing import select_cumcm_route
```

Remove `is_b_problem` from production imports.

- [ ] **Step 4: Add helper functions inside `make_competition_tools`**

Add near `_artifacts_for_state`:

```python
    def _trace_for_state(state: RunState) -> RunTraceWriter:
        return RunTraceWriter(run_store.run_dir(state.run_id))

    def _route_for_state(state: RunState, problem_text: str) -> dict[str, Any]:
        route = select_cumcm_route(problem_text, state.spec.options)
        route_payload = to_json_dict(route)
        _trace_for_state(state).write_json("routing_decision.json", route_payload)
        return route_payload

    def _is_benchmark_route(state: RunState, problem_text: str) -> bool:
        return bool(_route_for_state(state, problem_text).get("is_benchmark"))
```

- [ ] **Step 5: Add generic contract bundle writer inside `make_competition_tools`**

```python
    def _write_generic_contract_bundle(
        state: RunState,
        problem_text: str,
        data_files: list[str] | None = None,
    ) -> dict[str, Any]:
        run_dir = run_store.run_dir(state.run_id)
        store = ContractStore(run_dir)
        bundle = build_generic_cumcm_contract_bundle(
            problem_text=problem_text or state.spec.question,
            source_text_path=Path("question.md"),
            tables=(_read_json_artifact(state, "tables.json").get("tables") or []),
            figures=(_read_json_artifact(state, "figures.json").get("figures") or []),
            data_files=[Path(path) for path in (data_files or [])],
        )
        problem_contract_path = store.write_problem_contract(bundle.problem_contract)
        model_paths = {
            contract.subproblem_id: _write_contract_json(
                run_dir,
                f"contracts/models/{contract.subproblem_id}.json",
                contract,
            )
            for contract in bundle.model_contracts
        }
        experiment_paths = {
            contract.subproblem_id: _write_contract_json(
                run_dir,
                f"contracts/experiments/{contract.subproblem_id}.json",
                contract,
            )
            for contract in bundle.experiment_contracts
        }
        strategy_path = _write_contract_json(
            run_dir,
            "contracts/solver_strategies.json",
            bundle.solver_strategies,
        )
        return {
            "problem_contract": bundle.problem_contract,
            "model_contracts": bundle.model_contracts,
            "experiment_contracts": bundle.experiment_contracts,
            "solver_strategies": bundle.solver_strategies,
            "problem_contract_path": problem_contract_path,
            "model_paths": model_paths,
            "experiment_paths": experiment_paths,
            "solver_strategy_path": strategy_path,
        }
```

- [ ] **Step 6: Change benchmark helper naming**

Rename `_ensure_b_problem_contract_bundle` to `_ensure_benchmark_b_contract_bundle` and change its modeling plan workflow type:

```python
            "workflow_type": "cumcm_b_problem_benchmark_workflow",
            "benchmark_id": "cumcm_2024_b_production_decision",
```

- [ ] **Step 7: Replace `analyze_problem` B special case**

Inside `analyze_problem`, compute route first:

```python
        route = _route_for_state(state, clean_question)
        problem_contract = build_cumcm_problem_contract(
            clean_question,
            source_text_path=Path("question.md"),
            tables=(_read_json_artifact(state, "tables.json").get("tables") or []),
            figures=(_read_json_artifact(state, "figures.json").get("figures") or []),
        )
        generic_subproblems = [
            {
                "id": subproblem.subproblem_id,
                "title": subproblem.question_text[:64] or subproblem.subproblem_id,
                "objective": subproblem.question_text,
                "problem_type": subproblem.primary_type.value,
                "model": _model_name_for_problem_type(subproblem.primary_type),
                "algorithm": _algorithm_for_problem_type(subproblem.primary_type),
                "dependencies": subproblem.dependencies,
                "result_file": subproblem.expected_outputs[0] if subproblem.expected_outputs else f"results/{subproblem.subproblem_id}_result.csv",
            }
            for subproblem in problem_contract.subproblems
        ]
        brief = {
            "background": clean_question[:200],
            "workflow_type": route["workflow_type"],
            "questions": [item["objective"] for item in generic_subproblems],
            "objectives": ["建立可解释、可复现实证模型"],
            "constraints": ["使用本地输入文件", "记录假设与局限"],
            "deliverables": ["modeling_report.md", "solve.py", "paper.md", "paper.tex"],
            "subproblems": generic_subproblems,
        }
```

Add helpers near `_generic_model_markdown`:

```python
    def _model_name_for_problem_type(problem_type: SubproblemType) -> str:
        return {
            SubproblemType.SAMPLING_TEST: "统计抽样检验模型",
            SubproblemType.OPTIMIZATION: "约束优化模型",
            SubproblemType.MULTI_OBJECTIVE_DECISION: "多目标决策模型",
            SubproblemType.PREDICTION: "预测模型",
            SubproblemType.EVALUATION: "综合评价模型",
            SubproblemType.SIMULATION: "仿真模型",
            SubproblemType.GRAPH_NETWORK: "图网络模型",
            SubproblemType.STATISTICS: "统计推断模型",
            SubproblemType.OPERATIONS_RESEARCH: "运筹优化模型",
            SubproblemType.DIFFERENTIAL_OR_PHYSICAL_MODEL: "机理方程模型",
            SubproblemType.DATA_MINING: "数据挖掘模型",
        }.get(problem_type, "通用分析模型")

    def _algorithm_for_problem_type(problem_type: SubproblemType) -> str:
        return {
            SubproblemType.SAMPLING_TEST: "搜索样本量、临界值和风险概率。",
            SubproblemType.OPTIMIZATION: "识别目标函数、约束和可行决策并求解。",
            SubproblemType.MULTI_OBJECTIVE_DECISION: "构造权重、评分和 Pareto 或排序结果。",
            SubproblemType.PREDICTION: "建立基准预测模型并记录验证指标。",
            SubproblemType.EVALUATION: "归一化指标并输出可解释评分表。",
            SubproblemType.SIMULATION: "构造场景并重复仿真输出统计结果。",
            SubproblemType.GRAPH_NETWORK: "构建节点边关系并计算图指标或路径。",
            SubproblemType.STATISTICS: "估计参数、区间和不确定性边界。",
            SubproblemType.OPERATIONS_RESEARCH: "建立调度、库存、运输或分配优化模型。",
            SubproblemType.DIFFERENTIAL_OR_PHYSICAL_MODEL: "建立机理方程并求解状态变化。",
            SubproblemType.DATA_MINING: "提取特征并运行聚类、分类或异常检测。",
        }.get(problem_type, "生成可审阅 baseline 结果。")
```

Keep no `_is_production_decision_problem(clean_question)` branch in production analysis. Leave `_extract_generic_subproblems` unused only until a cleanup task removes it, or replace its callers in this task if all tests pass.

- [ ] **Step 8: Replace `plan_model` routing**

At the top of `plan_model`:

```python
        state = _load_state(run_id)
        problem_text = " ".join([state.spec.question, _problem_brief_text(problem_brief)])
        route = _route_for_state(state, problem_text)
        if route.get("is_benchmark"):
            bundle = _ensure_benchmark_b_contract_bundle(state, problem_text)
            modeling_plan = _b_problem_modeling_plan(bundle)
            modeling_plan["workflow_type"] = route["workflow_type"]
            modeling_plan["benchmark_id"] = route["selected_benchmark_id"]
            report_text = _b_problem_modeling_report(bundle)
            artifact_service = _artifacts_for_state(state)
            model_plan_path = artifact_service.write_json("model_plan.json", modeling_plan)
            report_path = artifact_service.write_text("modeling_report.md", report_text)
            return {
                "modeling_plan": modeling_plan,
                "model_plan_path": str(model_plan_path),
                "modeling_report_path": str(report_path),
                "problem_contract_path": str(bundle["problem_contract_path"]),
                "model_contract_paths": {key: str(path) for key, path in bundle["model_paths"].items()},
                "experiment_contract_paths": {key: str(path) for key, path in bundle["experiment_paths"].items()},
            }

        bundle = _write_generic_contract_bundle(state, problem_text)
        subproblem_plans = _subproblem_plans_from_generic_bundle(bundle)
        modeling_plan = {
            "selected_model": "CUMCM dynamic contract workflow",
            "workflow_type": route["workflow_type"],
            "problem_contract_path": str(bundle["problem_contract_path"]),
            "model_contract_paths": {key: str(path) for key, path in bundle["model_paths"].items()},
            "experiment_contract_paths": {key: str(path) for key, path in bundle["experiment_paths"].items()},
            "solver_strategy_path": str(bundle["solver_strategy_path"]),
            "subproblem_plans": subproblem_plans,
            "candidate_models": sorted({item["model"] for item in subproblem_plans}),
            "algorithm_plan": "Route each detected subproblem through its contract-selected solver strategy and write result-backed claims.",
            "evaluation_metrics": ["contract coverage", "result completeness", "claim traceability", "paper adequacy"],
            "experiment_conclusion_links": [
                f"{item['result_file']} -> 对应论文结论：{item['title']}；关系：支撑；结果文件：{item['result_file']}"
                for item in subproblem_plans
            ],
        }
```

Add this helper:

```python
    def _subproblem_plans_from_generic_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
        strategies = bundle["solver_strategies"]
        model_by_id = {contract.subproblem_id: contract for contract in bundle["model_contracts"]}
        plans = []
        for subproblem in bundle["problem_contract"].subproblems:
            model = model_by_id[subproblem.subproblem_id]
            strategy = strategies[subproblem.subproblem_id]
            plans.append(
                {
                    "id": subproblem.subproblem_id,
                    "title": subproblem.question_text[:64] or subproblem.subproblem_id,
                    "objective": subproblem.question_text,
                    "problem_type": subproblem.primary_type.value,
                    "model": model.algorithm,
                    "algorithm": model.algorithm,
                    "solver_mode": strategy.mode.value,
                    "dependencies": subproblem.dependencies,
                    "result_file": model.result_files[0],
                }
            )
        return plans
```

- [ ] **Step 9: Verify route integration**

Run:

```bash
pytest agent_app/tests/test_generic_cumcm_workflow.py agent_app/tests/test_deepagent_tools.py::test_generic_problem_dynamically_identifies_all_subproblems_and_runs_baselines -q
```

Expected:

```text
passed
```

- [ ] **Step 10: Spec review**

Confirm:

- Production B-looking text enters `generic_cumcm_contract_workflow`.
- Explicit benchmark mode enters `cumcm_b_problem_benchmark_workflow`.
- `analyze_problem` no longer contains a production-decision branch.

- [ ] **Step 11: Quality review**

Check:

- The route trace is written once per `analyze_problem` and `plan_model` call.
- The generic plan includes contract paths and solver strategy path.
- Existing non-B smoke tests still pass.

- [ ] **Step 12: Commit**

```bash
git add agent_app/tools/competition.py agent_app/tests/test_generic_cumcm_workflow.py agent_app/tests/test_deepagent_tools.py
git commit -m "feat: route production cumcm through generic contracts"
```

## Task 6: Make Experiments Use Generic Solver Strategies

**Files:**
- Modify: `agent_app/tools/competition.py`
- Modify: `agent_app/tests/test_generic_cumcm_workflow.py`

- [ ] **Step 1: Add failing experiment-route tests**

Add to `agent_app/tests/test_generic_cumcm_workflow.py`:

```python
def test_non_b_problem_does_not_enter_benchmark_solver(tmp_path):
    question = (
        "C 题 河流水质评价。"
        "问题1：建立水质综合评价指标体系。"
        "问题2：预测未来三个月水质等级。"
    )
    store, state, tools = _tools_for_question(tmp_path, question)

    problem = tools["analyze_problem"].invoke({"run_id": state.run_id, "question": question})
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )
    experiment = tools["run_experiment"].invoke(
        {"run_id": state.run_id, "modeling_plan": plan["modeling_plan"], "data_files": []}
    )

    run_dir = store.run_dir(state.run_id)
    assert experiment["experiment_result"]["execution_status"] == "success"
    assert (run_dir / "results" / "q1_result.csv").exists()
    assert (run_dir / "results" / "q2_result.csv").exists()
    assert not (run_dir / "results" / "q2_table1_decisions.csv").exists()
    assert "generic_cumcm_contract_workflow" in (run_dir / "solve.py").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the test and confirm it fails against current B routing**

Run:

```bash
pytest agent_app/tests/test_generic_cumcm_workflow.py::test_non_b_problem_does_not_enter_benchmark_solver -q
```

Expected:

```text
failed
```

- [ ] **Step 3: Update `run_experiment` route condition**

Replace:

```python
        if _is_b_problem_context(state, modeling_plan=modeling_plan):
```

with:

```python
        route = _route_for_state(state, state.spec.question)
        if route.get("is_benchmark") or modeling_plan.get("workflow_type") == "cumcm_b_problem_benchmark_workflow":
```

Update the benchmark call to use `_ensure_benchmark_b_contract_bundle`.

- [ ] **Step 4: Add route marker to generic solve code**

Inside `_generic_solve_code`, add this constant near `SUBPROBLEMS`:

```python
WORKFLOW_TYPE = "generic_cumcm_contract_workflow"
```

Add it to each result row:

```python
            "workflow_type": WORKFLOW_TYPE,
            "solver_mode": item.get("solver_mode", "generated_solver"),
```

- [ ] **Step 5: Write experiment trace in `run_experiment`**

Before returning generic experiment result:

```python
        trace = _trace_for_state(state)
        trace.append_event(
            "run_experiment",
            {
                "workflow_type": modeling_plan.get("workflow_type"),
                "result_paths": result_paths,
                "execution_status": experiment_result["execution_status"],
            },
        )
        trace.write_json("llm_outputs/run_experiment.json", experiment_result)
```

- [ ] **Step 6: Verify generic and benchmark experiment paths**

Run:

```bash
pytest agent_app/tests/test_generic_cumcm_workflow.py agent_app/tests/test_b_problem_solver.py -q
```

Expected:

```text
passed
```

- [ ] **Step 7: Spec review**

Confirm:

- Production experiments do not create B-specific q1-q4 result names.
- Benchmark experiments still create q1-q4 benchmark results.
- Result files include solver mode.

- [ ] **Step 8: Quality review**

Check:

- Re-running `solve.py` from run directory succeeds.
- Result paths are collected recursively.
- Trace does not include secrets.

- [ ] **Step 9: Commit**

```bash
git add agent_app/tools/competition.py agent_app/tests/test_generic_cumcm_workflow.py
git commit -m "feat: run cumcm experiments through generic strategies"
```

## Task 7: Build Generic Claims With Evidence Locators

**Files:**
- Modify: `agent_app/services/claim_map.py`
- Modify: `agent_app/evaluators/claim_gate.py`
- Modify: `agent_app/tests/test_claim_gate.py`

- [ ] **Step 1: Add failing locator tests**

Add to `agent_app/tests/test_claim_gate.py`:

```python
def test_claim_gate_rejects_supported_claim_without_locator(tmp_path):
    path = tmp_path / "results/q1_result.csv"
    path.parent.mkdir()
    path.write_text("subproblem_id,status\nq1,solved\n", encoding="utf-8")
    claim = Claim(
        claim_id="claim_q1_result",
        section="result_analysis",
        text="问题1已经得到结果。",
        evidence=[ClaimEvidence(kind="result_file", path=Path("results/q1_result.csv"))],
        status=ClaimStatus.SUPPORTED,
    )

    report = evaluate_claims([claim], artifact_root=tmp_path)

    assert report.passed is False
    assert "locator" in report.required_fixes[0]


def test_build_generic_claims_creates_result_locators(tmp_path):
    from agent_app.services.claim_map import build_generic_claims

    path = tmp_path / "results/q1_result.csv"
    path.parent.mkdir()
    path.write_text("subproblem_id,status\nq1,solved\n", encoding="utf-8")
    claims = build_generic_claims(
        [
            {
                "id": "q1",
                "title": "建立评价模型",
                "result_file": "results/q1_result.csv",
            }
        ],
        tmp_path,
    )

    assert claims[0].claim_id == "claim_q1_result"
    assert claims[0].evidence[0].locator == "row:1"
```

Also update the existing positive claim-gate test so its supported claim has a locator:

```python
ClaimEvidence(
    kind="result_file",
    path=Path("results/q1_sampling_plan.csv"),
    locator="row:1",
)
```

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
pytest agent_app/tests/test_claim_gate.py -q
```

Expected:

```text
failed
```

- [ ] **Step 3: Update claim gate**

```python
# agent_app/evaluators/claim_gate.py
def evaluate_claims(claims: list[Claim], artifact_root: Path) -> QualityReport:
    fixes: list[str] = []
    findings: list[str] = []
    for claim in claims:
        if not claim.is_supported():
            fixes.append(f"{claim.claim_id} 缺少证据支持")
            continue
        for evidence in claim.evidence:
            evidence_path = evidence.path if evidence.path.is_absolute() else artifact_root / evidence.path
            if not evidence_path.exists():
                fixes.append(f"{claim.claim_id} 引用的证据不存在: {evidence.path}")
            if not evidence.locator.strip():
                fixes.append(f"{claim.claim_id} 缺少 evidence locator")
    return QualityReport(
        gate_name="claim",
        passed=not fixes,
        score=1.0 if not fixes else max(0.0, 1.0 - len(fixes) / max(1, len(claims))),
        findings=findings,
        required_fixes=fixes,
    )
```

- [ ] **Step 4: Add generic claim builder and locators**

```python
# agent_app/services/claim_map.py
def build_generic_claims(subproblem_plans: list[dict], run_dir: Path | str) -> list[Claim]:
    root = Path(run_dir)
    claims: list[Claim] = []
    for item in subproblem_plans:
        subproblem_id = str(item["id"])
        relative_path = Path(str(item.get("result_file") or f"results/{subproblem_id}_result.csv"))
        evidence_path = root / relative_path
        status = ClaimStatus.SUPPORTED if evidence_path.exists() else ClaimStatus.UNSUPPORTED
        evidence = []
        if status == ClaimStatus.SUPPORTED:
            evidence = [
                ClaimEvidence(
                    kind="result_file",
                    path=relative_path,
                    locator="row:1",
                )
            ]
        claims.append(
            Claim(
                claim_id=f"claim_{subproblem_id}_result",
                section="result_analysis",
                text=f"{item.get('title', subproblem_id)} 的结论由 {relative_path.as_posix()} 支撑。",
                evidence=evidence,
                status=status,
                confidence="medium" if status == ClaimStatus.SUPPORTED else "",
            )
        )
    return claims
```

Update `build_b_problem_claims` evidence creation to include locators:

```python
        evidence = [
            ClaimEvidence(kind="result_file", path=Path(relative_path), locator="row:1")
        ] if status == ClaimStatus.SUPPORTED else []
```

- [ ] **Step 5: Verify claim tests**

Run:

```bash
pytest agent_app/tests/test_claim_gate.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Spec review**

Confirm:

- Supported claims require concrete locators.
- Generic claims are generated per detected subproblem.
- B benchmark claims still pass with locators.

- [ ] **Step 7: Quality review**

Check:

- Missing result files produce unsupported claims.
- Claim text names the result file.
- Claim gate reports actionable fixes.

- [ ] **Step 8: Commit**

```bash
git add agent_app/services/claim_map.py agent_app/evaluators/claim_gate.py agent_app/tests/test_claim_gate.py
git commit -m "feat: require claim evidence locators"
```

## Task 8: Replace Scaffold Sections With User-Facing Section Drafts

**Files:**
- Modify: `agent_app/services/section_writer.py`
- Modify: `agent_app/services/paper_sections.py`
- Modify: `agent_app/tools/competition.py`
- Modify: `agent_app/tests/test_section_writer.py`
- Modify: `agent_app/tests/test_section_paper_writer.py`

- [ ] **Step 1: Add failing section tests**

Update `agent_app/tests/test_section_writer.py`:

```python
def test_write_section_files_does_not_emit_internal_empty_claim_text(tmp_path):
    paths = write_section_files(tmp_path, [])

    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "暂无已支持结论" not in combined
    assert "Claim-Aware Section Context" not in combined
    assert "## Claims" not in combined
    assert (tmp_path / "sections" / "08_result_analysis.md").exists()
```

Add to `agent_app/tests/test_section_paper_writer.py`:

```python
def test_draft_competition_paper_generic_sections_are_user_facing(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="问题1：建立评价模型。"))
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    problem = tools["analyze_problem"].invoke({"run_id": state.run_id, "question": state.spec.question})
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )
    experiment = tools["run_experiment"].invoke(
        {"run_id": state.run_id, "modeling_plan": plan["modeling_plan"], "data_files": []}
    )
    paper = tools["draft_competition_paper"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "modeling_plan": plan["modeling_plan"],
            "experiment_result": experiment["experiment_result"],
            "evidence_notes": [],
        }
    )

    text = (store.run_dir(state.run_id) / "paper.md").read_text(encoding="utf-8")
    assert "Claim-Aware Section Context" not in text
    assert "暂无已支持结论" not in text
    assert "## 摘要" in text
    assert "## 结果分析" in text
    assert "claim_q1_result" in text
    assert paper["paper_section_paths"]
```

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
pytest agent_app/tests/test_section_writer.py agent_app/tests/test_section_paper_writer.py -q
```

Expected:

```text
failed
```

- [ ] **Step 3: Update section writer rendering**

Replace `_render_claim_section` in `agent_app/services/section_writer.py`:

```python
def _render_claim_section(section: str, context: dict) -> str:
    title = {
        "title": "题目",
        "abstract": "摘要",
        "keywords": "关键词",
        "problem_restatement": "问题重述",
        "problem_analysis": "问题分析",
        "assumptions": "模型假设",
        "symbols": "符号说明",
        "model_solution": "模型建立与求解",
        "result_analysis": "结果分析",
        "robustness_analysis": "灵敏度与稳健性分析",
        "model_evaluation": "模型评价",
        "references": "参考文献",
        "appendix": "附录",
    }.get(section, section)
    lines = [f"## {title}", ""]
    if context["claims"]:
        for claim in context["claims"]:
            evidence = "；".join(claim["evidence"])
            lines.append(f"{claim['text']} 该结论对应 `{claim['claim_id']}`，证据位置为 {evidence}。")
        return "\n".join(lines) + "\n"
    default_text = {
        "abstract": "本文围绕题面要求建立可复现的数学建模流程，并将模型、实验与论文结论逐项绑定。",
        "keywords": "数学建模；合同驱动；可复现实验；证据追踪",
        "problem_restatement": "本节概括赛题目标、输入数据、约束条件与需要提交的结果。",
        "problem_analysis": "本节根据子问题类型分析变量、参数、目标函数和求解依赖。",
        "assumptions": "模型假设仅服务于已识别的子问题，并在结果解释中保留适用边界。",
        "symbols": "主要符号随模型合同和结果文件一起定义，避免引入未使用变量。",
        "model_solution": "各子问题按合同选择求解策略，生成代码、结果文件和验证记录。",
        "result_analysis": "本节只写入已有结果文件能够支撑的结论。",
        "robustness_analysis": "稳健性分析围绕参数扰动、数据缺失和模型假设变化展开。",
        "model_evaluation": "模型评价从可解释性、可复现性、局限性和竞赛提交完整性展开。",
        "references": "参考文献由证据检索阶段与本地参考文件共同维护。",
        "appendix": "附录包含代码入口、合同文件、结果文件和审查报告路径。",
    }.get(section, "本节保留为用户可审阅正文，不包含内部调试上下文。")
    lines.append(default_text)
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Use generic claims in `draft_competition_paper`**

Import:

```python
from agent_app.services.claim_map import build_b_problem_claims, build_generic_claims
```

In the generic `draft_competition_paper` branch, before writing `paper.md`:

```python
        run_dir = run_store.run_dir(run_id)
        claims = build_generic_claims(subproblem_plans, run_dir)
        claim_map_path = ContractStore(run_dir).write_claim_map(claims)
        claim_report = evaluate_claims(claims, artifact_root=run_dir)
        claim_report_path = _write_contract_json(run_dir, "claims/claim_gate_report.json", claim_report)
        trace = _trace_for_state(state)
        trace.write_gate_report("claim_gate", to_json_dict(claim_report))
        section_paths = write_claim_section_files(run_dir, claims)
        section_text = "\n\n".join(path.read_text(encoding="utf-8").strip() for path in section_paths)
```

Build final `paper.md` from user-facing sections only:

```python
        markdown_path = _write_for_state(
            state,
            "paper.md",
            section_text + "\n",
        )
```

- [ ] **Step 5: Make `paper.tex` contain all required sections**

Use a deterministic LaTeX skeleton in the generic branch:

```python
        latex_body = "\n".join(
            [
                "\\section{摘要}",
                "本文构建通用 CUMCM 合同驱动建模流程。",
                "\\section{问题重述}",
                f"共识别 {len(subproblem_plans)} 个子问题。",
                "\\section{模型假设}",
                "所有假设均记录在模型合同中。",
                "\\section{符号说明}",
                "变量、参数和结果文件由模型合同定义。",
                "\\section{模型建立与求解}",
                "每个子问题通过 solver strategy 选择求解方式。",
                "\\section{结果分析}",
                "结果结论由 claim map 追踪到具体文件与 locator。",
                "\\section{灵敏度分析}",
                "稳健性结论只在实验产物支持时写入。",
                "\\section{模型评价}",
                "评价包括可解释性、可复现性与局限性。",
                "\\section{参考文献}",
                "参考文献由证据检索阶段维护。",
                "\\section{附录}",
                "附录列出代码、合同、结果和审查报告。",
            ]
        )
        latex_path = _write_for_state(
            state,
            "paper.tex",
            "\\documentclass[UTF8]{ctexart}\n\\begin{document}\n"
            + latex_body
            + "\n\\end{document}\n",
        )
```

- [ ] **Step 6: Verify section tests**

Run:

```bash
pytest agent_app/tests/test_section_writer.py agent_app/tests/test_section_paper_writer.py -q
```

Expected:

```text
passed
```

- [ ] **Step 7: Spec review**

Confirm:

- Final paper does not include internal section context.
- Section files are user-facing.
- Generic paper uses claim map and claim gate.

- [ ] **Step 8: Quality review**

Check:

- `paper.md` has required headings.
- `paper.tex` has complete manuscript structure.
- `claim_gate_report.json` is written and traced.

- [ ] **Step 9: Commit**

```bash
git add agent_app/services/section_writer.py agent_app/services/paper_sections.py agent_app/tools/competition.py agent_app/tests/test_section_writer.py agent_app/tests/test_section_paper_writer.py
git commit -m "feat: write user-facing cumcm paper sections"
```

## Task 9: Strengthen Paper And Submission Gates

**Files:**
- Modify: `agent_app/evaluators/paper_gate.py`
- Modify: `agent_app/evaluators/submission_gate.py`
- Modify: `agent_app/tools/competition.py`
- Modify: `agent_app/tests/test_quality_gates.py`
- Modify: `agent_app/tests/test_generic_cumcm_workflow.py`

- [ ] **Step 1: Add failing gate tests**

Add to `agent_app/tests/test_quality_gates.py`:

```python
def test_paper_gate_rejects_internal_context_and_thin_sections(tmp_path):
    paper = PaperDraft(
        markdown_path=tmp_path / "paper.md",
        latex_path=tmp_path / "paper.tex",
        sections={
            "摘要": "短",
            "关键词": "建模",
            "问题重述": "题面。",
            "模型假设": "独立。",
            "符号说明": "x。",
            "问题分析": "分析。",
            "模型建立与求解": "Claim-Aware Section Context",
            "结果分析": "暂无已支持结论",
            "灵敏度": "扰动。",
            "模型评价": "评价。",
            "参考文献": "[1]",
            "附录": "代码。",
        },
    )

    report = evaluate_paper(paper)

    assert report.passed is False
    assert any("内部上下文" in fix for fix in report.required_fixes)
    assert any("章节内容过短" in fix for fix in report.required_fixes)
```

Add to `agent_app/tests/test_generic_cumcm_workflow.py`:

```python
def test_package_blocks_when_claim_gate_failed(tmp_path):
    store, state, tools = _tools_for_question(tmp_path, "问题1：建立评价模型。")
    state.quality_reports = []
    store.save_state(state)
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("真实建模报告\n" * 60, encoding="utf-8")
    (run_dir / "solve.py").write_text("def main():\n    print('ok')\n", encoding="utf-8")
    (run_dir / "paper.tex").write_text("\\documentclass{article}\\begin{document}ok\\end{document}", encoding="utf-8")
    state.quality_reports.append(
        __import__("agent_app.domain.models", fromlist=["QualityReport"]).QualityReport(
            gate_name="claim",
            passed=False,
            required_fixes=["claim_q1_result 缺少 evidence locator"],
        )
    )
    store.save_state(state)

    try:
        tools["package_submission"].invoke({"run_id": state.run_id})
    except RuntimeError as exc:
        assert "质量审查未通过" in str(exc)
    else:
        raise AssertionError("package_submission must block failed claim gate")


def test_package_blocks_when_stale_marker_exists(tmp_path):
    store, state, tools = _tools_for_question(tmp_path, "问题1：建立评价模型。")
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("真实建模报告\n" * 60, encoding="utf-8")
    (run_dir / "solve.py").write_text("def main():\n    print('ok')\n", encoding="utf-8")
    (run_dir / "paper.tex").write_text("\\documentclass{article}\\begin{document}ok\\end{document}", encoding="utf-8")
    stale_dir = run_dir / "stale"
    stale_dir.mkdir()
    (stale_dir / "paper.json").write_text('{"artifact_group":"paper","reason":"upstream model changed"}', encoding="utf-8")

    try:
        tools["package_submission"].invoke({"run_id": state.run_id})
    except RuntimeError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("package_submission must block stale artifacts")
```

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
pytest agent_app/tests/test_quality_gates.py::test_paper_gate_rejects_internal_context_and_thin_sections agent_app/tests/test_generic_cumcm_workflow.py::test_package_blocks_when_claim_gate_failed agent_app/tests/test_generic_cumcm_workflow.py::test_package_blocks_when_stale_marker_exists -q
```

Expected:

```text
failed
```

- [ ] **Step 3: Strengthen `paper_gate.py`**

Add constants:

```python
INTERNAL_CONTEXT_MARKERS = [
    "Claim-Aware Section Context",
    "generic_cumcm_contract_workflow",
    "cumcm_b_problem_contract_workflow",
    "cumcm_b_problem_benchmark_workflow",
    "暂无已支持结论",
    "this is a scaffold",
]
MIN_SECTION_CHARS = 18
```

Add checks inside `evaluate_paper`:

```python
    leaked = [marker for marker in INTERNAL_CONTEXT_MARKERS if marker in section_text]
    if leaked:
        fixes.append("论文包含内部上下文或调试文本: " + ", ".join(leaked))

    for key, value in paper.sections.items():
        if key in REQUIRED_SECTIONS and len(value.strip()) < MIN_SECTION_CHARS:
            fixes.append(f"章节内容过短: {key}")
```

- [ ] **Step 4: Record paper gate in `review_submission`**

In `_review_paper_artifacts`, ensure paper gate output writes to trace gate reports. If `_review_paper_artifacts` currently returns only markdown review, add `paper_gate_report` to the aggregate path by calling `evaluate_paper` with parsed sections from `paper_draft` or markdown headings.

Use this helper inside `competition.py`:

```python
def _paper_draft_from_markdown(run_dir: Path) -> PaperDraft:
        paper_path = run_dir / "paper.md"
        sections: dict[str, str] = {}
        current = ""
        for line in paper_path.read_text(encoding="utf-8").splitlines() if paper_path.exists() else []:
            if line.startswith("## "):
                current = line.removeprefix("## ").strip()
                sections[current] = ""
            elif current:
                sections[current] = (sections[current] + "\n" + line).strip()
        return PaperDraft(
            markdown_path=paper_path if paper_path.exists() else None,
            latex_path=run_dir / "paper.tex" if (run_dir / "paper.tex").exists() else None,
            sections=sections,
        )
```

Also update `_blocking_quality_reports` inside `make_competition_tools` so stale markers block packaging:

```python
    def _blocking_quality_reports(state: RunState) -> list[QualityReport]:
        reports = [report for report in state.quality_reports if not report.passed]
        stale_dir = run_store.run_dir(state.run_id) / "stale"
        stale_files = sorted(path.name for path in stale_dir.glob("*.json")) if stale_dir.exists() else []
        if stale_files:
            reports.append(
                QualityReport(
                    gate_name="stale",
                    passed=False,
                    score=0.0,
                    findings=[f"stale marker exists: {name}" for name in stale_files],
                    required_fixes=[f"stale artifact requires regeneration: {name}" for name in stale_files],
                )
            )
        return reports
```

- [ ] **Step 5: Verify gates**

Run:

```bash
pytest agent_app/tests/test_quality_gates.py agent_app/tests/test_generic_cumcm_workflow.py::test_package_blocks_when_claim_gate_failed agent_app/tests/test_generic_cumcm_workflow.py::test_package_blocks_when_stale_marker_exists -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Spec review**

Confirm:

- Banned final-paper phrases fail the paper gate.
- Thin sections fail the paper gate.
- Failed claim gate blocks packaging.

- [ ] **Step 7: Quality review**

Check:

- Gate failures appear in `RunState.quality_reports`.
- Packaging error message lists actionable fixes.
- Gate trace files are written under `trace/gate_reports/`.

- [ ] **Step 8: Commit**

```bash
git add agent_app/evaluators/paper_gate.py agent_app/evaluators/submission_gate.py agent_app/tools/competition.py agent_app/tests/test_quality_gates.py agent_app/tests/test_generic_cumcm_workflow.py
git commit -m "feat: harden cumcm writing and submission gates"
```

## Task 10: End-To-End Generic And Benchmark Regression

**Files:**
- Modify: `agent_app/tests/test_competition_smoke.py`
- Modify: `agent_app/tests/test_deepagent_tools.py`
- Modify: `agent_app/tests/test_b_problem_acceptance.py`

- [ ] **Step 1: Update B acceptance test to explicit benchmark mode**

In `agent_app/tests/test_b_problem_acceptance.py`, create the run with:

```python
from agent_app.domain.models import RunOptions
from agent_app.workflow_packs.cumcm.routing import BENCHMARK_2024_B_ID

state = store.create_run(
    RunSpec(
        question="生产过程中的决策问题 零配件 拆解",
        options=RunOptions(workflow_mode="benchmark", benchmark_id=BENCHMARK_2024_B_ID),
    )
)
```

Update the expected workflow type:

```python
assert plan["modeling_plan"]["workflow_type"] == "cumcm_b_problem_benchmark_workflow"
```

- [ ] **Step 2: Update production B test expectations**

Rename `test_b_problem_tools_generate_executable_model_code_and_paper` in `agent_app/tests/test_deepagent_tools.py` to:

```python
def test_b_like_problem_in_production_uses_generic_workflow(tmp_path):
```

Change its workflow assertions:

```python
assert plan["modeling_plan"]["workflow_type"] == "generic_cumcm_contract_workflow"
assert "cumcm_b_problem_contract_workflow" not in modeling_report
assert not (run_dir / "results" / "q2_table1_decisions.csv").exists()
```

Keep a separate explicit benchmark test for q1-q4 deterministic files.

- [ ] **Step 3: Add trace assertions to smoke test**

In `agent_app/tests/test_competition_smoke.py`, after `run_dir` is defined:

```python
assert (run_dir / "trace" / "routing_decision.json").exists()
assert (run_dir / "trace" / "stage_events.jsonl").exists()
assert (run_dir / "contracts" / "problem_contract.json").exists()
assert (run_dir / "contracts" / "solver_strategies.json").exists()
```

- [ ] **Step 4: Run focused regression suite**

Run:

```bash
pytest agent_app/tests/test_cumcm_workflow_routing.py agent_app/tests/test_cumcm_contract_bundle.py agent_app/tests/test_run_trace.py agent_app/tests/test_generic_cumcm_workflow.py agent_app/tests/test_b_problem_solver.py agent_app/tests/test_b_problem_acceptance.py agent_app/tests/test_deepagent_tools.py agent_app/tests/test_competition_smoke.py agent_app/tests/test_quality_gates.py agent_app/tests/test_claim_gate.py -q
```

Expected:

```text
passed
```

- [ ] **Step 5: Run full agent_app tests if focused suite passes**

Run:

```bash
pytest agent_app/tests -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Spec review**

Confirm every acceptance criterion in `docs/superpowers/specs/2026-07-15-generic-cumcm-contract-workflow-design.md` maps to a passing test or an inspected code path:

- No production path branches on 2024 B or exact production-decision title.
- 2024 B passes as explicit benchmark fixture.
- Different subproblem counts create matching contracts and result files.
- Non-production CUMCM problems do not enter B solver.
- `paper.md` contains no internal context.
- `paper.tex` contains required sections.
- Thin paper drafts fail quality gates.
- Trace files explain observable routing and generation decisions.
- Packaging is blocked by failed gates.

- [ ] **Step 7: Quality review**

Check:

- No unrelated files are staged.
- The moved benchmark code is not duplicated.
- All newly added trace files are per-run artifacts only, not committed generated outputs.
- The full diff does not contain API keys.

- [ ] **Step 8: Commit**

```bash
git add agent_app/tests/test_competition_smoke.py agent_app/tests/test_deepagent_tools.py agent_app/tests/test_b_problem_acceptance.py
git commit -m "test: cover generic cumcm and benchmark regression"
```

## Final Verification

Run:

```bash
git diff --check
pytest agent_app/tests -q
```

Expected:

```text
passed
```

Then inspect:

```bash
git status --short
```

Expected:

```text
Only intentional source, test, and docs changes are present.
```

## Execution Notes

- Use exact-file staging because the worktree contains many unrelated changes.
- After each task, perform the required two reviews:
  - Spec review: compare the task result against this plan and the design spec.
  - Quality review: check naming, boundaries, tests, and accidental scope expansion.
- Prefer one fresh subagent per task. The main agent should review each task before dispatching the next one.
- Do not run the 2024 B deterministic solver in production mode.
- Do not expose hidden model reasoning. Save observable inputs, prompts, outputs, routes, and gate decisions only.
