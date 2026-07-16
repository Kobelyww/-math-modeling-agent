from agent_app.domain.models import RunOptions, RunSpec
from agent_app.services.paper_sections import REQUIRED_SECTION_FILES, section_path
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools
from agent_app.workflow_packs.cumcm.routing import BENCHMARK_2024_B_ID


def test_required_section_files_are_chapter_level():
    assert "00_abstract.md" in REQUIRED_SECTION_FILES
    assert "04_model_building.md" in REQUIRED_SECTION_FILES
    assert "09_appendix.md" in REQUIRED_SECTION_FILES


def test_section_path_uses_paper_sections_directory(tmp_path):
    assert section_path(tmp_path, "04_model_building.md") == tmp_path / "paper" / "sections" / "04_model_building.md"


class FakeWriterService:
    def __init__(self):
        self.roles = []

    def generate_markdown(self, role, messages):
        self.roles.append(role)
        if role == "paper_synthesizer":
            return "# Final Paper\n\nMerged section text."
        if role == "latex_synthesizer":
            return "\\documentclass{article}\n\\begin{document}\nMerged section text.\n\\end{document}\n"
        if role == "paper_consistency_reviewer":
            return "# Consistency\n\nAll sections cite artifacts."
        return "# Section\n\nUses cited artifacts."


def test_draft_competition_paper_writes_section_artifacts(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="建立模型"))
    writer = FakeWriterService()
    tools = {
        tool.name: tool
        for tool in make_competition_tools(
            run_store=store,
            generation_service=writer,
        )
    }

    result = tools["draft_competition_paper"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": {"subproblems": [{"id": "q1", "title": "抽样检测"}]},
            "data_audit": {},
            "modeling_plan": {"subproblem_plans": [{"id": "q1", "title": "抽样检测", "result_file": "results/q1.csv"}]},
            "experiment_result": {"result_paths": ["results/q1.csv"]},
            "evidence_notes": [],
        }
    )

    run_dir = store.run_dir(state.run_id)
    assert (run_dir / "paper" / "sections" / "00_abstract.md").exists()
    assert (run_dir / "paper" / "sections" / "04_model_building.md").exists()
    assert (run_dir / "paper_consistency_report.md").exists()
    assert "Merged section text" in (run_dir / "paper.md").read_text(encoding="utf-8")
    assert result["paper_markdown_path"].endswith("paper.md")
    assert writer.roles[-2:] == ["paper_synthesizer", "latex_synthesizer"]


def test_draft_competition_paper_generic_sections_are_user_facing(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="问题1：建立评价模型。"))
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    problem = tools["analyze_problem"].invoke({"run_id": state.run_id, "question": state.spec.question})
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )
    experiment = tools["run_experiment"].invoke(
        {"run_id": state.run_id, "modeling_plan": plan["modeling_plan"], "data_files": []}
    )
    paper = tools["draft_competition_paper"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "modeling_plan": plan["modeling_plan"],
            "experiment_result": experiment["experiment_result"],
            "evidence_notes": [],
        }
    )

    text = (store.run_dir(state.run_id) / "paper.md").read_text(encoding="utf-8")

    assert "Claim-Aware Section Context" not in text
    assert "暂无已支持结论" not in text
    assert "## Claims" not in text
    assert "## 摘要" in text
    assert "## 结果分析" in text
    assert "claim_q1_result" in text
    assert paper["paper_section_paths"]


def test_draft_competition_paper_with_writer_service_still_writes_generic_claim_artifacts(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="问题1：建立评价模型。"))
    writer = FakeWriterService()
    tools = {
        tool.name: tool
        for tool in make_competition_tools(
            run_store=store,
            generation_service=writer,
        )
    }

    problem = tools["analyze_problem"].invoke({"run_id": state.run_id, "question": state.spec.question})
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )
    experiment = tools["run_experiment"].invoke(
        {"run_id": state.run_id, "modeling_plan": plan["modeling_plan"], "data_files": []}
    )
    paper = tools["draft_competition_paper"].invoke(
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
    text = (run_dir / "paper.md").read_text(encoding="utf-8")
    latex = (run_dir / "paper.tex").read_text(encoding="utf-8")

    assert "Merged section text" not in text
    assert "Claim-Aware Section Context" not in text
    assert "## 结果分析" in text
    assert "claim_q1_result" in text
    assert (run_dir / "paper" / "sections" / "00_abstract.md").exists()
    assert (run_dir / "paper_consistency_report.md").exists()
    assert (run_dir / "paper" / "writer_synthesized.md").exists()
    assert (run_dir / "paper" / "writer_synthesized.tex").exists()
    assert (run_dir / "claims" / "claim_map.json").exists()
    assert (run_dir / "claims" / "claim_gate_report.json").exists()
    assert (run_dir / "trace" / "gate_reports" / "claim_gate.json").exists()
    assert writer.roles[-2:] == ["paper_synthesizer", "latex_synthesizer"]
    assert paper["claim_map_path"].endswith("claims/claim_map.json")
    assert paper["claim_gate_report_path"].endswith("claims/claim_gate_report.json")
    assert paper["paper_consistency_report_path"].endswith("paper_consistency_report.md")
    for section_name in (
        "摘要",
        "问题重述",
        "模型假设",
        "符号说明",
        "模型建立与求解",
        "结果分析",
        "灵敏度分析",
        "模型评价",
        "参考文献",
        "附录",
    ):
        assert f"\\section{{{section_name}}}" in latex


def test_draft_competition_paper_benchmark_does_not_append_internal_section_context(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(
        RunSpec(
            question="2024 年 B 题 生产过程中的决策问题。问题1：抽样检测。问题2：检测拆解决策。",
            options=RunOptions(
                workflow_mode="benchmark",
                benchmark_id=BENCHMARK_2024_B_ID,
            ),
        )
    )
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    problem = tools["analyze_problem"].invoke({"run_id": state.run_id, "question": state.spec.question})
    plan = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "evidence_notes": [],
        }
    )
    experiment = tools["run_experiment"].invoke(
        {"run_id": state.run_id, "modeling_plan": plan["modeling_plan"], "data_files": []}
    )
    paper = tools["draft_competition_paper"].invoke(
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
    text = (run_dir / "paper.md").read_text(encoding="utf-8")

    assert "Claim-Aware Section Context" not in text
    assert "暂无已支持结论" not in text
    assert "## Claims" not in text
    assert paper["paper_section_paths"]
    assert (run_dir / "sections" / "08_result_analysis.md").exists()
