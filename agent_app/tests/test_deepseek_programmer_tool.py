from agent_app.domain.models import RunSpec
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


class FakeGenerationService:
    def __init__(self):
        self.roles = []

    def generate_markdown(self, role, messages):
        assert role in {"programmer", "code_debugger"}
        self.roles.append(role)
        return (
            "```python\n"
            "from pathlib import Path\n"
            "def main():\n"
            "    out = Path('results'); out.mkdir(exist_ok=True)\n"
            "    (out / 'q1.csv').write_text('metric,value\\nanswer,1\\n', encoding='utf-8')\n"
            "    (out / 'model_equations.md').write_text('# Equations\\n', encoding='utf-8')\n"
            "if __name__ == '__main__': main()\n"
            "```"
        )


def test_run_experiment_uses_deepseek_programmer_output(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="建立模型"))
    generation_service = FakeGenerationService()
    tools = {
        tool.name: tool
        for tool in make_competition_tools(
            run_store=store,
            generation_service=generation_service,
        )
    }

    result = tools["run_experiment"].invoke(
        {
            "run_id": state.run_id,
            "modeling_plan": {"subproblem_plans": [{"id": "q1", "result_file": "results/q1.csv"}]},
            "data_files": [],
        }
    )

    assert result["experiment_result"]["execution_status"] == "success"
    assert (store.run_dir(state.run_id) / "results" / "q1.csv").exists()
    assert generation_service.roles == ["programmer"]


class DebuggingGenerationService:
    def __init__(self):
        self.roles = []

    def generate_markdown(self, role, messages):
        self.roles.append(role)
        if role == "programmer":
            return "```python\nraise RuntimeError('boom')\n```"
        assert role == "code_debugger"
        return (
            "```python\n"
            "from pathlib import Path\n"
            "def main():\n"
            "    out = Path('results'); out.mkdir(exist_ok=True)\n"
            "    (out / 'q1.csv').write_text('metric,value\\nfixed,1\\n', encoding='utf-8')\n"
            "if __name__ == '__main__': main()\n"
            "```"
        )


def test_run_experiment_retries_once_with_code_debugger(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="建立模型"))
    generation_service = DebuggingGenerationService()
    tools = {
        tool.name: tool
        for tool in make_competition_tools(
            run_store=store,
            generation_service=generation_service,
        )
    }

    result = tools["run_experiment"].invoke(
        {
            "run_id": state.run_id,
            "modeling_plan": {"subproblem_plans": [{"id": "q1", "result_file": "results/q1.csv"}]},
            "data_files": [],
        }
    )

    assert result["experiment_result"]["execution_status"] == "success"
    assert generation_service.roles == ["programmer", "code_debugger"]
    assert "fixed" in (store.run_dir(state.run_id) / "results" / "q1.csv").read_text(encoding="utf-8")
