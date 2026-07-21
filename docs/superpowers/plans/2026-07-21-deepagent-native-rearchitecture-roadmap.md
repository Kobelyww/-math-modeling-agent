# DeepAgent-Native Paper Factory Delivery Roadmap

**Goal:** Replace the demo-style fixed paper workflow with the approved DeepAgent-native,
artifact-driven paper factory without breaking current API, Web, artifact, or package
contracts during migration.

**Source spec:**
`docs/superpowers/specs/2026-07-21-deepagent-native-paper-factory-design.md`

**Execution policy:** Implement directly on
`codex/deepagent-native-rearchitecture`. Do not invoke Superpowers-prefixed skills or
development subagents. Preserve unrelated dirty files and stage only paths owned by the
active task.

**Architecture:** Delivery uses six vertical release slices behind
`DEEPAGENT_NATIVE_RUNTIME`. Each slice leaves a testable system, keeps the legacy runner
available, and publishes no new default until the old/new benchmark gate passes. Native
DeepAgent instances choose cognitive actions; application services own durable state,
permissions, budgets, evidence, and completion decisions.

**Tech stack:** Python 3.13, DeepAgents 0.6.8, LangChain 1.3, LangGraph 1.2,
`langgraph-checkpoint-sqlite` 3.1, SQLite/WAL, FastAPI/SSE, dataclasses, pytest.

---

## Delivery Invariants

These rules apply to every phase:

1. The legacy path remains selectable until Phase 6 acceptance.
2. No application enum, stage index, or fallback sequence selects DeepAgent's next
   domain action.
3. `run.json` remains a compatibility projection; runtime events and artifact versions
   are the new business authority.
4. A tool completion cannot complete the run.
5. External side effects, budget expansion, protected evaluator changes, and publication
   remain interrupt-protected.
6. Existing required artifact names and public routes remain stable during migration.
7. Every phase starts with failing tests, ends with focused and regression tests, and is
   committed independently.
8. Runtime databases, checkpoints, prompts, secrets, and private reasoning never enter a
   submission package.

## Dependency Order

```text
Phase 1 Runtime Foundation
  -> Phase 2 Native Agent And Delegation
    -> Phase 3 Goal Graph And Experiment Optimization
      -> Phase 4 Evidence, Review, And Paper Revision
        -> Phase 5 Streaming Web And Steering
          -> Phase 6 Benchmark, Knowledge Gate, And Cutover
```

No downstream phase starts while the preceding phase has unresolved blocking tests or
compatibility regressions.

## Phase 1: Durable Runtime Foundation

**Detailed plan:**
`docs/superpowers/plans/2026-07-21-deepagent-native-runtime-foundation.md`

Build:

- runtime contracts and native runtime statuses;
- run-scoped SQLite/WAL database and schema migrations;
- append-only event ledger and status projection;
- versioned artifact graph and dependency invalidation;
- budget ledger, steering inbox, and context manifest;
- tool contracts, policy preflight, idempotent execution records, and reconciliation;
- deterministic completion supervisor and no-progress detection;
- standalone run bootstrap and recovery projection without touching the legacy runner.

Acceptance:

- a run can be reconstructed without conversation checkpoints;
- duplicate idempotency keys do not repeat committed work;
- changed artifacts invalidate all transitive descendants;
- an early completion proposal is rejected with conditions, not a selected repair tool;
- all current runner, middleware, stream, and run-store regression tests remain green.

## Phase 2: Native DeepAgent And Delegation

Plan file to author at the Phase 1 gate:
`docs/superpowers/plans/2026-07-21-deepagent-native-agent-delegation.md`

Build:

- run-scoped strict SQLite checkpointer and LangGraph store lifecycle;
- `CompositeBackend`, filesystem permissions, Skills, memory, interrupts, and structured
  response composition;
- goal-and-invariants coordinator prompt with no fixed tool sequence;
- continuation driver that resumes the same checkpoint after rejected completion;
- declarative one-level subagents with `TaskEnvelope` and structured results;
- capability routing for Mimo visual/search work and DeepSeek reasoning/writing work;
- `RunStore`, runner status-transition, and internal-artifact filtering integration;
- native runtime feature-flag selection in `CompetitionPaperRunner`.

Acceptance:

- captured `create_deep_agent` arguments include every approved native capability;
- two independent fake subproblems delegate concurrently in isolated contexts;
- subagents cannot receive the native delegation tool;
- a fake early return is continued on the same `thread_id`;
- legacy mode remains byte-compatible for public outputs.

## Phase 3: Goal Graph And AutoSOTA Experiment Loop

Plan file to author at the Phase 2 gate:
`docs/superpowers/plans/2026-07-21-deepagent-goal-graph-autosota.md`

Build:

- arbitrary-count `GoalGraph` extraction and dependency validation;
- artifact-precondition registry replacing stage gating;
- model candidate and optimization objective contracts;
- isolated trial workspaces, protected evaluator digests, and experiment ledger;
- primary, secondary, guardrail, and feasibility metric decisions;
- promotion, rejection, budget exhaustion, stagnation, and restart behavior;
- problem-type-neutral regression fixtures beyond the 2024 B problem.

