from __future__ import annotations

from pathlib import Path

import pytest

from agent_app.domain import SubproblemSolutionContract, SymbolDefinition


def _load_gates():
    try:
        from agent_app.evaluators import (
            evaluate_algorithm_artifact,
            evaluate_derivation_artifact,
            evaluate_staged_solution_package,
            evaluate_symbol_table,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.fail(f"staged quality gate exports are missing: {exc}")
    return (
        evaluate_derivation_artifact,
        evaluate_algorithm_artifact,
        evaluate_symbol_table,
        evaluate_staged_solution_package,
    )


def _complete_contract(**overrides: Path) -> SubproblemSolutionContract:
    paths = {
        "model_derivation_path": Path("subproblems/q1/model_derivation.md"),
        "algorithm_path": Path("subproblems/q1/algorithm.md"),
        "solver_path": Path("subproblems/q1/solver.py"),
        "result_path": Path("subproblems/q1/result.csv"),
        "result_interpretation_path": Path("subproblems/q1/result_interpretation.md"),
        "symbol_delta_path": Path("subproblems/q1/symbol_delta.json"),
        "claim_delta_path": Path("subproblems/q1/claim_delta.json"),
    }
    paths.update(overrides)
    return SubproblemSolutionContract(
        subproblem_id="q1",
        question_text="建立生产检测优化模型。",
        problem_type="optimization",
        status="complete",
        **paths,
    )


def _write_complete_artifacts(root: Path, contract: SubproblemSolutionContract) -> None:
    files = {
        contract.model_derivation_path: (
            "变量：x 表示是否执行检测，y 表示是否拆解。\n"
            "参数：c 表示检测成本，r 表示调换损失。\n"
            "参数来源：c 与 r 来自题面表格和 problem contract。\n"
            "假设：零配件状态相互独立，成本参数来自题面表格。\n"
            "目标函数：min Z = 3x + 2y\n"
            "约束：x + y <= 10, x >= 0, y >= 0\n"
            "推导说明：由成本项与检测收益项合并得到线性规划，并支撑论文结论。"
        ),
        contract.algorithm_path: (
            "算法：枚举可行检测决策并记录最优目标值。\n"
            "算法策略：枚举可行检测决策。\n"
            "输入 schema：成本参数表和约束上界。\n"
            "输出 schema：decision、objective、estimate、diagnostic。\n"
            "步骤：1. 读取参数；2. 枚举可行解；3. 输出最优目标值。\n"
            "复杂度：O(n)，搜索空间随候选决策数量线性增长。\n"
            "失败与回退：若参数缺失，则回退为待补全状态并阻断提交。\n"
        ),
        contract.solver_path: "print('solve q1')\n",
        contract.result_path: (
            "case,decision,objective,estimate,diagnostic\n"
            "base,inspect,12.5,0.91,ok\n"
        ),
        contract.result_interpretation_path: (
            "直接回答：选择 inspect 决策。\n"
            "结果表引用：subproblems/q1/result.csv。\n"
            "为什么成立：该决策在目标函数中取得最低成本。\n"
            "局限与灵敏度：成本扰动后需要复查。\n"
            "claim ID：q1-result-supported。\n"
        ),
        contract.symbol_delta_path: '{"symbols": ["x", "y", "Z"]}\n',
        contract.claim_delta_path: (
            '[{"claim_id":"q1-result-supported","section":"结果分析",'
            '"text":"inspect 决策由 result.csv 支撑",'
            '"evidence":[{"kind":"csv",'
            '"path":"subproblems/q1/result.csv",'
            '"locator":"row=1"}],'
            '"status":"supported","confidence":"high"}]\n'
        ),
    }
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def test_derivation_gate_rejects_optimization_text_without_math_structure(tmp_path):
    evaluate_derivation_artifact, _, _, _ = _load_gates()
    derivation_path = tmp_path / "model_derivation.md"
    derivation_path.write_text(
        "本节说明将选择求解方式并给出最终结果，但没有写出数学模型。",
        encoding="utf-8",
    )

    report = evaluate_derivation_artifact(derivation_path, "optimization")

    assert report.passed is False
    assert any("公式" in item for item in report.required_fixes)
    assert any("目标函数" in item for item in report.required_fixes)
    assert any("约束" in item for item in report.required_fixes)


def test_derivation_gate_requires_variables_parameters_assumptions_and_conclusion_link(tmp_path):
    evaluate_derivation_artifact, _, _, _ = _load_gates()
    derivation_path = tmp_path / "model_derivation.md"
    derivation_path.write_text(
        "目标函数：min Z = 3x + 2y\n"
        "约束：x + y <= 10\n"
        "推导说明：由成本项与检测收益项合并得到线性规划。",
        encoding="utf-8",
    )

    report = evaluate_derivation_artifact(derivation_path, "optimization")

    assert report.passed is False
    assert any("变量" in item for item in report.required_fixes)
    assert any("参数" in item for item in report.required_fixes)
    assert any("假设" in item for item in report.required_fixes)
    assert any("论文结论" in item for item in report.required_fixes)


def test_derivation_gate_requires_parameter_sources(tmp_path):
    evaluate_derivation_artifact, _, _, _ = _load_gates()
    derivation_path = tmp_path / "model_derivation.md"
    derivation_path.write_text(
        "变量：x 表示是否执行检测。\n"
        "参数：c 表示检测成本。\n"
        "假设：参数估计稳定。\n"
        "目标函数：min Z = cx\n"
        "约束：0 <= x <= 1\n"
        "推导说明：该模型支撑论文结论。",
        encoding="utf-8",
    )

    report = evaluate_derivation_artifact(derivation_path, "optimization")

    assert report.passed is False
    assert any("参数来源" in item for item in report.required_fixes)


def test_derivation_gate_rejects_statistics_text_without_formula(tmp_path):
    evaluate_derivation_artifact, _, _, _ = _load_gates()
    derivation_path = tmp_path / "model_derivation.md"
    derivation_path.write_text(
        "变量：p 表示次品率。\n"
        "参数：n 表示样本量。\n"
        "假设：样本独立同分布。\n"
        "推导说明：本统计模型支撑论文结论。",
        encoding="utf-8",
    )

    report = evaluate_derivation_artifact(derivation_path, "statistics")

    assert report.passed is False
    assert any("公式" in item for item in report.required_fixes)


def test_derivation_gate_rejects_multi_objective_text_without_formula(tmp_path):
    evaluate_derivation_artifact, _, _, _ = _load_gates()
    derivation_path = tmp_path / "model_derivation.md"
    derivation_path.write_text(
        "变量：x 表示方案选择。\n"
        "参数：c 表示成本。\n"
        "假设：各指标已经归一化。\n"
        "目标函数：同时考虑成本与稳定性。\n"
        "约束：方案必须满足预算上限。\n"
        "推导说明：该模型支撑论文结论。",
        encoding="utf-8",
    )

    report = evaluate_derivation_artifact(derivation_path, "multi_objective_decision")

    assert report.passed is False
    assert any("公式" in item for item in report.required_fixes)


def test_algorithm_gate_rejects_baseline_result_without_required_columns(tmp_path):
    _, evaluate_algorithm_artifact, _, _ = _load_gates()
    algorithm_path = tmp_path / "algorithm.md"
    algorithm_path.write_text("算法：枚举候选决策并比较目标值。", encoding="utf-8")
    result_path = tmp_path / "result.csv"
    result_path.write_text(
        "case,workflow_summary\nbase,baseline 求解流程\n",
        encoding="utf-8",
    )

    report = evaluate_algorithm_artifact(algorithm_path, result_path)

    assert report.passed is False
    assert any(
        "baseline" in item.lower() or "workflow" in item.lower()
        for item in report.required_fixes
    )
    assert any(
        "decision/objective/estimate/diagnostic" in item
        for item in report.required_fixes
    )


def test_algorithm_gate_rejects_solved_baseline_even_with_required_columns(tmp_path):
    _, evaluate_algorithm_artifact, _, _ = _load_gates()
    algorithm_path = tmp_path / "algorithm.md"
    algorithm_path.write_text(
        "算法：枚举候选决策并比较目标值。\n"
        "输入 schema：参数表。\n"
        "输出 schema：decision、objective、estimate、diagnostic。\n"
        "步骤：读取、求解、输出。",
        encoding="utf-8",
    )
    result_path = tmp_path / "result.csv"
    result_path.write_text(
        "case,decision,objective,estimate,diagnostic,status\n"
        "base,inspect,12.5,0.91,ok,solved_baseline\n",
        encoding="utf-8",
    )

    report = evaluate_algorithm_artifact(algorithm_path, result_path)

    assert report.passed is False
    assert any("baseline" in item.lower() for item in report.required_fixes)


@pytest.mark.parametrize(
    "baseline_marker",
    ["baseline_score", "generic_cumcm_contract_workflow"],
)
def test_algorithm_gate_rejects_planned_baseline_markers_with_required_columns(
    tmp_path, baseline_marker
):
    _, evaluate_algorithm_artifact, _, _ = _load_gates()
    algorithm_path = tmp_path / "algorithm.md"
    algorithm_path.write_text(
        "算法：枚举候选决策并比较目标值。\n"
        "输入 schema：参数表。\n"
        "输出 schema：decision、objective、estimate、diagnostic。\n"
        "步骤：读取、求解、输出。",
        encoding="utf-8",
    )
    result_path = tmp_path / "result.csv"
    result_path.write_text(
        "case,decision,objective,estimate,diagnostic,marker\n"
        f"base,inspect,12.5,0.91,ok,{baseline_marker}\n",
        encoding="utf-8",
    )

    report = evaluate_algorithm_artifact(algorithm_path, result_path)

    assert report.passed is False
    assert any("baseline" in item.lower() for item in report.required_fixes)


def test_algorithm_gate_rejects_header_only_result_file(tmp_path):
    _, evaluate_algorithm_artifact, _, _ = _load_gates()
    algorithm_path = tmp_path / "algorithm.md"
    algorithm_path.write_text(
        "算法：枚举候选决策并比较目标值。\n"
        "输入 schema：参数表。\n"
        "输出 schema：decision、objective、estimate、diagnostic。\n"
        "步骤：读取、求解、输出。",
        encoding="utf-8",
    )
    result_path = tmp_path / "result.csv"
    result_path.write_text("case,decision,objective\n", encoding="utf-8")

    report = evaluate_algorithm_artifact(algorithm_path, result_path)

    assert report.passed is False
    assert any("数据行" in item or "结果记录" in item for item in report.required_fixes)


def test_algorithm_gate_requires_complete_result_column_shape(tmp_path):
    _, evaluate_algorithm_artifact, _, _ = _load_gates()
    algorithm_path = tmp_path / "algorithm.md"
    algorithm_path.write_text(
        "算法策略：枚举候选决策。\n"
        "输入 schema：参数表。\n"
        "输出 schema：decision、objective、estimate、diagnostic。\n"
        "步骤：读取、求解、输出。\n"
        "复杂度：O(n)。\n"
        "失败与回退：若参数缺失则停止提交。",
        encoding="utf-8",
    )
    result_path = tmp_path / "result.csv"
    result_path.write_text("case,estimate\nbase,0.91\n", encoding="utf-8")

    report = evaluate_algorithm_artifact(algorithm_path, result_path)

    assert report.passed is False
    assert any(
        "decision/objective/estimate/diagnostic" in item
        for item in report.required_fixes
    )


def test_algorithm_gate_requires_distinct_result_columns(tmp_path):
    _, evaluate_algorithm_artifact, _, _ = _load_gates()
    algorithm_path = tmp_path / "algorithm.md"
    algorithm_path.write_text(
        "算法策略：枚举候选决策。\n"
        "输入 schema：参数表。\n"
        "输出 schema：decision、objective、estimate、diagnostic。\n"
        "步骤：读取、求解、输出。\n"
        "复杂度：O(n)。\n"
        "失败与回退：若参数缺失则停止提交。",
        encoding="utf-8",
    )
    result_path = tmp_path / "result.csv"
    result_path.write_text(
        "case,decision_objective_estimate_diagnostic\nbase,packed\n",
        encoding="utf-8",
    )

    report = evaluate_algorithm_artifact(algorithm_path, result_path)

    assert report.passed is False
    assert any(
        "decision/objective/estimate/diagnostic" in item
        for item in report.required_fixes
    )


def test_algorithm_gate_rejects_template_decision_labels(tmp_path):
    _, evaluate_algorithm_artifact, _, _ = _load_gates()
    algorithm_path = tmp_path / "algorithm.md"
    algorithm_path.write_text(
        "算法策略：枚举候选决策。\n"
        "输入 schema：参数表。\n"
        "输出 schema：decision、objective、estimate、diagnostic。\n"
        "步骤：读取、求解、输出。\n"
        "复杂度：O(n)。\n"
        "失败与回退：若参数缺失则停止提交。",
        encoding="utf-8",
    )
    result_path = tmp_path / "result.csv"
    result_path.write_text(
        "case,decision,objective_value,estimate,diagnostic\n"
        "base,derived_decision,12.5,0.91,ok\n",
        encoding="utf-8",
    )

    report = evaluate_algorithm_artifact(algorithm_path, result_path)

    assert report.passed is False
    assert any(
        "baseline" in item.lower() or "template" in item.lower()
        for item in report.required_fixes
    )


def test_algorithm_gate_rejects_json_without_result_records(tmp_path):
    _, evaluate_algorithm_artifact, _, _ = _load_gates()
    algorithm_path = tmp_path / "algorithm.md"
    algorithm_path.write_text(
        "算法：枚举候选决策并比较目标值。\n"
        "输入 schema：参数表。\n"
        "输出 schema：decision、objective、estimate、diagnostic。\n"
        "步骤：读取、求解、输出。",
        encoding="utf-8",
    )
    result_path = tmp_path / "result.json"
    result_path.write_text("[]\n", encoding="utf-8")

    report = evaluate_algorithm_artifact(algorithm_path, result_path)

    assert report.passed is False
    assert any("数据行" in item or "结果记录" in item for item in report.required_fixes)


def test_algorithm_gate_requires_input_output_and_steps(tmp_path):
    _, evaluate_algorithm_artifact, _, _ = _load_gates()
    algorithm_path = tmp_path / "algorithm.md"
    algorithm_path.write_text("算法：枚举候选决策并比较目标值。", encoding="utf-8")
    result_path = tmp_path / "result.csv"
    result_path.write_text(
        "case,decision,objective,estimate,diagnostic\nbase,inspect,12.5,0.91,ok\n",
        encoding="utf-8",
    )

    report = evaluate_algorithm_artifact(algorithm_path, result_path)

    assert report.passed is False
    assert any("输入" in item for item in report.required_fixes)
    assert any("输出" in item for item in report.required_fixes)
    assert any("步骤" in item for item in report.required_fixes)


def test_algorithm_gate_requires_strategy_complexity_and_fallback(tmp_path):
    _, evaluate_algorithm_artifact, _, _ = _load_gates()
    algorithm_path = tmp_path / "algorithm.md"
    algorithm_path.write_text(
        "输入 schema：参数表。\n"
        "输出 schema：decision、objective、estimate、diagnostic。\n"
        "步骤：读取、求解、输出。",
        encoding="utf-8",
    )
    result_path = tmp_path / "result.csv"
    result_path.write_text(
        "case,decision,objective,estimate,diagnostic\nbase,inspect,12.5,0.91,ok\n",
        encoding="utf-8",
    )

    report = evaluate_algorithm_artifact(algorithm_path, result_path)

    assert report.passed is False
    assert any("算法策略" in item for item in report.required_fixes)
    assert any("复杂度" in item for item in report.required_fixes)
    assert any("失败" in item or "回退" in item for item in report.required_fixes)


def test_symbol_table_rejects_incomplete_entries_and_missing_used_symbols():
    _, _, evaluate_symbol_table, _ = _load_gates()
    symbols = [
        SymbolDefinition(
            symbol="x",
            meaning="",
            unit="",
            source_subproblem_id="",
            first_used_in=Path("subproblems/q1/model_derivation.md"),
            definition_artifact=Path("subproblems/q1/symbol_delta.json"),
        )
    ]
    paper_text = "模型使用 $x$ 和 $y$ 表示两个检测决策变量。"

    report = evaluate_symbol_table(symbols, paper_text)

    assert report.passed is False
    assert any("meaning/unit/source" in item for item in report.required_fixes)
    assert any("未在符号表定义" in item and "y" in item for item in report.required_fixes)


def test_symbol_table_detects_plain_text_subscript_symbols():
    _, _, evaluate_symbol_table, _ = _load_gates()
    symbols = [
        SymbolDefinition(
            symbol="x",
            meaning="是否检测",
            unit="0/1",
            source_subproblem_id="q1",
            first_used_in=Path("subproblems/q1/model_derivation.md"),
            definition_artifact=Path("subproblems/q1/symbol_delta.json"),
        )
    ]
    paper_text = "目标函数为 E[Pi]，其中 p_i 表示第 i 类零配件次品率。"

    report = evaluate_symbol_table(symbols, paper_text)

    assert report.passed is False
    assert any("p_i" in item for item in report.required_fixes)


def test_symbol_table_detects_plain_text_expectation_symbols():
    _, _, evaluate_symbol_table, _ = _load_gates()

    report = evaluate_symbol_table([], "目标函数为 E[Pi]。")

    assert report.passed is False
    assert any("E[Pi]" in item for item in report.required_fixes)


def test_symbol_table_accepts_defined_greek_latex_symbols_without_tail_noise():
    _, _, evaluate_symbol_table, _ = _load_gates()
    symbols = [
        SymbolDefinition(
            symbol="\\mu",
            meaning="均值",
            unit="件",
            source_subproblem_id="q1",
            first_used_in=Path("subproblems/q1/model_derivation.md"),
            definition_artifact=Path("subproblems/q1/symbol_delta.json"),
        ),
        SymbolDefinition(
            symbol="\\sigma",
            meaning="标准差",
            unit="件",
            source_subproblem_id="q1",
            first_used_in=Path("subproblems/q1/model_derivation.md"),
            definition_artifact=Path("subproblems/q1/symbol_delta.json"),
        ),
        SymbolDefinition(
            symbol="\\alpha_i",
            meaning="第 i 个权重",
            unit="比例",
            source_subproblem_id="q1",
            first_used_in=Path("subproblems/q1/model_derivation.md"),
            definition_artifact=Path("subproblems/q1/symbol_delta.json"),
        ),
    ]
    paper_text = r"统计模型使用 $\mu + \sigma + \alpha_i$ 表示核心参数。"

    report = evaluate_symbol_table(symbols, paper_text)

    assert report.passed is True
    assert report.required_fixes == []


def test_symbol_table_ignores_latex_text_and_operator_words():
    _, _, evaluate_symbol_table, _ = _load_gates()
    symbols = [
        SymbolDefinition(
            symbol="x_i",
            meaning="第 i 个决策变量",
            unit="0/1",
            source_subproblem_id="q1",
            first_used_in=Path("subproblems/q1/model_derivation.md"),
            definition_artifact=Path("subproblems/q1/symbol_delta.json"),
        )
    ]
    paper_text = r"目标函数为 $\mathrm{cost}(x_i) + \text{penalty}$。"

    report = evaluate_symbol_table(symbols, paper_text)

    assert report.passed is True
    assert report.required_fixes == []


def test_staged_solution_package_rejects_missing_required_artifact_files(tmp_path):
    _, _, _, evaluate_staged_solution_package = _load_gates()
    contract = _complete_contract()

    report = evaluate_staged_solution_package(contract, tmp_path)

    assert report.passed is False
    assert any("model_derivation" in item for item in report.required_fixes)
    assert any("result_interpretation" in item for item in report.required_fixes)


def test_staged_solution_package_accepts_complete_artifacts(tmp_path):
    _, _, _, evaluate_staged_solution_package = _load_gates()
    contract = _complete_contract()
    _write_complete_artifacts(tmp_path, contract)

    report = evaluate_staged_solution_package(contract, tmp_path)

    assert report.passed is True
    assert report.required_fixes == []


def test_staged_solution_package_rejects_non_finite_numeric_result_values(tmp_path):
    _, _, _, evaluate_staged_solution_package = _load_gates()
    contract = _complete_contract()
    _write_complete_artifacts(tmp_path, contract)
    (tmp_path / contract.result_path).write_text(
        "case,decision,objective_value,estimate,diagnostic\n"
        "base,inspect,not-a-number,NaN,ok\n",
        encoding="utf-8",
    )

    report = evaluate_staged_solution_package(contract, tmp_path)

    assert report.passed is False
    assert any("数值" in item or "finite" in item.lower() for item in report.required_fixes)


def test_staged_solution_package_rejects_thin_result_interpretation(tmp_path):
    _, _, _, evaluate_staged_solution_package = _load_gates()
    contract = _complete_contract()
    _write_complete_artifacts(tmp_path, contract)
    (tmp_path / contract.result_interpretation_path).write_text(
        "结果解释：inspect 决策在约束内取得最低成本。\n",
        encoding="utf-8",
    )

    report = evaluate_staged_solution_package(contract, tmp_path)

    assert report.passed is False
    assert any("结果解释" in item for item in report.required_fixes)


def test_staged_solution_package_rejects_malformed_claim_delta(tmp_path):
    _, _, _, evaluate_staged_solution_package = _load_gates()
    contract = _complete_contract()
    _write_complete_artifacts(tmp_path, contract)
    (tmp_path / contract.claim_delta_path).write_text(
        '{"claims": ["q1-result-supported"]}\n',
        encoding="utf-8",
    )

    report = evaluate_staged_solution_package(contract, tmp_path)

    assert report.passed is False
    assert any(
        "claim" in item.lower() or "声明" in item
        for item in report.required_fixes
    )


def test_staged_solution_package_rejects_malformed_claim_evidence(tmp_path):
    _, _, _, evaluate_staged_solution_package = _load_gates()
    contract = _complete_contract()
    _write_complete_artifacts(tmp_path, contract)
    (tmp_path / contract.claim_delta_path).write_text(
        '[{"claim_id":"q1-result-supported","section":"结果分析",'
        '"text":"inspect 决策由 result.csv 支撑",'
        '"evidence":"todo","status":"supported","confidence":"high"}]\n',
        encoding="utf-8",
    )

    report = evaluate_staged_solution_package(contract, tmp_path)

    assert report.passed is False
    assert any("evidence" in item.lower() for item in report.required_fixes)


def test_staged_solution_package_rejects_mixed_malformed_supported_claim(tmp_path):
    _, _, _, evaluate_staged_solution_package = _load_gates()
    contract = _complete_contract()
    _write_complete_artifacts(tmp_path, contract)
    (tmp_path / contract.claim_delta_path).write_text(
        "["
        '{"claim_id":"q1-result-supported","section":"结果分析",'
        '"text":"inspect 决策由 result.csv 支撑",'
        '"evidence":[{"kind":"csv","path":"subproblems/q1/result.csv"}],'
        '"status":"supported","confidence":"high"},'
        '{"claim_id":"q1-bad","section":"结果分析",'
        '"text":"坏 claim",'
        '"evidence":"todo","status":"supported","confidence":"high"}'
        "]\n",
        encoding="utf-8",
    )

    report = evaluate_staged_solution_package(contract, tmp_path)

    assert report.passed is False
    assert any("claim_delta" in item for item in report.required_fixes)


def test_staged_solution_package_rejects_missing_claim_evidence_file(tmp_path):
    _, _, _, evaluate_staged_solution_package = _load_gates()
    contract = _complete_contract()
    _write_complete_artifacts(tmp_path, contract)
    (tmp_path / contract.claim_delta_path).write_text(
        '[{"claim_id":"q1-result-supported","section":"结果分析",'
        '"text":"inspect 决策由 result.csv 支撑",'
        '"evidence":[{"kind":"csv","path":"subproblems/q1/missing.csv","locator":"row=1"}],'
        '"status":"supported","confidence":"high"}]\n',
        encoding="utf-8",
    )

    report = evaluate_staged_solution_package(contract, tmp_path)

    assert report.passed is False
    assert any("证据不存在" in item for item in report.required_fixes)


def test_staged_solution_package_rejects_claim_evidence_outside_root(tmp_path):
    _, _, _, evaluate_staged_solution_package = _load_gates()
    contract = _complete_contract()
    _write_complete_artifacts(tmp_path, contract)
    (tmp_path / contract.claim_delta_path).write_text(
        '[{"claim_id":"q1-result-supported","section":"结果分析",'
        '"text":"inspect 决策由 result.csv 支撑",'
        '"evidence":[{"kind":"csv","path":"../outside.csv","locator":"row=1"}],'
        '"status":"supported","confidence":"high"}]\n',
        encoding="utf-8",
    )

    report = evaluate_staged_solution_package(contract, tmp_path)

    assert report.passed is False
    assert any("artifact_root" in item or "证据路径" in item for item in report.required_fixes)


@pytest.mark.parametrize(
    "invalid_path",
    [
        Path(""),
        Path("."),
        Path(str("")),
        Path("subproblems") / "..",
    ],
)
def test_staged_solution_package_rejects_unset_required_artifact_paths(tmp_path, invalid_path):
    _, _, _, evaluate_staged_solution_package = _load_gates()
    contract = _complete_contract(model_derivation_path=invalid_path)
    valid_contract = _complete_contract()
    _write_complete_artifacts(tmp_path, valid_contract)

    report = evaluate_staged_solution_package(contract, tmp_path)

    assert report.passed is False
    assert any("未设置" in item or "artifact_root" in item for item in report.required_fixes)


def test_staged_solution_package_rejects_required_path_resolving_to_artifact_root(tmp_path):
    _, _, _, evaluate_staged_solution_package = _load_gates()
    contract = _complete_contract(model_derivation_path=tmp_path)
    valid_contract = _complete_contract()
    _write_complete_artifacts(tmp_path, valid_contract)

    report = evaluate_staged_solution_package(contract, tmp_path)

    assert report.passed is False
    assert any("未设置" in item or "artifact_root" in item for item in report.required_fixes)


@pytest.mark.parametrize(
    "outside_path_factory",
    [
        lambda root: Path("..") / "outside.txt",
        lambda root: root.parent / "outside.txt",
    ],
)
def test_staged_solution_package_rejects_paths_outside_artifact_root(
    tmp_path, outside_path_factory
):
    _, _, _, evaluate_staged_solution_package = _load_gates()
    contract = _complete_contract(model_derivation_path=outside_path_factory(tmp_path))
    valid_contract = _complete_contract()
    _write_complete_artifacts(tmp_path, valid_contract)

    report = evaluate_staged_solution_package(contract, tmp_path)

    assert report.passed is False
    assert any("artifact_root" in item or "路径必须位于" in item for item in report.required_fixes)
