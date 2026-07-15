import json

from agent_app.domain.models import RunOptions, RunSpec
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools
from agent_app.workflow_packs.cumcm.routing import BENCHMARK_2024_B_ID


class FakeFullChainGenerationService:
    def generate_json(self, role, messages):
        if role == "modeling_planner":
            return {
                "selected_model": "DeepSeek generated B problem model",
                "subproblem_plans": [
                    {"id": "q1", "title": "抽样检测", "result_file": "results/q1.csv"},
                    {"id": "q2", "title": "表1决策", "result_file": "results/q2.csv"},
                    {"id": "q3", "title": "表2决策", "result_file": "results/q3.csv"},
                    {"id": "q4", "title": "抽样不确定性", "result_file": "results/q4.csv"},
                ],
                "experiment_conclusion_links": ["q1-q4 -> 论文结论：四个子问题均有结果支撑；关系：支撑"],
            }
        return {"passed": True, "required_fixes": []}

    def generate_markdown(self, role, messages):
        if role == "modeling_planner":
            return (
                "# Modeling Plan\n\n"
                "生产过程中的决策问题采用 DeepSeek generated B problem model。\n\n"
                "## 问题 1\n二项抽样检测方案，输出 results/sampling_plan.csv。\n\n"
                "## 问题 2\n表1检测拆解决策，输出 results/table1_strategy_results.csv。\n\n"
                "## 问题 3\n表2装配树递归决策，输出 results/table2_tree_strategy_results.csv。\n\n"
                "## 问题 4\n抽样不确定性与敏感性分析，输出 results/sensitivity_results.csv。\n\n"
                "每个实验均说明与论文结论的支撑关系，变量、目标函数、约束和算法流程完整记录。"
                * 8
            )
        if role == "programmer":
            return (
                "```python\n"
                "import json\n"
                "from pathlib import Path\n"
                "def main():\n"
                "    subproblem_id = 'q1'\n"
                "    tables = json.loads(Path('tables.json').read_text(encoding='utf-8'))\n"
                "    out = Path('results'); out.mkdir(exist_ok=True)\n"
                "    expected_profit = 1.0\n"
                "    (out / 'q1.csv').write_text('metric,value\\nrows,' + str(len(tables.get('tables', []))) + '\\n', encoding='utf-8')\n"
                "    (out / 'sampling_plan.csv').write_text('case,n,k\\nq1,100,10\\n', encoding='utf-8')\n"
                "    (out / 'table1_strategy_results.csv').write_text('case,expected_profit\\n1,' + str(expected_profit) + '\\n', encoding='utf-8')\n"
                "    (out / 'table2_tree_strategy_results.csv').write_text('node,decision\\nroot,inspect\\n', encoding='utf-8')\n"
                "    (out / 'sensitivity_results.csv').write_text('case,confidence,strategy\\nbase,95,stable\\n', encoding='utf-8')\n"
                "    (out / 'model_equations.md').write_text('# Equations\\n二项 目标函数 约束 递归 敏感性\\n' * 80, encoding='utf-8')\n"
                "if __name__ == '__main__': main()\n"
                "```"
            )
        if role == "paper_synthesizer":
            body = (
                "# Final Paper\n\n"
                "## 摘要\n四个子问题均已回答。\n\n"
                "## 问题重述\n生产过程中的决策问题包含问题 1、问题 2、问题 3、问题 4。\n\n"
                "## 模型假设\n检测准确，成本来自题面表格。\n\n"
                "## 符号说明\n定义抽样、检测、拆解和期望利润变量。\n\n"
                "## 模型建立\n使用 results/model_equations.md 中的二项、目标函数、约束、递归和敏感性公式。\n\n"
                "## 结果分析\n引用 results/sampling_plan.csv、results/table1_strategy_results.csv、results/table2_tree_strategy_results.csv、results/sensitivity_results.csv。\n\n"
                "## 灵敏度分析\n问题 4 对抽样不确定性进行重求解。\n\n"
                "## 模型评价\n模型透明、可复现，局限是参数依赖题面估计。\n\n"
                "## 参考文献\n[1] Quality Control.\n\n"
                "## 附录\n代码见 solve.py。\n\n"
            )
            return body + ("该段补充论文论证，使正文达到审查长度要求。\n" * 120)
        if role == "latex_synthesizer":
            return "\\documentclass{article}\\begin{document}四个子问题均已回答。\\end{document}"
        if role == "paper_consistency_reviewer":
            return "# Consistency\n\n章节一致。"
        return "# Section\n\n章节内容引用了 results/q1.csv。"


def test_b_problem_full_chain_uses_structured_tables_and_sections(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(
        RunSpec(
            question="生产过程中的决策问题 零配件 拆解",
            options=RunOptions(
                workflow_mode="benchmark",
                benchmark_id=BENCHMARK_2024_B_ID,
            ),
        )
    )
    run_dir = store.run_dir(state.run_id)
    (run_dir / "tables.json").write_text('{"tables":[{"title":"表1","rows":[["1","10%"]]}]}', encoding="utf-8")
    tools = {
        tool.name: tool
        for tool in make_competition_tools(
            run_store=store,
            generation_service=FakeFullChainGenerationService(),
        )
    }

    plan = tools["plan_model"].invoke(
        {"run_id": state.run_id, "problem_brief": {"background": state.spec.question}, "data_audit": {}, "evidence_notes": []}
    )
    experiment = tools["run_experiment"].invoke(
        {"run_id": state.run_id, "modeling_plan": plan["modeling_plan"], "data_files": []}
    )
    paper = tools["draft_competition_paper"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": {},
            "data_audit": {},
            "modeling_plan": plan["modeling_plan"],
            "experiment_result": experiment["experiment_result"],
            "evidence_notes": [],
        }
    )
    review = tools["review_submission"].invoke(
        {"run_id": state.run_id, "paper_draft": paper["paper_draft"], "experiment_result": experiment["experiment_result"], "artifacts": []}
    )

    assert (run_dir / "tables.json").exists()
    assert (run_dir / "contracts" / "problem_contract.json").exists()
    assert (run_dir / "contracts" / "models" / "q1.json").exists()
    assert (run_dir / "contracts" / "experiments" / "q4.json").exists()
    assert (run_dir / "results" / "q1_sampling_plan.csv").exists()
    assert (run_dir / "results" / "q2_table1_decisions.csv").exists()
    assert (run_dir / "results" / "q3_table2_tree_decisions.csv").exists()
    assert (run_dir / "results" / "q4_uncertainty_re_solve.csv").exists()
    assert (run_dir / "results" / "parameter_audit.json").exists()
    assert "0.35" not in (run_dir / "solve.py").read_text(encoding="utf-8")
    assert "DeepSeek generated B problem model" not in (run_dir / "modeling_report.md").read_text(encoding="utf-8")
    assert (run_dir / "claims" / "claim_map.json").exists()
    assert (run_dir / "sections" / "08_result_analysis.md").exists()
    claim_map = json.loads((run_dir / "claims" / "claim_map.json").read_text(encoding="utf-8"))
    assert len(claim_map) == 4
    assert review["subagent_review_paths"]
