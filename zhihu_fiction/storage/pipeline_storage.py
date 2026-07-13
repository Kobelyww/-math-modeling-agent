"""Persistence helpers for fiction pipeline runs, schedule, and checkpoints."""

from __future__ import annotations

import json
from pathlib import Path


class PipelineStorage:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.runs_file = run_dir / "runs.jsonl"
        self.schedule_file = run_dir / "schedule.json"
        self.checkpoint_dir = run_dir / "checkpoints"

    def ensure(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def append_run(self, result) -> None:
        self.ensure()
        with self.runs_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result.to_json(), ensure_ascii=False) + "\n")

    def read_runs(self, limit: int = 50) -> list[dict]:
        if not self.runs_file.exists():
            return []
        runs: list[dict] = []
        with self.runs_file.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    try:
                        runs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        runs.reverse()
        return runs[:limit]

    def save_schedule(self, data: dict) -> None:
        self.ensure()
        self.schedule_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_schedule(self) -> dict | None:
        if not self.schedule_file.exists():
            return None
        return json.loads(self.schedule_file.read_text(encoding="utf-8"))

    def update_schedule(self, updates: dict) -> dict:
        data = self.read_schedule() or {}
        data.update(updates)
        self.save_schedule(data)
        return data

    def checkpoint_path(self, run_id: str) -> Path:
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        return self.checkpoint_dir / f"{run_id}.json"

    def save_checkpoint(self, run_id: str, **state) -> None:
        self.checkpoint_path(run_id).write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_checkpoint(self, run_id: str) -> dict | None:
        checkpoint = self.checkpoint_path(run_id)
        if not checkpoint.exists():
            return None
        try:
            return json.loads(checkpoint.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return None

    def clear_checkpoint(self, run_id: str) -> None:
        self.checkpoint_path(run_id).unlink(missing_ok=True)

    def list_checkpoints(self) -> list[dict]:
        if not self.checkpoint_dir.exists():
            return []
        checkpoints: list[dict] = []
        for path in sorted(self.checkpoint_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                continue
            data["_file"] = path.name
            checkpoints.append(data)
        return checkpoints

__all__ = ["PipelineStorage"]
