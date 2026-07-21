# License Review Batch Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development`
> (recommended) or `executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Do not use Ampere or Superpowers-prefixed
> workers for this plan.

**Goal:** Add a bounded, rollback-safe batch approval path and use it to persist the 30
Task 14 approvals without repeated full-store scans or false license-version labels.

**Architecture:** `CandidateStore` gains ordered batch inspection and lifecycle transition
primitives. `LicenseReviewService` composes those primitives into an approval-only batch
transaction that prevalidates every request, writes evidence/reviews under one license
lock, and rolls back on reconciliation failure. The existing single-review API and all
non-approval paths remain unchanged.

**Tech Stack:** Python 3.13, frozen dataclasses, secure POSIX `dir_fd` persistence, JSONL,
pytest, Ruff.

**Workspace constraint:** `agent_app/knowledge/` is currently an untracked subsystem in a
dirty worktree. Do not stage or commit implementation files during these tasks; doing so
would include unrelated pre-existing work. The already isolated specification and plan
documents may be committed separately.

---

### Task 1: Candidate Batch Inspection And Lifecycle Transition

**Files:**
- Modify: `agent_app/knowledge/candidates.py`
- Test: `agent_app/tests/test_open_knowledge_candidates.py`

- [ ] **Step 1: Write failing tests for ordered inspection and bounded reads**

Add tests that register two candidates, spy on `_read_store_unlocked`, and assert one
store read for an ordered `inspect_many()` call:

```python
def test_inspect_many_preserves_order_with_one_store_read(tmp_path, monkeypatch):
    store, first, second = _registered_pair(tmp_path)
    original = store._read_store_unlocked
    calls = 0

    def counted(descriptor):
        nonlocal calls
        calls += 1
        return original(descriptor)

    monkeypatch.setattr(store, "_read_store_unlocked", counted)

    inspections = store.inspect_many([second.candidate_id, first.candidate_id])

    assert [item.candidate for item in inspections] == [second, first]
    assert {item.state for item in inspections} == {
        SourceLifecycleState.LICENSE_REVIEW_REQUIRED
    }
    assert calls == 1
```

- [ ] **Step 2: Run the inspection test and verify RED**

Run:

```bash
pytest agent_app/tests/test_open_knowledge_candidates.py::test_inspect_many_preserves_order_with_one_store_read -q
```

Expected: FAIL because `CandidateStore.inspect_many` does not exist.

- [ ] **Step 3: Add immutable batch request/result types and `inspect_many()`**

Add these public value types near `CandidateRegistrationResult`:

```python
@dataclass(frozen=True)
class CandidateInspection:
    candidate: OpenSourceCandidate
    state: SourceLifecycleState


@dataclass(frozen=True)
class CandidateTransitionRequest:
    candidate_id: str
    state: SourceLifecycleState
    actor: str
    reason: str
    input_sha256: str
```

Implement `inspect_many(candidate_ids)` so it validates a list of identifiers, acquires
one shared discovery lock, calls `_read_store_unlocked()` once, and returns
`CandidateInspection` objects in input order. Unknown IDs must raise
`CandidateStoreError` before returning partial output.

- [ ] **Step 4: Run the inspection test and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Write failing tests for ordered transition, replay, and rollback**

Add three tests:

```python
def test_transition_many_updates_two_candidates_in_one_store_read(tmp_path, monkeypatch):
    store, first, second = _registered_pair(tmp_path)
    requests = [
        _approval_transition(first.candidate_id, "a" * 64),
        _approval_transition(second.candidate_id, "b" * 64),
    ]
    original = store._read_store_unlocked
    calls = 0

    def counted(descriptor):
        nonlocal calls
        calls += 1
        return original(descriptor)

    monkeypatch.setattr(store, "_read_store_unlocked", counted)
    events = store.transition_many(requests)

    assert [event.candidate_id for event in events] == [
        first.candidate_id,
        second.candidate_id,
    ]
    assert all(
        event.state == SourceLifecycleState.APPROVED_FULL_TEXT_CANDIDATE
        for event in events
    )
    assert calls == 1


def test_transition_many_exact_replay_is_idempotent(tmp_path):
    store, first, second = _registered_pair(tmp_path)
    requests = [
        _approval_transition(first.candidate_id, "a" * 64),
        _approval_transition(second.candidate_id, "b" * 64),
    ]

    first_run = store.transition_many(requests)
    replay = store.transition_many(requests)

    assert replay == first_run
    assert len(store.lifecycle_path.read_text(encoding="utf-8").splitlines()) == 4


