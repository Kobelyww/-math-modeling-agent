from __future__ import annotations

from pathlib import Path

from agent_app.config import APP_ROOT
from agent_app.deepagent.runner import CompetitionPaperRunner
from agent_app.domain.models import QualityReport, RunSpec, RunStatus


class FakeCoordinator:
    def invoke(self, payload):
        run_id = payload["run_id"]
        run_dir = Path(payload["run_dir"])
        for filename in [
            "problem_brief.md",
            "data_audit.md",
            "evidence_notes.md",
            "modeling_report.md",
            "solve.py",
            "paper.tex",
            "review_report.md",
            "final_synthesis.md",
        ]:
            (run_dir / filename).write_text(f"{filename}\n", encoding="utf-8")
        return {"messages": [{"content": f"completed {run_id}"}]}


def test_runner_creates_run_and_returns_result(tmp_path):
    runner = CompetitionPaperRunner(output_root=tmp_path, coordinator_factory=lambda **kwargs: FakeCoordinator())

    result = runner.run(RunSpec(question="建立预测模型"))

    assert result.run_id.startswith("run_")
    assert result.status == RunStatus.COMPLETED
    assert any(artifact.path.name == "paper.tex" for artifact in result.artifacts)
    assert "completed" in result.summary
    artifact_kinds = {artifact.path.name: artifact.kind for artifact in result.artifacts}
    assert artifact_kinds["paper.tex"] == "latex"
    assert artifact_kinds["solve.py"] == "python"
    assert artifact_kinds["problem_brief.md"] == "markdown"
    assert artifact_kinds["run.json"] == "json"


def test_runner_default_output_root_uses_existing_output_directory_name():
    runner = CompetitionPaperRunner(coordinator_factory=lambda **kwargs: FakeCoordinator())

    assert runner.output_root == APP_ROOT / "output" / "runs"


def test_runner_records_failure_as_partial_result(tmp_path):
    class FailingCoordinator:
        def invoke(self, payload):
            raise RuntimeError("model unavailable")

    runner = CompetitionPaperRunner(output_root=tmp_path, coordinator_factory=lambda **kwargs: FailingCoordinator())

    result = runner.run(RunSpec(question="建立预测模型"))

    assert result.status == RunStatus.FAILED
    assert "model unavailable" in result.summary


def test_runner_preserves_tool_saved_state_and_nested_artifacts(tmp_path):
    class StateMutatingCoordinator:
        def __init__(self, run_store):
            self.run_store = run_store

        def invoke(self, payload):
            run_id = payload["run_id"]
            run_dir = Path(payload["run_dir"])
            (run_dir / "results").mkdir()
            (run_dir / "results" / "output.csv").write_text("x,y\n1,2\n", encoding="utf-8")
            (run_dir / "paper.tex").write_text("\\documentclass{article}\n", encoding="utf-8")
            state = self.run_store.load_state(run_id)
            state.quality_reports.append(QualityReport(gate_name="tool_gate", passed=True, score=0.9))
            self.run_store.save_state(state)
            return {"messages": [{"content": "tool state saved"}]}

    runner = CompetitionPaperRunner(
        output_root=tmp_path,
        coordinator_factory=lambda **kwargs: StateMutatingCoordinator(kwargs["run_store"]),
    )

    result = runner.run(RunSpec(question="建立预测模型"))
    persisted = runner.run_store.load_state(result.run_id)

    assert result.status == RunStatus.COMPLETED
    assert [report.gate_name for report in result.quality_reports] == ["tool_gate"]
    assert [report.gate_name for report in persisted.quality_reports] == ["tool_gate"]
    assert Path("results/output.csv") in {artifact.path for artifact in result.artifacts}
    assert Path("results/output.csv") in {artifact.path for artifact in persisted.artifacts}


def test_runner_preserves_tool_saved_state_on_failure(tmp_path):
    class FailingAfterMutationCoordinator:
        def __init__(self, run_store):
            self.run_store = run_store

        def invoke(self, payload):
            run_id = payload["run_id"]
            run_dir = Path(payload["run_dir"])
            (run_dir / "results").mkdir()
            (run_dir / "results" / "output.csv").write_text("x,y\n1,2\n", encoding="utf-8")
            state = self.run_store.load_state(run_id)
            state.quality_reports.append(QualityReport(gate_name="pre_failure_gate", passed=False, score=0.2))
            self.run_store.save_state(state)
            raise RuntimeError("model unavailable")

    runner = CompetitionPaperRunner(
        output_root=tmp_path,
        coordinator_factory=lambda **kwargs: FailingAfterMutationCoordinator(kwargs["run_store"]),
    )

    result = runner.run(RunSpec(question="建立预测模型"))
    persisted = runner.run_store.load_state(result.run_id)

    assert result.status == RunStatus.FAILED
    assert persisted.status == RunStatus.FAILED
    assert "model unavailable" in result.summary
    assert [report.gate_name for report in result.quality_reports] == ["pre_failure_gate"]
    assert [report.gate_name for report in persisted.quality_reports] == ["pre_failure_gate"]
    assert Path("results/output.csv") in {artifact.path for artifact in result.artifacts}
    assert Path("results/output.csv") in {artifact.path for artifact in persisted.artifacts}
