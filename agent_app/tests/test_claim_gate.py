from pathlib import Path

from agent_app.domain.contracts import Claim, ClaimEvidence, ClaimStatus
from agent_app.evaluators.claim_gate import evaluate_claims
from agent_app.services.claim_map import build_b_problem_claims, build_generic_claims


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
        evidence=[ClaimEvidence(kind="result_file", path=Path("results/q1_sampling_plan.csv"), locator="row:1")],
        status=ClaimStatus.SUPPORTED,
    )

    report = evaluate_claims([claim], artifact_root=tmp_path)

    assert report.passed is True


def test_claim_gate_rejects_supported_claim_without_locator(tmp_path):
    result_file = tmp_path / "results/q1_result.csv"
    result_file.parent.mkdir()
    result_file.write_text("score\n0.91\n", encoding="utf-8")
    claim = Claim(
        claim_id="claim_q1_result",
        section="result_analysis",
        text="问题1结果由结果文件支撑。",
        evidence=[ClaimEvidence(kind="result_file", path=Path("results/q1_result.csv"))],
        status=ClaimStatus.SUPPORTED,
    )

    report = evaluate_claims([claim], artifact_root=tmp_path)

    assert report.passed is False
    assert "locator" in report.required_fixes[0]


def test_claim_gate_rejects_missing_evidence_file(tmp_path):
    claim = Claim(
        claim_id="claim_missing_file",
        section="result_analysis",
        text="引用了不存在的结果。",
        evidence=[ClaimEvidence(kind="result_file", path=Path("results/missing.csv"), locator="row:1")],
        status=ClaimStatus.SUPPORTED,
    )

    report = evaluate_claims([claim], artifact_root=tmp_path)

    assert report.passed is False
    assert "results/missing.csv" in report.required_fixes[0]


def test_build_generic_claims_creates_result_locators(tmp_path):
    result_file = tmp_path / "results/q1_result.csv"
    result_file.parent.mkdir()
    result_file.write_text("score\n0.91\n", encoding="utf-8")

    claims = build_generic_claims(
        [{"id": "q1", "title": "建立评价模型", "result_file": "results/q1_result.csv"}],
        tmp_path,
    )

    assert claims[0].claim_id == "claim_q1_result"
    assert claims[0].text == "建立评价模型 的结论由 results/q1_result.csv 支撑。"
    assert claims[0].status == ClaimStatus.SUPPORTED
    assert claims[0].confidence == "medium"
    assert claims[0].evidence[0].locator == "row:1"


def test_build_generic_claims_marks_missing_result_unsupported(tmp_path):
    claims = build_generic_claims(
        [{"id": "q2", "title": "优化生产决策", "result_file": "results/q2_result.csv"}],
        tmp_path,
    )

    assert claims[0].claim_id == "claim_q2_result"
    assert claims[0].status == ClaimStatus.UNSUPPORTED
    assert claims[0].confidence == ""
    assert claims[0].evidence == []


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
    assert all(claim.evidence[0].locator == "row:1" for claim in claims)
    assert evaluate_claims(claims, artifact_root=tmp_path).passed is True


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
