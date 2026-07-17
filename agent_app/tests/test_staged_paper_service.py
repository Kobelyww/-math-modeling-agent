from __future__ import annotations

import importlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from agent_app.services.subproblem_solution import (
    aggregate_symbol_deltas,
    write_subproblem_solution_packages,
)


def _staged_paper_module() -> Any:
    try:
        return importlib.import_module("agent_app.services.staged_paper")
    except ModuleNotFoundError as exc:
        if exc.name == "agent_app.services.staged_paper":
            pytest.fail("agent_app.services.staged_paper module is missing")
        raise


def test_build_paper_outline_marks_abstract_last():
    staged_paper = _staged_paper_module()
    problem_brief = {
        "title": "生产过程中的决策问题",
        "background": "企业需要在检测成本和调换损失之间权衡。",
        "subproblems": [{"id": "q1"}, {"id": "q2"}],
    }

    outline = staged_paper.build_paper_outline(problem_brief)

    assert outline.title == "生产过程中的决策问题"
    assert outline.problem_background_summary == "企业需要在检测成本和调换损失之间权衡。"
    assert outline.subproblem_ids == ["q1", "q2"]
    assert outline.abstract_policy == "write_last_after_results"
    assert "01_abstract.md" in outline.deferred_sections
    assert "03_problem_background.md" in outline.deferred_sections
    assert "04_problem_restatement.md" in outline.deferred_sections
    assert "05_problem_analysis.md" in outline.deferred_sections
    assert "06_assumptions.md" in outline.deferred_sections
    assert outline.section_order == list(staged_paper.FINAL_SECTION_FILES)
    assert outline.early_sections == list(staged_paper.EARLY_SECTION_FILES)


def test_write_early_sections_does_not_write_abstract(tmp_path):
    staged_paper = _staged_paper_module()
    problem_brief = {
        "title": "生产过程中的决策问题",
        "background": "企业需要在检测成本和调换损失之间权衡。",
        "subproblems": [
            {"id": "q1", "objective": "设计抽样检测方案，控制检测成本。"},
            {"id": "q2", "objective": "建立生产决策模型，降低调换损失。"},
        ],
    }

    paths = staged_paper.write_early_sections(tmp_path, problem_brief)

    outline_path = tmp_path / "paper_outline.json"
    problem_restatement_path = tmp_path / "paper" / "pre_sections" / "02_problem_restatement.md"
    abstract_path = tmp_path / "paper" / "pre_sections" / "01_abstract.md"

    assert outline_path.exists()
    outline_payload = json.loads(outline_path.read_text(encoding="utf-8"))
    assert outline_payload["abstract_policy"] == "write_last_after_results"
    assert problem_restatement_path.exists()
    assert not abstract_path.exists()
    assert [path.name for path in paths] == list(staged_paper.EARLY_SECTION_FILES)

    problem_restatement = problem_restatement_path.read_text(encoding="utf-8")
    assert "q1" in problem_restatement
    assert "设计抽样检测方案，控制检测成本。" in problem_restatement

    forbidden_final_result_language = ("最终结果", "实验表明", "见结果表")
    for path in paths:
        section_text = path.read_text(encoding="utf-8")
        assert not any(phrase in section_text for phrase in forbidden_final_result_language)

    assumptions = (tmp_path / "paper" / "pre_sections" / "04_preliminary_assumptions.md").read_text(
        encoding="utf-8"
    )
    assert "初步" in assumptions
    assert "仅基于题目与输入资料" in assumptions


def test_write_early_sections_avoids_placeholder_language_for_missing_objective(tmp_path):
    staged_paper = _staged_paper_module()
    problem_brief = {
        "title": "通用建模题",
        "subproblems": [{"id": "q1"}],
    }

    paths = staged_paper.write_early_sections(tmp_path, problem_brief)

    combined_text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "待补充" not in combined_text
    assert "q1" in combined_text
    assert "从题面进一步确认建模目标" in combined_text


