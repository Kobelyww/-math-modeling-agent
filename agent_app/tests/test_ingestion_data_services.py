from __future__ import annotations

import json

import pandas as pd
import pytest

from agent_app.domain.models import RunSpec
from agent_app.services.artifact_service import ArtifactService
from agent_app.services.data_analysis import DataAnalysisService
from agent_app.services.ingestion import InputIngestionService
from agent_app.services.run_store import RunStore


def test_ingestion_copies_inputs_and_writes_manifest(tmp_path):
    data_file = tmp_path / "source.csv"
    data_file.write_text("x,y\n1,2\n", encoding="utf-8")
    ref_file = tmp_path / "ref.md"
    ref_file.write_text("# Reference\n", encoding="utf-8")

    store = RunStore(output_root=tmp_path / "runs")
    state = store.create_run(
        RunSpec(
            question="建立预测模型",
            data_files=[data_file],
            reference_files=[ref_file],
        )
    )

    service = InputIngestionService(ArtifactService(store.run_dir(state.run_id)))
    manifest = service.ingest(state.spec)

    assert manifest["question_file"] == "question.md"
    assert manifest["data_files"][0]["name"] == "source.csv"
    assert manifest["reference_files"][0]["name"] == "ref.md"
    assert (store.run_dir(state.run_id) / "inputs" / "data" / "source.csv").exists()
    assert (store.run_dir(state.run_id) / "inputs_manifest.json").exists()


def test_ingestion_rejects_missing_file(tmp_path):
    store = RunStore(output_root=tmp_path / "runs")
    state = store.create_run(RunSpec(question="分析", data_files=[tmp_path / "missing.csv"]))
    service = InputIngestionService(ArtifactService(store.run_dir(state.run_id)))

    with pytest.raises(FileNotFoundError):
        service.ingest(state.spec)


def test_ingestion_rejects_duplicate_input_basenames_before_writing(tmp_path):
    first_dir = tmp_path / "a"
    second_dir = tmp_path / "b"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "same.csv"
    second = second_dir / "same.csv"
    first.write_text("x\n1\n", encoding="utf-8")
    second.write_text("x\n2\n", encoding="utf-8")

    store = RunStore(output_root=tmp_path / "runs")
    state = store.create_run(RunSpec(question="分析", data_files=[first, second]))
    service = InputIngestionService(ArtifactService(store.run_dir(state.run_id)))

    with pytest.raises(ValueError, match="duplicate input filename"):
        service.ingest(state.spec)

    assert not (store.run_dir(state.run_id) / "question.md").exists()
    assert not (store.run_dir(state.run_id) / "inputs_manifest.json").exists()
    assert not (store.run_dir(state.run_id) / "inputs" / "data" / "same.csv").exists()


def test_ingestion_prevalidates_missing_files_before_writing(tmp_path):
    existing = tmp_path / "source.csv"
    existing.write_text("x\n1\n", encoding="utf-8")

    store = RunStore(output_root=tmp_path / "runs")
    state = store.create_run(
        RunSpec(question="分析", data_files=[existing, tmp_path / "missing.csv"])
    )
    service = InputIngestionService(ArtifactService(store.run_dir(state.run_id)))

    with pytest.raises(FileNotFoundError):
        service.ingest(state.spec)

    assert not (store.run_dir(state.run_id) / "question.md").exists()
    assert not (store.run_dir(state.run_id) / "inputs_manifest.json").exists()
    assert not (store.run_dir(state.run_id) / "inputs" / "data" / "source.csv").exists()


def test_data_analysis_audits_csv(tmp_path):
    csv_path = tmp_path / "traffic.csv"
    pd.DataFrame(
        {
            "flow": [10, 20, None],
            "speed": [40.0, 35.5, 33.0],
            "road": ["A", "A", "B"],
        }
    ).to_csv(csv_path, index=False)

    service = DataAnalysisService()
    report = service.audit_files([csv_path])

    assert report.files == ["traffic.csv"]
    assert report.missing_values["flow"] == 1
    assert "flow" in report.usable_features
    assert "speed" in report.descriptive_statistics


def test_data_analysis_writes_markdown_summary(tmp_path):
    csv_path = tmp_path / "traffic.csv"
    csv_path.write_text("flow,speed\n1,2\n3,4\n", encoding="utf-8")
    service = DataAnalysisService()
    report = service.audit_files([csv_path])

    markdown = service.to_markdown(report)

    assert "traffic.csv" in markdown
    assert "flow" in markdown
    assert "缺失值" in markdown


def test_data_analysis_normalizes_non_finite_numeric_stats(tmp_path):
    csv_path = tmp_path / "bad_stats.csv"
    pd.DataFrame({"x": [float("inf"), float("inf")]}).to_csv(csv_path, index=False)

    report = DataAnalysisService().audit_files([csv_path])

    stats = report.descriptive_statistics["x"]
    assert all(value is None or isinstance(value, (int, float, str)) for value in stats.values())
    assert stats["std"] is None


def test_data_analysis_records_csv_read_failure(tmp_path):
    directory = tmp_path / "not_a_file.csv"
    directory.mkdir()

    report = DataAnalysisService().audit_files([directory])

    assert report.files == ["not_a_file.csv"]
    assert report.data_limitations
    assert "CSV 读取失败" in report.data_limitations[0]
