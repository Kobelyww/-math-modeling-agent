from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_app.domain.contracts import (
    PaperOutline,
    StagedPaperManifest,
    SubproblemSolutionContract,
    SymbolDefinition,
)
from agent_app.domain.serialization import to_json_dict


EARLY_SECTION_FILES: tuple[str, ...] = (
    "00_title.md",
    "01_problem_background.md",
    "02_problem_restatement.md",
    "03_problem_analysis.md",
    "04_preliminary_assumptions.md",
)

FINAL_SECTION_FILES: tuple[str, ...] = (
    "00_title.md",
    "01_abstract.md",
    "02_keywords.md",
    "03_problem_background.md",
    "04_problem_restatement.md",
    "05_problem_analysis.md",
    "06_assumptions.md",
    "07_symbols.md",
    "08_model_derivation.md",
    "09_algorithm_and_solution.md",
    "10_results.md",
    "11_sensitivity.md",
    "12_model_evaluation.md",
    "13_references.md",
    "14_appendix.md",
)

def build_paper_outline(problem_brief: dict[str, Any]) -> PaperOutline:
    title = _clean_text(problem_brief.get("title")) or "数学建模竞赛论文"
    background = _clean_text(problem_brief.get("background"))
    subproblem_ids = [item["id"] for item in _subproblem_items(problem_brief)]

    deferred_sections = [section_file for section_file in FINAL_SECTION_FILES if section_file != "00_title.md"]

    return PaperOutline(
        title=title,
        problem_background_summary=background,
        subproblem_ids=subproblem_ids,
        section_order=list(FINAL_SECTION_FILES),
        early_sections=list(EARLY_SECTION_FILES),
        deferred_sections=deferred_sections,
        abstract_policy="write_last_after_results",
    )


