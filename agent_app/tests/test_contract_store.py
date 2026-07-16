from pathlib import Path

import pytest

from agent_app.domain.contracts import (
    Claim,
    ClaimEvidence,
    ClaimStatus,
    ProblemContract,
    ProjectType,
    SubproblemContract,
    SubproblemType,
)
from agent_app.services.contract_store import ContractStore


def test_contract_store_writes_problem_contract_under_contracts(tmp_path):
    store = ContractStore(tmp_path)
    contract = ProblemContract(
        project_type=ProjectType.CUMCM,
        title="生产过程中的决策问题",
        source_text_path=Path("question.md"),
        subproblems=[
            SubproblemContract(
                subproblem_id="q1",
                question_text="抽样检测",
                primary_type=SubproblemType.SAMPLING_TEST,
            )
        ],
    )

    path = store.write_problem_contract(contract)
    restored = store.read_problem_contract()

    assert path == tmp_path / "contracts" / "problem_contract.json"
    assert restored.title == "生产过程中的决策问题"
    assert restored.subproblems[0].subproblem_id == "q1"


def test_contract_store_writes_claim_map_and_stale_markers(tmp_path):
    store = ContractStore(tmp_path)
    claims = [
        Claim(
            claim_id="claim_q1_1",
            section="result_analysis",
            text="拒收规则满足 95% 信度要求。",
            evidence=[ClaimEvidence(kind="result_file", path=Path("results/q1_sampling_plan.csv"))],
            status=ClaimStatus.SUPPORTED,
        )
    ]

    claim_path = store.write_claim_map(claims)
    stale_path = store.mark_stale("sections", reason="claims changed")

    assert claim_path == tmp_path / "claims" / "claim_map.json"
    assert store.read_claim_map()[0].is_supported()
    assert stale_path == tmp_path / "stale" / "sections.json"
    assert "claims changed" in stale_path.read_text(encoding="utf-8")


def test_contract_store_rejects_empty_stale_marker_name(tmp_path):
    store = ContractStore(tmp_path)

    with pytest.raises(ValueError, match="artifact_group"):
        store.mark_stale("///", reason="invalid")