def test_transition_many_rolls_back_all_lifecycle_events_on_late_failure(
    tmp_path, monkeypatch
):
    store, first, second = _registered_pair(tmp_path)
    before = store.lifecycle_path.read_bytes()
    original = store._append_json_line

    def fail_second(path, payload):
        if path == store.lifecycle_path and payload.get("candidate_id") == second.candidate_id:
            raise OSError("simulated second transition failure")
        original(path, payload)

    monkeypatch.setattr(store, "_append_json_line", fail_second)
    with pytest.raises(CandidateStoreError, match="simulated second transition failure"):
        store.transition_many(
            [
                _approval_transition(first.candidate_id, "a" * 64),
                _approval_transition(second.candidate_id, "b" * 64),
            ]
        )

    assert store.lifecycle_path.read_bytes() == before
```

- [ ] **Step 6: Run transition tests and verify RED**

Run:

```bash
pytest agent_app/tests/test_open_knowledge_candidates.py -k 'transition_many or inspect_many' -q
```

Expected: FAIL because `transition_many()` is missing.

- [ ] **Step 7: Implement `transition_many()` and delegate `transition()`**

The method must validate the complete request list and reject duplicate candidate IDs
before locking. Under one exclusive discovery lock it snapshots `lifecycle.jsonl`, reads
the store once, keeps an in-memory latest-event map, applies transitions in order, and
uses `_rollback_store_changes((lifecycle_snapshot,))` on any failure. Replace the body of
`transition()` with:

```python
return self.transition_many(
    [
        CandidateTransitionRequest(
            candidate_id=candidate_id,
            state=state,
            actor=actor,
            reason=reason,
            input_sha256=input_sha256,
        )
    ]
)[0]
```

- [ ] **Step 8: Verify Task 1**

Run:

```bash
pytest agent_app/tests/test_open_knowledge_candidates.py -q
ruff check agent_app/knowledge/candidates.py agent_app/tests/test_open_knowledge_candidates.py
python -m py_compile agent_app/knowledge/candidates.py
```

Expected: all tests and checks pass.

---

### Task 2: Atomic Batch Approval Service

**Files:**
- Modify: `agent_app/knowledge/licensing.py`
- Test: `agent_app/tests/test_open_knowledge_licensing.py`

- [ ] **Step 1: Write failing tests for ordered approval and attribution**

Add a helper that registers two distinct candidates and tests the intended API:

```python
def test_record_approvals_preserves_order_and_attribution(tmp_path):
    service, store, candidates = _approval_batch_service(tmp_path)
    requests = [
        LicenseApprovalRequest(
            candidate_id=candidate.candidate_id,
            license_id=(
                LicenseId.EQUIVALENT_OPEN if index == 1 else LicenseId.CC_BY_4_0
            ),
            reviewer_id="reviewer_haobo",
            evidence=_evidence(
                license_text=f"official-license-{index}",
                attribution_required=True,
                attribution_text=f"Attribution {index}",
            ),
            reason=f"Official evidence {index} was verified.",
        )
        for index, candidate in enumerate(candidates)
    ]

    events = service.record_approvals(requests)

    assert [event.candidate_id for event in events] == [
        candidate.candidate_id for candidate in candidates
    ]
    assert all(event.evidence.attribution_required for event in events)
    assert all(
        store.current_state(candidate.candidate_id)
        == SourceLifecycleState.APPROVED_FULL_TEXT_CANDIDATE
        for candidate in candidates
    )
```

- [ ] **Step 2: Run the approval test and verify RED**

Run:

```bash
pytest agent_app/tests/test_open_knowledge_licensing.py::test_record_approvals_preserves_order_and_attribution -q
```

Expected: FAIL because `LicenseApprovalRequest` and `record_approvals()` do not exist.

- [ ] **Step 3: Add `LicenseApprovalRequest` and prevalidation**

Add this service request type:

```python
@dataclass(frozen=True)
class LicenseApprovalRequest:
    candidate_id: str
    license_id: LicenseId
    reviewer_id: str
    evidence: LicenseEvidence
    reason: str
    legal_approval_reference: str = ""
