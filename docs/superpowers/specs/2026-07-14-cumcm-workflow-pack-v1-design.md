# CUMCM Workflow Pack v1 Design

## Purpose

This spec defines the first workflow pack for the Paper Factory platform: CUMCM competition paper production. The pack must support general CUMCM problem solving, not only the 2024 B problem. The 2024 B problem is the first gold benchmark because it exposes table reconstruction, subproblem recognition, statistical testing, production decision modeling, experiment execution, paper writing, and quality review in one task.

## Goals

The CUMCM pack must:

1. Parse a CUMCM problem PDF or text into a structured problem contract.
2. Dynamically identify all subproblems, without assuming a fixed number of questions.
3. Classify each subproblem into a modeling family.
4. Retrieve useful external references and method examples through Mimo2.5 internet search when enabled.
5. Generate model, experiment, and writing contracts before producing prose.
6. Execute reproducible code and produce result artifacts.
7. Write a sectioned CUMCM-style paper from claims and evidence.
8. Run model, experiment, paper, claim, and submission quality gates.
9. Block packaging when quality gates fail.

## Non-Goals

This v1 pack does not implement MCM/ICM English workflows, graduation thesis workflows, academic paper submission workflows, or full multi-route tree search. Those are platform roadmap items.

This v1 pack does not claim to solve every possible CUMCM problem optimally. It provides a contract-driven workflow, a robust type system, and gold benchmark coverage that can be expanded.

## Supported Inputs

The pack supports:

- Problem PDFs.
- Problem text pasted into the Web or CLI.
- Images embedded in PDFs.
- Tables embedded in PDFs.
- CSV, Excel, JSON, TXT, Markdown, and PDF data/reference files.
- User-provided constraints or preferred methods.

All input assets must produce extraction metadata:

- original filename.
- file type.
- extraction method.
- confidence.
- extracted text length.
- table count.
- image count.
- warnings.
- source map entries.

## Model Responsibilities

Mimo2.5 is used for:

- PDF image understanding.
- Table reconstruction when PyMuPDF output is empty, malformed, or low confidence.
- Figure description.
- Internet search for background, method references, public datasets, and literature candidates.
- Source cards with title, URL, date, summary, relevance, and risk notes.

DeepSeek V4 Pro is used for:

- Problem decomposition.
- Model and experiment planning.
- Mathematical derivation.
- Code generation and debugging.
- Result interpretation.
- Section-level paper writing.
- Quality review and revision planning.

The pack must preserve query logs and source summaries for all Mimo-backed internet retrieval.

## Problem Type Taxonomy

Each subproblem is classified into one or more modeling families:

- `sampling_test`: sampling inspection, confidence, hypothesis testing, quality control.
- `optimization`: linear, integer, nonlinear, dynamic, or heuristic optimization.
- `multi_objective_decision`: weighted decision, Pareto tradeoff, TOPSIS, AHP, entropy weight.
- `prediction`: regression, time series, machine learning, forecasting.
- `evaluation`: scoring, ranking, index systems, comprehensive evaluation.
- `simulation`: Monte Carlo, queueing, agent simulation, sensitivity scenarios.
- `graph_network`: shortest path, flow, matching, network robustness.
- `statistics`: estimation, inference, uncertainty quantification.
- `operations_research`: scheduling, inventory, routing, assignment, production planning.
- `differential_or_physical_model`: continuous dynamics, mechanism equations, physics-inspired models.
- `data_mining`: clustering, classification, feature extraction, anomaly detection.

The classifier may assign multiple labels, but it must select one primary family for each subproblem.

## Core Contracts

### ProblemContract

The problem contract contains:

- contest family: `cumcm`.
- problem title.
- problem year if detected.
- raw problem text reference.
- extracted tables and figures.
- subproblems.
- required deliverables.
- known constraints.
- input asset dependencies.
- extraction warnings.

### SubproblemContract

Each subproblem contains:

- `subproblem_id`.
- question text.
- primary problem type.
- secondary problem types.
- required input tables and data files.
- dependencies on previous subproblems.
- expected output artifacts.
- risk notes.

### ModelContract

Each subproblem has a model contract:

- variables.
- parameters with source.
- assumptions.
- objective functions.
- constraints.
- algorithm.
- expected formulas.
- limitations.
- experiment-to-claim links.

### ExperimentContract

Each subproblem has an experiment contract:

- code entrypoint.
- input files.
- output schema.
- parameter audit requirements.
- validation checks.
- figure/table outputs.
- rerun conditions.

### ClaimMap

The claim map links paper conclusions to evidence:

