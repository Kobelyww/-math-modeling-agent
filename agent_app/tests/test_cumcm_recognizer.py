from agent_app.domain.contracts import SubproblemType
from agent_app.workflow_packs.cumcm.recognizer import recognize_subproblems
from agent_app.workflow_packs.cumcm.taxonomy import classify_subproblem


def test_recognizer_detects_four_b_problem_subproblems():
    text = """
    B 题 生产过程中的决策问题
    问题1：供应商声称次品率不会超过标称值，请设计抽样检测方案。
    问题2：已知两种零配件和成品次品率，请作出检测和拆解决策。
    问题3：对 m 道工序、n 个零配件，重复问题2，给出多工序决策方案。
    问题4：假设次品率均通过抽样检测得到，请重新完成问题2和问题3。
    """

    subproblems = recognize_subproblems(text)

    assert [item.subproblem_id for item in subproblems] == ["q1", "q2", "q3", "q4"]
    assert subproblems[0].primary_type == SubproblemType.SAMPLING_TEST
    assert subproblems[1].primary_type == SubproblemType.OPTIMIZATION
    assert subproblems[3].primary_type == SubproblemType.STATISTICS
    assert subproblems[3].dependencies == ["q2", "q3"]


def test_recognizer_handles_non_four_question_problem():
    text = "问题1：建立预测模型。问题2：对预测结果进行综合评价。"

    subproblems = recognize_subproblems(text)

    assert [item.subproblem_id for item in subproblems] == ["q1", "q2"]
    assert subproblems[0].primary_type == SubproblemType.PREDICTION
    assert subproblems[1].primary_type == SubproblemType.EVALUATION


def test_recognizer_handles_pdf_extracted_question_headings_without_colons():
    text = """
    请建立数学模型，解决以下问题：
    问题1  供应商声称次品率不会超过标称值，请设计抽样检测方案。
    问题2  已知两种零配件和成品次品率，请作出检测和拆解决策。
    问题3  对 m 道工序、n 个零配件，已知零配件、半成品和成品的次品率，重复问题
    2，给出生产过程的决策方案。
    问题4  假设问题2 和问题3 中零配件、半成品和成品的次品率均是通过抽样检测方法得到的。
    """

    subproblems = recognize_subproblems(text)

    assert [item.subproblem_id for item in subproblems] == ["q1", "q2", "q3", "q4"]
    assert subproblems[2].dependencies == ["q2"]
    assert subproblems[3].dependencies == ["q2", "q3"]


def test_classifier_prioritizes_sampling_over_generic_statistics():
    assert classify_subproblem("在95%的信度下认定次品率超过标称值").primary == SubproblemType.SAMPLING_TEST


def test_recognizer_handles_chinese_question_numbers():
    text = "问题一：建立预测模型。问题二：进行路径网络优化。"

    subproblems = recognize_subproblems(text)

    assert [item.subproblem_id for item in subproblems] == ["q1", "q2"]
    assert subproblems[0].primary_type == SubproblemType.PREDICTION
    assert subproblems[1].primary_type == SubproblemType.GRAPH_NETWORK


def test_recognizer_falls_back_to_single_analysis_problem():
    subproblems = recognize_subproblems("分析影响因素并给出建议。")

    assert [item.subproblem_id for item in subproblems] == ["q1"]
    assert subproblems[0].primary_type == SubproblemType.ANALYSIS
    assert subproblems[0].expected_outputs == ["results/q1_result.csv"]
