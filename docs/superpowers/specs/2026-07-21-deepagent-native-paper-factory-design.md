# DeepAgent-Native Mathematical Modeling Paper Factory Design

**Date:** 2026-07-21
**Status:** Approved direction, pending written-spec review
**Branch:** `codex/deepagent-native-rearchitecture`
**Target:** `agent_app`

## 1. Decision Summary

Rebuild the mathematical-modeling paper workflow around DeepAgents 0.6.8 as the
cognitive orchestration runtime. DeepAgent owns planning, todo management, contextual
file work, skill discovery, delegation, and conversational steering. Application code
owns the non-negotiable control plane: permissions, artifact contracts, experiment
budgets, evidence integrity, durable audit records, idempotent writes, and final release
gates.

The design intentionally does not recreate a LangGraph-style fixed workflow around
DeepAgent. Readiness is artifact-driven. The main agent may choose and parallelize work
as long as every tool's preconditions and permissions are satisfied.

The cognitive loop adapts the publicly documented Claude Code pattern of gathering
context, taking action, verifying results, and repeating while accepting user steering at
any point. DeepAgent's native agent loop is the only component that chooses the next
cognitive action. Application code may reject an unsafe action or an unsupported claim of
completion, but it does not select the next tool or recreate a second workflow scheduler.

The AutoSOTA-inspired optimization loop applies only to models, algorithms, and
experiments. Paper writing uses a separate evidence-constrained review and revision
loop, preventing the generator from gaming a paper score instead of improving the
underlying solution.

## 2. Current Problems

### 2.1 DeepAgent is used as a fixed tool runner

The coordinator prompt prescribes nine tools in one sequence, while
`CompetitionStageMiddleware` exposes only the tools associated with the current stage.
This suppresses the behaviors DeepAgent is designed to provide:

- autonomous decomposition through `write_todos`;
- isolated delegation through the native `task` tool;
- concurrent subagent work;
- native filesystem context and message offloading;
- layered Agent Skills;
- persistent memory and checkpoints;
- tool-level human interrupts;
- structured subagent responses.

### 2.2 The three reviewers are not independent agents

The current model, experiment, and paper reviews are deterministic Python checks that
write three Markdown files. They do not invoke independent agents, use isolated context,
produce criterion-level evidence, expose confidence, or resolve disagreements.

### 2.3 Quality reports are too shallow

`QualityReport` only stores a gate name, pass flag, score, findings, fixes, and optional
improvements. It cannot represent:

- rubric version and digest;
- criterion-level scores;
- evidence locators;
- reviewer identity and model;
- confidence and uncertainty;
- disagreement and arbitration;
- review rounds and supersession;
- affected artifacts and invalidation scope.

### 2.4 Claim validation checks existence, not support

A result file and non-empty locator currently make a claim appear supported. The system
does not prove that a cited row, column, figure, formula, or source actually entails the
claim or that the number in the paper matches the underlying result.

### 2.5 Skills are hard-coded and weakly governed

The current Python registry embeds large prompt fragments and uses keyword overlap.
Skills do not have consistently enforced versions, content hashes, source provenance,
licenses, tool permissions, environment requirements, compatibility ranges, or trust
levels.

### 2.6 Review failure stops instead of improving the run

When review fails, the run becomes partial and packaging stops. There is no structured
revision plan, dependency invalidation, targeted rerun, score trajectory, or bounded
retry loop.

### 2.7 Corpus legality and corpus usefulness are conflated

An open license permits processing but does not make a source useful for CUMCM. The
current first 30-source shortlist satisfies the category allocation but contains only
two Chinese sources and many generic domain papers. A relevance and instructional-value
gate is required before acquisition and indexing.

### 2.8 The legacy agent loop is still a demo state machine

The older `agent_app.agent_loop` path restricts the coordinator to a fixed action enum,
keeps only the latest text output per role, falls back to a mostly fixed sequence, and
stops after a small global step count. It has no authoritative artifact graph, durable
tool transaction protocol, content-aware completion gate, or crash-safe continuation.
Renaming this mechanism an agent loop does not make it a production agent harness.

## 3. Goals

1. Use DeepAgent's native planning, delegation, skills, memory, filesystem, permissions,
   interrupts, structured output, checkpointer, and store capabilities.
2. Produce a genuinely autonomous workflow without allowing agents to bypass evidence,
   security, budget, or publication invariants.
3. Run a budgeted AutoSOTA-style inner loop for each model/experiment branch.
4. Run independent model, experiment, paper, and fact-check reviews against structured
   rubrics and bounded evidence packets.
5. Convert review findings into executable revision work with dependency-aware
   invalidation and bounded re-review.
6. Make every material paper claim traceable to current-run evidence or a verified
   external source.
7. Replace the hard-coded skill catalog with native Agent Skills plus license and trust
   governance.
