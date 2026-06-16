"""Tests for pipeline persistence helpers."""
from __future__ import annotations

import json

from zhihu_fiction.pipeline import RunResult, StageRecord
from zhihu_fiction.pipeline_storage import PipelineStorage


def test_pipeline_storage_appends_and_reads_recent_runs(tmp_path):
    storage = PipelineStorage(tmp_path)
    first = RunResult(
        run_id="run_1",
        trigger="manual",
        topic="选题一",
        genre="悬疑",
        stages={"create": StageRecord(status="ok", duration_s=1.2, extra={"words": 100})},
        timestamp="2026-06-11T00:00:00+00:00",
    )
    second = RunResult(
        run_id="run_2",
        trigger="manual",
        topic="选题二",
        genre="现实",
        timestamp="2026-06-11T00:01:00+00:00",
    )
    storage.append_run(first)
    (tmp_path / "runs.jsonl").write_text(
        (tmp_path / "runs.jsonl").read_text(encoding="utf-8") + "bad json\n",
        encoding="utf-8",
    )
    storage.append_run(second)

    runs = storage.read_runs(limit=2)

    assert [run["run_id"] for run in runs] == ["run_2", "run_1"]
    assert runs[1]["stages"]["create"]["words"] == 100


def test_pipeline_storage_round_trips_schedule(tmp_path):
    storage = PipelineStorage(tmp_path)

    storage.save_schedule({"active": True, "interval_minutes": 15})
    storage.update_schedule({"active": False, "stopped_at": "now"})

    assert storage.read_schedule() == {
        "active": False,
        "interval_minutes": 15,
        "stopped_at": "now",
    }


def test_pipeline_storage_round_trips_checkpoints(tmp_path):
    storage = PipelineStorage(tmp_path)

    storage.save_checkpoint("run_1", topic="选题", stage="pre_create")
    storage.save_checkpoint("run_2", topic="选题二", stage="pre_publish")
    (tmp_path / "checkpoints" / "broken.json").write_text("{", encoding="utf-8")

    assert storage.load_checkpoint("run_1") == {"topic": "选题", "stage": "pre_create"}
    checkpoints = storage.list_checkpoints()

    assert {checkpoint["_file"] for checkpoint in checkpoints} == {"run_1.json", "run_2.json"}
    storage.clear_checkpoint("run_1")
    assert storage.load_checkpoint("run_1") is None


def test_pipeline_storage_read_runs_returns_empty_when_missing(tmp_path):
    storage = PipelineStorage(tmp_path)

    assert storage.read_runs() == []
    assert storage.read_schedule() is None
    assert storage.load_checkpoint("missing") is None
    assert storage.list_checkpoints() == []
