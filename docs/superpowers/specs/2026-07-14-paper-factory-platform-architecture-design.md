# Paper Factory Platform Architecture Design

## Purpose

This spec defines the long-term architecture for turning `agent_app` into a multi-workflow paper production platform. The platform must support CUMCM first, then MCM/ICM, graduation thesis workflows, and finally academic paper workflows. The design keeps the current DeepAgent direction but replaces demo-style generation with contract-driven workflow execution, evidence tracking, quality gates, and revision loops.

The platform is not a single "paper writing agent". It is a paper factory: each workflow produces traceable inputs, plans, experiments, claims, sections, reviews, and submission packages.

## Product Scope

The platform supports four workflow families:

1. CUMCM competition papers.
2. MCM/ICM competition papers.
3. Graduation thesis lifecycle workflows, including proposal, midterm defense, literature translation, experiments, final thesis, formatting, duplication-risk rewriting, and final submission.
4. Academic research paper workflows, including idea audit, literature gap analysis, experiment protocol, manuscript drafting, claim audit, venue adaptation, review response, and camera-ready packaging.

The first implementation target is CUMCM. B problem is a gold benchmark, not a hard-coded product boundary.

## Reference Projects

The architecture borrows patterns from mature open-source research-agent projects:

- Sakana AI Scientist v1: template-level contracts for experiments, plots, prompts, LaTeX writing, and reviewer feedback.
- Sakana AI Scientist v2: later-stage agentic tree search for exploring multiple experiment paths.
- STORM: pre-writing research, outline-first generation, and perspective-guided question asking.
- Open Deep Research: role-separated research, compression, writing, and final report workflows.
- PaperQA: citation-grounded scientific QA and claim support.

These are design references, not direct dependencies for v1.

## Model Responsibilities

Mimo2.5 is responsible for perception and discovery:

- PDF text extraction support.
- Image and table reconstruction.
- Internet-backed literature and data-source retrieval.
- Initial source credibility screening.
- Candidate citation and reference discovery.

DeepSeek V4 Pro is responsible for reasoning and production:

- Problem decomposition.
- Mathematical modeling.
- Algorithm and code generation.
- Experiment debugging.
- Result interpretation.
- Section-level paper writing.
- Review and revision planning.

The platform must not allow model responsibilities to blur silently. Each model call should declare a role, expected output schema, and allowed actions.

## Core Architecture

The platform consists of seven layers:

1. Input Layer: stores uploaded PDFs, images, tables, datasets, references, user notes, and chat instructions.
2. Understanding Layer: converts raw input into problem, thesis, or paper contracts.
3. Evidence Layer: retrieves and stores external sources, literature notes, source credibility metadata, and citation candidates.
4. Planning Layer: produces model, experiment, writing, and revision contracts.
5. Execution Layer: generates and runs code, tables, charts, analysis logs, and reproducible result artifacts.
6. Writing Layer: writes sections from claims and evidence, never from free-form memory alone.
7. Review-Revise Layer: runs quality gates, creates revision tasks, marks stale downstream artifacts, and reruns affected stages.

## Core Domain Objects

The platform should standardize these durable objects:

- `Project`: long-lived user project with type, title, owner notes, and workflow family.
- `WorkflowRun`: one execution attempt inside a project.
- `InputAsset`: uploaded or discovered file with extraction status.
- `EvidenceItem`: literature, web source, dataset source, or local reference.
- `ProblemContract`: task scope, subproblems, constraints, required outputs, and input dependencies.
- `ResearchPlan`: retrieval queries, source requirements, inclusion/exclusion criteria, and expected evidence outputs.
- `ModelContract`: variables, parameters, assumptions, objective functions, constraints, algorithms, and result requirements.
- `ExperimentContract`: executable plan, input files, output schemas, validation checks, and rerun conditions.
- `ResultArtifact`: CSV, JSON, figure, log, notebook, code, or compiled output.
- `Claim`: a paper conclusion linked to evidence, formulas, or result artifacts.
- `PaperSection`: one section draft with claim references and source references.
- `ReviewReport`: model, experiment, writing, claim, or submission review.
- `RevisionTask`: required fix with owner stage, stale scope, and rerun policy.
- `SubmissionPackage`: final allowed package after all required gates pass.

## Claim-Evidence Contract

Every workflow family must use claim-evidence tracking. A claim is not accepted unless it points to at least one valid support item.

Example shape:

```json
{
  "claim_id": "claim_q2_1",
  "workflow_family": "cumcm",
  "text": "For case 1, the optimal strategy is to skip part inspection, skip final inspection, and disassemble defective returns.",
  "evidence": [
    {
      "type": "result_file",
      "path": "results/table1_strategy_results.csv",
      "rows": ["case=1"]
    },
    {
      "type": "equation",
      "path": "equations/q2_expected_profit.md"
    }
  ],
  "status": "supported"
}
```

Unsupported claims must block writing or submission. Writers may phrase uncertainty or limitations, but they may not invent unsupported conclusions.

## Workflow Pack System

Workflow packs are pluggable packages under a common contract:

