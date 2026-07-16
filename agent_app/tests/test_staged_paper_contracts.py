from pathlib import Path

from agent_app.domain import (
    PaperOutline,
    StagedPaperManifest,
    SubproblemSolutionContract,
    SymbolDefinition,
)
from agent_app.domain.serialization import from_json_dict, to_json_dict
from agent_app.services.contract_store import ContractStore


def test_symbol_definition_round_trips():
    symbol = SymbolDefinition(
        symbol="p_i",
        meaning="第 i 类零配件次品率",
        unit="比例",
        source_subproblem_id="q2",
        first_used_in=Path("subproblems/q2/model_derivation.md"),
        definition_artifact=Path("subproblems/q2/symbol_delta.json"),
    )

    restored = from_json_dict(SymbolDefinition, to_json_dict(symbol))

    assert restored.symbol == "p_i"
    assert restored.first_used_in == Path("subproblems/q2/model_derivation.md")


def test_subproblem_solution_contract_records_all_required_paths():
    contract = SubproblemSolutionContract(
        subproblem_id="q1",
        question_text="设计抽样检测方案。",
        problem_type="sampling_test",
        dependencies=[],
        input_artifacts=[Path("contracts/problem_contract.json")],
        model_derivation_path=Path("subproblems/q1/model_derivation.md"),
        algorithm_path=Path("subproblems/q1/algorithm.md"),
        solver_path=Path("subproblems/q1/solver.py"),
        result_path=Path("subproblems/q1/result.csv"),
        result_interpretation_path=Path("subproblems/q1/result_interpretation.md"),
        symbol_delta_path=Path("subproblems/q1/symbol_delta.json"),
        claim_delta_path=Path("subproblems/q1/claim_delta.json"),
        status="complete",
    )

    payload = to_json_dict(contract)
    restored = from_json_dict(SubproblemSolutionContract, payload)

    assert restored.status == "complete"
    assert restored.result_path == Path("subproblems/q1/result.csv")


def test_contract_store_writes_staged_manifest_and_symbol_table(tmp_path):
    store = ContractStore(tmp_path)
    outline = PaperOutline(
        title="生产过程中的决策问题",
        problem_background_summary="企业需要在检测成本和调换损失之间权衡。",
        subproblem_ids=["q1", "q2"],
        section_order=["00_title.md", "01_abstract.md"],
        early_sections=["00_title.md"],
        deferred_sections=["01_abstract.md"],
        abstract_policy="write_last_after_results",
    )
    manifest = StagedPaperManifest(
        outline_path=Path("paper_outline.json"),
        early_section_paths=[Path("paper/pre_sections/00_title.md")],
        subproblem_contract_paths=[Path("subproblems/q1/solution_contract.json")],
        symbol_table_path=Path("symbol_table.json"),
        final_section_paths=[Path("paper/sections/01_abstract.md")],
        abstract_generated_after_results=True,
    )
    symbols = [
        SymbolDefinition(
            symbol="x",
            meaning="是否检测",
            unit="0/1",
            source_subproblem_id="q1",
            first_used_in=Path("subproblems/q1/model_derivation.md"),
            definition_artifact=Path("subproblems/q1/symbol_delta.json"),
        )
    ]

    outline_path = store.write_paper_outline(outline)
    manifest_path = store.write_staged_paper_manifest(manifest)
    symbol_path = store.write_symbol_table(symbols)

    assert outline_path == tmp_path / "paper_outline.json"
    assert manifest_path == tmp_path / "staged_paper_manifest.json"
    assert symbol_path == tmp_path / "symbol_table.json"
    assert store.read_symbol_table()[0].symbol == "x"
