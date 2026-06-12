from __future__ import annotations

from pathlib import Path

from agent_app.deepagent.runner import CompetitionPaperRunner
from agent_app.domain.models import RunSpec, RunStatus
from agent_app.tools.competition import make_competition_tools


class ToolDrivingCoordinator:
    def __init__(self, run_store):
        self.tools = {tool.name: tool for tool in make_competition_tools(run_store=run_store)}

    def _invoke_tool(self, name, payload):
        result = self.tools[name].invoke(payload)
        assert isinstance(result, dict), name
        return result

    def invoke(self, payload):
        run_id = payload["run_id"]
        question = payload["question"]
        data_files = payload["data_files"]
        reference_files = payload["reference_files"]

        manifest = self._invoke_tool(
            "ingest_inputs",
            {
                "run_id": run_id,
                "question": question,
                "data_files": data_files,
                "reference_files": reference_files,
            },
        )
        problem = self._invoke_tool("analyze_problem", {"run_id": run_id, "question": question})
        audit = self._invoke_tool("audit_data", {"run_id": run_id, "file_paths": data_files})
        evidence = self._invoke_tool(
            "retrieve_evidence",
            {
                "run_id": run_id,
                "query": question,
                "reference_files": reference_files,
                "top_k": 3,
                "allow_online_search": False,
            },
        )
        plan = self._invoke_tool(
            "plan_model",
            {
                "run_id": run_id,
                "problem_brief": problem["problem_brief"],
                "data_audit": audit["data_audit"],
                "evidence_notes": evidence["evidence_notes"],
            },
        )
        experiment = self._invoke_tool(
            "run_experiment",
            {
                "run_id": run_id,
                "modeling_plan": plan["modeling_plan"],
                "data_files": data_files,
            },
        )
        paper = self._invoke_tool(
            "draft_competition_paper",
            {
                "run_id": run_id,
                "problem_brief": problem["problem_brief"],
                "data_audit": audit["data_audit"],
                "modeling_plan": plan["modeling_plan"],
                "experiment_result": experiment["experiment_result"],
                "evidence_notes": evidence["evidence_notes"],
            },
        )
        review = self._invoke_tool(
            "review_submission",
            {
                "run_id": run_id,
                "paper_draft": paper["paper_draft"],
                "experiment_result": experiment["experiment_result"],
                "artifacts": [
                    plan["modeling_report_path"],
                    experiment["code_path"],
                    paper["paper_tex_path"],
                ],
            },
        )
        assert review["quality_report"]["passed"] is True
        package = self._invoke_tool("package_submission", {"run_id": run_id})
        return {"messages": [{"content": package["final_synthesis_path"]}]}


def test_minimal_competition_workflow_smoke(tmp_path):
    data_file = tmp_path / "traffic.csv"
    data_file.write_text("flow,speed\n10,40\n20,35\n", encoding="utf-8")
    ref_file = tmp_path / "reference.md"
    ref_file.write_text("层次分析法可用于评价类数学建模问题。", encoding="utf-8")

    runner = CompetitionPaperRunner(
        output_root=tmp_path / "runs",
        coordinator_factory=lambda run_store, **kwargs: ToolDrivingCoordinator(run_store),
    )

    result = runner.run(
        RunSpec(
            question="根据交通流量数据建立预测模型，并评价模型稳定性。",
            data_files=[data_file],
            reference_files=[ref_file],
        )
    )

    run_dir = tmp_path / "runs" / result.run_id
    assert result.status == RunStatus.COMPLETED
    assert "final_synthesis.md" in result.summary
    assert result.artifacts

    artifact_paths = {artifact.path.as_posix() for artifact in result.artifacts}
    assert all(not artifact.path.is_absolute() for artifact in result.artifacts)
    assert {
        "final_synthesis.md",
        "run.json",
        "paper.md",
        "paper.tex",
        "question.md",
        "inputs/data/traffic.csv",
        "inputs/references/reference.md",
    }.issubset(artifact_paths)

    artifact_by_path = {artifact.path.as_posix(): artifact for artifact in result.artifacts}
    assert artifact_by_path["paper.tex"].kind == "latex"
    assert artifact_by_path["solve.py"].kind == "python"
    assert artifact_by_path["run.json"].kind == "json"
    for markdown_path in ["final_synthesis.md", "paper.md", "question.md"]:
        assert artifact_by_path[markdown_path].kind == "markdown"

    persisted = runner.run_store.load_state(result.run_id)
    persisted_artifact_paths = {artifact.path.as_posix() for artifact in persisted.artifacts}
    assert persisted.status == RunStatus.COMPLETED
    assert {"final_synthesis.md", "run.json"}.issubset(persisted_artifact_paths)
    assert persisted.quality_reports
    assert any(report.gate_name == "submission" for report in persisted.quality_reports)

    final_synthesis = (run_dir / "final_synthesis.md").read_text(encoding="utf-8")
    assert "Structured DeepAgent competition artifacts are ready for review." in final_synthesis

    for filename in [
        "inputs_manifest.json",
        "problem_brief.md",
        "data_audit.md",
        "evidence_notes.md",
        "modeling_report.md",
        "solve.py",
        "paper.tex",
        "review_report.md",
        "final_synthesis.md",
        "run.json",
    ]:
        assert (run_dir / filename).exists(), filename
