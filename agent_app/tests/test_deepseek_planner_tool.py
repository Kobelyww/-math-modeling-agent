import json

from agent_app.domain.models import RunSpec
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


class FakeGenerationService:
    def __init__(self):
        self.calls = []

    def generate_json(self, role, messages):
        assert role == "modeling_planner"
        self.calls.append(("json", messages))
        combined = json.dumps(messages, ensure_ascii=False)
        assert "problem_spec.json" in combined
        assert "tables.json" in combined
        return {
            "selected_model": "DeepSeek generated plan",
            "subproblem_plans": [{"id": "q1", "title": "抽样检测", "result_file": "results/q1.csv"}],
            "experiment_conclusion_links": ["q1 -> 论文结论：抽样检测方案；关系：支撑"],
        }

    def generate_markdown(self, role, messages):
        assert role == "modeling_planner"
        self.calls.append(("markdown", messages))
        return "# Modeling Plan\n\nDeepSeek generated modeling report."


def test_plan_model_uses_deepseek_generation_for_b_problem(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="生产过程中的决策问题 零配件 拆解"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "problem_spec.json").write_text('{"background":"生产过程中的决策问题"}', encoding="utf-8")
    (run_dir / "tables.json").write_text('{"tables":[{"title":"表1"}]}', encoding="utf-8")
    generation_service = FakeGenerationService()
    tools = {
        tool.name: tool
        for tool in make_competition_tools(
            run_store=store,
            generation_service=generation_service,
        )
    }

    result = tools["plan_model"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": {"background": "生产过程中的决策问题 零配件 拆解"},
            "data_audit": {},
            "evidence_notes": [],
        }
    )

    assert result["modeling_plan"]["selected_model"] == "DeepSeek generated plan"
    assert (run_dir / "model_plan.json").exists()
    report = (run_dir / "modeling_report.md").read_text(encoding="utf-8")
    assert "DeepSeek generated modeling report" in report
    assert [kind for kind, _ in generation_service.calls] == ["json", "markdown"]
