from pathlib import Path

from agent_app.domain.contracts import Claim, ClaimEvidence, ClaimStatus
from agent_app.services.section_writer import CUMCM_SECTION_ORDER, build_section_context, write_section_files


def test_build_section_context_includes_only_matching_claims():
    claims = [
        Claim(
            claim_id="claim_q1",
            section="result_analysis",
            text="抽样方案满足信度要求。",
            evidence=[ClaimEvidence(kind="result_file", path=Path("results/q1_sampling_plan.csv"))],
            status=ClaimStatus.SUPPORTED,
        ),
        Claim(claim_id="claim_intro", section="problem_restatement", text="题目要求解决生产决策。"),
    ]

    context = build_section_context("result_analysis", claims)

    assert "claim_q1" in context["claim_ids"]
    assert "claim_intro" not in context["claim_ids"]
    assert context["claims"][0]["evidence"] == ["results/q1_sampling_plan.csv"]


def test_write_section_files_creates_ordered_markdown_files(tmp_path):
    claims = [
        Claim(
            claim_id="claim_q1",
            section="result_analysis",
            text="抽样方案满足信度要求。",
            evidence=[ClaimEvidence(kind="result_file", path=Path("results/q1_sampling_plan.csv"))],
            status=ClaimStatus.SUPPORTED,
        )
    ]

    paths = write_section_files(tmp_path, claims)

    assert len(paths) == len(CUMCM_SECTION_ORDER)
    assert paths[0].name == "00_title.md"
    assert (tmp_path / "sections" / "08_result_analysis.md").exists()
    assert "claim_q1" in (tmp_path / "sections" / "08_result_analysis.md").read_text(encoding="utf-8")
