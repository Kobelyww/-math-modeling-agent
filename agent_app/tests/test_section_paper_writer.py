from agent_app.domain.models import RunSpec
from agent_app.services.paper_sections import REQUIRED_SECTION_FILES, section_path
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


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
