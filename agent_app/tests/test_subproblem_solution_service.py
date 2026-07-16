from __future__ import annotations

import importlib
import csv
import json
from pathlib import Path

from agent_app.domain.contracts import SymbolDefinition
from agent_app.domain.serialization import from_json_dict
from agent_app.evaluators.staged_quality import (
    evaluate_staged_solution_package,
    evaluate_symbol_table,
)


def _service():
    return importlib.import_module("agent_app.services.subproblem_solution")


def _base_plan(subproblem_id: str = "q1", **overrides: object) -> dict[str, object]:
    plan: dict[str, object] = {
        "id": subproblem_id,
        "title": "抽样检测方案",
        "problem_type": "sampling_test",
        "model": "二项抽样检验模型",
        "algorithm": "搜索最小样本量",
        "result_file": f"results/{subproblem_id}_result.csv",
        "result_rows": [
            {
                "decision": "采用抽样检测方案",
                "objective_value": 0.83,
                "estimate": 0.91,
                "diagnostic": "参数来自计划结果记录",
            }
        ],
    }
    plan.update(overrides)
    return plan


def test_write_subproblem_solution_packages_creates_required_artifacts(tmp_path):
    service = _service()

    contracts = service.write_subproblem_solution_packages(tmp_path, [_base_plan()])

    package_dir = tmp_path / "subproblems" / "q1"
    expected_artifacts = {
        "analysis.md",
        "model_derivation.md",
        "algorithm.md",
        "solver.py",
        "result.csv",
        "result_interpretation.md",
        "symbol_delta.json",
        "claim_delta.json",
        "solution_contract.json",
    }
    assert {path.name for path in package_dir.iterdir()} == expected_artifacts
    assert contracts[0].status == "complete"
    assert "目标函数" in (package_dir / "model_derivation.md").read_text(
        encoding="utf-8"
    )
    assert "抽样检测方案" in (package_dir / "analysis.md").read_text(
        encoding="utf-8"
    )
    assert contracts[0].input_artifacts == [
        Path("contracts/problem_contract.json"),
        Path("tables.json"),
    ]
    assert all("symbol_delta.json" in str(symbol.definition_artifact) for symbol in from_json_dict(
        list[SymbolDefinition],
        json.loads((package_dir / "symbol_delta.json").read_text(encoding="utf-8")),
    ))


def test_aggregate_symbol_deltas_writes_symbol_table(tmp_path):
    service = _service()
    service.write_subproblem_solution_packages(tmp_path, [_base_plan("q1"), _base_plan("q2")])

    symbols = service.aggregate_symbol_deltas(tmp_path)

    symbol_table_path = tmp_path / "symbol_table.json"
    assert symbol_table_path.exists()
    stored_symbols = from_json_dict(
        list[SymbolDefinition],
        json.loads(symbol_table_path.read_text(encoding="utf-8")),
    )
    assert {(symbol.symbol, symbol.source_subproblem_id) for symbol in stored_symbols} == {
        (symbol.symbol, symbol.source_subproblem_id) for symbol in symbols
    }
    assert {symbol.source_subproblem_id for symbol in symbols} == {"q1", "q2"}
    assert all(symbol.meaning for symbol in symbols)


def test_generated_package_passes_staged_solution_quality_gate(tmp_path):
    service = _service()

    [contract] = service.write_subproblem_solution_packages(tmp_path, [_base_plan()])

    report = evaluate_staged_solution_package(contract, tmp_path)
    assert report.passed, report.required_fixes


