import pytest

from agent_app.deepagent.runner import CompetitionPaperRunner
from agent_app.domain.models import RunSpec, RunStatus
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools
from agent_app.web.paper_stream import EventDrivingCoordinator


def test_failed_review_prevents_completed_package(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="生产过程中的决策问题 零配件 拆解"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("生产过程中的决策问题\n", encoding="utf-8")
    (run_dir / "solve.py").write_text("def main():\n    print('shallow')\n", encoding="utf-8")
    (run_dir / "paper.tex").write_text("\\documentclass{article}\\begin{document}shallow\\end{document}", encoding="utf-8")
    (run_dir / "paper.md").write_text("# 生产过程中的决策问题\n\n浅层论文。", encoding="utf-8")

    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}
    review = tools["review_submission"].invoke(
        {"run_id": state.run_id, "paper_draft": {}, "experiment_result": {}, "artifacts": []}
    )

    assert review["quality_report"]["passed"] is False
    assert review["quality_report"]["required_fixes"]
    persisted = store.load_state(state.run_id)
    assert [(report.gate_name, report.passed) for report in persisted.quality_reports] == [("review", False)]
    with pytest.raises(Exception, match="质量审查未通过"):
        tools["package_submission"].invoke({"run_id": state.run_id})
    assert not (run_dir / "final_synthesis.md").exists()


