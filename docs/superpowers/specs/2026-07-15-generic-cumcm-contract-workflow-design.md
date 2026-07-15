# Generic CUMCM Contract Workflow Design

## Purpose

This spec corrects the current CUMCM implementation direction. The 2024 B problem helped validate the contract, solver, claim, and review pipeline, but a year-specific or problem-specific branch must not become the product path. CUMCM B problems vary by year, and even problems with the same letter can require unrelated methods.

The product workflow must solve CUMCM problems by dynamically understanding the problem structure, not by matching a hard-coded benchmark.

## Architecture Decision

The main CUMCM route must be `generic_cumcm_contract_workflow`.

The current `cumcm_b_problem_contract_workflow` becomes a benchmark fixture and regression suite. It may keep deterministic expected artifacts for the 2024 B problem, but it must not be selected as the primary production workflow for user runs.

The general rule is:

```text
Problem text + assets -> subproblem contracts -> model-family routing -> model contracts
-> experiment contracts -> generated or selected solvers -> results -> claims -> sections
-> reviews -> package
```

The system must not route by contest letter, year, or exact title except in benchmark tests.

## Problem With The Current B Branch

The current B-specific branch creates a misleading sense of progress:

1. It can pass review while producing a thin paper draft.
2. It bakes one production-decision structure into the main tool path.
3. It treats B as if future B problems share the same mathematics.
4. It hides the real product need: dynamic model planning and solver generation.
5. It lets quality gates check artifact existence and traceability more strongly than paper adequacy.

This is useful for smoke testing, but unsafe as product architecture.

## Goals

The refactor must:

1. Remove year-specific B-problem routing from the production tool path.
2. Preserve the 2024 B problem as a benchmark fixture with deterministic expected outputs.
3. Use dynamic subproblem recognition for all CUMCM runs.
4. Classify each subproblem into one or more model families.
5. Generate a `ProblemContract`, `ModelContract`, and `ExperimentContract` for every subproblem.
6. Select solver strategy by model family and asset availability.
7. Generate paper sections from validated claims, not from internal scaffold text.
8. Save observable trace files for debugging prompts, routing decisions, contracts, model calls, and gate decisions.
9. Strengthen quality gates so "review passed" means more than "files exist".

## Non-Goals

This refactor does not need to solve every CUMCM problem optimally in one step.

This refactor does not implement MCM/ICM, thesis, or academic-paper workflows.

This refactor does not remove the 2024 B benchmark. It moves it out of the production route.

## Workflow Routing

The tool path should use these routing levels:

1. `workflow_family`: `cumcm`.
2. `problem_contract`: dynamic subproblems and dependencies.
3. `model_family`: task type per subproblem.
4. `solver_strategy`: deterministic template, generated code, external library, or human-confirmed plan.
5. `writing_strategy`: section-by-section paper writing from claims and evidence.

The workflow may use benchmark templates only when the run is explicitly marked as a benchmark or test fixture. User-facing production runs should not silently switch into a benchmark-specific branch.

## Subproblem Type Routing

Each subproblem should be routed by model family:

- `sampling_test`: hypothesis test, confidence interval, OC curve, sample-size search.
- `optimization`: linear, integer, nonlinear, dynamic programming, enumeration, heuristic search.
- `multi_objective_decision`: Pareto, weighted scoring, TOPSIS, AHP, entropy weight, robustness tradeoff.
- `prediction`: regression, time series, machine learning baseline, validation metrics.
- `evaluation`: index system, normalization, ranking, sensitivity of weights.
- `simulation`: Monte Carlo, queueing, agent simulation, scenario design.
- `graph_network`: shortest path, flow, matching, robustness, centrality.
- `statistics`: estimation, uncertainty quantification, inference, hypothesis testing.
- `operations_research`: scheduling, inventory, routing, assignment, production planning.
- `differential_or_physical_model`: mechanism equations, ODE/PDE, physics-inspired dynamics.
- `data_mining`: clustering, classification, anomaly detection, feature extraction.

The classifier may assign secondary types, but every subproblem needs one primary type and an explicit solver strategy.

## Solver Strategy

The generic workflow should choose among four solver modes:

1. `template_solver`: a reusable, model-family template for common tasks.
2. `generated_solver`: DeepSeek writes code from contracts and schemas.
3. `library_solver`: use a known library such as scipy, statsmodels, networkx, pulp, cvxpy, sklearn, or pandas.
4. `manual_review_required`: the plan is too under-specified, so the workflow asks the user to confirm missing modeling choices before code generation.