```

`record_approvals()` must reject non-list input, wrong item types, empty batches, and
duplicate candidate IDs before mutation. Use `candidate_store.inspect_many()` once, then
reuse the existing field, evidence-authority, global-use, attribution, and expiry
validators with the fixed decision `APPROVED_FULL_TEXT_CANDIDATE`.

- [ ] **Step 4: Implement bounded review-log/evidence rollback helpers**

Add private helpers that operate through the existing secure directory descriptors:

```python
@dataclass(frozen=True)
class _ReviewLogSnapshot:
    size: int
    existed: bool


def _snapshot_review_log(self, licenses_descriptor: int) -> _ReviewLogSnapshot:
    try:
        descriptor = os.open(
            self.reviews_path.name,
            os.O_RDONLY | os.O_NOFOLLOW,
            dir_fd=licenses_descriptor,
        )
    except FileNotFoundError:
        return _ReviewLogSnapshot(size=0, existed=False)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise LicenseReviewError("license review log is not a regular file")
        return _ReviewLogSnapshot(size=metadata.st_size, existed=True)
    finally:
        os.close(descriptor)


def _rollback_review_log(
    self, licenses_descriptor: int, snapshot: _ReviewLogSnapshot
) -> None:
    if not snapshot.existed:
        try:
            os.unlink(self.reviews_path.name, dir_fd=licenses_descriptor)
        except FileNotFoundError:
            return
        os.fsync(licenses_descriptor)
        return
    descriptor = os.open(
        self.reviews_path.name,
        os.O_RDWR | os.O_NOFOLLOW,
        dir_fd=licenses_descriptor,
    )
    try:
        os.ftruncate(descriptor, snapshot.size)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(licenses_descriptor)


def _evidence_file_exists(
    self, licenses_descriptor: int, evidence_sha256: str
) -> bool:
    with self._evidence_descriptor(licenses_descriptor) as evidence_descriptor:
        return self._read_file_at(
            evidence_descriptor,
            f"{evidence_sha256}.txt",
            max_bytes=_MAX_EVIDENCE_BYTES,
        ) is not None


def _remove_evidence_file(
    self, licenses_descriptor: int, evidence_sha256: str
) -> None:
    with self._evidence_descriptor(licenses_descriptor) as evidence_descriptor:
        try:
            os.unlink(f"{evidence_sha256}.txt", dir_fd=evidence_descriptor)
        except FileNotFoundError:
            return
        os.fsync(evidence_descriptor)
