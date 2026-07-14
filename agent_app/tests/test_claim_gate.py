from pathlib import Path

from agent_app.domain.contracts import Claim, ClaimEvidence, ClaimStatus
from agent_app.evaluators.claim_gate import evaluate_claims
from agent_app.services.claim_map import build_b_problem_claims


def test_claim_gate_rejects_unsupported_claims():
    report = evaluate_claims(
        [
            Claim(
                claim_id="claim_bad",
                section="result_analysis",
                text="没有证据的结论。",
                status=ClaimStatus.UNSUPPORTED,
            )
        ],
        artifact_root=Path("."),
    )

    assert report.passed is False
    assert "claim_bad" in report.required_fixes[0]


def test_claim_gate_accepts_existing_evidence_file(tmp_path):
    result_file = tmp_path / "results/q1_sampling_plan.csv"
    result_file.parent.mkdir()
    result_file.write_text("decision,n\nreject,270\n", encoding="utf-8")
    claim = Claim(
        claim_id="claim_q1",
        section="result_analysis",
        text="拒收规则需要 270 次抽样。",
        evidence=[ClaimEvidence(kind="result_file", path=Path("results/q1_sampling_plan.csv"))],
        status=ClaimStatus.SUPPORTED,
    )

    report = evaluate_claims([claim], artifact_root=tmp_path)

    assert report.passed is True


def test_claim_gate_rejects_missing_evidence_file(tmp_path):
    claim = Claim(
        claim_id="claim_missing_file",
        section="result_analysis",
        text="引用了不存在的结果。",
        evidence=[ClaimEvidence(kind="result_file", path=Path("results/missing.csv"))],
        status=ClaimStatus.SUPPORTED,
    )

    report = evaluate_claims([claim], artifact_root=tmp_path)

    assert report.passed is False
    assert "results/missing.csv" in report.required_fixes[0]


def test_build_b_problem_claims_creates_four_claim_groups(tmp_path):
    for relative_path in [
        "results/q1_sampling_plan.csv",
        "results/q2_table1_decisions.csv",
        "results/q3_table2_tree_decisions.csv",
        "results/q4_uncertainty_re_solve.csv",
    ]:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n1\n", encoding="utf-8")

    claims = build_b_problem_claims(tmp_path)

    assert {claim.claim_id for claim in claims} == {
        "claim_q1_sampling_plan",
        "claim_q2_table1_decisions",
        "claim_q3_tree_decisions",
        "claim_q4_uncertainty_limits",
    }


def test_build_b_problem_claims_marks_missing_result_unsupported(tmp_path):
    for relative_path in [
        "results/q1_sampling_plan.csv",
        "results/q2_table1_decisions.csv",
        "results/q3_table2_tree_decisions.csv",
    ]:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n1\n", encoding="utf-8")

    claims = build_b_problem_claims(tmp_path)
    by_id = {claim.claim_id: claim for claim in claims}

    assert by_id["claim_q4_uncertainty_limits"].status == ClaimStatus.UNSUPPORTED
    assert by_id["claim_q4_uncertainty_limits"].evidence == []