8. Stream observable work, artifacts, review evidence, and steering controls to Web
   without exposing private chain-of-thought.
9. Preserve existing public routes and core artifact paths during migration.
10. Remain generic across CUMCM questions; no year- or question-letter production
    branch is permitted.
11. Use one native cognitive loop with durable continuation, verification-driven stopping,
    and user steering instead of a fixed action enum or global stage index.

## 4. Non-Goals

- Exposing model chain-of-thought or hidden reasoning tokens.
- Copying the custom-licensed CUMCM review Skill or other restricted prompt text.
- Optimizing paper prose inside the AutoSOTA metric loop.
- Automatically publishing a pilot knowledge index as production current.
- Requiring a distributed microservice deployment for the first release.
- Replacing deterministic validators with LLM judgments.
- Treating the 2024 B problem as a universal problem template.
- Copying leaked or proprietary Claude Code source, system prompts, or internal material.
- Allowing recursive subagent delegation in the first production release.

## 5. Architectural Model

The system has three planes.

### 5.1 Cognitive orchestration plane

DeepAgent performs:

- task decomposition and todo maintenance;
- selection and parallel dispatch of subagents;
- skill discovery and progressive loading;
- reading and writing scoped workspace artifacts;
- interpreting tool results and review feedback;
- deciding which eligible action to take next;
- conversational ask, pause, resume, and steer behavior.

### 5.2 Trusted execution plane

Application services perform:

- input reconstruction and problem-contract persistence;
- safe code execution and experiment collection;
- objective and metric evaluation;
- result freezing and artifact hashing;
- claim extraction and evidence resolution;
- deterministic paper and submission validation;
- knowledge retrieval and source provenance;
- package construction.

Agents may request these operations but cannot redefine their validation logic.

### 5.3 Governance control plane

Middleware and durable services enforce:

- filesystem and tool permissions;
- protected paths and anti-tampering digests;
- stage-independent artifact preconditions;
- per-run time, token, iteration, and compute budgets;
- idempotency, leases, retries, and recovery;
- immutable audit events;
- human interrupts for configured high-risk actions;
- final read-only verification.

## 6. DeepAgent Runtime Composition

`create_competition_paper_agent` will be rebuilt around the complete native API:

```python
create_deep_agent(
    model=coordinator_model,
    tools=domain_tools,
    system_prompt=goal_and_invariants_prompt,
    middleware=policy_middleware,
    subagents=subagent_specs,
    skills=skill_sources,
    memory=memory_sources,
    permissions=filesystem_permissions,
    backend=composite_backend,
    interrupt_on=interrupt_policy,
    response_format=CoordinatorResult,
    checkpointer=checkpointer,
    store=store,
)
```

The coordinator prompt describes the objective, available capabilities, artifact
contracts, and invariants. It does not prescribe a fixed sequence of tool calls.

### 6.1 Native todo planning

The main agent maintains the active decomposition with `write_todos`. Todo entries are
observability data, not the source of truth for completed domain work. Completion still
requires the corresponding signed artifact or service record.

### 6.2 Native delegation

The main agent uses `task` to launch isolated subagents. Parallel delegation is expected
for independent subproblems, literature searches, candidate methods, and final reviews.
Subagents return structured final reports; their private transcripts are not copied into
the parent context.

### 6.3 Native skills and memory

`SkillsMiddleware` loads only catalog metadata into standing context and progressively
loads selected `SKILL.md` files. `MemoryMiddleware` supplies stable project rules and
approved reusable lessons. Run-specific facts remain artifacts, not memory.

### 6.4 Native checkpoints and store

The checkpointer persists DeepAgent conversation and control state by run/thread ID. The
store persists approved cross-run memories and user preferences. Domain artifacts and
the experiment ledger remain canonical business state; checkpoint state must not be the
only copy of a result.

### 6.5 Claude-Code-inspired native loop semantics

The design adapts behavior described in Anthropic's public Claude Code documentation,
not leaked implementation material. The relevant behavior is a blended loop:

1. gather only the context needed for the current decision;
2. take one or more actions through tools or isolated subagents;
3. verify the observed result against executable or inspectable criteria;
4. use each observation to choose the next action;
5. accept user interruption or steering between actions;
6. stop only when completion can be demonstrated.

These are behavioral phases, not workflow states. A single DeepAgent turn may move among
them repeatedly and may issue many tool calls. There is no replacement
`AgentLoopDecision` action enum and no outer application loop that chooses a domain tool
for the model. The application wraps native turn, tool, checkpoint, and stop boundaries
only to enforce trusted invariants.

### 6.6 Durable loop state

The runtime persists seven state objects with distinct authority:

