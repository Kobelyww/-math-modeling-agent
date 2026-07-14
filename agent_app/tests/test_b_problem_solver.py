from agent_app.workflow_packs.cumcm.templates.production_decision import (
    build_b_problem_experiment_contracts,
    build_b_problem_model_contracts,
    is_b_problem,
)


B_PROBLEM_TEXT = "B 题 生产过程中的决策问题。问题1：抽样检测。问题2：检测拆解决策。问题3：多工序。问题4：抽样不确定性。"


def test_b_problem_detection_is_specific():
    assert is_b_problem(B_PROBLEM_TEXT)
    assert not is_b_problem("A 题 城市交通预测问题")


def test_b_problem_model_contracts_cover_four_subproblems():
    contracts = build_b_problem_model_contracts()

    assert [contract.subproblem_id for contract in contracts] == ["q1", "q2", "q3", "q4"]
    assert "X ~ Binomial(n, p)" in contracts[0].formulas
    assert "expected_profit" in " ".join(contracts[1].objective_functions)
    assert "results/q4_uncertainty_re_solve.csv" in contracts[3].result_files


def test_b_problem_experiment_contracts_define_output_schemas():
    contracts = build_b_problem_experiment_contracts()

    assert contracts[0].output_schemas["results/q1_sampling_plan.csv"] == [
        "subproblem",
        "decision",
        "n",
        "critical_value",
        "confidence",
        "risk_probability",
    ]
    assert "parameter_audit_has_no_unexplained_constants" in contracts[1].validation_checks


def test_b_problem_model_and_experiment_contract_ids_stay_aligned():
    models = build_b_problem_model_contracts()
    experiments = build_b_problem_experiment_contracts()

    assert [contract.subproblem_id for contract in models] == [
        contract.subproblem_id for contract in experiments
    ]
