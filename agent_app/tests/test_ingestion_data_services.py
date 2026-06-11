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