| Object | Purpose and authority |
| --- | --- |
| `GoalEnvelope` | current user objective, constraints, mode, and acceptance criteria |
| `TodoProjection` | DeepAgent's mutable plan for reasoning and display; never completion authority |
| `ArtifactGraph` | versioned artifacts, dependencies, validity, provenance, and evidence links |
| `EventLedger` | append-only record of material actions and state transitions |
| `BudgetLedger` | token, time, retrieval, experiment, and financial reservations and consumption |
| `SteeringInbox` | ordered user corrections, answers, pause, resume, and cancellation requests |
| `ContextManifest` | derived compact snapshot of goals, valid references, blockers, and active work |

DeepAgent checkpoints are authoritative for conversation and control continuation.
`ArtifactGraph` and `EventLedger` are authoritative for business facts. A run must be
reconstructible from the business ledgers even if a model checkpoint is unavailable;
missing conversation context may require a new turn, but it must not erase or invent a
completed experiment.

Run state is one of `running`, `waiting_user`, `waiting_external`,
`revision_required`, `partial`, `completed`, `cancelled`, or `failed`. Quality failure
does not masquerade as infrastructure failure, and an individual tool completion does not
complete the run.

### 6.7 Tool lifecycle and policy hooks

Every domain capability declares a `ToolContract` containing:

- input and output schemas;
- permitted roles and side-effect class;
- required artifact names and minimum versions;
- expected read and write scopes;
- idempotency, timeout, retry, and budget policies;
- expected artifact effects and deterministic verifier.

Before execution, policy middleware validates identity and schema, applies deny-before-
ask-before-allow permission precedence, checks artifact versions, reserves budget,
acquires write leases, and snapshots locally reversible file edits. Publishing, expanding
approved budgets, changing protected evaluators, or making uncheckpointable external
changes requires the configured interrupt.

After execution, middleware normalizes the structured result, verifies actual files and
exit state, settles budget, commits the event and artifact version atomically, releases
leases, invalidates stale descendants, and emits a bounded Web event. Tool failures use
machine-readable reasons such as `permission_denied`, `precondition_missing`,
`version_conflict`, `retryable_provider_error`, `execution_failed`,
`verification_failed`, and `budget_exhausted`. DeepAgent decides what to do with that
observation.

For filesystem artifacts, "atomic" means a prepare-and-commit protocol: write to a
run-scoped temporary path, verify and hash it, atomically rename it into the versioned
artifact path, then commit artifact metadata and its event in one ledger transaction. A
durable prepared record allows recovery to reconcile the narrow rename-to-ledger crash
window. Backends that cannot provide these guarantees must expose a reconciliation token
and may not report success until reconciliation completes.

Every material call carries an idempotency key, input digest, expected write set, and
causation identifier. Recovery after a committed success returns the existing result
instead of repeating an experiment, paid request, or package write.

### 6.8 Completion supervision and continuation

DeepAgent proposes completion through structured `CoordinatorResult`; it cannot directly
set the run to `completed`. A read-only completion supervisor checks that:

- the current `GoalEnvelope` and every recognized subproblem are covered;
- required artifacts exist, are current, and passed deterministic validation;
- executable work actually ran and produced frozen results;
- material claims resolve to content-valid evidence;
- blocking reviews and fact checks pass;
- the submission package references current artifact versions.

The `final_verifier` subagent may produce an independent `FinalVerification`, but the
supervisor is the deterministic policy aggregator that enforces its hard findings and all
non-LLM validators. The reviewer cannot approve around a failed deterministic gate.

When the proposal is premature, the supervisor emits a `ContinuationDirective` containing
only unsatisfied conditions, stale artifacts, available capabilities, and remaining
budget. It does not prescribe the next tool. DeepAgent resumes from the same checkpoint
and chooses the repair path.

Progress is measured by new or changed valid artifacts, resolved conditions, improved
verified metrics, or newly accepted evidence. Three consecutive continuation attempts
with the same failure signature and no such progress end in `revision_required`,
`waiting_user`, or `partial` according to the blocker. This bounds no-progress behavior
without imposing a demo-style global step limit.

### 6.9 Context management and compaction

Context is layered:

1. standing context contains the goal, invariants, permissions, and budget summary;
2. index context contains todos, artifact references, evidence references, and Skill
   descriptions;
3. on-demand context contains selected files, Skill bodies, experiment diagnostics, and
   section packets;
4. offloaded context contains large tables, complete logs, historical reviews, and
   intermediate derivations stored as artifacts.

Compaction must preserve the current objective and acceptance conditions, latest user
steering, current artifact versions, unresolved blockers, failed approaches and their
causes, remaining budgets, and active subagents. Older raw tool output is offloaded before
conversation summarization. Repeated immediate refilling after compaction is treated as
context thrashing and causes a bounded task split or user interrupt instead of an
infinite compact loop.

### 6.10 User steering

