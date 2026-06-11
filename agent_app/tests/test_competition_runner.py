from __future__ import annotations

from pathlib import Path

from agent_app.config import APP_ROOT
from agent_app.deepagent.runner import CompetitionPaperRunner
from agent_app.domain.models import RunSpec, RunStatus


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
