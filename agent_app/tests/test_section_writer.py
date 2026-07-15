from pathlib import Path

from agent_app.domain.contracts import Claim, ClaimEvidence, ClaimStatus
from agent_app.services.section_writer import CUMCM_SECTION_ORDER, build_section_context, write_section_files


def test_build_section_context_includes_only_matching_claims():
    claims = [
        Claim(
            claim_id="claim_q1",
            section="result_analysis",
            text="抽样方案满足信度要求。",
            evidence=[ClaimEvidence(kind="result_file", path=Path("results/q1_sampling_plan.csv"), locator="row:1")],
            status=ClaimStatus.SUPPORTED,
        ),
        Claim(claim_id="claim_intro", section="problem_restatement", text="题目要求解决生产决策。"),
    ]

    context = build_section_context("result_analysis", claims)

    assert "claim_q1" in context["claim_ids"]
    assert "claim_intro" not in context["claim_ids"]
    assert context["claims"][0]["evidence"] == ["results/q1_sampling_plan.csv#row:1"]


def test_write_section_files_creates_ordered_markdown_files(tmp_path):
    claims = [
        Claim(
            claim_id="claim_q1",
            section="result_analysis",
            text="抽样方案满足信度要求。",
            evidence=[ClaimEvidence(kind="result_file", path=Path("results/q1_sampling_plan.csv"), locator="row:1")],
            status=ClaimStatus.SUPPORTED,
        )
    ]

    paths = write_section_files(tmp_path, claims)

    assert len(paths) == len(CUMCM_SECTION_ORDER)
    assert paths[0].name == "00_title.md"
    assert (tmp_path / "sections" / "08_result_analysis.md").exists()
    assert "claim_q1" in (tmp_path / "sections" / "08_result_analysis.md").read_text(encoding="utf-8")
    assert "row:1" in (tmp_path / "sections" / "08_result_analysis.md").read_text(encoding="utf-8")


def test_write_section_files_does_not_emit_internal_empty_claim_text(tmp_path):
    paths = write_section_files(tmp_path, [])

    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "暂无已支持结论" not in combined
    assert "Claim-Aware Section Context" not in combined
    assert "## Claims" not in combined
    assert (tmp_path / "sections" / "08_result_analysis.md").exists()


def test_write_section_files_omits_unsupported_claims_from_user_facing_conclusions(tmp_path):
    claims = [
        Claim(
            claim_id="claim_q_missing_result",
            section="result_analysis",
            text="缺失结果文件支撑了该结论。",
            status=ClaimStatus.UNSUPPORTED,
        )
    ]

    write_section_files(tmp_path, claims)

    text = (tmp_path / "sections" / "08_result_analysis.md").read_text(encoding="utf-8")
    assert "缺失结果文件支撑了该结论" not in text
    assert "claim_q_missing_result" not in text
    assert "证据位置待补充" not in text
    assert "本节只写入已有结果文件能够支撑的结论" in text