User messages are appended to `SteeringInbox` while work is running. Pause and cancel
requests attempt to stop a cancellable tool immediately; otherwise the tool may finish,
but its result is revalidated against the newest goal before being applied. Corrections
and answers are consumed before the next cognitive action. Resume continues the same
checkpoint and ledger rather than creating a new run.

## 7. Backend And Permission Layout

A `CompositeBackend` presents a virtual filesystem with explicit routes:

| Virtual path | Backend | Access |
| --- | --- | --- |
| `/workspace/` | run-scoped filesystem | role-dependent read/write |
| `/sandbox/` | isolated execution backend | experiment agent only |
| `/knowledge/` | published knowledge backend | read-only |
| `/skills/base/` | trusted built-in skills | read-only |
| `/skills/project/` | project skills | read-only to agents |
| `/memory/` | persistent store backend | governed read/write |
| `/audit/` | append-only audit service | tool-mediated only |

Permissions are least-privilege and role-specific. In particular:

- writers cannot modify frozen results, experiment code, or claim evidence;
- experiment agents cannot modify raw inputs, metric evaluators, test data, rubrics, or
  paper review reports;
- reviewers are read-only;
- fact checkers can use retrieval tools but cannot modify claims;
- only trusted services can freeze results, append authoritative audit events, or build
  a submission package.

## 8. Subagent Topology

Each declarative subagent has a narrow description, tools, skills, permissions, and
structured response schema.

| Subagent | Responsibility | Key output |
| --- | --- | --- |
| `problem_analyst` | reconstruct and decompose arbitrary questions | `ProblemContract` |
| `data_auditor` | inspect data quality, fields, units, and limitations | `DataAuditContract` |
| `research_scout` | retrieve methods and literature with source verification | `ResearchBundle` |
| `model_strategist` | propose alternatives, assumptions, equations, and minimum PoCs | `ModelCandidateSet` |
| `experiment_optimizer` | run the AutoSOTA-style inner loop | `ExperimentLedger` |
| `statistical_validator` | independently validate metrics and robustness | `ValidationVerdict` |
| `section_writer` | write one bounded section from an evidence packet | `SectionDraft` |
| `model_reviewer` | review mathematical formulation and method fit | `ReviewerVerdict` |
| `experiment_reviewer` | review reproducibility, metrics, and validation | `ReviewerVerdict` |
| `paper_reviewer` | review structure, exposition, figures, and competition fit | `ReviewerVerdict` |
| `fact_checker` | verify local claims and external citations | `FactCheckReport` |
| `review_arbiter` | resolve material reviewer disagreement | `ArbitrationVerdict` |
| `revision_integrator` | execute approved, bounded revision tasks | `RevisionResult` |
| `final_verifier` | perform immutable read-only acceptance | `FinalVerification` |

Subagents may use `RubricMiddleware` for bounded self-correction. Final reviewers and the
final verifier do not revise the artifacts they evaluate.

### 8.1 Task envelopes and result isolation

Every delegation uses a `TaskEnvelope` containing the task and parent run identifiers,
objective, input artifact references and version digest, expected output schema,
acceptance checks, allowed tools, read and write scopes, budget, and deadline. The
subagent receives this bounded packet instead of the full parent transcript.

A subagent result contains structured output, created or changed artifact references,
executed verification evidence, unresolved issues, confidence, and the input version
digest it actually used. If an upstream input changes before merge, the result is stale
and must be revalidated or rerun.

Independent subproblems, candidate methods, searches, and reviews may run concurrently.
Competing writers use isolated candidate paths; shared artifact writes require a lease
and optimistic version check. The coordinator receives only structured summaries and
artifact references, while full logs remain in the event ledger.

The first production release permits one delegation level:
`coordinator -> subagent`. Subagents do not receive the native delegation tool. This
prevents recursive task trees and unbounded budget multiplication while preserving
native isolated execution and parallelism.

### 8.2 Capability-based model routing

Model selection is policy-driven rather than encoded in the goal graph. The initial
policy routes multimodal PDF and table reconstruction, plus configured online literature
retrieval, to Mimo 2.5-class models. DeepSeek handles orchestration, mathematical
reasoning, experiment design, implementation, review, and section writing. Every call
records the selected capability, model, provider, and fallback reason without recording
credentials. Providers remain replaceable as long as they satisfy the same subagent and
tool contracts.

## 9. Artifact-Driven Readiness

There is no global fixed stage index. Every domain action declares prerequisites and
effects.

Examples:

- model candidate generation requires a valid `ProblemContract` and relevant data audit;
- an experiment trial requires an approved candidate, objective, budget reservation, and
  runnable sandbox;
- a section draft requires an evidence packet for that section;
- result claims require a frozen result set;
- packaging requires a satisfied final verification and no stale descendants.

