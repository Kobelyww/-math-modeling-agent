from __future__ import annotations

from pathlib import Path

from agent_app.deepagent.runner import CompetitionPaperRunner
from agent_app.domain.models import RunSpec, RunStatus
from agent_app.tools.competition import make_competition_tools


class ToolDrivingCoordinator:
    def __init__(self, run_store):
        self.tools = {tool.name: tool for tool in make_competition_tools(run_store=run_store)}

    def invoke(self, payload):
        run_id = payload["run_id"]
        question = payload["question"]
        data_files = payload["data_files"]
        reference_files = payload["reference_files"]

        manifest = self.tools["ingest_inputs"].invoke(
            {
                "run_id": run_id,
                "question": question,
                "data_files": data_files,
                "reference_files": reference_files,
            }
        )
        problem = self.tools["analyze_problem"].invoke({"run_id": run_id, "question": question})
        audit = self.tools["audit_data"].invoke({"run_id": run_id, "file_paths": data_files})
        evidence = self.tools["retrieve_evidence"].invoke(
            {
                "run_id": run_id,
                "query": question,
                "reference_files": reference_files,
                "top_k": 3,
                "allow_online_search": False,
            }
        )
        plan = self.tools["plan_model"].invoke(
            {
                "run_id": run_id,
                "problem_brief": problem["problem_brief"],
                "data_audit": audit["data_audit"],
                "evidence_notes": evidence["evidence_notes"],
            }
        )
        experiment = self.tools["run_experiment"].invoke(
            {
                "run_id": run_id,
                "modeling_plan": plan["modeling_plan"],
                "data_files": data_files,
            }
        )
        paper = self.tools["draft_competition_paper"].invoke(
            {
                "run_id": run_id,
                "problem_brief": problem["problem_brief"],
                "data_audit": audit["data_audit"],
                "modeling_plan": plan["modeling_plan"],
                "experiment_result": experiment["experiment_result"],
                "evidence_notes": evidence["evidence_notes"],
            }
        )
        self.tools["review_submission"].invoke(
            {
                "run_id": run_id,
                "paper_draft": paper["paper_draft"],
                "experiment_result": experiment["experiment_result"],
                "artifacts": [],
            }
        )
        package = self.tools["package_submission"].invoke({"run_id": run_id})
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
