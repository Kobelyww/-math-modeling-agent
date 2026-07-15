from agent_app.domain.models import RunSpec
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


class FailingGenerationService:
    def __init__(self):
        self.calls = []

    def generate_json(self, role, messages):
        self.calls.append(("json", messages))
        raise AssertionError("plan_model should not use generation_service for production CUMCM routing")

    def generate_markdown(self, role, messages):
        self.calls.append(("markdown", messages))
        raise AssertionError("plan_model should not use generation_service for production CUMCM routing")


def test_plan_model_keeps_contract_first_route_when_generation_service_is_injected(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="生产过程中的决策问题 零配件 拆解"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "problem_spec.json").write_text('{"background":"生产过程中的决策问题"}', encoding="utf-8")
    (run_dir / "tables.json").write_text('{"tables":[{"title":"表1"}]}', encoding="utf-8")
    generation_service = FailingGenerationService()
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

    assert result["modeling_plan"]["selected_model"] == "CUMCM dynamic contract workflow"
    assert result["modeling_plan"]["workflow_type"] == "generic_cumcm_contract_workflow"
    assert result["problem_contract_path"].endswith("contracts/problem_contract.json")
    assert result["solver_strategy_path"].endswith("contracts/solver_strategies.json")
    assert (run_dir / "model_plan.json").exists()
    assert (run_dir / "contracts" / "problem_contract.json").exists()
    assert (run_dir / "contracts" / "solver_strategies.json").exists()
    assert generation_service.calls == []