```

Rollback must truncate an existing log to its original byte size or unlink a log created
by the failed batch. It may remove only content-addressed evidence files that did not
exist before the batch.

- [ ] **Step 5: Implement `record_approvals()`**

Within one exclusive license lock:

1. Read and validate existing reviews once.
2. Reuse exact latest matches; construct new events for other requests using one
   `reviewed_at` timestamp.
3. Snapshot the review log and record which evidence hashes already exist.
4. Write each unique evidence body once and append only new review events.
5. Build `CandidateTransitionRequest` values for candidates still in
   `LICENSE_REVIEW_REQUIRED` and call `transition_many()` once.
6. On exception, restore the review log and remove only evidence files created by this
   batch. Include rollback failures in `LicenseReviewError`.
7. Return review events in request order.

- [ ] **Step 6: Verify the first approval test is GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 7: Write failing rollback, duplicate, replay, and read-count tests**

Add tests asserting:

- a duplicate candidate ID raises before creating `reviews.jsonl`;
- a failure on the second lifecycle append restores both lifecycle and review logs and
  removes newly written evidence;
- exact replay returns the same review IDs and does not append lines;
- `record_approvals()` calls `inspect_many()` once and `transition_many()` once;
- `equivalent_open` evidence retains `attribution_required=True` and its exact
  attribution text.

- [ ] **Step 8: Run the new tests and verify GREEN**

Run:

```bash
pytest agent_app/tests/test_open_knowledge_licensing.py -k 'record_approvals' -q
```

Expected: all selected rollback, replay, duplicate, attribution, and read-count tests
pass.

- [ ] **Step 9: Verify Task 2 compatibility**

Run:

```bash
pytest agent_app/tests/test_open_knowledge_licensing.py agent_app/tests/test_open_knowledge_candidates.py -q
ruff check agent_app/knowledge/licensing.py agent_app/knowledge/candidates.py agent_app/tests/test_open_knowledge_licensing.py agent_app/tests/test_open_knowledge_candidates.py
python -m py_compile agent_app/knowledge/licensing.py agent_app/knowledge/candidates.py
```

Expected: all tests and checks pass, including existing single-review and withdrawal
tests.

---

### Task 3: Apply The Audited Task 14 Batch

**Files:**
- Modify runtime-only: `/private/tmp/task14_apply_bulk_approval.py`
- Read: `agent_app/knowledge_base/licenses/task14_shortlist_ids_v1.json`
- Read: `agent_app/knowledge_base/licenses/task14_bulk_approval_audit_v1.md`
- Write runtime-only: `agent_app/knowledge_base/licenses/reviews.jsonl`
- Write runtime-only: `agent_app/knowledge_base/licenses/evidence/<sha256>.txt`
- Write runtime-only: `agent_app/knowledge_base/discovery/lifecycle.jsonl`

- [ ] **Step 1: Replace the script's per-item calls with one batch request**

Keep the existing shortlist hash and official-evidence validation. Construct
`LicenseApprovalRequest` objects and call:

```python
events = service.record_approvals(
    [
        LicenseApprovalRequest(
            candidate_id=approval.candidate.candidate_id,
            license_id=approval.license_id,
            reviewer_id=REVIEWER_ID,
            evidence=_license_evidence(approval),
            reason=approval.reason,
        )
        for approval in approvals
    ]
)
```

- [ ] **Step 2: Run syntax and lint checks on the runtime executor**

Run:

```bash
PYTHONPATH=. python -m py_compile /private/tmp/task14_apply_bulk_approval.py
ruff check /private/tmp/task14_apply_bulk_approval.py
```

Expected: both pass.

- [ ] **Step 3: Execute against a copied runtime root**

Create a fresh temporary directory, copy `agent_app/knowledge_base/.` into it, and run the
script with `PYTHONPATH=.`. Expected JSON: `approved_count` is `30`.

- [ ] **Step 4: Verify the copied root**

Run `list-license-queue` for `approved_full_text_candidate`. Assert:

```text
count=30
cc_by_4_0=28
equivalent_open=2
attribution_status required_captured=30
reviewer_id reviewer_haobo=30
```

Run the script a second time and assert review/lifecycle line counts and SHA-256 values are
unchanged.

- [ ] **Step 5: Execute once against the real runtime root**

Only after the copied-root checks pass, run:

```bash
PYTHONPATH=. python /private/tmp/task14_apply_bulk_approval.py \
  --root agent_app/knowledge_base \
  --shortlist agent_app/knowledge_base/licenses/task14_shortlist_ids_v1.json
```

Expected: `approved_count=30`, no partial failures.

- [ ] **Step 6: Verify Task 14 acceptance state**

Confirm the real queue has exactly the counts from Step 4, every shortlist ID has a
current approval, `reviews.jsonl` contains exactly 30 review events for this batch, and
the production pointer remains absent. Do not enqueue acquisition.

---

### Task 4: Regression And Static Verification

**Files:**
- Verify: `agent_app/knowledge/candidates.py`
- Verify: `agent_app/knowledge/licensing.py`
- Verify: `agent_app/tests/`

- [ ] **Step 1: Run focused knowledge tests**

```bash
pytest agent_app/tests/test_open_knowledge_candidates.py \
  agent_app/tests/test_open_knowledge_licensing.py \
  agent_app/tests/test_knowledge_pilot_cli.py -q
```

Expected: all pass.

- [ ] **Step 2: Run the complete application suite**

```bash
python -m pytest agent_app/tests -q
```

Expected: at least the existing baseline of 1,480 tests plus the new batch tests passes.

- [ ] **Step 3: Run scoped static checks**

```bash
ruff check agent_app/knowledge/candidates.py agent_app/knowledge/licensing.py \
  agent_app/tests/test_open_knowledge_candidates.py \
  agent_app/tests/test_open_knowledge_licensing.py
python -m py_compile agent_app/knowledge/candidates.py agent_app/knowledge/licensing.py
git diff --check
```

Expected: all pass. Do not use whole-tree Ruff or whole-tree `py_compile`; the existing
generated `agent_app/output/solve_raw.py` and unrelated legacy files are not clean.

- [ ] **Step 4: Produce the completion report**

Report test counts, approval/license/attribution counts, evidence and review hashes,
production-pointer state, files changed, and the fact that Task 15 was not started.