The policy middleware rejects an ineligible operation with a machine-readable
precondition report. The main agent uses that report to schedule missing work.

### 9.1 Goal and subproblem graph

The problem analyst creates a `GoalGraph` from the actual statement. It records an
arbitrary number of subproblems, dependencies, required data, and acceptance conditions;
it never assumes four questions or routes on a year or problem letter.

Each subproblem normally evolves through versioned artifacts rather than a fixed stage:

```text
SubproblemContract
  -> ModelCandidateSet
  -> SelectedModel
  -> AlgorithmArtifact
  -> ExperimentLedger
  -> FrozenResultSet
  -> ClaimSet
  -> SectionDraft
  -> ReviewerVerdict
```

The coordinator may revisit context, models, code, experiments, or prose whenever an
observation warrants it. Independent branches may run in parallel; a dependent branch
waits only for the specific upstream artifact it needs. A changed frozen result
invalidates dependent claims, tables, sections, reviews, and packages automatically.

## 10. AutoSOTA-Inspired Experiment Optimization

### 10.1 Scope

The loop optimizes models, algorithms, preprocessing, parameters, and experiment design.
It never optimizes paper prose or changes evaluation rules.

### 10.2 Objective contract

`OptimizationObjective` records:

- primary metrics and direction;
- secondary metrics;
- guardrail metrics that may not regress beyond tolerance;
- feasibility and constraint checks;
- baseline values and provenance;
- statistical comparison policy;
- iteration, wall-time, token, and compute budgets.

There is no percentage-improvement success shortcut. The run stops when its approved
budget is exhausted, ideas are genuinely depleted, or stagnation policy is met. A large
primary-metric gain cannot compensate for a guardrail violation.

### 10.3 Iteration protocol

1. Establish and verify a runnable baseline.
2. Perform bounded method research and record whether web search was verified.
3. Add hypotheses to an `IdeaLibrary` with expected benefit, cost, risk, and required
   evidence.
4. Select one compatible idea or a justified small combination.
5. Create an isolated trial workspace from the current best version.
6. Apply a bounded patch and execute the protected evaluation command.
7. Record all metrics, diagnostics, code digest, artifact digest, and resource usage.
8. Promote the candidate only when the primary objective improves and all guardrails
   remain satisfied.
9. Record failed and regressing ideas so they are not repeated without new evidence.
10. Continue until the budget or stagnation condition ends the loop.

### 10.4 Anti-tampering

Protected raw data, test partitions, metric implementations, evaluation scripts, problem
contracts, and rubrics are hashed before each trial. Any protected-path change invalidates
the trial. The experiment agent has no direct write permission to these paths.

### 10.5 Resume and supervision

Every completed trial is durable. After process interruption, the optimizer reuses the
baseline, idea library, trial records, and best version. If the agent returns early while
budget remains and runnable ideas still exist, a bounded continuation supervisor resumes
the same checkpoint. Repeated no-progress returns trigger stagnation, not an infinite
loop.

### 10.6 User steering

Web and chat commands may pause the loop, inspect the ledger, ask about a decision, or
write one bounded instruction for the next iteration. Steering cannot override protected
paths, budgets, evidence requirements, or safety rules.

## 11. Paper Construction And Revision

Paper construction is evidence-first and section-scoped.

1. Problem background, problem restatement, and initial assumptions are drafted from the
   problem contract before result-dependent subproblem sections.
2. Each subproblem section is drafted after its result set is frozen.
3. Symbols are merged from subproblem deltas after actual use.
4. Result interpretation is expanded from claim-evidence links and validation reports.
5. Abstract and conclusion are written last.
6. Deterministic gates run before paid reviewers.
7. Independent reviewers and fact checking produce structured findings.
8. Findings become dependency-aware `RevisionTask` records.
9. Only affected artifacts are revised or rerun.
10. A read-only final verifier decides whether packaging is allowed.

The paper loop defaults to three review/revision rounds. It stops earlier when all
blocking criteria pass. It stops as partial when scores stagnate, evidence is unavailable,
or a required upstream experiment cannot be repaired within budget.

## 12. Review Architecture

### 12.1 Hybrid rubric

Every review combines:

- deterministic hard gates;
- competition-specific fixed criteria;
- paper-type criteria for traditional, data-analysis, machine-learning, and
  engineering/signal papers;
- task-specific criteria derived from current problem and experiment contracts;
- optional governed rubric cards from the pinned knowledge index.

The rubric is persisted with version, digest, sources, criterion weights, hard-veto
flags, and generation rationale.

### 12.2 Evidence packets

Reviewers receive bounded packets rather than the entire run. Packets contain only the
artifacts and locators needed by the assigned criteria. This improves isolation, lowers
context cost, and prevents one reviewer from anchoring on another review.

