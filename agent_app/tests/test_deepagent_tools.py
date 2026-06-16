from __future__ import annotations

from pathlib import Path

import pytest

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


def test_competition_tools_return_required_structured_shapes(tmp_path):
    data = tmp_path / "data.csv"
    data.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    reference = tmp_path / "reference.md"
    reference.write_text("reference", encoding="utf-8")
    store = RunStore(output_root=tmp_path / "runs")
    state = store.create_run(RunSpec(question="建立模型"))
    tool_by_name = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    question = "建立模型并分析数据" * 20
    problem = tool_by_name["analyze_problem"].invoke(
        {"run_id": state.run_id, "question": question}
    )
    assert problem["problem_brief"]["background"] == question[:200]
    assert problem["problem_brief"]["questions"] == [question]
    assert problem["problem_brief_path"].endswith("problem_brief.md")
    assert "path" not in problem

    audit = tool_by_name["audit_data"].invoke(
        {"run_id": state.run_id, "file_paths": [str(data)]}
    )
    assert audit["data_audit_path"].endswith("data_audit.md")
    assert "path" not in audit

    evidence = tool_by_name["retrieve_evidence"].invoke(
        {
            "run_id": state.run_id,
            "query": "建模依据",
            "reference_files": [str(reference), str(data)],
            "top_k": 1,
        }
    )
    assert evidence["evidence_notes"] == [
        "# Evidence Notes",
        "",
        "Query: 建模依据",
        "",
        "- reference.md",
    ]
    assert evidence["evidence_notes_path"].endswith("evidence_notes.md")
    assert "path" not in evidence

    plan = tool_by_name["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": audit["data_audit"],
            "evidence_notes": evidence["evidence_notes"],
        }
    )
    assert plan["modeling_plan"]["selected_model"] == "DeepAgent generated model"
    assert plan["modeling_report_path"].endswith("modeling_report.md")
    assert "path" not in plan

    experiment = tool_by_name["run_experiment"].invoke(
        {
            "run_id": state.run_id,
            "modeling_plan": plan["modeling_plan"],
            "data_files": [str(data)],
        }
    )
    assert experiment["experiment_result"]["execution_status"] == "not_run"
    assert experiment["experiment_result"]["script_generated"] is True
    assert "deferred" in experiment["experiment_result"]["reproducibility_notes"]
    assert experiment["experiment_result"]["code_path"] == experiment["code_path"]
    assert experiment["result_paths"]
    assert experiment["figure_paths"] == []

    paper = tool_by_name["draft_competition_paper"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": audit["data_audit"],
            "modeling_plan": plan["modeling_plan"],
            "experiment_result": experiment["experiment_result"],
            "evidence_notes": evidence["evidence_notes"],
        }
    )
    assert paper["paper_draft"]["markdown_path"] == paper["paper_markdown_path"]
    assert paper["paper_draft"]["latex_path"] == paper["paper_tex_path"]
    assert "markdown_path" not in paper
    assert "latex_path" not in paper

    review = tool_by_name["review_submission"].invoke(
        {
            "run_id": state.run_id,
            "paper_draft": paper["paper_draft"],
            "experiment_result": experiment["experiment_result"],
            "artifacts": [
                plan["modeling_report_path"],
                paper["paper_tex_path"],
                experiment["code_path"],
            ],
        }
    )
    assert review["quality_report"]["gate_name"] == "review"
    assert review["quality_report"]["passed"] is True
    assert review["review_report_path"].endswith("review_report.md")
    assert "path" not in review


def test_write_tools_raise_without_creating_missing_run_directory(tmp_path):
    store = RunStore(output_root=tmp_path)
    tool_by_name = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    with pytest.raises(FileNotFoundError):
        tool_by_name["analyze_problem"].invoke(
            {"run_id": "run_missing", "question": "建立模型"}
        )

    assert not (tmp_path / "run_missing").exists()


def test_review_submission_fails_when_core_artifacts_are_missing(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="建立模型"))
    tool_by_name = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    result = tool_by_name["review_submission"].invoke(
        {
            "run_id": state.run_id,
            "paper_draft": {},
            "experiment_result": {},
            "artifacts": [],
        }
    )

    assert result["quality_report"]["gate_name"] == "review"
    assert result["quality_report"]["passed"] is False
    assert result["quality_report"]["required_fixes"]
    assert (store.run_dir(state.run_id) / "review_report.md").exists()


def test_retrieve_evidence_warns_when_online_search_requested(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="建立模型"))
    tool_by_name = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    result = tool_by_name["retrieve_evidence"].invoke(
        {
            "run_id": state.run_id,
            "query": "建模依据",
            "reference_files": [],
            "allow_online_search": True,
        }
    )

    assert result["warnings"] == [
        "online search is not implemented in this local tool slice"
    ]


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
    saved_state = store.load_state(state.run_id)
    artifact_by_name = {artifact.name: artifact for artifact in saved_state.artifacts}
    assert {"run.json", "final_synthesis.md"}.issubset(artifact_by_name)
    assert artifact_by_name["final_synthesis.md"].kind == "markdown"
    assert artifact_by_name["solve.py"].kind == "python"
    assert artifact_by_name["paper.tex"].kind == "latex"
    assert artifact_by_name["run.json"].kind == "json"
    assert saved_state.quality_reports
    assert saved_state.quality_reports[-1].gate_name == "submission"
