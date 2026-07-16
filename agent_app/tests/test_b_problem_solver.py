import csv
import json

from agent_app.workflow_packs.cumcm.benchmarks.y2024_b_production_decision import (
    build_b_problem_experiment_contracts,
    build_b_problem_model_contracts,
    is_b_problem,
)
from agent_app.workflow_packs.cumcm.benchmarks.y2024_b_production_decision_solver import (
    run_b_problem_solver,
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


def test_b_problem_solver_is_imported_from_benchmark_namespace():
    assert run_b_problem_solver.__module__.endswith("benchmarks.y2024_b_production_decision_solver")


def _read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_b_problem_solver_writes_q1_to_q4_results(tmp_path):
    result = run_b_problem_solver(tmp_path)

    assert result.success is True
    for relative_path in [
        "results/q1_sampling_plan.csv",
        "results/q2_table1_decisions.csv",
        "results/q3_table2_tree_decisions.csv",
        "results/q4_uncertainty_re_solve.csv",
        "results/parameter_audit.json",
    ]:
        assert (tmp_path / relative_path).exists(), relative_path


def test_q1_sampling_plan_rejects_trivial_accept_rule(tmp_path):
    run_b_problem_solver(tmp_path)

    rows = _read_csv(tmp_path / "results/q1_sampling_plan.csv")
    accept_rows = [row for row in rows if row["decision"] == "accept"]

    assert accept_rows
    assert all(int(row["n"]) > 1 for row in accept_rows)


def test_parameter_audit_has_no_unexplained_constants(tmp_path):
    run_b_problem_solver(tmp_path)

    audit = json.loads((tmp_path / "results/parameter_audit.json").read_text(encoding="utf-8"))

    assert audit["unexplained_constants"] == []
    assert "0.35" not in (tmp_path / "code/solve.py").read_text(encoding="utf-8")


def test_b_problem_solver_writes_reviewable_decision_rows(tmp_path):
    run_b_problem_solver(tmp_path)

    q2_rows = _read_csv(tmp_path / "results/q2_table1_decisions.csv")
    q3_rows = _read_csv(tmp_path / "results/q3_table2_tree_decisions.csv")
    q4_rows = _read_csv(tmp_path / "results/q4_uncertainty_re_solve.csv")

    assert {row["case"] for row in q2_rows} == {"1", "2", "3", "4", "5", "6"}
    assert any(row["node"] == "final_product" for row in q3_rows)
    assert {row["source_interval"] for row in q4_rows} == {"q1_binomial_interval"}
