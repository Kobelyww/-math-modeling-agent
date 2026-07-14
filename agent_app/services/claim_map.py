from __future__ import annotations

from pathlib import Path

from agent_app.domain.contracts import Claim, ClaimEvidence, ClaimStatus


def build_b_problem_claims(run_dir: Path | str) -> list[Claim]:
    root = Path(run_dir)
    specs = [
        ("claim_q1_sampling_plan", "result_analysis", "问题1的抽样检测方案由 q1 结果表支撑。", "results/q1_sampling_plan.csv"),
        ("claim_q2_table1_decisions", "result_analysis", "问题2的表1生产决策由 q2 结果表支撑。", "results/q2_table1_decisions.csv"),
        ("claim_q3_tree_decisions", "result_analysis", "问题3的装配树决策由 q3 结果表支撑。", "results/q3_table2_tree_decisions.csv"),
        ("claim_q4_uncertainty_limits", "robustness_analysis", "问题4的不确定性结论由 q4 重求解结果支撑。", "results/q4_uncertainty_re_solve.csv"),
    ]
    claims: list[Claim] = []
    for claim_id, section, text, relative_path in specs:
        status = ClaimStatus.SUPPORTED if (root / relative_path).exists() else ClaimStatus.UNSUPPORTED
        evidence = [ClaimEvidence(kind="result_file", path=Path(relative_path))] if status == ClaimStatus.SUPPORTED else []
        claims.append(Claim(claim_id=claim_id, section=section, text=text, evidence=evidence, status=status))
    return claims
