from __future__ import annotations

import json
import subprocess
import sys
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
    assert len(problem["problem_brief"]["subproblems"]) == 1
    assert problem["problem_brief"]["subproblems"][0]["id"] == "q1"
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
    assert plan["modeling_plan"]["selected_model"] == "动态子问题 baseline 建模工作流"
    assert plan["modeling_plan"]["workflow_type"] == "dynamic_subproblem_workflow"
    assert plan["modeling_plan"]["subproblem_plans"][0]["id"] == "q1"
    assert plan["modeling_plan"]["experiment_conclusion_links"]
    assert "论文结论" in plan["modeling_plan"]["experiment_conclusion_links"][0]
    assert "关系" in plan["modeling_plan"]["experiment_conclusion_links"][0]
    assert plan["modeling_report_path"].endswith("modeling_report.md")
    modeling_report = Path(plan["modeling_report_path"]).read_text(encoding="utf-8")
    assert "Experiment-to-Conclusion Mapping" in modeling_report
    assert "论文结论" in modeling_report
    assert "path" not in plan

    experiment = tool_by_name["run_experiment"].invoke(
        {
            "run_id": state.run_id,
            "modeling_plan": plan["modeling_plan"],
            "data_files": [str(data)],
        }
    )
    assert experiment["experiment_result"]["execution_status"] == "success"
    assert experiment["experiment_result"]["script_generated"] is True
    assert "subproblem_summary.csv" in experiment["experiment_result"]["reproducibility_notes"]
    assert experiment["experiment_result"]["code_path"] == experiment["code_path"]
    assert any(path.endswith("subproblem_summary.csv") for path in experiment["result_paths"])
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
    assert review["quality_report"]["required_fixes"] == []
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


def test_review_submission_uses_run_directory_artifacts_when_model_argument_is_empty(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="建立模型"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text(
        "# Modeling Plan\n\n"
        + "真实模型说明，包含变量、目标函数、约束、实验设计和论文结论映射。\n" * 80,
        encoding="utf-8",
    )
    (run_dir / "solve.py").write_text(
        "def expected_profit():\n"
        "    return 1.0\n\n"
        "def main():\n"
        "    print(expected_profit())\n",
        encoding="utf-8",
    )
    (run_dir / "paper.tex").write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Model}\n"
        "Real paper content.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
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
    assert result["quality_report"]["passed"] is True
    assert result["quality_report"]["required_fixes"] == []