def write_early_sections(run_dir: Path | str, problem_brief: dict[str, Any]) -> list[Path]:
    run_path = Path(run_dir)
    outline = build_paper_outline(problem_brief)

    outline_path = run_path / "paper_outline.json"
    outline_path.parent.mkdir(parents=True, exist_ok=True)
    outline_path.write_text(
        json.dumps(to_json_dict(outline), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    pre_sections_dir = run_path / "paper" / "pre_sections"
    pre_sections_dir.mkdir(parents=True, exist_ok=True)

    section_texts = _early_section_texts(outline, problem_brief)
    paths: list[Path] = []
    for section_file in EARLY_SECTION_FILES:
        path = pre_sections_dir / section_file
        path.write_text(section_texts[section_file], encoding="utf-8")
        paths.append(path)
    return paths


def write_final_sections_from_staged_artifacts(
    run_dir: Path | str,
    solution_contracts: list[SubproblemSolutionContract],
    symbols: list[SymbolDefinition],
) -> list[Path]:
    run_path = Path(run_dir)
    if not solution_contracts:
        raise ValueError("solution contracts are required for final paper backfill")
    _solution_contract_paths(run_path, solution_contracts)
    _validate_solution_contract_artifacts(run_path, solution_contracts)
    section_dir = run_path / "paper" / "sections"
    section_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    early_sections = {
        "00_title.md": Path("paper/pre_sections/00_title.md"),
        "03_problem_background.md": Path("paper/pre_sections/01_problem_background.md"),
        "04_problem_restatement.md": Path("paper/pre_sections/02_problem_restatement.md"),
        "05_problem_analysis.md": Path("paper/pre_sections/03_problem_analysis.md"),
        "06_assumptions.md": Path("paper/pre_sections/04_preliminary_assumptions.md"),
    }
    for section_file, source_path in early_sections.items():
        paths.append(
            _write_section(section_dir, section_file, _read_required(run_path, source_path))
        )

    _write_symbol_table(run_path, symbols)
    paths.append(_write_section(section_dir, "02_keywords.md", _render_keywords()))
    paths.append(
        _write_section(
            section_dir,
            "08_model_derivation.md",
            _join_contract_files(run_path, solution_contracts, "model_derivation_path"),
        )
    )
    paths.append(
        _write_section(
            section_dir,
            "09_algorithm_and_solution.md",
            _join_contract_files(run_path, solution_contracts, "algorithm_path"),
        )
    )
    paths.append(
        _write_section(
            section_dir,
            "10_results.md",
            _join_contract_files(
                run_path,
                solution_contracts,
                "result_interpretation_path",
            ),
        )
    )
    paths.append(_write_section(section_dir, "11_sensitivity.md", _render_sensitivity()))
    paths.append(
        _write_section(section_dir, "12_model_evaluation.md", _render_model_evaluation())
    )
    paths.append(_write_section(section_dir, "13_references.md", _render_references()))
    paths.append(
        _write_section(
            section_dir,
            "14_appendix.md",
            _render_appendix(run_path, solution_contracts),
        )
    )
    paths.append(_write_section(section_dir, "07_symbols.md", _render_symbol_section(symbols)))

    abstract_path = _write_section(
        section_dir,
        "01_abstract.md",
        _render_abstract(solution_contracts),
    )
    paths.append(abstract_path)

    ordered_paths = [
        section_dir / section_file
        for section_file in FINAL_SECTION_FILES
        if (section_dir / section_file).exists()
    ]
    paper_text = "\n\n".join(
        path.read_text(encoding="utf-8").strip()
        for path in ordered_paths
    )
    (run_path / "paper.md").write_text(f"{paper_text}\n", encoding="utf-8")
    (run_path / "paper.tex").write_text(_render_latex(ordered_paths), encoding="utf-8")
    _write_final_manifest(run_path, solution_contracts, ordered_paths)
    return paths


def _early_section_texts(outline: PaperOutline, problem_brief: dict[str, Any]) -> dict[str, str]:
    subproblems = _subproblem_items(problem_brief)
    background = outline.problem_background_summary or "题目未提供单独的背景说明，后续将以输入资料为准补充。"
    subproblem_lines = _subproblem_lines(subproblems)

    return {
        "00_title.md": f"# {outline.title}\n",
        "01_problem_background.md": (
            "# 问题背景\n\n"
            f"{background}\n"
        ),
        "02_problem_restatement.md": (
            "# 问题重述\n\n"
            "本文前期围绕以下子问题整理建模任务：\n\n"
            f"{subproblem_lines}\n"
        ),
        "03_problem_analysis.md": (
            "# 问题分析\n\n"
            "本阶段只进行题意拆解与建模准备，不写入求解结论。\n\n"
            f"{_analysis_lines(subproblems)}\n"
        ),
        "04_preliminary_assumptions.md": (
            "# 初步假设\n\n"
            "以下假设仅基于题目与输入资料，用于前期建模准备，后续需结合求解过程与证据审查更新。\n\n"
            "- 题目给出的数据、约束和业务描述在前期建模中暂按可信输入处理。\n"
            "- 未在题面中明确给出的参数先作为待审查参数记录，不在本阶段给出结论性取值。\n"
        ),
    }


def _subproblem_items(problem_brief: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    raw_subproblems = problem_brief.get("subproblems", [])
    if not isinstance(raw_subproblems, list):
        return items

    for raw_item in raw_subproblems:
        if not isinstance(raw_item, dict):
            continue
        subproblem_id = _clean_text(raw_item.get("id"))
        if not subproblem_id:
            continue
        items.append(
            {
                "id": subproblem_id,
                "objective": _first_present_text(
                    raw_item,
                    ("objective", "question_text", "title"),
                ),
            }
        )
    return items


def _subproblem_lines(subproblems: list[dict[str, str]]) -> str:
    if not subproblems:
        return "- 暂未识别到编号子问题，后续需从题面补充。\n"
    return "".join(
        f"- {item['id']}: {item['objective'] or '从题面进一步确认建模目标。'}\n"
        for item in subproblems
    )


def _analysis_lines(subproblems: list[dict[str, str]]) -> str:
    if not subproblems:
        return "- 先确认题目目标、约束、输入数据和可交付内容。\n"
    return "".join(
        f"- {item['id']}: 明确目标、约束、输入资料和后续模型接口。"
        f"{' 目标：' + item['objective'] if item['objective'] else ''}\n"
        for item in subproblems
    )


def _clean_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _first_present_text(source: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _clean_text(source.get(key))
        if value:
            return value
    return ""


def _read_required(run_path: Path, path: Path) -> str:
    resolved = _resolve_required_run_artifact(run_path, path)
    return resolved.read_text(encoding="utf-8")


def _write_section(section_dir: Path, section_file: str, text: str) -> Path:
    path = section_dir / section_file
    path.write_text(text if text.endswith("\n") else f"{text}\n", encoding="utf-8")
    return path


def _write_symbol_table(run_path: Path, symbols: list[SymbolDefinition]) -> Path:
    path = run_path / "symbol_table.json"
    path.write_text(
        json.dumps(to_json_dict(symbols), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _render_keywords() -> str:
    return "# 关键词\n\n数学建模；模型推导；算法求解；证据追踪\n"


def _render_symbol_section(symbols: list[SymbolDefinition]) -> str:
    lines = [
        "# 符号说明",
        "",
        "| 符号 | 含义 | 单位 | 来源子问题 |",
        "| --- | --- | --- | --- |",
    ]
    for symbol in symbols:
        lines.append(_render_symbol_row(symbol))
    return "\n".join(lines) + "\n"


def _render_symbol_row(symbol: SymbolDefinition) -> str:
    return (
        f"| {symbol.symbol} | {symbol.meaning} | {symbol.unit} | "
        f"{symbol.source_subproblem_id} |"
    )


def _join_contract_files(
    run_path: Path,
    solution_contracts: list[SubproblemSolutionContract],
    path_attr: str,
) -> str:
    parts: list[str] = []
    for contract in solution_contracts:
        relative_path = getattr(contract, path_attr)
        path = _resolve_required_run_artifact(run_path, relative_path)
        parts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(parts) + "\n"


def _resolve_required_run_artifact(run_path: Path, raw_path: Path | str) -> Path:
    root = run_path.resolve(strict=False)
    relative_or_absolute = Path(raw_path)
    candidate = (
        relative_or_absolute
        if relative_or_absolute.is_absolute()
        else root / relative_or_absolute
    ).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"artifact path outside run directory: {raw_path}") from exc
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"missing staged artifact: {raw_path}")
    return candidate


def _relative_artifact_path(run_path: Path, raw_path: Path | str) -> Path:
    return _resolve_required_run_artifact(run_path, raw_path).relative_to(
        run_path.resolve(strict=False)
    )


def _validate_solution_contract_artifacts(
    run_path: Path, solution_contracts: list[SubproblemSolutionContract]
) -> None:
    for contract in solution_contracts:
        for field_name in (
            "model_derivation_path",
            "algorithm_path",
            "solver_path",
            "result_path",
            "result_interpretation_path",
            "symbol_delta_path",
            "claim_delta_path",
        ):
            _resolve_required_run_artifact(run_path, getattr(contract, field_name))


def _render_sensitivity() -> str:
    return (
        "# 灵敏度与稳健性分析\n\n"
        "本节基于各子问题结果解释中的局限与参数来源，说明结论适用边界。"
        "后续人工审稿时应优先检查关键阈值、数据规模和约束扰动对最终决策的影响。\n"
    )


def _render_model_evaluation() -> str:
    return (
        "# 模型评价\n\n"
        "模型评价从推导完整性、算法可复现性、结果可解释性和参数敏感性展开。"
        "各子问题均保留独立的求解包，便于复核公式、代码、结果表和证据链。\n"
    )


def _render_references() -> str:
    return (
        "# 参考文献\n\n"
        "参考文献由证据检索阶段、本地参考文件和模型方法说明共同维护，"
        "最终提交前需按竞赛格式补全。\n"
    )


def _render_appendix(
    run_path: Path, solution_contracts: list[SubproblemSolutionContract]
) -> str:
    lines = ["# 附录", ""]
    for contract in solution_contracts:
        solver_path = _relative_artifact_path(run_path, contract.solver_path)
        result_path = _relative_artifact_path(run_path, contract.result_path)
        derivation_path = _relative_artifact_path(
            run_path,
            contract.model_derivation_path,
        )
        lines.append(
            "- "
            f"{contract.subproblem_id}: "
            f"{solver_path}, {result_path}, {derivation_path}"
        )
    return "\n".join(lines) + "\n"


def _render_abstract(solution_contracts: list[SubproblemSolutionContract]) -> str:
    subproblem_ids = (
        "、".join(contract.subproblem_id for contract in solution_contracts) or "各"
    )
    return (
        "# 摘要\n\n"
        f"本文按照题面动态识别并求解{subproblem_ids}子问题。"
        "每个子问题均形成建模推导、算法流程、结果表和结果解释，"
        "并在最终论文中通过符号表和证据链回填。"
        "摘要在结果章节之后生成，因此只总结已产出的模型和结果。\n"
    )


def _render_latex(section_paths: list[Path]) -> str:
    body: list[str] = []
    for path in section_paths:
        text = path.read_text(encoding="utf-8")
        heading = _markdown_heading(text, fallback=path.stem)
        body.append(
            "\\section{"
            + _escape_latex(heading)
            + "}\n"
            + _markdown_body_to_latex(text)
        )
    return (
        "\\documentclass[UTF8]{ctexart}\n\\begin{document}\n"
        + "\n".join(body)
        + "\n\\end{document}\n"
    )


def _markdown_heading(text: str, *, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                return heading
        if stripped:
            return stripped
    return fallback


def _markdown_body_to_latex(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    index = 0
    skipped_first_heading = False
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not skipped_first_heading and stripped.startswith("#"):
            skipped_first_heading = True
            index += 1
            continue
        if _is_markdown_table_start(lines, index):
            table_lines: list[str] = []
            while index < len(lines) and _is_table_row(lines[index]):
                table_lines.append(lines[index])
                index += 1
            output.append(_render_latex_table(table_lines))
            continue
        if _is_unordered_list_item(stripped):
            items: list[str] = []
            while index < len(lines):
                item_text = _unordered_list_item_text(lines[index].strip())
                if item_text is None:
                    break
                items.append(item_text)
                index += 1
            output.append(_render_latex_items(items))
            continue
        if _is_ordered_list_item(stripped):
            items = []
            while index < len(lines):
                item_text = _ordered_list_item_text(lines[index].strip())
                if item_text is None:
                    break
                items.append(item_text)
                index += 1
            output.append(_render_latex_items(items, environment="enumerate"))
            continue
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            heading = stripped.lstrip("#").strip()
            command = "subsection" if level <= 2 else "subsubsection"
            output.append(f"\\{command}{{{_escape_latex(heading)}}}\n")
            index += 1
            continue
        if stripped:
            output.append(_render_inline_latex(stripped) + "\n")
        else:
            output.append("\n")
        index += 1
    return "".join(output)


def _is_markdown_table_start(lines: list[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and _is_table_row(lines[index])
        and _is_table_separator(lines[index + 1])
    )


def _is_table_row(line: str) -> bool:
    return line.strip().startswith("|") and line.strip().endswith("|")


def _is_table_separator(line: str) -> bool:
    cells = _table_cells(line)
    return bool(cells) and all(set(cell.strip()) <= {"-", ":"} for cell in cells)


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_unordered_list_item(line: str) -> bool:
    return _unordered_list_item_text(line) is not None


def _unordered_list_item_text(line: str) -> str | None:
    if len(line) < 3 or line[0] not in {"-", "*", "+"} or line[1] != " ":
        return None
    return line[2:].strip()


def _is_ordered_list_item(line: str) -> bool:
    return _ordered_list_item_text(line) is not None


def _ordered_list_item_text(line: str) -> str | None:
    dot_marker, dot_separator, dot_rest = line.partition(".")
    paren_marker, paren_separator, paren_rest = line.partition(")")
    if dot_separator and dot_marker.isdigit() and dot_rest.startswith(" "):
        return dot_rest.strip()
    if paren_separator and paren_marker.isdigit() and paren_rest.startswith(" "):
        return paren_rest.strip()
    return None


def _render_latex_table(table_lines: list[str]) -> str:
    rows = [_table_cells(line) for line in table_lines]
    rows = [
        row
        for row in rows
        if row and not all(set(cell.strip()) <= {"-", ":"} for cell in row)
    ]
    if not rows:
        return ""
    column_count = max(len(row) for row in rows)
    spec = "l" * column_count
    rendered_rows = []
    for row in rows:
        padded = row + [""] * (column_count - len(row))
        rendered_rows.append(
            " & ".join(_render_inline_latex(cell) for cell in padded) + r" \\"
        )
    return (
        "\\begin{tabular}{"
        + spec
        + "}\n"
        + "\n".join(rendered_rows)
        + "\n\\end{tabular}\n"
    )


def _render_latex_items(items: list[str], *, environment: str = "itemize") -> str:
    lines = [f"\\begin{{{environment}}}"]
    lines.extend(f"\\item {_render_inline_latex(item)}" for item in items)
    lines.append(f"\\end{{{environment}}}")
    return "\n".join(lines) + "\n"


def _render_inline_latex(value: str) -> str:
    parts = value.split("`")
    if len(parts) == 1:
        return _escape_latex(value)
    rendered = []
    for index, part in enumerate(parts):
        if index % 2 == 1:
            rendered.append(r"\texttt{" + _escape_latex(part) + "}")
        else:
            rendered.append(_escape_latex(part))
    return "".join(rendered)


def _escape_latex(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def _write_final_manifest(
    run_path: Path,
    solution_contracts: list[SubproblemSolutionContract],
    ordered_paths: list[Path],
) -> None:
    subproblem_contract_paths = _solution_contract_paths(run_path, solution_contracts)
    manifest = StagedPaperManifest(
        outline_path=Path("paper_outline.json"),
        early_section_paths=[
            Path("paper/pre_sections") / section_file
            for section_file in EARLY_SECTION_FILES
        ],
        subproblem_contract_paths=subproblem_contract_paths,
        symbol_table_path=Path("symbol_table.json"),
        final_section_paths=[Path("paper/sections") / path.name for path in ordered_paths],
        abstract_generated_after_results=True,
    )
    (run_path / "staged_paper_manifest.json").write_text(
        json.dumps(to_json_dict(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _solution_contract_paths(
    run_path: Path, solution_contracts: list[SubproblemSolutionContract]
) -> list[Path]:
    paths: list[Path] = []
    for contract in solution_contracts:
        relative_path = (
            Path("subproblems") / contract.subproblem_id / "solution_contract.json"
        )
        resolved_path = _resolve_required_run_artifact(run_path, relative_path)
        paths.append(resolved_path.relative_to(run_path.resolve(strict=False)))
    return paths


__all__ = [
    "EARLY_SECTION_FILES",
    "FINAL_SECTION_FILES",
    "build_paper_outline",
    "write_early_sections",
    "write_final_sections_from_staged_artifacts",
]