```text
workflow_packs/
  cumcm/
    workflow.yaml
    templates/
    prompts/
    rubrics/
    schemas/
    examples/
  mcm_icm/
  graduation_thesis/
  academic_paper/
```

Each pack defines:

- Supported project types.
- Required input assets.
- Agent roles.
- Workflow stages.
- Contract schemas.
- Quality gates.
- Section templates.
- Review rubrics.
- Submission package rules.

The core engine should not know the details of CUMCM or thesis writing. It should execute pack-provided stages and enforce shared safety and traceability rules.

## Common Workflow Lifecycle

All workflow packs use this lifecycle:

1. Create project.
2. Classify workflow family.
3. Ingest and extract input assets.
4. Build a contract.
5. Retrieve evidence and references.
6. Create a plan.
7. Ask user to confirm high-impact plans.
8. Execute experiments or drafting tasks.
9. Generate result artifacts.
10. Build claim map.
11. Write section by section.
12. Run quality gates.
13. Create revision tasks when gates fail.
14. Rerun affected stages and mark downstream outputs stale.
15. Package only after required gates pass.

## Quality Gates

The platform has shared gates:

- Input Gate: required inputs exist and extraction quality is sufficient.
- Research Gate: evidence is relevant, deduplicated, and credible enough for the workflow.
- Plan Gate: plan is scoped, executable, and tied to expected conclusions.
- Model or Method Gate: variables, assumptions, formulas, algorithms, and limitations are reviewable.
- Experiment Gate: code runs, outputs match schema, logs are saved, and unexplained parameters are rejected.
- Claim-Evidence Gate: every important conclusion is supported.
- Writing Gate: sections are complete, coherent, and style-appropriate for the workflow.
- Submission Gate: all required final artifacts exist and no blocking review remains.

Failed gates produce `RevisionTask` objects. Failed gates must set the run status to `partial` or `revise_required`, never `completed`.

## Staleness Rules

When an upstream artifact changes, downstream artifacts become stale:

- Input change stales all contracts, plans, experiments, claims, sections, reviews, and packages.
- Problem contract change stales model plans, experiments, claims, sections, reviews, and packages.
- Model contract change stales experiments, result analysis, claims, sections, reviews, and packages.
- Experiment result change stales claims, result sections, reviews, and packages.
- Claim change stales affected sections, reviews, and packages.
- Paper section change stales writing reviews and package.

The system must never package stale downstream artifacts.

## Human Review Gates

The system should expose major stage outputs for user review:

- Problem contract.
- Research plan.
- Model plan.
- Experiment plan.
- Main result tables and figures.
- Paper outline.
- Section drafts.
- Review reports.

If the user rewrites an upstream artifact, downstream artifacts must be marked stale and rerun before packaging.

## Storage Layout

Recommended run layout:

```text
agent_app/output/projects/<project_id>/
  project.json
  memory/
  assets/
  runs/<run_id>/
    run.json
    events.jsonl
    contracts/
    evidence/
    plans/
    code/
    results/
    figures/
    claims/
    sections/
    reviews/
    revisions/
    package/
```

The current `agent_app/output/runs/<run_id>/` can remain during migration, but the platform architecture should move toward project-scoped storage.

## Prompt Architecture

Prompts must be role-specific and schema-first:

- Input prompts return extraction metadata, not narrative guesses.
- Research prompts return source cards and query logs.
- Planner prompts return contracts.
- Programmer prompts return code plus parameter audit.
- Writer prompts return one section at a time and cite claim IDs.
- Reviewer prompts return structured findings and required fixes.

Free-form prose can exist only as a human-facing rendering of structured outputs.

## Safety And Reliability

The platform must enforce:

- No arbitrary writes outside run/project directories.
- No submission package when required gates fail.
- Code execution timeout and sandboxing.
- Network retrieval logs for Mimo-backed internet search.
- Source provenance for every external claim.
- API key diagnostics without leaking secrets.
- Reproducibility logs for generated code and experiments.

## Future Expansion

MCM/ICM adds English writing, summary sheet, citation style, and international contest structure.

Graduation thesis adds long-running project memory, advisor feedback tracking, staged deliverables, document formatting, translation, defense slides, and duplication-risk rewriting.

Academic paper workflows add literature gap analysis, experiment protocol, venue adaptation, cover letter, reviewer response, and camera-ready revision.

These expansions must reuse the same core contracts and gates.

## Success Criteria

The platform architecture is successful when:

1. Workflow packs can be added without changing core engine logic.
2. Every major output is traceable to inputs, evidence, contracts, or results.
3. Quality gates can block packaging and produce actionable revision tasks.
4. A project can evolve through multiple runs without losing prior decisions.
5. CUMCM v1 can be implemented as the first workflow pack using this architecture.

## Non-Goals For The First Implementation

- Do not implement all workflow packs at once.
- Do not add academic paper tree search in the first milestone.
- Do not build a general citation manager replacement.
- Do not promise final publication quality without human review.
- Do not hide failing quality gates behind polished prose.