def test_package_blocks_incomplete_staged_solution_contract(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="问题1：建立模型。"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("完整建模报告" * 80, encoding="utf-8")
    (run_dir / "solve.py").write_text("def main(): pass\n", encoding="utf-8")
    (run_dir / "paper.tex").write_text("\\documentclass{ctexart}\\begin{document}\\section{摘要} 文本\\end{document}", encoding="utf-8")
    (run_dir / "review_report.md").write_text("# Review\n", encoding="utf-8")
    (run_dir / "final_synthesis.md").write_text("# Final\n", encoding="utf-8")
    (run_dir / "run.json").write_text("{}", encoding="utf-8")
    store.save_state(state)
    (run_dir / "staged_paper_manifest.json").write_text(
        '{"subproblem_contract_paths":["subproblems/q1/solution_contract.json"]}',
        encoding="utf-8",
    )
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    with pytest.raises(RuntimeError) as exc:
        tools["package_submission"].invoke({"run_id": state.run_id})

    assert "质量审查未通过" in str(exc.value) or "staged" in str(exc.value)


def test_review_blocks_staged_result_csv_without_objective_or_real_result(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="问题1：建立模型。"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("完整建模报告" * 80, encoding="utf-8")
    (run_dir / "solve.py").write_text(
        "def main():\n"
        "    subproblem_id = 'q1'\n"
        "    print(subproblem_id)\n",
        encoding="utf-8",
    )
    (run_dir / "paper.tex").write_text(
        "\\documentclass{ctexart}\\begin{document}\\section{摘要} 文本\\end{document}",
        encoding="utf-8",
    )
    result_path = run_dir / "subproblems" / "q1" / "result.csv"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(
        "case,decision\n"
        "base,solved_baseline\n",
        encoding="utf-8",
    )
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    review = tools["review_submission"].invoke(
        {"run_id": state.run_id, "paper_draft": {}, "experiment_result": {}, "artifacts": []}
    )

    assert review["quality_report"]["passed"] is False
    assert any(
        "subproblems/q1/result.csv 缺少目标值、利润或估计字段" in fix
        for fix in review["quality_report"]["required_fixes"]
    )
    assert any(
        "subproblems/q1/result.csv 仍是 baseline-only 结果" in fix
        for fix in review["quality_report"]["required_fixes"]
    )


def test_review_requires_exact_staged_result_value_columns(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="问题1：建立模型。"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("完整建模报告" * 80, encoding="utf-8")
    (run_dir / "solve.py").write_text(
        "def main():\n"
        "    subproblem_id = 'q1'\n"
        "    print(subproblem_id)\n",
        encoding="utf-8",
    )
    (run_dir / "paper.tex").write_text(
        "\\documentclass{ctexart}\\begin{document}\\section{摘要} 文本\\end{document}",
        encoding="utf-8",
    )
    result_path = run_dir / "subproblems" / "q1" / "result.csv"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(
        "case,decision,objective_value_note\n"
        "base,accept,only a note\n",
        encoding="utf-8",
    )
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    review = tools["review_submission"].invoke(
        {"run_id": state.run_id, "paper_draft": {}, "experiment_result": {}, "artifacts": []}
    )

    assert any(
        "subproblems/q1/result.csv 缺少目标值、利润或估计字段" in fix
        for fix in review["quality_report"]["required_fixes"]
    )


def test_review_submission_reports_invalid_staged_manifest(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="问题1：建立模型。"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("完整建模报告" * 80, encoding="utf-8")
    (run_dir / "solve.py").write_text(
        "def main():\n"
        "    subproblem_id = 'q1'\n"
        "    print(subproblem_id)\n",
        encoding="utf-8",
    )
    (run_dir / "paper.tex").write_text(
        "\\documentclass{ctexart}\\begin{document}\\section{摘要} 文本\\end{document}",
        encoding="utf-8",
    )
    (run_dir / "staged_paper_manifest.json").write_bytes(b"\xff\xfe\xff")
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    review = tools["review_submission"].invoke(
        {"run_id": state.run_id, "paper_draft": {}, "experiment_result": {}, "artifacts": []}
    )

    assert any(
        fix.startswith("无法读取 staged_paper_manifest.json:")
        for fix in review["quality_report"]["required_fixes"]
    )


def test_review_submission_reports_unreadable_staged_result_csv(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="问题1：建立模型。"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("完整建模报告" * 80, encoding="utf-8")
    (run_dir / "solve.py").write_text(
        "def main():\n"
        "    subproblem_id = 'q1'\n"
        "    print(subproblem_id)\n",
        encoding="utf-8",
    )
    (run_dir / "paper.tex").write_text(
        "\\documentclass{ctexart}\\begin{document}\\section{摘要} 文本\\end{document}",
        encoding="utf-8",
    )
    result_path = run_dir / "subproblems" / "q1" / "result.csv"
    result_path.parent.mkdir(parents=True)
    result_path.write_bytes(b"\xff\xfe\xff")
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    review = tools["review_submission"].invoke(
        {"run_id": state.run_id, "paper_draft": {}, "experiment_result": {}, "artifacts": []}
    )

    assert any(
        "subproblems/q1/result.csv 无法读取" in fix
        for fix in review["quality_report"]["required_fixes"]
    )


class FakeTool:
    def __init__(self, result=None):
        self.result = result
        self.calls = 0

    def invoke(self, payload):
        self.calls += 1
        if callable(self.result):
            return self.result(payload)
        return self.result


def test_event_driving_coordinator_skips_package_when_review_fails(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="建立模型"))
    events = []
    coordinator = EventDrivingCoordinator(store, events.append)
    package_tool = FakeTool({"final_synthesis_path": "should-not-run.md"})
    coordinator.tools = {
        "ingest_inputs": FakeTool({"inputs_manifest": {}}),
        "analyze_problem": FakeTool({"problem_brief": {}}),
        "audit_data": FakeTool({"data_audit": {}}),
        "retrieve_evidence": FakeTool({"evidence_notes": []}),
        "plan_model": FakeTool({"modeling_plan": {}, "modeling_report_path": "modeling_report.md"}),
        "run_experiment": FakeTool({"experiment_result": {}, "code_path": "solve.py"}),
        "draft_competition_paper": FakeTool({"paper_draft": {}, "paper_tex_path": "paper.tex"}),
        "review_submission": FakeTool(
            {
                "quality_report": {
                    "passed": False,
                    "score": 0.0,
                    "findings": ["shallow"],
                    "required_fixes": ["rewrite"],
                },
                "review_report_path": "review_report.md",
            }
        ),
        "package_submission": package_tool,
    }

    result = coordinator.invoke(
        {
            "run_id": state.run_id,
            "question": "建立模型",
            "data_files": [],
            "reference_files": [],
        }
    )

    assert result["status"] == "partial"
    assert package_tool.calls == 0
    assert any(event.get("type") == "revise_required" for event in events)


def test_runner_marks_partial_when_coordinator_requests_revision(tmp_path):
    class PartialCoordinator:
        def __init__(self, run_store, settings=None, event_handler=None):
            self.run_store = run_store

        def invoke(self, payload):
            run_dir = self.run_store.run_dir(payload["run_id"])
            (run_dir / "modeling_report.md").write_text("model", encoding="utf-8")
            (run_dir / "solve.py").write_text("print('ok')", encoding="utf-8")
            (run_dir / "paper.tex").write_text("paper", encoding="utf-8")
            return {"status": "partial", "messages": [{"content": "review failed"}]}

    runner = CompetitionPaperRunner(
        output_root=tmp_path / "runs",
        coordinator_factory=PartialCoordinator,
    )

    result = runner.run(RunSpec(question="建立模型"))

    assert result.status == RunStatus.PARTIAL
    assert result.summary == "review failed"