Acceptance:

- no code path assumes four subproblems, a year, or a problem letter;
- independent branches can run concurrently while dependencies wait;
- failed, regressing, or tampered trials cannot become the best version;
- interruption resumes from committed trials without rerunning them;
- every planned experiment links to a supported, limited, or falsified paper claim.

## Phase 4: Evidence, Review, And Paper Revision

Plan file to author at the Phase 3 gate:
`docs/superpowers/plans/2026-07-21-deepagent-review-paper-revision.md`

Build:

- criterion-level rubric, evidence locator, verdict, arbitration, and revision contracts;
- local numeric equality and tolerance checks against frozen result cells;
- external proposition and citation verification;
- isolated model, experiment, paper, and fact-check reviewers;
- dependency-aware revision tasks and bounded re-review;
- section-scoped paper writing with early front matter, per-subproblem derivation,
  symbol-table backfill, and abstract/conclusion last;
- deterministic package gate over current artifact versions.

Acceptance:

- reviewers cannot write artifacts they review;
- deterministic failures cannot be overruled by an LLM reviewer;
- changed results invalidate claims, sections, reviews, and packages;
- review failures drive upstream model or experiment repair when required;
- every material paper number resolves to current-run evidence.

## Phase 5: Streaming Web And Conversation Steering

Plan file to author at the Phase 4 gate:
`docs/superpowers/plans/2026-07-21-deepagent-web-steering.md`

Build:

- committed event projection to replayable SSE with `Last-Event-ID`;
- action timeline, artifact versions, experiment ledger, and reviewer workspace;
- one conversation surface for pause, resume, cancel, ask, answer, and correction;
- steering consumption at native action boundaries;
- compatibility projection for existing stage events and DOM contracts;
- refresh, reconnect, duplicate-delivery, stale-view, and mobile layout tests.

Acceptance:

- reconnect replays missing events without duplicate state transitions;
- one tool completion never completes all UI stages;
- pause and correction affect the same run and checkpoint;
- hidden chain-of-thought is absent from events and logs;
- existing `/paper` and compatibility consumers continue to work.

## Phase 6: Benchmark, Knowledge Gate, And Cutover

Plan file to author at the Phase 5 gate:
`docs/superpowers/plans/2026-07-21-deepagent-benchmark-cutover.md`

Build:

- source usefulness admission in addition to existing rights approval;
- pinned-knowledge and no-RAG benchmark modes;
- unseen CUMCM suite across optimization, prediction, evaluation, statistics,
  simulation, and engineering/signal tasks;
- old/new quality, reliability, recovery, time, token, and cost comparison;
- audited default-runtime switch and rollback procedure;
- removal of the fixed nine-tool prompt, `CompetitionStageMiddleware` scheduling role,
  legacy action enum, and smoke coordinator only after the compatibility window.

Acceptance:

- the new runtime does not regress workflow completion on the benchmark suite;
- evidence-grounded paper quality improves on the approved metrics;
- production knowledge publication remains an explicit audited action;
- rollback to the legacy runtime is tested before default cutover;
- obsolete scheduling code is removed only after no supported caller depends on it.

## Spec Coverage Matrix

| Spec area | Delivery phase |
| --- | --- |
| 6.5 native loop semantics | Phase 2, enforced by Phase 1 policy boundaries |
| 6.6 durable loop state | Phase 1 |
| 6.7 tool lifecycle and policy hooks | Phase 1, wired in Phase 2 |
| 6.8 completion and continuation | Phase 1, wired in Phase 2 |
| 6.9 context and compaction | Phase 1 manifest, Phase 2 native context |
| 6.10 user steering | Phase 1 inbox, Phase 5 interaction |
| 7 backend and permissions | Phase 1 policy, Phase 2 backend composition |
| 8 subagent topology and model routing | Phase 2 |
| 9 artifact readiness and goal graph | Phases 1 and 3 |
| 10 AutoSOTA experiment optimization | Phase 3 |
| 11 paper construction and revision | Phase 4 |
| 12 review, fact checking, and arbitration | Phase 4 |
| 13 core contracts | Phases 1 through 4 by ownership |
| 14 native Skill platform | Phase 2, governance audit in Phase 6 |
| 15 knowledge usefulness gate | Phase 6 |
| 16 Web and conversation experience | Phase 5 |
| 17 modes and human control | Phases 2 and 5 |
| 18 failure handling | Phase 1 foundation plus phase-local tests |
| 19 observability and audit | Phases 1 and 5 |
| 20 compatibility and migration | All phases, final removal in Phase 6 |
| 21 testing and 22 acceptance | Every phase, aggregate gate in Phase 6 |

## Release Gates

At every phase boundary run:

```bash
python -m pytest agent_app/tests -q
python -m py_compile <all Python files changed in the phase>
git diff --check
git status --short
```

Before Phase 6 default cutover also run the approved end-to-end B-problem regression and
the unseen multi-type benchmark suite. Record commands, model IDs, input digests,
knowledge index versions, costs, and artifact digests in the benchmark report.
