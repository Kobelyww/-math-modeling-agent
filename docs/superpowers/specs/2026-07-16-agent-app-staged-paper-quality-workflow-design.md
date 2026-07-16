# Agent App Staged Paper Quality Workflow Design

Date: 2026-07-16

## Goal

Upgrade the math-modeling paper factory from a traceable baseline generator into a staged writing and solving workflow that can produce a reviewable competition-paper draft with real modeling derivation, algorithms, and result interpretation.

The key product change is that paper writing must not happen as a single final pass. The system should first draft the stable front matter from the problem statement, then solve each subproblem with its own derivation and algorithm, then fill the symbol table and final result sections from the actual subproblem artifacts.

## Problem

The current generic CUMCM path can run end to end, but the generated paper remains thin:

- `solve.py` may write baseline result rows without real mathematical solving.
- `paper.md` can pass gates while only summarizing workflow structure.
- the symbol section is written before symbols are known from derivations.
- model, experiment, and paper reviews can pass while only offering optional advice.
- packaging may succeed before the output is a credible math-modeling paper.

This is a workflow-ordering problem and a quality-gate problem. The product needs stronger intermediate artifacts and gates that treat missing derivation, algorithm, symbols, and result interpretation as blocking defects.

## Confirmed Direction

The paper should be generated in staged passes:

1. Write front-matter sections before subproblem solving.
2. Analyze and solve each subproblem independently.
3. Collect symbols discovered during subproblem derivation.
4. Fill the symbol table after subproblem analysis.
5. Rewrite model, algorithm, result, sensitivity, and evaluation sections from solved artifacts.
6. Write the abstract last.
7. Block packaging when any stage only produces placeholders or baseline summaries.

## Target Workflow

```text
PDF / text input
  -> problem package and contracts
  -> front-matter drafting
       title
       problem background
       problem restatement
       initial problem analysis
       preliminary assumptions
  -> subproblem loop
       subproblem analysis
       variable and parameter extraction
       model derivation
       objective and constraint construction
       algorithm plan
       executable solver
       result table
       result interpretation
       symbol_delta.json
       claim_delta.json
  -> symbol aggregation
       symbol_table.json
       paper section: symbols
  -> paper backfill and rewrite
       model building
       solution and algorithm
       result analysis
       sensitivity
       model evaluation
       appendix
  -> abstract and final synthesis
  -> model / experiment / paper reviews
  -> package only if all quality gates pass
```

## Section Timing

### Early Sections

These sections are drafted before solving:

- title
- problem background
- problem restatement
- initial problem analysis
- preliminary assumptions

They may use only the problem statement, extracted tables, figures, and structured problem contract. They must not invent final results.

### Deferred Sections

These sections are generated after subproblem solving:

- symbol table
- model derivation and solving
- algorithm description
- result analysis
- sensitivity and robustness
- model evaluation
- appendix

They must cite subproblem artifacts, result files, and claim IDs.

### Last Section

The abstract is generated last because it summarizes final methods, algorithms, and results.

## New Artifacts

### Paper Plan

`paper_outline.json`

Required fields:

- `title`
- `problem_background_summary`
- `subproblem_ids`
- `section_order`
- `early_sections`
- `deferred_sections`
- `abstract_policy`

### Early Drafts

```text
paper/pre_sections/
  00_title.md
  01_problem_background.md
  02_problem_restatement.md
  03_problem_analysis.md
  04_preliminary_assumptions.md
```

### Subproblem Artifacts

Each subproblem gets an isolated workspace:

```text
subproblems/qN/
  analysis.md
  model_derivation.md
  algorithm.md
  solver.py
  result.csv
  result_interpretation.md
  symbol_delta.json
  claim_delta.json
```

`model_derivation.md` must include:

- decision variables
- parameters and parameter sources
- assumptions specific to the subproblem
- equations or objective functions
- constraints
- solving logic
- relationship to paper conclusion

`algorithm.md` must include:

- algorithm name or strategy
- input schema
- output schema
- step-by-step pseudocode
- complexity or search-space note when relevant
- failure or fallback conditions

`result_interpretation.md` must include:

- direct answer to the subproblem
- result table references
- why the chosen action or estimate follows from the model
- limitations and sensitivity notes
- claim IDs supported by the result

### Symbol Aggregation

`symbol_table.json`

Required fields per symbol:

- `symbol`
- `meaning`
- `unit`
- `source_subproblem_id`
- `first_used_in`
- `definition_artifact`

The final symbol section must be generated from `symbol_table.json`, not from a generic template.

### Final Sections

```text
paper/sections/
  00_title.md
  01_abstract.md
  02_keywords.md
  03_problem_background.md
  04_problem_restatement.md
  05_problem_analysis.md
  06_assumptions.md
  07_symbols.md
  08_model_derivation.md
  09_algorithm_and_solution.md
  10_results.md
  11_sensitivity.md
  12_model_evaluation.md
  13_references.md
  14_appendix.md
```