### 12.3 Independent verdicts

Model, experiment, and paper reviewers run as genuine DeepAgent subagents with isolated
contexts and structured `ReviewerVerdict` responses. Every failing criterion must include
an artifact locator and actionable gap. Unsupported praise is excluded from scoring.

### 12.4 Fact checking

The fact checker verifies:

- numeric equality or declared tolerance against local result cells;
- formulas and parameter sources against model artifacts;
- figure/table references against actual assets;
- external factual claims against verified sources;
- citations against title, author, year, URL/DOI, and cited proposition;
- claim strength against the available evidence boundary.

Local experiment claims cannot be justified by external literature. External sources
cannot replace current-run numerical evidence.

### 12.5 Aggregation and disagreement

Aggregation is criterion-aware, not a simple minimum or average. Hard-veto failures
block release. Material pass/fail conflict, high score spread, or low-confidence novelty
judgments trigger the read-only arbiter. The aggregate report preserves every individual
verdict and never erases disagreement.

## 13. Core Contracts

New or extended contracts include:

- `GoalEnvelope`
- `GoalGraph`
- `TodoProjection`
- `ArtifactGraph`
- `ArtifactVersion`
- `EventRecord`
- `BudgetLedger`
- `SteeringCommand`
- `ContextManifest`
- `ToolContract`
- `TaskEnvelope`
- `SubagentResult`
- `CoordinatorResult`
- `ContinuationDirective`
- `ArtifactPreconditionReport`
- `OptimizationObjective`
- `CandidateIdea`
- `ExperimentTrial`
- `MetricObservation`
- `ExperimentLedger`
- `FrozenResultSet`
- `RubricDefinition`
- `RubricCriterion`
- `EvidenceLocator`
- `ReviewFinding`
- `ReviewerVerdict`
- `ReviewPanelResult`
- `FactCheckReport`
- `ArbitrationVerdict`
- `RevisionTask`
- `RevisionRound`
- `FinalVerification`
- `SkillProvenance`

Existing `ProblemContract`, `ModelContract`, `ExperimentContract`, `Claim`,
`SubproblemSolutionContract`, and `StagedPaperManifest` are extended where compatible
instead of duplicated.

## 14. Skill Platform

The custom Python prompt registry is replaced gradually by native Agent Skills.

Each skill contains `SKILL.md` plus optional references, scripts, assets, and tests. YAML
frontmatter and a generated provenance record capture:

- name, description, and semantic version;
- source repository and commit;
- license and commercial-use status;
- content digest;
- DeepAgent and project compatibility;
- allowed tools and filesystem scope;
- required environment variables;
- dependencies and trust tier;
- security-scan status.

Skill sources are layered: trusted built-ins, project skills, and optional user skills.
Later sources may override names only when policy allows it; overrides are visible in the
run audit.

K-Dense MIT-licensed patterns may be adapted with attribution and pinned provenance.
DeepResearchEval's Apache-2.0 evaluation concepts may be independently integrated. The
custom-licensed CUMCM review Skill is not copied; CUMCM criteria are independently
implemented from official and user-provided rules.

## 15. Knowledge Quality Gate

Rights approval and content admission are separate decisions. Before acquisition or
indexing, candidate sources receive a relevance profile covering:

- CUMCM or mathematical-modeling relevance;
- language and Chinese-writing value;
- completeness of formulation and derivation;
- executable or reproducible experiment value;
- result interpretation and conclusion linkage;
- usefulness as a method, section, experiment, or review exemplar;
- duplication and source diversity.

The existing 30-source legal shortlist is not automatically accepted as the Milestone 30
knowledge snapshot. Low-value sources may remain legally approved but excluded from the
pilot index. Language and category deviations are explicit acceptance evidence.

## 16. Web And Conversation Experience

The Web stream projects committed ledger events, including:

- `goal.created` and `goal.updated`;
- `todo.updated`;
- `agent.turn_started` and `agent.turn_completed`;
- `subagent.started`, `subagent.completed`, and `subagent.failed`;
- `tool.started`, `tool.completed`, `tool.failed`, and `tool.denied`;
- `artifact.created`, `artifact.versioned`, and `artifact.invalidated`;
- experiment trial, guardrail, rejection, and promotion events;
- verification, review, fact-check, disagreement, and arbitration events;
- `continuation.requested` and context-compaction events;
- interrupt, pause, resume, cancel, ask, and steer events;
- final verification and package disposition.

Each event has a monotonic sequence ID, run and actor IDs, correlation and causation IDs,
timestamp, status, bounded decision summary, artifact and evidence references, and a
budget snapshot. SSE honors `Last-Event-ID`, so reconnecting clients replay missed events
without mutating state twice.

