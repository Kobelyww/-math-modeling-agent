from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_app.domain.serialization import from_json_dict, to_json_dict
from agent_app.services.run_store import RunStore


@dataclass
class StageDependencyRef:
    stage: str
    version: int
    output_id: str


@dataclass
class StageReviewOutput:
    stage: str
    version: int
    status: str
    run_id: str
    output_id: str
    stage_label: str = ""
    created_at: str = ""
    approved_at: str = ""
    input_fingerprint: str = ""
    depends_on: list[StageDependencyRef] = field(default_factory=list)
    invalidated_by: dict[str, Any] | None = None
    summary: str = ""
    review_payload: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    quality_reports: list[dict[str, Any]] = field(default_factory=list)

    def dependency_ref(self) -> StageDependencyRef:
        return StageDependencyRef(stage=self.stage, version=self.version, output_id=self.output_id)

    def to_event(self, event_type: str = "stage_review_created") -> dict[str, Any]:
        return {
            "type": event_type,
            "run_id": self.run_id,
            "stage": self.stage,
            "stage_label": self.stage_label,
            "output_id": self.output_id,
            "version": self.version,
            "status": self.status,
            "summary": self.summary,
            "review_payload": to_json_dict(self.review_payload),
            "artifacts": to_json_dict(self.artifacts),
            "quality_reports": to_json_dict(self.quality_reports),
            "depends_on": to_json_dict(self.depends_on),
            "invalidated_by": to_json_dict(self.invalidated_by),
        }


class StageReviewService:
    def __init__(self, run_store: RunStore) -> None:
        self.run_store = run_store

    def create_review(
        self,
        *,
        run_id: str,
        stage: str,
        stage_label: str,
        status: str,
        summary: str,
        review_payload: dict[str, Any],
        input_payload: dict[str, Any],
        depends_on: list[StageDependencyRef] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        quality_reports: list[dict[str, Any]] | None = None,
    ) -> StageReviewOutput:
        version = self._next_version(run_id, stage)
        review = StageReviewOutput(
            stage=stage,
            version=version,
            status=status,
            run_id=run_id,
            output_id=f"{stage}_v{version}",
            stage_label=stage_label,
            created_at=self._now(),
            approved_at=self._now() if status == "approved" else "",
            input_fingerprint=self.compute_fingerprint(input_payload),
            depends_on=depends_on or [],
            summary=summary,
            review_payload=review_payload,
            artifacts=artifacts or [],
            quality_reports=quality_reports or [],
        )
        self._save_review(review)
        return review

    def list_reviews(self, run_id: str) -> list[StageReviewOutput]:
        directory = self._review_dir(run_id)
        if not directory.exists():
            return []
        reviews = [
            from_json_dict(StageReviewOutput, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(directory.glob("*.json"))
        ]
        return sorted(reviews, key=lambda item: (item.created_at, item.stage, item.version))

    def get_review(self, run_id: str, output_id: str) -> StageReviewOutput:
        path = self._review_dir(run_id) / f"{output_id}.json"
        if not path.exists():
            raise ValueError(f"stage review output not found: {output_id}")
        return from_json_dict(StageReviewOutput, json.loads(path.read_text(encoding="utf-8")))

    def mark_status(self, run_id: str, output_id: str, status: str, *, approved: bool = False) -> StageReviewOutput:
        review = self.get_review(run_id, output_id)
        updated = replace(review, status=status, approved_at=self._now() if approved else review.approved_at)
        self._save_review(updated)
        return updated

    def invalidate_downstream(
        self,
        *,
        run_id: str,
        stage: str,
        version: int,
        decision_id: str,
        reason: str,
    ) -> list[StageReviewOutput]:
        source_key = (stage, version)
        stale: list[StageReviewOutput] = []
        changed = True
        stale_keys: set[tuple[str, int]] = {source_key}
        while changed:
            changed = False
            for review in self.list_reviews(run_id):
                key = (review.stage, review.version)
                if key in stale_keys or review.status == "stale":
                    continue
                depends_on_stale = any((dep.stage, dep.version) in stale_keys for dep in review.depends_on)
                if depends_on_stale:
                    stale_keys.add(key)
                    changed = True
                    updated = replace(
                        review,
                        status="stale",
                        invalidated_by={
                            "stage": stage,
                            "version": version,
                            "decision_id": decision_id,
                            "reason": reason,
                        },
                    )
                    self._save_review(updated)
                    stale.append(updated)
        return sorted(stale, key=lambda item: (item.created_at, item.stage, item.version))

    def approve_with_payload_patch(
        self,
        *,
        run_id: str,
        output_id: str,
        payload_patch: dict[str, Any],
        decision_id: str,
    ) -> tuple[StageReviewOutput, list[StageReviewOutput]]:
        current = self.get_review(run_id, output_id)
        if not payload_patch:
            return self.mark_status(run_id, output_id, "approved", approved=True), []
        patched_payload = {**current.review_payload, **payload_patch}
        patched = self.create_review(
            run_id=run_id,
            stage=current.stage,
            stage_label=current.stage_label,
            status="approved",
            summary=current.summary,
            review_payload=patched_payload,
            input_payload={
                "previous_output_id": current.output_id,
                "payload_patch": payload_patch,
                "previous_fingerprint": current.input_fingerprint,
            },
            depends_on=current.depends_on,
            artifacts=current.artifacts,
            quality_reports=current.quality_reports,
        )
        stale = self.invalidate_downstream(
            run_id=run_id,
            stage=current.stage,
            version=current.version,
            decision_id=decision_id,
            reason=f"{current.stage_label or current.stage} 的审阅字段被用户修改。",
        )
        return patched, stale

    def current_approved_outputs(self, run_id: str) -> dict[str, StageReviewOutput]:
        current: dict[str, StageReviewOutput] = {}
        for review in self.list_reviews(run_id):
            if review.status == "approved":
                previous = current.get(review.stage)
                if previous is None or review.version > previous.version:
                    current[review.stage] = review
        return current

    @staticmethod
    def compute_fingerprint(payload: dict[str, Any]) -> str:
        encoded = json.dumps(to_json_dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _next_version(self, run_id: str, stage: str) -> int:
        versions = [review.version for review in self.list_reviews(run_id) if review.stage == stage]
        return max(versions, default=0) + 1

    def _save_review(self, review: StageReviewOutput) -> None:
        directory = self._review_dir(review.run_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{review.output_id}.json"
        path.write_text(json.dumps(to_json_dict(review), ensure_ascii=False, indent=2), encoding="utf-8")

    def _review_dir(self, run_id: str) -> Path:
        return self.run_store.run_dir(run_id) / "stage_reviews"

    @staticmethod
    def _now() -> str:
        return datetime.now().replace(microsecond=0).isoformat()