## Subproblem Solving Contract

Every detected subproblem must have a `SubproblemSolutionContract`:

- `subproblem_id`
- `question_text`
- `problem_type`
- `dependencies`
- `input_artifacts`
- `model_derivation_path`
- `algorithm_path`
- `solver_path`
- `result_path`
- `result_interpretation_path`
- `symbol_delta_path`
- `claim_delta_path`
- `status`

A subproblem is not complete until all required paths exist and pass quality checks.

## Quality Gates

### Model Gate

Reject when:

- derivation is missing variables, parameters, objective, constraints, or assumptions.
- formulas are absent for optimization, statistics, sampling, prediction, or evaluation subproblems.
- arbitrary constants appear without parameter source or sensitivity label.
- the derivation does not explain how it supports a paper conclusion.

### Algorithm Gate

Reject when:

- algorithm steps are missing.
- solver input or output schema is unspecified.
- generated code does not read the relevant contract, table, or data artifact.
- result files only contain generic baseline status without decision variables, estimates, objective values, or diagnostics.

### Symbol Gate

Reject when:

- final paper uses symbols missing from `symbol_table.json`.
- symbol table includes symbols not used in any derivation or result section.
- a symbol lacks meaning, unit, source subproblem, or definition artifact.

### Paper Gate

Reject when:

- paper is below a configured minimum length for competition drafts.
- any required final section is missing or thin.
- result analysis only says a result file exists without interpreting the result.
- abstract is generated before result sections.
- final paper contains internal workflow names or baseline-only language.

### Review Gate

The model, experiment, and paper reviewers must convert serious advice into blocking fixes. Suggestions such as "should include objective values" are not optional when the current artifacts lack objective values.

## Web UX Requirements

The paper page should expose the staged process:

- front-matter draft created.
- each subproblem analysis started/completed.
- model derivation artifact link.
- algorithm artifact link.
- result artifact link.
- symbol table updated.
- final sections backfilled.
- abstract generated last.
- quality gates passed/failed.

Users should be able to inspect early sections before solving, and inspect each subproblem package before final paper synthesis.

## Testing Strategy

Unit tests:

- early-section generation runs before subproblem solving.
- abstract is generated after result sections.
- symbol table is built from `symbol_delta.json`.
- symbol gate rejects missing or unused symbols.
- model gate rejects derivation without equations or constraints.
- algorithm gate rejects baseline-only result rows.
- paper gate rejects short papers and baseline-only wording.

Integration tests:

- a four-subproblem CUMCM prompt produces four subproblem folders.
- each subproblem folder contains derivation, algorithm, solver, result, interpretation, symbols, and claims.
- final symbols section is generated from `symbol_table.json`.
- final paper contains derivation, algorithm, and result interpretation sections.
- package submission is blocked when any subproblem solution contract is incomplete.

Manual acceptance:

- run the provided B problem PDF.
- confirm q1-q4 each produce a readable derivation, algorithm, result table, and interpretation.
- confirm final `paper.md` reads like a math-modeling draft, not a workflow summary.
- confirm reviewers fail a baseline-only run.

## Implementation Phases

### Phase 1: Artifact Contracts And Gates

Add the staged paper and subproblem solution domain contracts. Add gates for derivation, algorithm, symbol, and baseline-only results.

### Phase 2: Early Paper Drafting

Generate front-matter sections before subproblem solving. Do not generate abstract yet.

### Phase 3: Subproblem Solution Packages

For every detected subproblem, create isolated derivation, algorithm, solver, result, interpretation, symbol, and claim artifacts.

### Phase 4: Symbol Aggregation And Final Section Backfill

Build `symbol_table.json`, fill the symbol section, and rewrite model/result/evaluation sections from solved artifacts.

### Phase 5: Review And Packaging Enforcement

Make reviewers and package submission fail on baseline-only output, missing derivations, weak algorithms, missing symbols, or thin paper sections.

## Acceptance Criteria

The change is accepted when:

1. A production CUMCM run no longer packages a baseline-only paper.
2. Every subproblem has a complete solution package.
3. Symbol explanation is generated after subproblem derivations and matches used symbols.
4. Final paper includes concrete derivations, algorithm descriptions, result tables, and result interpretation.
5. The abstract is generated last.
6. Quality gates reject thin or workflow-summary papers.
7. B problem PDF run is blocked until q1-q4 have real derivation, algorithm, and result interpretation artifacts.
8. Full `agent_app/tests` passes.

## Spec Self-Review

- Placeholder scan: no TBD or open placeholder remains.
- Internal consistency: section timing, artifacts, gates, and acceptance criteria all follow the same staged workflow.
- Scope check: this is scoped to CUMCM paper quality workflow and does not add MCM/ICM, thesis, or academic-paper workflows.
- Ambiguity check: baseline-only output is explicitly disallowed by algorithm, paper, review, and package gates.