def test_write_early_sections_uses_question_text_and_title_for_objectives(tmp_path):
    staged_paper = _staged_paper_module()
    problem_brief = {
        "title": "生产决策题",
        "subproblems": [
            {"id": "q1", "question_text": "请设计抽样检测方案。"},
            {"id": "q2", "title": "建立拆解与退货决策模型"},
        ],
    }

    paths = staged_paper.write_early_sections(tmp_path, problem_brief)

    combined_text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "请设计抽样检测方案。" in combined_text
    assert "建立拆解与退货决策模型" in combined_text
    assert "从题面进一步确认建模目标" not in combined_text


def test_write_final_sections_generates_symbols_and_abstract_last(tmp_path):
    staged_paper = _staged_paper_module()
    plans = [
        {
            "id": "q1",
            "title": "抽样检测方案",
            "problem_type": "sampling_test",
            "algorithm": "搜索最小样本量",
            "result_file": "results/q1.csv",
            "result_rows": [
                {
                    "decision": "选择 n=42 的抽样方案",
                    "objective_value": 0.87,
                    "estimate": 0.93,
                    "diagnostic": "置信区间宽度满足阈值",
                }
            ],
        }
    ]
    staged_paper.write_early_sections(
        tmp_path,
        {
            "title": "生产过程中的决策问题",
            "background": "背景",
            "subproblems": [{"id": "q1", "objective": "抽样检测"}],
        },
    )
    contracts = write_subproblem_solution_packages(tmp_path, plans)
    symbols = aggregate_symbol_deltas(tmp_path)

    paths = staged_paper.write_final_sections_from_staged_artifacts(
        tmp_path,
        contracts,
        symbols,
    )

    assert (tmp_path / "paper" / "sections" / "07_symbols.md").exists()
    assert (tmp_path / "paper" / "sections" / "01_abstract.md").exists()
    assert [path.name for path in paths] == [
        "00_title.md",
        "03_problem_background.md",
        "04_problem_restatement.md",
        "05_problem_analysis.md",
        "06_assumptions.md",
        "02_keywords.md",
        "08_model_derivation.md",
        "09_algorithm_and_solution.md",
        "10_results.md",
        "11_sensitivity.md",
        "12_model_evaluation.md",
        "13_references.md",
        "14_appendix.md",
        "07_symbols.md",
        "01_abstract.md",
    ]
    assert paths[-2].name == "07_symbols.md"
    assert paths[-1].name == "01_abstract.md"
    assert [path.name for path in paths] != list(staged_paper.FINAL_SECTION_FILES)

    symbols_text = (tmp_path / "paper" / "sections" / "07_symbols.md").read_text(
        encoding="utf-8"
    )
    assert "p_q1" in symbols_text

    final_text = (tmp_path / "paper.md").read_text(encoding="utf-8")
    assert final_text.index("# 摘要") < final_text.index("# 关键词")
    assert "建模推导" in final_text
    assert "算法策略" in final_text
    assert "结果解释" in final_text

    manifest = json.loads(
        (tmp_path / "staged_paper_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["abstract_generated_after_results"] is True
    assert manifest["final_section_paths"] == [
        f"paper/sections/{section_file}" for section_file in staged_paper.FINAL_SECTION_FILES
    ]
    tex_text = (tmp_path / "paper.tex").read_text(encoding="utf-8")
    assert "\\section{摘要}" in tex_text
    assert "# 摘要" not in tex_text
    assert "p\\_q1" in tex_text
    assert "\\begin{tabular}" in tex_text


def test_write_final_sections_requires_early_sections(tmp_path):
    staged_paper = _staged_paper_module()
    contracts = write_subproblem_solution_packages(
        tmp_path,
        [
            {
                "id": "q1",
                "title": "抽样检测方案",
                "problem_type": "sampling_test",
                "result_rows": [
                    {
                        "decision": "选择 n=42 的抽样方案",
                        "objective_value": 0.87,
                        "estimate": 0.93,
                        "diagnostic": "置信区间宽度满足阈值",
                    }
                ],
            }
        ],
    )
    symbols = aggregate_symbol_deltas(tmp_path)

    with pytest.raises(FileNotFoundError, match="pre_sections"):
        staged_paper.write_final_sections_from_staged_artifacts(
            tmp_path,
            contracts,
            symbols,
        )


def test_write_final_sections_writes_symbol_table_when_missing(tmp_path):
    staged_paper = _staged_paper_module()
    staged_paper.write_early_sections(
        tmp_path,
        {
            "title": "生产过程中的决策问题",
            "background": "背景",
            "subproblems": [{"id": "q1", "objective": "抽样检测"}],
        },
    )
    contracts = write_subproblem_solution_packages(
        tmp_path,
        [
            {
                "id": "q1",
                "title": "抽样检测方案",
                "problem_type": "sampling_test",
                "result_rows": [
                    {
                        "decision": "选择 n=42 的抽样方案",
                        "objective_value": 0.87,
                        "estimate": 0.93,
                        "diagnostic": "置信区间宽度满足阈值",
                    }
                ],
            }
        ],
    )
    symbols = aggregate_symbol_deltas(tmp_path)
    (tmp_path / "symbol_table.json").unlink()

    staged_paper.write_final_sections_from_staged_artifacts(
        tmp_path,
        contracts,
        symbols,
    )

    symbol_payload = json.loads(
        (tmp_path / "symbol_table.json").read_text(encoding="utf-8")
    )
    assert {item["symbol"] for item in symbol_payload} >= {"x_q1", "p_q1"}
    manifest = json.loads(
        (tmp_path / "staged_paper_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["symbol_table_path"] == "symbol_table.json"


def test_write_final_sections_renders_compile_oriented_latex(tmp_path):
    staged_paper = _staged_paper_module()
    staged_paper.write_early_sections(
        tmp_path,
        {
            "title": "收益_成本 & 风险%",
            "background": "背景包含 100% 约束与 A&B 指标。",
            "subproblems": [{"id": "q1", "objective": "抽样检测"}],
        },
    )
    contracts = write_subproblem_solution_packages(
        tmp_path,
        [
            {
                "id": "q1",
                "title": "抽样检测方案",
                "problem_type": "sampling_test",
                "result_rows": [
                    {
                        "decision": "选择 n=42 的抽样方案",
                        "objective_value": 0.87,
                        "estimate": 0.93,
                        "diagnostic": "置信区间宽度满足阈值",
                    }
                ],
            }
        ],
    )
    symbols = [
        replace(symbol, symbol=f"{symbol.symbol}_extra&safe%")
        for symbol in aggregate_symbol_deltas(tmp_path)
    ]

    staged_paper.write_final_sections_from_staged_artifacts(
        tmp_path,
        contracts,
        symbols,
    )

    tex_text = (tmp_path / "paper.tex").read_text(encoding="utf-8")
    assert "# " not in tex_text
    assert "| --- |" not in tex_text
    assert "收益\\_成本 \\& 风险\\%" in tex_text
    assert "p\\_q1\\_extra\\&safe\\%" in tex_text
    assert "\\begin{itemize}" in tex_text
    assert "\\begin{tabular}" in tex_text


def test_write_final_sections_rejects_solution_artifacts_outside_run(tmp_path):
    staged_paper = _staged_paper_module()
    staged_paper.write_early_sections(
        tmp_path,
        {
            "title": "生产过程中的决策问题",
            "background": "背景",
            "subproblems": [{"id": "q1", "objective": "抽样检测"}],
        },
    )
    contracts = write_subproblem_solution_packages(
        tmp_path,
        [
            {
                "id": "q1",
                "title": "抽样检测方案",
                "problem_type": "sampling_test",
                "result_rows": [
                    {
                        "decision": "选择 n=42 的抽样方案",
                        "objective_value": 0.87,
                        "estimate": 0.93,
                        "diagnostic": "置信区间宽度满足阈值",
                    }
                ],
            }
        ],
    )
    symbols = aggregate_symbol_deltas(tmp_path)
    outside_path = tmp_path.parent / "outside_derivation.md"
    outside_path.write_text("# outside\n", encoding="utf-8")
    unsafe_contract = replace(contracts[0], model_derivation_path=Path(outside_path))

    with pytest.raises(ValueError, match="outside run directory"):
        staged_paper.write_final_sections_from_staged_artifacts(
            tmp_path,
            [unsafe_contract],
            symbols,
        )


def test_write_final_sections_rejects_appendix_artifact_paths_outside_run(tmp_path):
    staged_paper = _staged_paper_module()
    staged_paper.write_early_sections(
        tmp_path,
        {
            "title": "生产过程中的决策问题",
            "background": "背景",
            "subproblems": [{"id": "q1", "objective": "抽样检测"}],
        },
    )
    contracts = write_subproblem_solution_packages(
        tmp_path,
        [
            {
                "id": "q1",
                "title": "抽样检测方案",
                "problem_type": "sampling_test",
                "result_rows": [
                    {
                        "decision": "选择 n=42 的抽样方案",
                        "objective_value": 0.87,
                        "estimate": 0.93,
                        "diagnostic": "置信区间宽度满足阈值",
                    }
                ],
            }
        ],
    )
    symbols = aggregate_symbol_deltas(tmp_path)
    outside_path = tmp_path.parent / "outside_solver.py"
    outside_path.write_text("print('outside')\n", encoding="utf-8")
    unsafe_contract = replace(contracts[0], solver_path=Path(outside_path))

    with pytest.raises(ValueError, match="outside run directory"):
        staged_paper.write_final_sections_from_staged_artifacts(
            tmp_path,
            [unsafe_contract],
            symbols,
        )


def test_write_final_sections_converts_ordered_lists_and_inline_code_to_latex(tmp_path):
    staged_paper = _staged_paper_module()
    staged_paper.write_early_sections(
        tmp_path,
        {
            "title": "生产过程中的决策问题",
            "background": "背景",
            "subproblems": [{"id": "q1", "objective": "抽样检测"}],
        },
    )
    contracts = write_subproblem_solution_packages(
        tmp_path,
        [
            {
                "id": "q1",
                "title": "抽样检测方案",
                "problem_type": "sampling_test",
                "result_rows": [
                    {
                        "decision": "选择 n=42 的抽样方案",
                        "objective_value": 0.87,
                        "estimate": 0.93,
                        "diagnostic": "置信区间宽度满足阈值",
                    }
                ],
            }
        ],
    )
    symbols = aggregate_symbol_deltas(tmp_path)
    algorithm_path = tmp_path / contracts[0].algorithm_path
    algorithm_path.write_text(
        "# 算法\n\n"
        "1. 读取 `p_q1` 参数。\n"
        "2. 输出 `x_q1` 决策。\n",
        encoding="utf-8",
    )

    staged_paper.write_final_sections_from_staged_artifacts(
        tmp_path,
        contracts,
        symbols,
    )

    tex_text = (tmp_path / "paper.tex").read_text(encoding="utf-8")
    assert "1. 读取" not in tex_text
    assert "`" not in tex_text
    assert "\\begin{enumerate}" in tex_text
    assert "\\texttt{p\\_q1}" in tex_text


def test_write_final_sections_supports_relative_run_dir(tmp_path, monkeypatch):
    staged_paper = _staged_paper_module()
    run_dir = tmp_path / "relative_run"
    run_dir.mkdir()
    staged_paper.write_early_sections(
        run_dir,
        {
            "title": "生产过程中的决策问题",
            "background": "背景",
            "subproblems": [{"id": "q1", "objective": "抽样检测"}],
        },
    )
    contracts = write_subproblem_solution_packages(
        run_dir,
        [
            {
                "id": "q1",
                "title": "抽样检测方案",
                "problem_type": "sampling_test",
                "result_rows": [
                    {
                        "decision": "选择 n=42 的抽样方案",
                        "objective_value": 0.87,
                        "estimate": 0.93,
                        "diagnostic": "置信区间宽度满足阈值",
                    }
                ],
            }
        ],
    )
    symbols = aggregate_symbol_deltas(run_dir)
    monkeypatch.chdir(tmp_path)

    staged_paper.write_final_sections_from_staged_artifacts(
        Path("relative_run"),
        contracts,
        symbols,
    )

    assert (run_dir / "paper.md").exists()


def test_write_final_sections_converts_markdown_variants_in_latex(tmp_path):
    staged_paper = _staged_paper_module()
    staged_paper.write_early_sections(
        tmp_path,
        {
            "title": "生产过程中的决策问题",
            "background": "背景",
            "subproblems": [{"id": "q1", "objective": "抽样检测"}],
        },
    )
    contracts = write_subproblem_solution_packages(
        tmp_path,
        [
            {
                "id": "q1",
                "title": "抽样检测方案",
                "problem_type": "sampling_test",
                "result_rows": [
                    {
                        "decision": "选择 n=42 的抽样方案",
                        "objective_value": 0.87,
                        "estimate": 0.93,
                        "diagnostic": "置信区间宽度满足阈值",
                    }
                ],
            }
        ],
    )
    symbols = aggregate_symbol_deltas(tmp_path)
    algorithm_path = tmp_path / contracts[0].algorithm_path
    algorithm_path.write_text(
        "# 算法\n\n"
        "* 读取 `p_q1` 参数。\n"
        "+ 输出 `x_q1` 决策。\n"
        "1) 写入 `result_q1` 表。\n\n"
        "| 字段 | 含义 |\n"
        "| --- | --- |\n"
        "| `p_q1` | 次品率 |\n",
        encoding="utf-8",
    )

    staged_paper.write_final_sections_from_staged_artifacts(
        tmp_path,
        contracts,
        symbols,
    )

    tex_text = (tmp_path / "paper.tex").read_text(encoding="utf-8")
    assert "* 读取" not in tex_text
    assert "+ 输出" not in tex_text
    assert "1) 写入" not in tex_text
    assert "`" not in tex_text
    assert "\\texttt{p\\_q1}" in tex_text
    assert "\\texttt{result\\_q1}" in tex_text


def test_write_final_sections_requires_solution_contracts(tmp_path):
    staged_paper = _staged_paper_module()
    staged_paper.write_early_sections(
        tmp_path,
        {
            "title": "生产过程中的决策问题",
            "background": "背景",
            "subproblems": [{"id": "q1", "objective": "抽样检测"}],
        },
    )

    with pytest.raises(ValueError, match="solution contracts"):
        staged_paper.write_final_sections_from_staged_artifacts(
            tmp_path,
            [],
            [],
        )


def test_write_final_sections_rejects_pre_section_symlink_outside_run(tmp_path):
    staged_paper = _staged_paper_module()
    staged_paper.write_early_sections(
        tmp_path,
        {
            "title": "生产过程中的决策问题",
            "background": "背景",
            "subproblems": [{"id": "q1", "objective": "抽样检测"}],
        },
    )
    contracts = write_subproblem_solution_packages(
        tmp_path,
        [
            {
                "id": "q1",
                "title": "抽样检测方案",
                "problem_type": "sampling_test",
                "result_rows": [
                    {
                        "decision": "选择 n=42 的抽样方案",
                        "objective_value": 0.87,
                        "estimate": 0.93,
                        "diagnostic": "置信区间宽度满足阈值",
                    }
                ],
            }
        ],
    )
    symbols = aggregate_symbol_deltas(tmp_path)
    outside_path = tmp_path.parent / "outside_pre_section.md"
    outside_path.write_text("# outside\n", encoding="utf-8")
    background_path = tmp_path / "paper" / "pre_sections" / "01_problem_background.md"
    background_path.unlink()
    background_path.symlink_to(outside_path)

    with pytest.raises(ValueError, match="outside run directory"):
        staged_paper.write_final_sections_from_staged_artifacts(
            tmp_path,
            contracts,
            symbols,
        )


def test_write_final_sections_requires_contract_manifest_files(tmp_path):
    staged_paper = _staged_paper_module()
    staged_paper.write_early_sections(
        tmp_path,
        {
            "title": "生产过程中的决策问题",
            "background": "背景",
            "subproblems": [{"id": "q1", "objective": "抽样检测"}],
        },
    )
    contracts = write_subproblem_solution_packages(
        tmp_path,
        [
            {
                "id": "q1",
                "title": "抽样检测方案",
                "problem_type": "sampling_test",
                "result_rows": [
                    {
                        "decision": "选择 n=42 的抽样方案",
                        "objective_value": 0.87,
                        "estimate": 0.93,
                        "diagnostic": "置信区间宽度满足阈值",
                    }
                ],
            }
        ],
    )
    symbols = aggregate_symbol_deltas(tmp_path)
    (tmp_path / "subproblems" / "q1" / "solution_contract.json").unlink()

    with pytest.raises(FileNotFoundError, match="solution_contract"):
        staged_paper.write_final_sections_from_staged_artifacts(
            tmp_path,
            contracts,
            symbols,
        )
