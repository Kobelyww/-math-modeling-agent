from __future__ import annotations

from pathlib import Path

from agent_app.domain.contracts import ExperimentContract, ModelContract


def is_b_problem(problem_text: str) -> bool:
    return all(token in problem_text for token in ("生产过程中的决策问题", "抽样", "拆解"))


def build_b_problem_model_contracts() -> list[ModelContract]:
    return [
        ModelContract(
            subproblem_id="q1",
            variables={"n": "sample size", "k": "critical defective count", "X": "defect count"},
            parameters={"p0": "nominal defect rate", "alpha": "producer or rejection risk"},
            parameter_sources={"p0": "problem statement"},
            assumptions=["Independent Bernoulli sampling."],
            objective_functions=["minimize n subject to confidence constraints"],
            constraints=["X ~ Binomial(n, p)", "reject rule must satisfy confidence and discrimination constraints"],
            algorithm="Enumerate n and critical values, then filter by risk probabilities.",
            formulas=["X ~ Binomial(n, p)", "P_p0(X >= k) <= alpha"],
            result_files=["results/q1_sampling_plan.csv"],
            experiment_to_claim_links=["q1 sampling result supports claim_q1_sampling_plan"],
        ),
        ModelContract(
            subproblem_id="q2",
            variables={"d1": "inspect part 1", "d2": "inspect part 2", "df": "inspect final product", "r": "disassemble defective product"},
            parameters={"p1": "part 1 defect rate", "p2": "part 2 defect rate", "pf": "assembly defect rate"},
            parameter_sources={"p1": "table_1", "p2": "table_1", "pf": "table_1"},
            objective_functions=["maximize expected_profit(d1,d2,df,r)"],
            constraints=["d1,d2,df,r in {0,1}"],
            algorithm="Enumerate binary decisions and compare expected profit.",
            formulas=["q = 1 - (1-p1_eff)(1-p2_eff)(1-pf)"],
            result_files=["results/q2_table1_decisions.csv"],
            experiment_to_claim_links=["q2 table result supports claim_q2_decision_table"],
        ),
        ModelContract(
            subproblem_id="q3",
            variables={"node_decision": "inspection/disassembly decision for each assembly node"},
            parameters={"node_defect_rate": "part, semi-finished, or final product defect rate"},
            parameter_sources={"node_defect_rate": "table_2"},
            objective_functions=["maximize final expected profit on assembly tree"],
            constraints=["tree probabilities propagate bottom-up"],
            algorithm="Dynamic programming on assembly tree nodes.",
            formulas=["q_node = 1 - prod(1-q_child) * (1-p_node)"],
            result_files=["results/q3_table2_tree_decisions.csv"],
            experiment_to_claim_links=["q3 tree result supports claim_q3_tree_strategy"],
        ),
        ModelContract(
            subproblem_id="q4",
            variables={"p_lower": "lower confidence bound", "p_upper": "upper confidence bound"},
            parameters={"confidence": "sampling confidence level"},
            parameter_sources={"confidence": "q1 sampling plan"},
            objective_functions=["identify stable and unstable decisions under defect-rate uncertainty"],
            constraints=["uncertainty scenarios derive from sampling intervals"],
            algorithm="Re-solve q2 and q3 using interval-derived defect rates.",
            formulas=["p in [p_lower, p_upper]"],
            result_files=["results/q4_uncertainty_re_solve.csv"],
            experiment_to_claim_links=["q4 uncertainty result limits q2 and q3 claims"],
        ),
    ]


def build_b_problem_experiment_contracts() -> list[ExperimentContract]:
    return [
        ExperimentContract(
            subproblem_id="q1",
            entrypoint=Path("code/solve.py"),
            output_schemas={
                "results/q1_sampling_plan.csv": [
                    "subproblem",
                    "decision",
                    "n",
                    "critical_value",
                    "confidence",
                    "risk_probability",
                ]
            },
            validation_checks=["non_empty_csv", "reject_trivial_n_equals_one"],
        ),
        ExperimentContract(
            subproblem_id="q2",
            entrypoint=Path("code/solve.py"),
            output_schemas={"results/q2_table1_decisions.csv": ["case", "strategy", "expected_profit"]},
            validation_checks=["non_empty_csv", "parameter_audit_has_no_unexplained_constants"],
        ),
        ExperimentContract(
            subproblem_id="q3",
            entrypoint=Path("code/solve.py"),
            output_schemas={"results/q3_table2_tree_decisions.csv": ["node", "strategy", "expected_profit"]},
            validation_checks=["non_empty_csv", "tree_has_final_product_row"],
        ),
        ExperimentContract(
            subproblem_id="q4",
            entrypoint=Path("code/solve.py"),
            output_schemas={"results/q4_uncertainty_re_solve.csv": ["scenario", "source_interval", "strategy_changed"]},
            validation_checks=["non_empty_csv", "uncertainty_uses_sampling_intervals"],
        ),
    ]