def test_generated_documents_include_spec_required_reasoning_fields(tmp_path):
    service = _service()
    plan = _base_plan(
        algorithm="二分搜索最小样本量",
        result_rows=[
            {
                "decision": "选择 n=42 的抽样方案",
                "objective_value": 0.87,
                "estimate": 0.93,
                "diagnostic": "置信区间宽度满足阈值",
            }
        ],
    )

    [contract] = service.write_subproblem_solution_packages(tmp_path, [plan])

    package_dir = tmp_path / "subproblems" / contract.subproblem_id
    derivation = (package_dir / "model_derivation.md").read_text(encoding="utf-8")
    algorithm = (package_dir / "algorithm.md").read_text(encoding="utf-8")
    interpretation = (package_dir / "result_interpretation.md").read_text(
        encoding="utf-8"
    )

    assert "参数来源" in derivation
    assert "problem contract" in derivation
    assert "tables.json" in derivation
    assert "算法策略：二分搜索最小样本量" in algorithm
    assert "复杂度" in algorithm
    assert "失败与回退" in algorithm
    assert "直接回答" in interpretation
    assert "为什么成立" in interpretation
    assert "局限与灵敏度" in interpretation
    assert f"{contract.subproblem_id}-result-supported" in interpretation


def test_complete_status_requires_generated_artifacts_to_pass_quality_gate(tmp_path):
    service = _service()
    plan = _base_plan(
        algorithm="",
        result_rows=[
            {
                "decision": "采用抽样检测方案",
                "objective_value": 0.83,
                "estimate": 0.91,
                "diagnostic": "参数来自计划结果记录",
            }
        ],
    )

    [contract] = service.write_subproblem_solution_packages(tmp_path, [plan])

    assert contract.status == "draft"
    report = evaluate_staged_solution_package(contract, tmp_path)
    assert report.passed is False


def test_generated_symbol_table_passes_quality_gate_without_unused_symbols(tmp_path):
    service = _service()
    service.write_subproblem_solution_packages(tmp_path, [_base_plan("q1"), _base_plan("q2")])

    symbols = service.aggregate_symbol_deltas(tmp_path)

    paper_text = (
        "符号表正文只引用生成符号：$x_q1$ 与 $p_q1$ 描述 q1，"
        "$x_q2$ 与 $p_q2$ 描述 q2。"
    )
    report = evaluate_symbol_table(symbols, paper_text)
    assert report.passed, report.required_fixes


def test_common_plan_shapes_use_specific_question_text_and_skip_missing_ids(tmp_path):
    service = _service()
    plans = [
        {
            "subproblem_id": "q1",
            "objective": "确定抽样检测的最小样本量",
            "problem_type": "sampling_test",
        },
        {
            "id": "q2",
            "question_text": "优化多阶段库存调度",
            "problem_type": "optimization",
        },
        {
            "title": "缺少编号的计划应被跳过",
            "problem_type": "analysis",
        },
    ]

    contracts = service.write_subproblem_solution_packages(tmp_path, plans)

    assert [contract.subproblem_id for contract in contracts] == ["q1", "q2"]
    assert contracts[0].question_text == "确定抽样检测的最小样本量"
    assert contracts[1].question_text == "优化多阶段库存调度"
    assert "确定抽样检测的最小样本量" in (
        tmp_path / "subproblems" / "q1" / "analysis.md"
    ).read_text(encoding="utf-8")
    assert "优化多阶段库存调度" in (
        tmp_path / "subproblems" / "q2" / "model_derivation.md"
    ).read_text(encoding="utf-8")
    assert not (tmp_path / "subproblems" / "缺少编号的计划应被跳过").exists()


def test_generated_package_avoids_template_decision_labels(tmp_path):
    service = _service()

    service.write_subproblem_solution_packages(tmp_path, [_base_plan()])

    combined_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "subproblems" / "q1").iterdir()
        if path.is_file() and path.suffix in {".md", ".csv", ".py"}
    )
    assert "accept_generated_plan" not in combined_text
    assert "derived_decision" not in combined_text


def test_package_without_real_result_rows_is_draft_and_unsupported(tmp_path):
    service = _service()
    plan = _base_plan(result_rows=[])

    [contract] = service.write_subproblem_solution_packages(tmp_path, [plan])

    assert contract.status == "draft"
    package_report = evaluate_staged_solution_package(contract, tmp_path)
    assert package_report.passed is False
    claims_payload = json.loads(
        (tmp_path / "subproblems" / "q1" / "claim_delta.json").read_text(
            encoding="utf-8"
        )
    )
    assert claims_payload[0]["status"] == "unsupported"