The 2024 B deterministic solver becomes a `benchmark_solver`, not a production default.

## Benchmark Fixtures

Benchmark fixtures should live under a clearly non-production location, for example:

```text
agent_app/workflow_packs/cumcm/benchmarks/
  2024_b_production_decision/
    problem_text.md
    expected_contracts/
    expected_results/
    expected_claims/
    acceptance.md
```

Benchmark tests may assert exact q1-q4 outputs. Production tests should assert workflow properties, not 2024-B-specific files.

## Writing Workflow

The final paper must not concatenate internal section context.

The writing stage should:

1. Build a `PaperOutline` from the problem contract.
2. Build `ClaimMap` from validated results.
3. Write each section independently.
4. Require each result statement to cite a claim ID, equation file, result row, figure, or table.
5. Save section drafts under `sections/`.
6. Merge only user-facing prose into `paper.md`.
7. Store internal contexts under `trace/` or `debug/`, never inside the final paper.

## Observable Trace Requirement

The system cannot expose hidden model reasoning, but it must expose observable decision traces.

Each run should save:

```text
trace/
  routing_decision.json
  stage_events.jsonl
  prompts/
    plan_model.json
    run_experiment.json
    write_section_*.json
  llm_outputs/
    plan_model.json
    write_section_*.md
  gate_reports/
    model_gate.json
    experiment_gate.json
    claim_gate.json
    writing_gate.json
```

Trace files must include inputs, selected route, rejected routes, role, model name, output schema, and final output. They must not leak API keys or private hidden reasoning.

## Quality Gates

Quality gates must become stricter:

1. Banned final-paper phrases: internal workflow names, `Claim-Aware Section Context`, "this is a scaffold", "暂无已支持结论", and raw debug instructions.
2. Each required paper section must have substantial user-facing content.
3. Each claim must include a concrete locator such as result row, equation ID, figure ID, or table row.
4. Experiment outputs must satisfy minimum completeness for the detected subproblem type.
5. Sampling tests must reject trivial sample plans and include risk interpretation.
6. Optimization results must include objective values, decision variables, parameter sources, and feasibility checks.
7. Sensitivity analysis must include meaningful scenarios derived from model uncertainty or user-approved assumptions.
8. `paper.tex` must be a real renderable manuscript, not a placeholder.
9. Passing review must mean the result is reviewable as a competition submission draft, not only traceable.

## Migration Plan

The implementation should proceed in stages:

1. Add generic workflow routing metadata without removing the current B benchmark.
2. Move B-specific contracts, solver, and expected outputs into benchmark fixture modules.
3. Change production `plan_model`, `run_experiment`, and `draft_competition_paper` to use generic contracts.
4. Add solver-strategy selection by model family.
5. Add trace files for prompts, routing decisions, and quality gates.
6. Replace scaffold section writer with real section writers.
7. Strengthen gates and update B benchmark expectations.
8. Re-run the 2024 B benchmark plus at least two non-B or different-year CUMCM problems.

## Acceptance Criteria

The refactor is accepted when:

1. No user-facing production path branches on "2024 B" or the exact title "production decision problem".
2. The 2024 B problem still passes as a benchmark fixture.
3. A problem with a different number of subproblems creates matching contracts and result files.
4. A non-production-decision CUMCM problem does not enter the B solver.
5. `paper.md` contains no internal scaffold or trace text.
6. `paper.tex` contains a complete manuscript skeleton with all required sections.
7. Quality gates fail the current thin B paper for writing adequacy.
8. Trace files explain observable routing and generation decisions.
9. Packaging is blocked when writing, claim, experiment, or stale gates fail.

## Test Strategy

Tests should cover:

- Generic CUMCM routing does not select B-specific production workflow.
- B benchmark fixture still produces expected q1-q4 outputs in benchmark mode.
- Dynamic subproblem recognition works for 1, 3, 4, and 5 question prompts.
- Solver strategy is selected by subproblem type.
- Generated paper excludes internal scaffold text.
- Writing gate rejects empty sections and context leakage.
- Claim gate requires row-level or equation-level locators.
- Trace files are written and redact secrets.
- Package submission fails when any upstream gate is stale or failed.

## Product Implication

The platform should feel like a general mathematical modeling factory, not a collection of hand-coded contest cases. Benchmarks are how we measure generality; they are not how we route production work.
