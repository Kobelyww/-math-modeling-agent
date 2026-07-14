from pathlib import Path

import agent_app.domain as domain
from agent_app.domain.contracts import (
    Claim,
    ClaimEvidence,
    ClaimStatus,
    EvidenceItem,
    ExperimentContract,
    ModelContract,
    ProblemContract,
    ProjectType,
    SubproblemContract,
    SubproblemType,
)
from agent_app.domain.serialization import from_json_dict, to_json_dict


def test_problem_contract_round_trips_with_subproblems():
    contract = ProblemContract(
        project_type=ProjectType.CUMCM,
        title="生产过程中的决策问题",
        source_text_path=Path("question.md"),
        subproblems=[
            SubproblemContract(
                subproblem_id="q1",
                question_text="设计抽样检测方案。",
                primary_type=SubproblemType.SAMPLING_TEST,
                expected_outputs=["results/q1_sampling_plan.csv"],
            )
        ],
    )

    payload = to_json_dict(contract)
    restored = from_json_dict(ProblemContract, payload)

    assert restored.project_type == ProjectType.CUMCM
    assert restored.source_text_path == Path("question.md")
    assert restored.subproblems[0].primary_type == SubproblemType.SAMPLING_TEST


def test_claim_requires_evidence_for_supported_status():
    claim = Claim(
        claim_id="claim_q1_1",
        section="result_analysis",
        text="拒收规则需要至少 270 次抽样。",
        evidence=[
            ClaimEvidence(
                kind="result_file",
                path=Path("results/q1_sampling_plan.csv"),
                locator="decision=reject",
            )
        ],
        status=ClaimStatus.SUPPORTED,
    )

    assert claim.is_supported()
    assert to_json_dict(claim)["evidence"][0]["path"] == "results/q1_sampling_plan.csv"


def test_model_and_experiment_contracts_record_parameter_sources():
    model = ModelContract(
        subproblem_id="q2",
        variables={"d1": "是否检测零配件1"},
        parameters={"p1": "零配件1次品率"},
        parameter_sources={"p1": "tables/table_1"},
        objective_functions=["maximize expected_profit"],
        constraints=["d1,d2,df,r in {0,1}"],
        algorithm="Enumerate binary inspection and disassembly decisions.",
        result_files=["results/q2_table1_decisions.csv"],
    )
    experiment = ExperimentContract(
        subproblem_id="q2",
        entrypoint=Path("code/solve.py"),
        output_schemas={"results/q2_table1_decisions.csv": ["case", "expected_profit"]},
        validation_checks=["non_empty_csv", "parameter_audit_has_no_unexplained_constants"],
    )

    assert model.parameter_sources["p1"] == "tables/table_1"
    assert experiment.output_schemas["results/q2_table1_decisions.csv"] == [
        "case",
        "expected_profit",
    ]


def test_evidence_item_defaults_are_serializable():
    evidence = EvidenceItem(
        evidence_id="mimo_1",
        title="Acceptance sampling reference",
        source="https://example.test/sampling",
        summary="Binomial acceptance sampling uses operating characteristic curves.",
        relevance="Supports q1 sampling plan.",
    )

    payload = to_json_dict(evidence)

    assert payload["credibility_risk"] == ""
    assert payload["recommended_use"] == ""


def test_domain_package_exports_contract_symbols():
    for symbol in [
        "Claim",
        "ClaimEvidence",
        "ClaimStatus",
        "EvidenceItem",
        "ExperimentContract",
        "ExtractionWarning",
        "ModelContract",
        "ProblemContract",
        "ProjectType",
        "SubproblemContract",
        "SubproblemType",
    ]:
        assert hasattr(domain, symbol)
        assert symbol in domain.__all__
