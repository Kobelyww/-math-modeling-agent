# License Review Batch Approval Design

## Context

Task 14 has 30 human-approved candidates. The current `record_review()` path performs
multiple complete candidate and lifecycle log scans for every review: candidate lookup,
state lookup, and state transition. With the current 6.3 MB immutable candidate log, a
30-item approval run requires roughly 90 full validations and is impractical.

The user issued one explicit bulk approval instruction. Official evidence has been
captured and checked for every selected candidate. This change optimizes persistence; it
does not weaken the evidence policy or create automatic approval authority.

## Decision

Add three batch APIs while retaining existing single-item compatibility:

- `CandidateStore.inspect_many(candidate_ids)` reads and validates the candidate and
  lifecycle logs once, then returns each candidate and current state in input order.
- `CandidateStore.transition_many(items)` validates the store once, applies ordered
  lifecycle transitions under one discovery lock, and rolls back the complete lifecycle
  batch on failure. `transition()` delegates to the one-item batch path.
- `LicenseReviewService.record_approvals(requests)` accepts only full-text approval
  requests. It prevalidates all candidates, human reviewer IDs, evidence hashes,
  evidence authorities, licenses, uses, attribution, expiry, and states before mutation.
  It reads the review log once, persists evidence and review events under one license
  lock, and reconciles lifecycle state through `transition_many()`.

The request object contains the same fields as `record_review()` except the decision is
fixed to `approved_full_text_candidate`. Duplicate candidate IDs in one batch are
rejected. Results preserve input order.

## Transaction And Recovery

- The lock order remains license store, then candidate store, matching the existing
  reconciliation path.
- The review log and lifecycle log are snapshotted once before their respective writes.
- Evidence files are content-addressed. The batch tracks which evidence hashes existed
  before the transaction and removes only files created by the failed batch.
- Any validation, evidence write, review append, or lifecycle transition failure restores
  the review log, lifecycle log, and newly created evidence files to their pre-batch state.
- Exact replay returns the existing reviews and repairs a missing lifecycle reconciliation
  without appending duplicate review events.
- A conflicting replay creates no mutations and reports the offending candidate.

Cross-process behavior remains protected by the existing POSIX file locks. No mutable
candidate cache survives a lock boundary.

## Runtime Application

The Task 14 batch uses the existing shortlist SHA-256 as its scope binding. Each request
references a local UTF-8 evidence file and records the real reviewer ID,
`reviewer_haobo`. Twenty-eight entries use `cc_by_4_0`. The CC BY 1.0 and CC BY 2.0
entries use `equivalent_open` with `attribution_required=true`; neither is relabelled as
CC BY 4.0.

The audit reason states that the human supplied a bulk approval instruction and that the
official evidence was verified automatically. It does not claim item-by-item human
inspection.

## Verification

Tests must prove:

- ordered 30-style batch approval with one candidate-store inspection and one lifecycle
  transition transaction;
- exact replay idempotency;
- duplicate candidate rejection before mutation;
- rollback after a late evidence, review-log, or lifecycle failure;
- attribution retention for `equivalent_open` CC BY 1.0/2.0 evidence;
- single-item `record_review()` and `transition()` compatibility;
- unchanged rejection, metadata-only, withdrawal, and approval-guard behavior.

After targeted tests pass, run the batch first against a copied runtime root, then against
the real `agent_app/knowledge_base`. Verify exactly 30 current approvals, license counts
`28 cc_by_4_0 / 2 equivalent_open`, all attribution statuses captured, and an unchanged or
absent production index pointer.

## Non-Goals

- Do not batch rejection, metadata-only decisions, withdrawal, or source removal.
- Do not download, extract, distill, snapshot, build an index, or publish production state.
- Do not migrate JSONL stores to a database in this change.
- Do not infer human approval from model output or evidence checks.