The UI centers on an action timeline, versioned artifacts, experiment ledger, reviewer
workspace, and one conversation surface for steering. It presents decision summaries,
evidence, tool outcomes, and audit history, but not hidden chain-of-thought. Completing a
tool completes only that action; run state changes only from committed business events and
completion supervision.

Existing routes and SSE event names remain available through a compatibility projector
during migration. The old stage board is a read-only compatibility view derived from the
artifact graph. It is never an input to scheduling and cannot mark the run complete.

## 17. Modes And Human Control

Two policies share the same runtime:

- `autopilot`: DeepAgent proceeds without routine review pauses. Security, legal,
  protected-path, budget-expansion, and publication interrupts remain mandatory.
- `manual`: selected model routes, expensive experiment budgets, low-confidence
  arbitration, and final release require user action.

Changing mode modifies interrupt policy, not the workflow graph.

## 18. Failure Handling

| Failure | Required behavior |
| --- | --- |
| subagent timeout | record failed task, retry within policy, then choose fallback or partial |
| malformed structured output | bounded schema repair; never coerce silently |
| model provider unavailable | preserve checkpoint and pending task; do not fabricate output |
| artifact precondition missing | return a machine-readable gap; let DeepAgent choose the repair |
| concurrent version conflict | reject the stale write and re-read the current artifact version |
| sandbox execution failure | persist stdout/stderr and failed trial; do not promote |
| committed tool result lost before response | return the existing idempotent result on recovery |
| artifact renamed before ledger commit | reconcile the prepared record and digest before retrying |
| event and artifact metadata commit failure | expose no success; roll back or reconcile before resume |
| protected path changed | invalidate trial and raise security finding |
| guardrail regression | reject promotion even if primary metric improves |
| reviewer disagreement | invoke arbiter or configured human interrupt |
| citation unavailable | narrow or remove claim; never mark verified |
| knowledge index unavailable | continue no-RAG where permitted and record degradation |
| stale upstream result | invalidate dependent claims, sections, reviews, and package |
| context overflow | rely on files, subagent isolation, and native summarization/offloading |
| repeated compaction refill | split the task or interrupt; do not compact indefinitely |
| steering arrives during a tool | cancel when safe or revalidate the result against the new goal |
| repeated no progress | terminate bounded loop with partial status and explicit blocker |

## 19. Observability And Audit

Every material action records:

- monotonic sequence, run, thread, task, subagent, and tool identifiers;
- correlation, causation, and idempotency identifiers;
- input contract and artifact digests;
- model/provider identifiers without secrets;
- selected skill names, versions, sources, and hashes;
- budget reservations and consumption;
- trial metrics and promotion decisions;
- reviewer rubric/version and evidence locators;
- revisions, invalidations, and final disposition.

Audit events are immutable and bounded. Prompts, third-party full text, credentials, and
private reasoning are not copied into general logs. The event ledger is the source for
run status and Web replay; UI acknowledgements and legacy stage projections are not.

## 20. Compatibility And Migration

Migration is incremental behind a runtime option such as
`deepagent_native_runtime=True`.

1. Characterize and freeze current public API, event, and artifact compatibility tests.
2. Add `GoalEnvelope`, artifact, event, budget, steering, and context contracts.
3. Add `ToolContract`, lifecycle hooks, idempotent execution, and completion supervision.
4. Compose the native DeepAgent runtime with backend, permissions, checkpoints, store,
   memory, Skills, structured output, and interrupts.
5. Register real declarative subagents, task envelopes, and one-level delegation policy.
6. Replace fixed stage middleware with artifact-precondition and invalidation policy.
7. Add the experiment optimizer and protected evaluation ledger.
8. Add independent review, fact checking, arbitration, and revision.
9. Project committed events into existing SSE/Web contracts and add the action-oriented
   views and steering controls.
10. Run old/new benchmark comparisons and make the native runtime default only after
    acceptance.
11. Remove the fixed nine-tool sequence and legacy action-enum loop after the
    compatibility window.

No unrelated dirty files are rewritten as part of the migration.

## 21. Testing Strategy

### 21.1 Unit tests

- contracts and serialization invariants;
- goal, artifact, event, budget, steering, and context state invariants;
- skill manifest and license policy;
- backend path routing and permissions;
- tool lifecycle, permission precedence, leases, and idempotency;
- artifact preconditions and invalidation;
- event replay and run-state reconstruction;
- completion checks, continuation directives, and no-progress signatures;
- compaction preservation and thrashing detection;
- optimization objective and guardrail decisions;
- protected-path digest checks;
- review aggregation and arbitration triggers;
- claim-to-evidence numerical matching.

### 21.2 DeepAgent runtime tests

- native subagent delegation is exercised, not mocked as Markdown generation;
- independent subagents receive isolated packets and permissions;
- native DeepAgent instances are the only cognitive next-action selectors; application
  code never selects the next domain action;
