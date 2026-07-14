from pathlib import Path

from agent_app.domain.contracts import ProjectType, SubproblemType
from agent_app.workflow_packs.cumcm.problem_builder import build_cumcm_problem_contract


def test_build_cumcm_problem_contract_detects_title_year_and_tables():
    text = """
    2024 年高教社杯全国大学生数学建模竞赛题目
    B 题 生产过程中的决策问题
    问题1：设计抽样检测方案。
    问题2：作出生产过程检测和拆解决策。
    """
    tables = [{"id": "table_1", "title": "表1 企业在生产中遇到的情况"}]

    contract = build_cumcm_problem_contract(text, source_text_path=Path("question.md"), tables=tables, figures=[])

    assert contract.project_type == ProjectType.CUMCM
    assert contract.year == "2024"
    assert contract.title == "B 题 生产过程中的决策问题"
    assert [item.subproblem_id for item in contract.subproblems] == ["q1", "q2"]
    assert contract.subproblems[0].primary_type == SubproblemType.SAMPLING_TEST
    assert "paper.md" in contract.required_deliverables