def test_template_result_label_is_draft_and_unsupported(tmp_path):
    service = _service()
    plan = _base_plan(
        result_rows=[
            {
                "decision": "derived_decision",
                "objective_value": 0.83,
                "estimate": 0.91,
                "diagnostic": "参数来自计划结果记录",
            }
        ],
    )

    [contract] = service.write_subproblem_solution_packages(tmp_path, [plan])

    assert contract.status == "draft"
    claims_payload = json.loads(
        (tmp_path / "subproblems" / "q1" / "claim_delta.json").read_text(
            encoding="utf-8"
        )
    )
    assert claims_payload[0]["status"] == "unsupported"


def test_baseline_marker_in_extra_result_field_is_draft_and_unsupported(tmp_path):
    service = _service()
    plan = _base_plan(
        result_rows=[
            {
                "decision": "采用抽样检测方案",
                "objective_value": 0.83,
                "estimate": 0.91,
                "diagnostic": "参数来自计划结果记录",
                "status": "solved_baseline",
            }
        ],
    )

    [contract] = service.write_subproblem_solution_packages(tmp_path, [plan])

    assert contract.status == "draft"
    claims_payload = json.loads(
        (tmp_path / "subproblems" / "q1" / "claim_delta.json").read_text(
            encoding="utf-8"
        )
    )
    assert claims_payload[0]["status"] == "unsupported"


def test_non_numeric_result_values_are_draft_and_unsupported(tmp_path):
    service = _service()
    plan = _base_plan(
        result_rows=[
            {
                "decision": "采用抽样检测方案",
                "objective_value": "not-a-number",
                "estimate": 0.91,
                "diagnostic": "参数来自计划结果记录",
            }
        ],
    )

    [contract] = service.write_subproblem_solution_packages(tmp_path, [plan])

    assert contract.status == "draft"
    solver_text = (tmp_path / "subproblems" / "q1" / "solver.py").read_text(
        encoding="utf-8"
    )
    assert "not-a-number" not in solver_text
    claims_payload = json.loads(
        (tmp_path / "subproblems" / "q1" / "claim_delta.json").read_text(
            encoding="utf-8"
        )
    )
    assert claims_payload[0]["status"] == "unsupported"


def test_result_csv_quotes_commas_newlines_and_quotes(tmp_path):
    service = _service()
    decision = '方案,A\n"优先检测"'
    plan = _base_plan(
        title="抽样,检测方案",
        result_rows=[
            {
                "decision": decision,
                "objective_value": 0.82,
                "estimate": 0.9,
                "diagnostic": '诊断,"稳定"',
            }
        ],
    )

    service.write_subproblem_solution_packages(tmp_path, [plan])

    with (tmp_path / "subproblems" / "q1" / "result.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["decision"] == decision
    assert rows[0]["diagnostic"] == '诊断,"稳定"'


def test_subproblem_id_collision_is_rejected(tmp_path):
    service = _service()
    plans = [
        _base_plan("q/1"),
        _base_plan("q?1"),
    ]

    try:
        service.write_subproblem_solution_packages(tmp_path, plans)
    except ValueError as exc:
        assert "collision" in str(exc)
    else:
        raise AssertionError("expected collision to be rejected")


def test_symbol_aggregation_rejects_conflicting_duplicate_definitions(tmp_path):
    service = _service()
    service.write_subproblem_solution_packages(tmp_path, [_base_plan("q1")])
    first_delta = tmp_path / "subproblems" / "q1" / "symbol_delta.json"
    second_delta = tmp_path / "subproblems" / "q1_copy" / "symbol_delta.json"
    second_delta.parent.mkdir(parents=True)
    payload = json.loads(first_delta.read_text(encoding="utf-8"))
    payload[0]["meaning"] = "冲突含义"
    second_delta.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    try:
        service.aggregate_symbol_deltas(tmp_path)
    except ValueError as exc:
        assert "Conflicting symbol definition" in str(exc)
    else:
        raise AssertionError("expected conflicting duplicate symbol to be rejected")