- subagents cannot recursively delegate in the first release;
- todo planning can choose different legal orders;
- SkillsMiddleware loads only selected skills;
- checkpoints resume interrupted agent and experiment work;
- an early completion proposal is rejected without the supervisor choosing the repair tool;
- interrupt policy differs correctly between autopilot and manual modes;
- RubricMiddleware revisions terminate within configured limits.

### 21.3 Integration tests

- arbitrary subproblem count and dependency topology;
- parallel independent subproblems;
- crash recovery before and after tool-result commit without duplicate side effects;
- concurrent write conflict and stale subagent result rejection;
- model trial failure, recovery, and best-version promotion;
- result changes invalidate downstream claims and sections;
- review failure generates targeted revision and re-review;
- pause, steer, resume, and cancel against the same run checkpoint;
- SSE replay from `Last-Event-ID` without duplicate state transitions;
- no-RAG fallback and pinned-RAG runs;
- existing API, route, SSE, artifact, and package compatibility.

### 21.4 Evaluation suite

The 2024 B problem remains a regression fixture, not a route heuristic. The suite also
uses unseen CUMCM problems across optimization, prediction, evaluation, statistics,
simulation, and engineering/signal types. Old and new runtimes are compared on:

- subproblem coverage;
- executable-code success;
- mathematical formulation completeness;
- metric and guardrail correctness;
- numeric claim consistency;
- evidence-grounded conclusion rate;
- section depth and result interpretation;
- reviewer calibration and disagreement handling;
- recovery after interruption;
- token, time, and experiment cost.

## 22. Acceptance Criteria

The redesign is accepted only when:

1. The production coordinator uses native DeepAgent subagents, Skills, memory, backend,
   permissions, checkpointer, store, interrupts, and structured output where applicable.
2. DeepAgent is the only cognitive next-action loop; no application action enum, fixed
   tool sequence, or global stage index selects the next domain action.
3. A completion supervisor rejects unsupported completion and returns conditions without
   prescribing the next tool.
4. `ArtifactGraph` and `EventLedger` can reconstruct business state independently of the
   conversation checkpoint.
5. At least two independent subproblems can be delegated concurrently, while first-release
   subagents cannot recursively delegate.
6. The model/experiment optimizer maintains a durable ledger, enforces budgets and
   guardrails, protects evaluators, resumes after interruption, and promotes only verified
   improvements.
7. Model, experiment, and paper reviewers are real isolated subagents.
8. Material claims resolve to evidence that is validated for content, not only existence.
9. Review disagreement is preserved and arbitrated.
10. Failed review can drive bounded, dependency-aware revision and re-review.
11. Skills are native, lazily loaded, versioned, licensed, hashed, and audited.
12. Web supports replayable streaming subagent, tool, artifact, experiment, review,
    revision, continuation, and steering events
    without exposing private reasoning.
13. A single tool completion cannot complete unrelated actions or the whole run.
14. Pause, correction, and resume operate on the same checkpoint and business ledger.
15. Existing public routes and required artifact paths remain compatible during migration.
16. Full tests and unseen-problem evaluations show no regression in workflow completion
    and measurable improvement in evidence-grounded paper quality.
17. Pilot knowledge sources pass both rights and usefulness gates before indexing.
18. Production index publication remains an explicit, audited action.

## 23. Implementation Sequence

The implementation plan should split this design into independently testable milestones:

1. Compatibility characterization and native-loop test harness.
2. Goal, artifact, event, budget, steering, and context ledgers.
3. Tool contracts, policy hooks, idempotency, and completion supervision.
4. Native DeepAgent composition, context management, and recovery.
5. Declarative subagents, task envelopes, native Skills, and model routing.
6. Artifact-driven mathematical-modeling goal graph.
7. AutoSOTA-inspired experiment optimization.
8. Independent review, fact checking, arbitration, and revision.
9. Web event projection, review workspace, conversation steering, and compatibility.
10. Knowledge relevance admission, benchmarks, native-default cutover, and obsolete-path
    removal.

## 24. Public Design Basis

The Claude Code influence in this design is limited to publicly documented behavior and
general agent-harness patterns. No leaked source or proprietary prompt is an input.

- [How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works): blended
  gather-context, take-action, verify-results loop; tool observations; steering; context
  compaction; checkpoints and permissions.
- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices):
  executable verification, deterministic stop checks, fresh-context review, and bounded
  unattended work.
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents): isolated context,
  scoped tools and permissions, structured delegation, and work isolation.
- [Checkpointing](https://code.claude.com/docs/en/checkpointing): reversible local edits,
  session resume, and the boundary between local snapshots and external side effects.
- [Permissions](https://code.claude.com/docs/en/permissions): deny-first rules, runtime
  hooks, workspace scope, and sandbox layering.