- `claim_id`.
- section target.
- claim text.
- evidence files.
- supporting equations.
- result rows or figures.
- confidence level.
- status: `supported`, `limited`, `unsupported`, or `stale`.

Unsupported claims block packaging.

## CUMCM Workflow Stages

The v1 workflow stages are:

1. `ingest_inputs`: copy and register problem, data, and reference assets.
2. `reconstruct_inputs`: extract text, reconstruct tables, describe images, and create source maps.
3. `identify_subproblems`: create `ProblemContract` and `SubproblemContract` artifacts.
4. `retrieve_references`: use local references and Mimo internet search to collect method/source cards.
5. `plan_models`: create one `ModelContract` per subproblem.
6. `review_model_plan`: check model plan coverage before code generation.
7. `plan_experiments`: create one `ExperimentContract` per subproblem.
8. `implement_experiments`: generate code and parameter audit.
9. `run_experiments`: execute code, store logs, tables, and figures.
10. `validate_results`: verify schemas, non-empty outputs, and parameter provenance.
11. `build_claim_map`: convert validated results into claims.
12. `write_sections`: write paper sections one at a time.
13. `review_submission`: run subagent reviews and claim-evidence review.
14. `revise_or_package`: create revision tasks or package final submission.

## CUMCM Paper Sections

The writing stage must generate sections separately:

- title.
- abstract.
- keywords.
- problem restatement.
- problem analysis.
- model assumptions.
- symbol table.
- model establishment.
- model solution.
- result analysis.
- sensitivity or robustness analysis.
- model evaluation.
- references.
- appendix.

Each section must include claim IDs or evidence references where it states results.

## B Problem Gold Benchmark

The 2024 CUMCM B problem is the first gold benchmark. It must be handled by the general workflow, with optional specialized templates. The expected decomposition is:

- q1: sampling inspection plan under stated confidence requirements.
- q2: production-stage inspection and disassembly decisions for Table 1.
- q3: multi-stage assembly tree decisions for Table 2.
- q4: uncertainty-aware re-solving when defect rates are estimated by sampling.

Required outputs:

- `contracts/problem_contract.json`.
- `contracts/subproblems/q1.json` through q4.
- `contracts/models/q1.json` through q4.
- `contracts/experiments/q1.json` through q4.
- `equations/q1_sampling.md`.
- `equations/q2_expected_profit.md`.
- `equations/q3_assembly_tree.md`.
- `equations/q4_uncertainty.md`.
- `code/solve.py`.
- `results/q1_sampling_plan.csv`.
- `results/q2_table1_decisions.csv`.
- `results/q3_table2_tree_decisions.csv`.
- `results/q4_uncertainty_re_solve.csv`.
- `results/parameter_audit.json`.
- `claims/claim_map.json`.
- section drafts under `sections/`.
- review reports under `reviews/`.

## B Problem Required Fixes From Current Quality Gate

The current quality gate exposed issues that v1 must fix:

- Remove or justify the hard-coded `0.35` reuse/salvage coefficient.
- Redefine q1 sampling constraints so a trivial `n=1` accept rule cannot pass.
- Tie q4 uncertainty scenarios to sampling confidence intervals or posterior intervals, not arbitrary low/base/high labels.
- Expand formula files into a reviewable equation system.
- Expand paper writing into full section-level CUMCM prose.
- Ensure all final paper claims reference result files or equations.

## Sampling Test Requirements

For q1-like subproblems, the system must:

- State null and alternative hypotheses.
- Define producer and consumer risk or explain the chosen confidence interpretation.
- Search over sample size and critical values.
- Reject rules that satisfy only a one-sided trivial condition but fail practical discrimination.
- Save operating characteristic or probability tables when appropriate.
- Explain how the sampling plan affects later defect-rate uncertainty.

## Optimization Requirements

For q2-like subproblems, the system must:

- Enumerate or optimize decision variables.
- Define expected profit or expected cost from source parameters.
- Record every parameter source.
- Explain treatment of rework, return, disassembly, replacement, and salvage.
- Avoid unexplained empirical constants.
- Output both best strategy and competing strategy comparison.

## Assembly Tree Requirements

For q3-like subproblems, the system must:

- Represent parts, semi-finished products, and finished products as a tree or DAG.
- Propagate defect probabilities bottom-up.
- Define node-level inspection and disassembly choices.
- Compare final inspection and market return choices.
- Save node-level decisions and final expected profit or cost.

## Uncertainty Requirements

For q4-like subproblems, the system must:

- Use q1-derived confidence intervals or posterior intervals.
- Rerun q2/q3 under uncertainty scenarios.
- Mark stable and unstable strategies.
- Explain when recommendations are conditional.
- Avoid generic low/base/high sensitivity unless linked to statistical estimates.

## Internet Retrieval Requirements

When internet retrieval is enabled, the pack must ask Mimo2.5 for:

- method references for the detected model family.
- background context if the problem uses real-world terms.
- public data source candidates when the problem permits external data.
- citation candidates for paper references.

Each retrieval result must become an `EvidenceItem` with:

- source title.
- URL or source identifier.
- retrieval time.
- summary.
- relevance.
- credibility risk.
- recommended use.

The system must not cite internet content in final writing unless it is stored as an evidence item.

## Quality Gates

### Input Gate

Passes only if problem text exists, all required pages are extracted, table/figure extraction status is recorded, and warnings are visible to the user.

### Problem Gate

Passes only if all detected subproblems have type labels, dependencies, and expected outputs.

### Research Gate

Passes only if required external or local references are either retrieved or explicitly marked unnecessary.

### Model Gate

Passes only if every subproblem has variables, parameters, formulas, assumptions, algorithm, limitations, and conclusion mapping.

### Experiment Gate

Passes only if code runs, result files exist, result schemas match contracts, and parameter audit has no unexplained constants.

### Claim Gate

Passes only if every important conclusion has evidence from results, equations, source data, or references.

### Paper Gate

Passes only if required CUMCM sections exist, results are discussed, limitations are stated, references are present when used, and no placeholder text remains.

### Submission Gate

Passes only if no required quality gate is failed, stale, or unreviewed.

## Revision Policy

Review failures must route to responsible stages:

- Input extraction failure routes to `reconstruct_inputs`.
- Missing subproblem routes to `identify_subproblems`.
- Weak equations route to `plan_models`.
- Bad or non-running code routes to `implement_experiments`.
- Empty or implausible results route to `run_experiments`.
- Unsupported claims route to `build_claim_map`.
- Thin paper sections route to `write_sections`.

When an upstream stage is rerun, downstream artifacts are marked stale.

## UI Requirements

The Web UI should expose:

- current workflow stage.
- subproblem list.
- contracts for review.
- result tables and figures.
- claim map.
- review reports.
- revision tasks.
- approve, rewrite previous stage, and stop controls.

If the user selects rewrite for an earlier stage, all dependent later stages must be rerun before packaging.

## Storage Layout For CUMCM Runs

Recommended layout:

```text
contracts/
  problem_contract.json
  subproblems/
  models/
  experiments/
evidence/
equations/
code/
results/
figures/
claims/
sections/
reviews/
revisions/
package/
```

The pack may initially map this layout into the current `agent_app/output/runs/<run_id>/` directory, but the layout should be preserved logically.

## Test Strategy

Tests must include:

- PDF extraction and table reconstruction tests.
- Dynamic subproblem recognition tests with 1, 2, 3, and 4+ questions.
- B problem gold benchmark contract tests.
- B problem q1 sampling tests that reject trivial `n=1` accept outputs.
- B problem q2/q3 parameter audit tests.
- Claim-evidence gate tests.
- Review failure blocks package tests.
- Stale downstream artifact tests.
- Web event streaming tests for `revise_required`.

## Acceptance Criteria

The CUMCM v1 pack is accepted when:

1. B problem produces four subproblem contracts.
2. B problem produces four model contracts and four experiment contracts.
3. B problem code runs and writes q1-q4 result files.
4. q1 sampling plan passes statistical plausibility checks.
5. q2/q3 code contains no unexplained empirical constants.
6. q4 uncertainty derives from sampling intervals or posterior intervals.
7. Paper sections are generated separately and reference claim IDs.
8. Claim gate rejects unsupported conclusions.
9. Review failures block package generation.
10. A non-B CUMCM-style problem can still run through dynamic subproblem recognition and baseline contracts.

## Migration Notes

Current tools such as `ingest_inputs`, `analyze_problem`, `plan_model`, `run_experiment`, `draft_competition_paper`, `review_submission`, and `package_submission` can be retained as compatibility wrappers, but their internals should move toward contract-based services.

Current B problem deterministic logic should be moved behind a CUMCM template rather than embedded directly in a large generic tool file.

The existing three subagent review pattern should remain, but it should read structured contracts and claims, not only final Markdown files.

## Success Signal

The most important success signal is not that `paper.md` exists. The success signal is:

- the system identifies the real subproblems,
- produces executable experiments,
- generates supported claims,
- writes sections from those claims,
- and refuses to package until model, experiment, claim, paper, and submission gates pass.
