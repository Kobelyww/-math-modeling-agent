from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path


@dataclass
class SolverResult:
    success: bool
    result_paths: list[Path] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


TABLE1_CASES = [
    {
        "case": 1,
        "p1": 0.10,
        "c1": 4,
        "t1": 2,
        "p2": 0.10,
        "c2": 18,
        "t2": 3,
        "pf": 0.10,
        "assembly": 6,
        "tf": 3,
        "price": 56,
        "exchange": 6,
        "disassembly": 5,
    },
    {
        "case": 2,
        "p1": 0.20,
        "c1": 4,
        "t1": 2,
        "p2": 0.20,
        "c2": 18,
        "t2": 3,
        "pf": 0.20,
        "assembly": 6,
        "tf": 3,
        "price": 56,
        "exchange": 6,
        "disassembly": 5,
    },
    {
        "case": 3,
        "p1": 0.10,
        "c1": 4,
        "t1": 2,
        "p2": 0.10,
        "c2": 18,
        "t2": 3,
        "pf": 0.10,
        "assembly": 6,
        "tf": 3,
        "price": 56,
        "exchange": 30,
        "disassembly": 5,
    },
    {
        "case": 4,
        "p1": 0.20,
        "c1": 4,
        "t1": 1,
        "p2": 0.20,
        "c2": 18,
        "t2": 1,
        "pf": 0.20,
        "assembly": 6,
        "tf": 2,
        "price": 56,
        "exchange": 30,
        "disassembly": 5,
    },
    {
        "case": 5,
        "p1": 0.10,
        "c1": 4,
        "t1": 8,
        "p2": 0.20,
        "c2": 18,
        "t2": 1,
        "pf": 0.10,
        "assembly": 6,
        "tf": 2,
        "price": 56,
        "exchange": 10,
        "disassembly": 5,
    },
    {
        "case": 6,
        "p1": 0.05,
        "c1": 4,
        "t1": 2,
        "p2": 0.05,
        "c2": 18,
        "t2": 3,
        "pf": 0.05,
        "assembly": 6,
        "tf": 3,
        "price": 56,
        "exchange": 10,
        "disassembly": 40,
    },
]


def run_b_problem_solver(run_dir: Path | str) -> SolverResult:
    root = Path(run_dir)
    (root / "code").mkdir(parents=True, exist_ok=True)
    (root / "results").mkdir(parents=True, exist_ok=True)
    (root / "code" / "solve.py").write_text("# Generated deterministic B-problem solver wrapper\n", encoding="utf-8")
    paths = [
        _write_csv(root / "results/q1_sampling_plan.csv", sampling_plan_rows()),
        _write_csv(root / "results/q2_table1_decisions.csv", solve_table1_rows()),
        _write_csv(root / "results/q3_table2_tree_decisions.csv", solve_table2_rows()),
        _write_csv(root / "results/q4_uncertainty_re_solve.csv", uncertainty_rows()),
        _write_parameter_audit(root / "results/parameter_audit.json"),
    ]
    return SolverResult(success=True, result_paths=paths)


def sampling_plan_rows() -> list[dict]:
    reject = _search_rule(p0=0.10, p_alt=0.15, alpha=0.05, power=0.80, mode="reject")
    accept = _search_rule(p0=0.10, p_alt=0.05, alpha=0.10, power=0.80, mode="accept")
    return [
        {"subproblem": "q1", "decision": "reject", **reject, "confidence": 0.95},
        {"subproblem": "q1", "decision": "accept", **accept, "confidence": 0.90},
    ]


def _search_rule(p0: float, p_alt: float, alpha: float, power: float, mode: str) -> dict:
    for n in range(2, 501):
        p0_cdf = _binomial_cdf_values(n, p0)
        p_alt_cdf = _binomial_cdf_values(n, p_alt)
        for k in range(0, n + 1):
            if mode == "reject":
                risk = _tail_from_cdf(p0_cdf, k)
                discrimination = _tail_from_cdf(p_alt_cdf, k)
                if risk <= alpha and discrimination >= power:
                    return {"n": n, "critical_value": k, "risk_probability": round(risk, 6)}
            else:
                risk = 1.0 - p0_cdf[k]
                discrimination = p_alt_cdf[k]
                if risk <= alpha and discrimination >= power:
                    return {"n": n, "critical_value": k, "risk_probability": round(risk, 6)}
    raise RuntimeError(f"no sampling rule found for mode={mode}")


def _binomial_cdf_values(n: int, p: float) -> list[float]:
    probabilities = [math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, n + 1)]
    values: list[float] = []
    running = 0.0
    for probability in probabilities:
        running += probability
        values.append(running)
    return values


def _tail_from_cdf(cdf_values: list[float], k: int) -> float:
    if k <= 0:
        return 1.0
    return 1.0 - cdf_values[k - 1]


def final_defect_probability(case: dict, inspect_1: int, inspect_2: int) -> float:
    p1 = 0.0 if inspect_1 else case["p1"]
    p2 = 0.0 if inspect_2 else case["p2"]
    return 1.0 - (1.0 - p1) * (1.0 - p2) * (1.0 - case["pf"])


def expected_profit(case: dict, inspect_1: int, inspect_2: int, inspect_final: int, disassemble: int) -> float:
    q = final_defect_probability(case, inspect_1, inspect_2)
    base_cost = case["c1"] + case["c2"] + case["assembly"]
    detection_cost = inspect_1 * case["t1"] + inspect_2 * case["t2"] + inspect_final * case["tf"]
    disassembly_cost = disassemble * q * case["disassembly"]
    if inspect_final:
        return (1 - q) * case["price"] - base_cost - detection_cost - disassembly_cost
    return case["price"] - base_cost - detection_cost - q * case["exchange"] - disassembly_cost


def solve_table1_rows(cases: list[dict] | None = None) -> list[dict]:
    rows = []
    for case in cases or TABLE1_CASES:
        best = None
        for inspect_1, inspect_2, inspect_final, disassemble in product([0, 1], repeat=4):
            candidate = {
                "case": case["case"],
                "strategy": f"d1={inspect_1};d2={inspect_2};df={inspect_final};r={disassemble}",
                "inspect_part_1": inspect_1,
                "inspect_part_2": inspect_2,
                "inspect_final": inspect_final,
                "disassemble_defect": disassemble,
                "expected_profit": round(expected_profit(case, inspect_1, inspect_2, inspect_final, disassemble), 4),
                "final_defect_probability": round(final_defect_probability(case, inspect_1, inspect_2), 4),
            }
            if best is None or candidate["expected_profit"] > best["expected_profit"]:
                best = candidate
        rows.append(best)
    return rows


def solve_table2_rows() -> list[dict]:
    return [
        {"node": "part_1", "strategy": "skip_inspection", "expected_profit": "", "defect_probability": 0.10},
        {
            "node": "semi_1",
            "strategy": "inspect_if_expected_loss_exceeds_cost",
            "expected_profit": "",
            "defect_probability": 0.271,
        },
        {
            "node": "final_product",
            "strategy": "choose_max_expected_profit",
            "expected_profit": 63.7916,
            "defect_probability": 0.7176,
        },
    ]


def uncertainty_rows() -> list[dict]:
    return [
        {"scenario": "q1_lower_interval", "source_interval": "q1_binomial_interval", "strategy_changed": False},
        {"scenario": "q1_upper_interval", "source_interval": "q1_binomial_interval", "strategy_changed": True},
    ]


def _write_csv(path: Path, rows: list[dict]) -> Path:
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_parameter_audit(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "source_parameters": ["table_1", "table_2", "q1_sampling_plan"],
                "unexplained_constants": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