def test_b_problem_tools_generate_executable_model_code_and_paper(tmp_path):
    question = (
        "生产过程中的决策问题。企业购买零配件 1 和零配件 2 装配成成品，"
        "需要决定是否检测零配件、是否检测成品、是否拆解不合格成品，"
        "并结合表 1 与表 2 的次品率、检测成本、拆解费用和调换损失完成建模。"
    )
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question=question))
    tool_by_name = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    problem = tool_by_name["analyze_problem"].invoke(
        {"run_id": state.run_id, "question": question}
    )
    subproblems = problem["problem_brief"]["subproblems"]
    assert [item["id"] for item in subproblems] == ["q1", "q2", "q3", "q4"]
    assert all(item["result_file"] for item in subproblems)

    plan = tool_by_name["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )
    experiment = tool_by_name["run_experiment"].invoke(
        {
            "run_id": state.run_id,
            "modeling_plan": plan["modeling_plan"],
            "data_files": [],
        }
    )
    paper = tool_by_name["draft_competition_paper"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "modeling_plan": plan["modeling_plan"],
            "experiment_result": experiment["experiment_result"],
            "evidence_notes": [],
        }
    )

    modeling_report = Path(plan["modeling_report_path"]).read_text(encoding="utf-8")
    solve_code = Path(experiment["code_path"]).read_text(encoding="utf-8")
    paper_markdown = Path(paper["paper_markdown_path"]).read_text(encoding="utf-8")
    run_dir = store.run_dir(state.run_id)
    decision_csv = run_dir / "results" / "q2_table1_decisions.csv"
    expected_result_files = {
        "q1_sampling_plan.csv",
        "q2_table1_decisions.csv",
        "q3_table2_tree_decisions.csv",
        "q4_uncertainty_re_solve.csv",
        "parameter_audit.json",
    }

    assert plan["modeling_plan"]["selected_model"] == "二项抽样 + 0-1检测拆解决策优化"
    assert plan["modeling_plan"]["workflow_type"] == "cumcm_b_problem_contract_workflow"
    assert {item["id"] for item in plan["modeling_plan"]["subproblem_plans"]} == {"q1", "q2", "q3", "q4"}
    assert (run_dir / "contracts" / "problem_contract.json").exists()
    for subproblem_id in ["q1", "q2", "q3", "q4"]:
        assert (run_dir / "contracts" / "models" / f"{subproblem_id}.json").exists()
        assert (run_dir / "contracts" / "experiments" / f"{subproblem_id}.json").exists()
    problem_contract = json.loads((run_dir / "contracts" / "problem_contract.json").read_text(encoding="utf-8"))
    assert [item["subproblem_id"] for item in problem_contract["subproblems"]] == ["q1", "q2", "q3", "q4"]
    assert "二项" in modeling_report
    assert "q2_table1_decisions.csv" in modeling_report
    assert "问题 1" in modeling_report
    assert "问题 4" in modeling_report
    assert "DeepAgent generated model" not in modeling_report
    assert experiment["experiment_result"]["execution_status"] == "success"
    assert decision_csv.exists()
    assert expected_result_files.issubset(
        {Path(path).name for path in experiment["experiment_result"]["result_paths"]}
    )
    for filename in expected_result_files:
        assert (store.run_dir(state.run_id) / "results" / filename).exists()
    assert "DeepAgent competition experiment placeholder" not in solve_code
    assert "0.35" not in solve_code
    rerun = subprocess.run(
        [sys.executable, "solve.py"],
        cwd=run_dir,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert rerun.returncode == 0, rerun.stderr
    audit = json.loads((run_dir / "results" / "parameter_audit.json").read_text(encoding="utf-8"))
    assert audit["unexplained_constants"] == []
    assert "expected_profit" in (run_dir / "results" / "q2_table1_decisions.csv").read_text(encoding="utf-8")
    assert "final_product" in (run_dir / "results" / "q3_table2_tree_decisions.csv").read_text(encoding="utf-8")
    assert "strategy_changed" in (run_dir / "results" / "q4_uncertainty_re_solve.csv").read_text(encoding="utf-8")
    assert (run_dir / "claims" / "claim_map.json").exists()
    assert (run_dir / "sections" / "08_result_analysis.md").exists()
    claim_map = json.loads((run_dir / "claims" / "claim_map.json").read_text(encoding="utf-8"))
    assert {claim["claim_id"] for claim in claim_map} == {
        "claim_q1_sampling_plan",
        "claim_q2_table1_decisions",
        "claim_q3_tree_decisions",
        "claim_q4_uncertainty_limits",
    }
    assert "## 摘要" in paper_markdown
    assert "## 模型建立与求解" in paper_markdown
    assert "results/q1_sampling_plan.csv" in paper_markdown
    assert "results/q3_table2_tree_decisions.csv" in paper_markdown
    assert "生产过程中的决策问题" in paper_markdown


def test_review_submission_runs_three_subagent_reviews_for_b_problem_contract_workflow(tmp_path):
    question = (
        "生产过程中的决策问题。企业购买零配件 1 和零配件 2 装配成成品，"
        "需要决定是否检测零配件、是否检测成品、是否拆解不合格成品，"
        "并结合表 1 与表 2 的次品率、检测成本、拆解费用和调换损失完成建模。"
    )
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question=question))
    tool_by_name = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    problem = tool_by_name["analyze_problem"].invoke(
        {"run_id": state.run_id, "question": question}
    )
    plan = tool_by_name["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )
    experiment = tool_by_name["run_experiment"].invoke(
        {
            "run_id": state.run_id,
            "modeling_plan": plan["modeling_plan"],
            "data_files": [],
        }
    )
    paper = tool_by_name["draft_competition_paper"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "modeling_plan": plan["modeling_plan"],
            "experiment_result": experiment["experiment_result"],
            "evidence_notes": [],
        }
    )

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
    run_dir = store.run_dir(state.run_id)

    assert review["quality_report"]["gate_name"] == "review"
    assert review["quality_report"]["passed"] is True
    assert not any("极小样本量" in fix for fix in review["quality_report"]["required_fixes"])
    assert not any("model_equations.md" in fix for fix in review["quality_report"]["required_fixes"])
    assert "reviews/model_review.md" in review["subagent_review_paths"]
    assert "reviews/experiment_review.md" in review["subagent_review_paths"]
    assert "reviews/paper_review.md" in review["subagent_review_paths"]
    for relative_path in review["subagent_review_paths"]:
        content = (run_dir / relative_path).read_text(encoding="utf-8")
        assert "## 结论" in content
        assert "## 必须修改" in content
    summary = Path(review["review_report_path"]).read_text(encoding="utf-8")
    assert "三子智能体质量审查总评" in summary
    assert "模型审查子智能体" in summary
    assert "实验审查子智能体" in summary
    assert "论文审查子智能体" in summary
    assert "通过" in summary


def test_generic_problem_dynamically_identifies_all_subproblems_and_runs_baselines(tmp_path):
    question = (
        "某城市需要建立交通管理模型。"
        "问题1：预测未来七天各路段交通流量。"
        "问题2：在道路容量约束下优化信号灯配时，使平均等待时间最小。"
        "问题3：基于问题1和问题2的结果，分析容量扰动下方案是否稳健。"
    )
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question=question))
    tool_by_name = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    problem = tool_by_name["analyze_problem"].invoke(
        {"run_id": state.run_id, "question": question}
    )
    subproblems = problem["problem_brief"]["subproblems"]

    assert [item["id"] for item in subproblems] == ["q1", "q2", "q3"]
    assert [item["problem_type"] for item in subproblems] == [
        "prediction",
        "optimization",
        "sensitivity",
    ]
    assert subproblems[2]["dependencies"] == ["q1", "q2"]

    plan = tool_by_name["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )
    experiment = tool_by_name["run_experiment"].invoke(
        {
            "run_id": state.run_id,
            "modeling_plan": plan["modeling_plan"],
            "data_files": [],
        }
    )
    paper = tool_by_name["draft_competition_paper"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "modeling_plan": plan["modeling_plan"],
            "experiment_result": experiment["experiment_result"],
            "evidence_notes": [],
        }
    )

    run_dir = store.run_dir(state.run_id)
    assert experiment["experiment_result"]["execution_status"] == "success"
    assert (run_dir / "results" / "q1_result.csv").exists()
    assert (run_dir / "results" / "q2_result.csv").exists()
    assert (run_dir / "results" / "q3_result.csv").exists()
    assert (run_dir / "results" / "subproblem_summary.csv").exists()
    assert "subproblem_id" in (run_dir / "results" / "q1_result.csv").read_text(encoding="utf-8")
    paper_markdown = Path(paper["paper_markdown_path"]).read_text(encoding="utf-8")
    assert "共识别 3 个子问题" in paper_markdown
    assert "results/q3_result.csv" in paper_markdown


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
