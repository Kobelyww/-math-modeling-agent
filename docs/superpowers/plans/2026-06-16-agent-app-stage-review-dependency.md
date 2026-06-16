# Stage Review Dependency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reviewable stage output versions and dependency invalidation events for the paper workflow.

**Architecture:** Add a `StageReviewService` that persists versioned stage outputs under each run directory, computes deterministic input fingerprints, and marks downstream outputs stale. Integrate it into the event-driven paper coordinator and render review cards in the Web UI.

**Tech Stack:** Python dataclasses, JSON persistence, pytest, FastAPI WebSocket event protocol, vanilla JS/CSS.

---

### Task 1: Stage Review Service

- [ ] Write failing service tests for version creation, fingerprints, downstream invalidation, and payload patch approval.
- [ ] Implement domain models and `agent_app/services/stage_review_service.py`.
- [ ] Run service tests until green.

### Task 2: Event Stream Integration

- [ ] Write failing stream test for `stage_review_created` events.
- [ ] Emit review events after every stage in `EventDrivingCoordinator`.
- [ ] Run stream tests until green.

### Task 3: Web Review Queue

- [ ] Add frontend state/rendering for stage review cards and stale events.
- [ ] Add CSS for review queue cards and stale status.
- [ ] Run existing web tests and inspect health endpoint.
