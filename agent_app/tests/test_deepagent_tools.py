from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import RunSpec
from agent_app.services.artifact_service import ArtifactService
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


def test_competition_tools_expose_expected_names(tmp_path):
    store = RunStore(output_root=tmp_path)
    tools = make_competition_tools(run_store=store)
    names = {tool.name for tool in tools}

    assert {
        "ingest_inputs",
        "analyze_problem",
        "audit_data",
        "retrieve_evidence",
        "plan_model",
        "run_experiment",
        "draft_competition_paper",
        "review_submission",
        "package_submission",
    }.issubset(names)


def test_ingest_inputs_tool_returns_manifest(tmp_path):
    data = tmp_path / "data.csv"
    data.write_text("x,y\n1,2\n", encoding="utf-8")
    store = RunStore(output_root=tmp_path / "runs")
    state = store.create_run(RunSpec(question="建立模型", data_files=[data]))
    tool_by_name = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    result = tool_by_name["ingest_inputs"].invoke(
        {
            "run_id": state.run_id,
            "question": "建立模型",
            "data_files": [str(data)],
            "reference_files": [],
        }
    )

    assert result["inputs_manifest"]["question_file"] == "question.md"
    assert result["saved_paths"][0].endswith("data.csv")


def test_package_submission_tool_writes_summary(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="建立模型"))
    run_dir = store.run_dir(state.run_id)
    for filename in ["modeling_report.md", "solve.py", "paper.tex", "review_report.md"]:
        (run_dir / filename).write_text("content", encoding="utf-8")
    tool_by_name = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    result = tool_by_name["package_submission"].invoke({"run_id": state.run_id})

    assert result["final_synthesis_path"].endswith("final_synthesis.md")
    assert (run_dir / "final_synthesis.md").exists()
