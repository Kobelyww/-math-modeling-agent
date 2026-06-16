from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import (
    ArtifactRef,
    DataAuditReport,
    ExperimentResult,
    ProblemBrief,
    QualityReport,
    RunIssue,
    RunOptions,
    RunResult,
    RunSpec,
    RunState,
    RunStatus,
    RunStage,
)
from agent_app.domain.serialization import from_json_dict, to_json_dict


def test_domain_package_exports_serialization_helpers():
    import agent_app.domain as domain

    assert domain.to_json_dict is to_json_dict
    assert domain.from_json_dict is from_json_dict


def test_run_spec_defaults_to_competition_paper():
    spec = RunSpec(question="建立交通流优化模型")

    assert spec.output_profile == "competition_paper"
    assert spec.options.top_k == 6
    assert spec.data_files == []
    assert spec.reference_files == []


def test_run_state_round_trips_through_json_dict():
    state = RunState(
        run_id="run_20260611_000001",
        spec=RunSpec(
            question="预测需求",
            data_files=[Path("data.csv")],
            reference_files=[Path("paper.pdf")],
            options=RunOptions(max_repair_attempts=3),
        ),
        status=RunStatus.RUNNING,
        stage=RunStage.AUDIT_DATA,
        artifacts=[ArtifactRef(name="data_audit", path=Path("data_audit.md"), kind="markdown")],
        issues=[RunIssue(stage="audit_data", message="文件编码已使用 utf-8 读取")],
        quality_reports=[QualityReport(gate_name="input", passed=True, score=1.0)],
    )

    payload = to_json_dict(state)
    restored = from_json_dict(RunState, payload)

    assert restored.run_id == state.run_id
    assert restored.spec.data_files == [Path("data.csv")]
    assert restored.status == RunStatus.RUNNING
    assert restored.stage == RunStage.AUDIT_DATA
    assert restored.artifacts[0].path == Path("data_audit.md")
    assert restored.quality_reports[0].passed is True


def test_problem_and_experiment_models_store_expected_fields():
    brief = ProblemBrief(
        background="交通拥堵",
        questions=["预测流量", "优化信号灯"],
        objectives=["降低平均延误"],
        constraints=["道路容量"],
        required_data=["车流量"],
        deliverables=["论文"],
    )
    audit = DataAuditReport(files=["traffic.csv"], usable_features=["flow", "speed"])
    experiment = ExperimentResult(
        code_path=Path("solve.py"),
        execution_status="success",
        result_files=[Path("results/metrics.json")],
        figure_files=[Path("figures/flow.png")],
        sensitivity_results=["改变容量参数后平均延误变化 4.2%"],
    )

    assert brief.questions[0] == "预测流量"
    assert audit.files == ["traffic.csv"]
    assert experiment.execution_status == "success"


def test_run_result_is_small_interface_payload():
    result = RunResult(
        run_id="run_1",
        status=RunStatus.COMPLETED,
        stage=RunStage.PACKAGE_SUBMISSION,
        artifacts=[ArtifactRef(name="paper_tex", path=Path("paper.tex"), kind="tex")],
        quality_reports=[QualityReport(gate_name="submission", passed=True, score=1.0)],
        summary="已生成竞赛论文包",
    )

    assert result.artifacts[0].name == "paper_tex"
    assert result.summary.startswith("已生成")


def test_input_asset_round_trips_through_json():
    from pathlib import Path

    from agent_app.domain.models import AssetKind, AssetStatus, InputAsset
    from agent_app.domain.serialization import from_json_dict, to_json_dict

    asset = InputAsset(
        asset_id="asset_abc123",
        original_name="traffic.csv",
        stored_path=Path("assets/asset_abc123/traffic.csv"),
        kind=AssetKind.DATA,
        status=AssetStatus.VALIDATED,
        size=18,
        suffix=".csv",
        content_type="text/csv",
        created_at="2026-06-12T12:00:00",
    )

    payload = to_json_dict(asset)
    restored = from_json_dict(InputAsset, payload)

    assert payload["kind"] == "data"
    assert payload["status"] == "validated"
    assert restored == asset
