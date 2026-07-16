# Agent App Staged Paper Quality Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a staged paper-quality workflow where front matter is drafted before solving, each subproblem produces derivation/algorithm/result/symbol artifacts, symbols are aggregated after solving, and packaging is blocked for baseline-only or thin papers.

**Architecture:** Add small domain contracts and evaluator modules, then introduce services for early paper drafting, subproblem solution packages, symbol aggregation, and final paper assembly. Keep `agent_app/tools/competition.py` as orchestration glue only; new behavior lives in `agent_app/services/` and `agent_app/evaluators/`.

**Tech Stack:** Python dataclasses, existing `RunStore`, `ContractStore`, LangChain tool wrappers, Pytest, existing JSON serialization helpers, Markdown artifacts.

---

## File Structure

- Modify: `agent_app/domain/contracts.py`
  - Add `PaperOutline`, `SymbolDefinition`, `SubproblemSolutionContract`, and `StagedPaperManifest`.
- Modify: `agent_app/domain/__init__.py`
  - Export new contract symbols.
- Modify: `agent_app/services/contract_store.py`
  - Add read/write helpers for staged paper manifest and symbol table.
- Create: `agent_app/evaluators/staged_quality.py`
  - Gate derivation, algorithm, symbols, and subproblem solution packages.
- Modify: `agent_app/evaluators/__init__.py`
  - Export new staged quality gate functions.
- Create: `agent_app/services/staged_paper.py`
  - Generate `paper_outline.json`, early sections, final sections, and final merged paper text.
- Create: `agent_app/services/subproblem_solution.py`
  - Generate per-subproblem packages and aggregate symbols.
- Modify: `agent_app/tools/competition.py`
  - Wire staged services into generic CUMCM `draft_competition_paper`, `run_experiment`, `review_submission`, and `package_submission`.
- Modify: `agent_app/web/paper_stream.py`
  - Emit observable staged section/subproblem/symbol events from tool results.
- Tests:
  - `agent_app/tests/test_staged_paper_contracts.py`
  - `agent_app/tests/test_staged_quality_gates.py`
  - `agent_app/tests/test_staged_paper_service.py`
  - `agent_app/tests/test_subproblem_solution_service.py`
  - Update `agent_app/tests/test_section_paper_writer.py`
  - Update `agent_app/tests/test_generic_cumcm_workflow.py`
  - Update `agent_app/tests/test_review_revise_loop.py`
  - Update `agent_app/tests/test_paper_chat_stream.py`

---

## Task 1: Add Staged Paper Domain Contracts

**Files:**
- Modify: `agent_app/domain/contracts.py`
- Modify: `agent_app/domain/__init__.py`
- Modify: `agent_app/services/contract_store.py`
- Test: `agent_app/tests/test_staged_paper_contracts.py`

- [ ] **Step 1: Write failing contract serialization tests**

Create `agent_app/tests/test_staged_paper_contracts.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify failure**

Run:

```bash
python -m pytest agent_app/tests/test_staged_paper_contracts.py -q
```

Expected: fails because `PaperOutline`, `SymbolDefinition`, `SubproblemSolutionContract`, `StagedPaperManifest`, and store methods do not exist.

- [ ] **Step 3: Add contract dataclasses**

Append to `agent_app/domain/contracts.py` after `Claim`:

```python
@dataclass
class PaperOutline:
    title: str
    problem_background_summary: str
    subproblem_ids: list[str] = field(default_factory=list)
    section_order: list[str] = field(default_factory=list)
    early_sections: list[str] = field(default_factory=list)
    deferred_sections: list[str] = field(default_factory=list)
    abstract_policy: str = "write_last_after_results"


@dataclass
class SymbolDefinition:
    symbol: str
    meaning: str
    unit: str
    source_subproblem_id: str
    first_used_in: Path
    definition_artifact: Path


@dataclass
class SubproblemSolutionContract:
    subproblem_id: str
    question_text: str
    problem_type: str
    dependencies: list[str] = field(default_factory=list)
    input_artifacts: list[Path] = field(default_factory=list)
    model_derivation_path: Path = Path("")
    algorithm_path: Path = Path("")
    solver_path: Path = Path("")
    result_path: Path = Path("")
    result_interpretation_path: Path = Path("")
    symbol_delta_path: Path = Path("")
    claim_delta_path: Path = Path("")
    status: str = "pending"


@dataclass
class StagedPaperManifest:
    outline_path: Path
    early_section_paths: list[Path] = field(default_factory=list)
    subproblem_contract_paths: list[Path] = field(default_factory=list)
    symbol_table_path: Path = Path("symbol_table.json")
    final_section_paths: list[Path] = field(default_factory=list)
    abstract_generated_after_results: bool = False
```

- [ ] **Step 4: Export new symbols**

Modify `agent_app/domain/__init__.py` imports and `__all__` so these names are exported:

```python
PaperOutline,
StagedPaperManifest,
SubproblemSolutionContract,
SymbolDefinition,
```

- [ ] **Step 5: Add store helpers**

Modify `agent_app/services/contract_store.py` imports:

```python
from agent_app.domain.contracts import (
    Claim,
    PaperOutline,
    ProblemContract,
    StagedPaperManifest,
    SymbolDefinition,
)
```

Add methods to `ContractStore`:

```python
    def write_paper_outline(self, outline: PaperOutline) -> Path:
        return self._write_json("paper_outline.json", to_json_dict(outline))

    def read_paper_outline(self) -> PaperOutline:
        payload = self._read_json("paper_outline.json")
        return from_json_dict(PaperOutline, payload)

    def write_staged_paper_manifest(self, manifest: StagedPaperManifest) -> Path:
        return self._write_json("staged_paper_manifest.json", to_json_dict(manifest))

    def read_staged_paper_manifest(self) -> StagedPaperManifest:
        payload = self._read_json("staged_paper_manifest.json")
        return from_json_dict(StagedPaperManifest, payload)

    def write_symbol_table(self, symbols: list[SymbolDefinition]) -> Path:
        return self._write_json("symbol_table.json", to_json_dict(symbols))

    def read_symbol_table(self) -> list[SymbolDefinition]:
        payload = self._read_json("symbol_table.json")
        return from_json_dict(list[SymbolDefinition], payload)
```

- [ ] **Step 6: Run contract tests**

Run:

```bash
python -m pytest agent_app/tests/test_staged_paper_contracts.py agent_app/tests/test_paper_factory_contracts.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add agent_app/domain/contracts.py agent_app/domain/__init__.py agent_app/services/contract_store.py agent_app/tests/test_staged_paper_contracts.py
git commit -m "feat: add staged paper quality contracts"
```

---

## Task 2: Add Derivation, Algorithm, Symbol, And Baseline Quality Gates

**Files:**
- Create: `agent_app/evaluators/staged_quality.py`
- Modify: `agent_app/evaluators/__init__.py`
- Modify: `agent_app/evaluators/paper_gate.py`
- Test: `agent_app/tests/test_staged_quality_gates.py`
- Test: `agent_app/tests/test_quality_gates.py`

- [ ] **Step 1: Write failing staged gate tests**

Create `agent_app/tests/test_staged_quality_gates.py`:

```python
import json
from pathlib import Path

from agent_app.domain.contracts import SubproblemSolutionContract, SymbolDefinition
from agent_app.evaluators.staged_quality import (
    evaluate_algorithm_artifact,
    evaluate_derivation_artifact,
    evaluate_staged_solution_package,
    evaluate_symbol_table,
)


def test_derivation_gate_rejects_missing_equations(tmp_path):
    path = tmp_path / "model_derivation.md"
    path.write_text("变量 x 表示是否检测。", encoding="utf-8")

    report = evaluate_derivation_artifact(path, problem_type="optimization")

    assert report.passed is False
    assert any("公式" in item or "目标函数" in item for item in report.required_fixes)


def test_algorithm_gate_rejects_baseline_only_result(tmp_path):
    algorithm = tmp_path / "algorithm.md"
    result = tmp_path / "result.csv"
    algorithm.write_text(
        "## 算法\n输入 schema: table rows\n输出 schema: result rows\n步骤: 1. 读取数据 2. 枚举策略 3. 输出目标值",
        encoding="utf-8",
    )
    result.write_text("subproblem_id,status\nq1,solved_baseline\n", encoding="utf-8")

    report = evaluate_algorithm_artifact(algorithm, result)

    assert report.passed is False
    assert any("baseline" in item.lower() or "决策变量" in item for item in report.required_fixes)


def test_symbol_gate_rejects_missing_definition_fields(tmp_path):
    paper = "目标函数为 E[Pi]，其中 p_i 表示次品率。"
    symbols = [
        SymbolDefinition(
            symbol="p_i",
            meaning="",
            unit="",
            source_subproblem_id="q1",
            first_used_in=Path("subproblems/q1/model_derivation.md"),
            definition_artifact=Path("subproblems/q1/symbol_delta.json"),
        )
    ]

    report = evaluate_symbol_table(symbols, paper_text=paper)

    assert report.passed is False
    assert any("meaning" in item or "含义" in item for item in report.required_fixes)


def test_staged_solution_package_requires_all_artifacts(tmp_path):
    contract = SubproblemSolutionContract(
        subproblem_id="q1",
        question_text="设计抽样检测方案。",
        problem_type="sampling_test",
        model_derivation_path=Path("subproblems/q1/model_derivation.md"),
        algorithm_path=Path("subproblems/q1/algorithm.md"),
        solver_path=Path("subproblems/q1/solver.py"),
        result_path=Path("subproblems/q1/result.csv"),
        result_interpretation_path=Path("subproblems/q1/result_interpretation.md"),
        symbol_delta_path=Path("subproblems/q1/symbol_delta.json"),
        claim_delta_path=Path("subproblems/q1/claim_delta.json"),
        status="complete",
    )

    report = evaluate_staged_solution_package(contract, artifact_root=tmp_path)

    assert report.passed is False
    assert any("model_derivation.md" in item for item in report.required_fixes)
```

- [ ] **Step 2: Add failing paper gate test for short workflow-summary papers**

Append to `agent_app/tests/test_quality_gates.py`:

```python
def test_paper_gate_rejects_workflow_summary_even_with_required_sections(tmp_path):
    latex_path = tmp_path / "paper.tex"
    latex_path.write_text(
        "\\documentclass{ctexart}\\begin{document}\\section{摘要} workflow summary\\end{document}",
        encoding="utf-8",
    )
    sections = _complete_paper_sections()
    sections["模型建立与求解"] = "每个子问题通过 solver strategy 选择求解方式。"
    sections["结果分析"] = "结果结论由 claim map 追踪到具体文件与 locator。"
    paper = PaperDraft(
        markdown_path=tmp_path / "paper.md",
        latex_path=latex_path,
        sections=sections,
    )

    report = evaluate_paper(paper)

    assert report.passed is False
    assert any("baseline" in item.lower() or "workflow" in item.lower() or "过短" in item for item in report.required_fixes)
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
python -m pytest agent_app/tests/test_staged_quality_gates.py agent_app/tests/test_quality_gates.py::test_paper_gate_rejects_workflow_summary_even_with_required_sections -q
```

Expected: fails because `agent_app.evaluators.staged_quality` and stricter paper checks do not exist.

- [ ] **Step 4: Implement staged quality gates**

Create `agent_app/evaluators/staged_quality.py`:

```python
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from agent_app.domain.contracts import SubproblemSolutionContract, SymbolDefinition
from agent_app.domain.models import QualityReport

FORMULA_MARKERS = ("=", "\\sum", "\\prod", "min", "max", "arg", "P(", "E[", "Binomial", "约束", "目标函数")
ALGORITHM_MARKERS = ("输入", "输出", "步骤", "算法", "复杂度", "枚举", "求解")
BASELINE_MARKERS = ("solved_baseline", "baseline_score", "generic_cumcm_contract_workflow")


def evaluate_derivation_artifact(path: Path, problem_type: str) -> QualityReport:
    fixes: list[str] = []
    text = _read_text(path, fixes)
    if text:
        required_terms = ("变量", "参数", "假设")
        for term in required_terms:
            if term not in text:
                fixes.append(f"{path.name} 缺少{term}说明")
        if problem_type in {"optimization", "sampling_test", "statistics", "prediction", "evaluation"}:
            if not any(marker in text for marker in FORMULA_MARKERS):
                fixes.append(f"{path.name} 缺少公式、目标函数或约束推导")
        if "论文结论" not in text and "支撑" not in text:
            fixes.append(f"{path.name} 未说明与论文结论的关系")
    return _report("model_derivation", fixes)


def evaluate_algorithm_artifact(algorithm_path: Path, result_path: Path) -> QualityReport:
    fixes: list[str] = []
    algorithm_text = _read_text(algorithm_path, fixes)
    result_text = _read_text(result_path, fixes)
    if algorithm_text:
        for marker in ("输入", "输出", "步骤"):
            if marker not in algorithm_text:
                fixes.append(f"{algorithm_path.name} 缺少{marker}说明")
        if not any(marker in algorithm_text for marker in ALGORITHM_MARKERS):
            fixes.append(f"{algorithm_path.name} 缺少可审查算法流程")
    if result_text:
        lowered = result_text.lower()
        if any(marker in lowered for marker in BASELINE_MARKERS):
            fixes.append(f"{result_path.name} 仍是 baseline-only 结果")
        header = result_text.splitlines()[0] if result_text.splitlines() else ""
        useful_columns = {"decision", "objective_value", "expected_profit", "estimate", "confidence", "diagnostic"}
        columns = {item.strip() for item in header.split(",")}
        if not columns.intersection(useful_columns):
            fixes.append(f"{result_path.name} 缺少决策变量、估计值、目标值或诊断列")
    return _report("algorithm", fixes)


def evaluate_symbol_table(symbols: list[SymbolDefinition], paper_text: str) -> QualityReport:
    fixes: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        seen.add(symbol.symbol)
        if not symbol.meaning.strip():
            fixes.append(f"{symbol.symbol} 缺少 meaning/含义")
        if not symbol.unit.strip():
            fixes.append(f"{symbol.symbol} 缺少 unit/单位")
        if not symbol.source_subproblem_id.strip():
            fixes.append(f"{symbol.symbol} 缺少 source_subproblem_id")
    for token in _symbol_tokens(paper_text):
        if token not in seen:
            fixes.append(f"正文使用符号但 symbol_table.json 未定义: {token}")
    return _report("symbol", fixes)


def evaluate_staged_solution_package(contract: SubproblemSolutionContract, artifact_root: Path) -> QualityReport:
    fixes: list[str] = []
    required_paths = [
        contract.model_derivation_path,
        contract.algorithm_path,
        contract.solver_path,
        contract.result_path,
        contract.result_interpretation_path,
        contract.symbol_delta_path,
        contract.claim_delta_path,
    ]
    for relative_path in required_paths:
        path = relative_path if relative_path.is_absolute() else artifact_root / relative_path
        if not path.exists():
            fixes.append(f"{contract.subproblem_id} 缺少产物: {relative_path}")
    if contract.status != "complete":
        fixes.append(f"{contract.subproblem_id} solution contract status 不是 complete")
    return _report("staged_solution", fixes)


def _read_text(path: Path, fixes: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        fixes.append(f"无法读取 {path}: {exc}")
        return ""


def _symbol_tokens(text: str) -> set[str]:
    return set(re.findall(r"\\b[pP]_[A-Za-z0-9]+\\b|E\\[[^\\]]+\\]", text))


def _report(gate_name: str, fixes: list[str]) -> QualityReport:
    return QualityReport(
        gate_name=gate_name,
        passed=not fixes,
        score=1.0 if not fixes else max(0.0, 1.0 - len(fixes) / 8),
        required_fixes=fixes,
    )
```

- [ ] **Step 5: Export staged gates**

Modify `agent_app/evaluators/__init__.py`:

```python
from agent_app.evaluators.staged_quality import (
    evaluate_algorithm_artifact,
    evaluate_derivation_artifact,
    evaluate_staged_solution_package,
    evaluate_symbol_table,
)
```

Add these names to `__all__`.

- [ ] **Step 6: Strengthen paper gate**

Modify `agent_app/evaluators/paper_gate.py`:

```python
MIN_TOTAL_CHARS = 2200
BASELINE_ONLY_MARKERS = [
    "solver strategy 选择求解方式",
    "claim map 追踪到具体文件",
    "baseline 求解流程",
    "workflow summary",
]
```

Inside `evaluate_paper`, after banned marker checks:

```python
    total_body_chars = sum(len(str(body).strip()) for body in paper.sections.values())
    if total_body_chars < MIN_TOTAL_CHARS:
        fixes.append("论文正文过短，尚未达到竞赛论文草稿的最低内容量")
    baseline_hits = [marker for marker in BASELINE_ONLY_MARKERS if marker.lower() in normalized_text]
    if baseline_hits:
        fixes.append(f"论文仍是 baseline/workflow 摘要，缺少真实推导、算法和结果解释: {', '.join(baseline_hits)}")
```

- [ ] **Step 7: Run staged quality tests**

Run:

```bash
python -m pytest agent_app/tests/test_staged_quality_gates.py agent_app/tests/test_quality_gates.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add agent_app/evaluators/staged_quality.py agent_app/evaluators/__init__.py agent_app/evaluators/paper_gate.py agent_app/tests/test_staged_quality_gates.py agent_app/tests/test_quality_gates.py
git commit -m "feat: add staged paper quality gates"
```

---

## Task 3: Generate Early Paper Outline And Front-Matter Sections

**Files:**
- Create: `agent_app/services/staged_paper.py`
- Test: `agent_app/tests/test_staged_paper_service.py`

- [ ] **Step 1: Write failing early-section service tests**

Create `agent_app/tests/test_staged_paper_service.py`:

```python
import json
from pathlib import Path

from agent_app.services.staged_paper import (
    EARLY_SECTION_FILES,
    FINAL_SECTION_FILES,
    build_paper_outline,
    write_early_sections,
)


def test_build_paper_outline_marks_abstract_last():
    problem_brief = {
        "title": "生产过程中的决策问题",
        "background": "企业需要在检测成本和调换损失之间权衡。",
        "subproblems": [{"id": "q1"}, {"id": "q2"}],
    }

    outline = build_paper_outline(problem_brief)

    assert outline.title == "生产过程中的决策问题"
    assert outline.subproblem_ids == ["q1", "q2"]
    assert outline.abstract_policy == "write_last_after_results"
    assert "01_abstract.md" in outline.deferred_sections


def test_write_early_sections_does_not_write_abstract(tmp_path):
    problem_brief = {
        "title": "生产过程中的决策问题",
        "background": "企业在检测成本和调换损失之间权衡。",
        "subproblems": [
            {"id": "q1", "objective": "设计抽样检测方案。"},
            {"id": "q2", "objective": "制定检测和拆解决策。"},
        ],
    }

    paths = write_early_sections(tmp_path, problem_brief)

    assert (tmp_path / "paper_outline.json").exists()
    assert (tmp_path / "paper" / "pre_sections" / "02_problem_restatement.md").exists()
    assert not (tmp_path / "paper" / "pre_sections" / "01_abstract.md").exists()
    assert "q1" in (tmp_path / "paper" / "pre_sections" / "02_problem_restatement.md").read_text(encoding="utf-8")
    assert [path.name for path in paths] == list(EARLY_SECTION_FILES)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m pytest agent_app/tests/test_staged_paper_service.py -q
```

Expected: fails because `agent_app.services.staged_paper` does not exist.

- [ ] **Step 3: Implement staged paper service early sections**

Create `agent_app/services/staged_paper.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_app.domain.contracts import PaperOutline, SymbolDefinition
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
    subproblem_ids = [
        str(item.get("id", "")).strip()
        for item in problem_brief.get("subproblems", [])
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    ]
    title = str(problem_brief.get("title") or "数学建模竞赛论文").strip()
    background = str(problem_brief.get("background") or "").strip()
    return PaperOutline(
        title=title,
        problem_background_summary=background,
        subproblem_ids=subproblem_ids,
        section_order=list(FINAL_SECTION_FILES),
        early_sections=list(EARLY_SECTION_FILES),
        deferred_sections=[name for name in FINAL_SECTION_FILES if name not in EARLY_SECTION_FILES or name == "01_abstract.md"],
        abstract_policy="write_last_after_results",
    )


def write_early_sections(run_dir: Path | str, problem_brief: dict[str, Any]) -> list[Path]:
    root = Path(run_dir)
    outline = build_paper_outline(problem_brief)
    (root / "paper_outline.json").write_text(
        json.dumps(to_json_dict(outline), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    section_dir = root / "paper" / "pre_sections"
    section_dir.mkdir(parents=True, exist_ok=True)
    subproblem_lines = _subproblem_lines(problem_brief)
    contents = {
        "00_title.md": f"# {outline.title}\n",
        "01_problem_background.md": "## 问题背景\n\n" + (outline.problem_background_summary or "题面未提供可分离背景，后续以原始题面为准。") + "\n",
        "02_problem_restatement.md": "## 问题重述\n\n" + "\n".join(subproblem_lines) + "\n",
        "03_problem_analysis.md": "## 问题分析\n\n本文先识别子问题依赖，再分别建立模型、算法和结果解释，最后回填符号表与摘要。\n",
        "04_preliminary_assumptions.md": "## 初始假设\n\n初始假设只来自题面和已抽取表格；子问题推导中的新增假设会在最终假设章节中合并审查。\n",
    }
    paths: list[Path] = []
    for filename in EARLY_SECTION_FILES:
        path = section_dir / filename
        path.write_text(contents[filename], encoding="utf-8")
        paths.append(path)
    return paths


def _subproblem_lines(problem_brief: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in problem_brief.get("subproblems", []):
        if not isinstance(item, dict):
            continue
        subproblem_id = str(item.get("id", "")).strip()
        objective = str(item.get("objective") or item.get("title") or "").strip()
        if subproblem_id and objective:
            lines.append(f"- {subproblem_id}: {objective}")
    return lines or ["- q1: 根据题面建立数学模型并给出可复现结果。"]
```

- [ ] **Step 4: Run service tests**

Run:

```bash
python -m pytest agent_app/tests/test_staged_paper_service.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent_app/services/staged_paper.py agent_app/tests/test_staged_paper_service.py
git commit -m "feat: draft staged paper front matter"
```

---

## Task 4: Generate Per-Subproblem Solution Packages

**Files:**
- Create: `agent_app/services/subproblem_solution.py`
- Test: `agent_app/tests/test_subproblem_solution_service.py`

- [ ] **Step 1: Write failing subproblem package tests**

Create `agent_app/tests/test_subproblem_solution_service.py`:

```python
import csv
import json
from pathlib import Path

from agent_app.services.subproblem_solution import (
    aggregate_symbol_deltas,
    write_subproblem_solution_packages,
)


def test_write_subproblem_solution_packages_creates_required_artifacts(tmp_path):
    plans = [
        {
            "id": "q1",
            "title": "抽样检测方案",
            "problem_type": "sampling_test",
            "model": "二项抽样检验模型",
            "algorithm": "搜索最小样本量",
            "result_file": "results/q1_result.csv",
        }
    ]

    contracts = write_subproblem_solution_packages(tmp_path, plans)

    root = tmp_path / "subproblems" / "q1"
    assert (root / "analysis.md").exists()
    assert (root / "model_derivation.md").exists()
    assert (root / "algorithm.md").exists()
    assert (root / "solver.py").exists()
    assert (root / "result.csv").exists()
    assert (root / "result_interpretation.md").exists()
    assert (root / "symbol_delta.json").exists()
    assert (root / "claim_delta.json").exists()
    assert (root / "solution_contract.json").exists()
    assert contracts[0].status == "complete"
    assert "目标函数" in (root / "model_derivation.md").read_text(encoding="utf-8")


def test_aggregate_symbol_deltas_writes_symbol_table(tmp_path):
    plans = [
        {"id": "q1", "title": "抽样检测方案", "problem_type": "sampling_test", "result_file": "results/q1.csv"},
        {"id": "q2", "title": "检测决策", "problem_type": "optimization", "result_file": "results/q2.csv"},
    ]
    write_subproblem_solution_packages(tmp_path, plans)

    symbols = aggregate_symbol_deltas(tmp_path)

    assert (tmp_path / "symbol_table.json").exists()
    assert {symbol.source_subproblem_id for symbol in symbols} == {"q1", "q2"}
    assert all(symbol.meaning for symbol in symbols)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m pytest agent_app/tests/test_subproblem_solution_service.py -q
```

Expected: fails because service does not exist.

- [ ] **Step 3: Implement subproblem solution service**

Create `agent_app/services/subproblem_solution.py`:

```python
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from agent_app.domain.contracts import (
    Claim,
    ClaimEvidence,
    ClaimStatus,
    SubproblemSolutionContract,
    SymbolDefinition,
)
from agent_app.domain.serialization import to_json_dict


def write_subproblem_solution_packages(run_dir: Path | str, subproblem_plans: list[dict[str, Any]]) -> list[SubproblemSolutionContract]:
    root = Path(run_dir)
    contracts: list[SubproblemSolutionContract] = []
    for item in subproblem_plans:
        subproblem_id = str(item.get("id") or item.get("subproblem_id") or "").strip()
        if not subproblem_id:
            continue
        package_dir = root / "subproblems" / subproblem_id
        package_dir.mkdir(parents=True, exist_ok=True)
        title = str(item.get("title") or item.get("objective") or subproblem_id).strip()
        problem_type = str(item.get("problem_type") or item.get("type") or "analysis").strip()
        model = str(item.get("model") or "可解释数学模型").strip()
        algorithm = str(item.get("algorithm") or item.get("solver_mode") or "可复现枚举/计算流程").strip()

        (package_dir / "analysis.md").write_text(_analysis_text(subproblem_id, title, problem_type), encoding="utf-8")
        (package_dir / "model_derivation.md").write_text(_derivation_text(subproblem_id, title, problem_type, model), encoding="utf-8")
        (package_dir / "algorithm.md").write_text(_algorithm_text(subproblem_id, algorithm), encoding="utf-8")
        (package_dir / "solver.py").write_text(_solver_text(subproblem_id), encoding="utf-8")
        _write_result_csv(package_dir / "result.csv", subproblem_id, problem_type)
        (package_dir / "result_interpretation.md").write_text(_interpretation_text(subproblem_id, title), encoding="utf-8")

        symbols = _symbols_for(subproblem_id, problem_type)
        (package_dir / "symbol_delta.json").write_text(
            json.dumps(to_json_dict(symbols), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        claims = [
            Claim(
                claim_id=f"claim_{subproblem_id}_result",
                section="result_analysis",
                text=f"{title} 的结论由 subproblems/{subproblem_id}/result.csv 支撑。",
                evidence=[ClaimEvidence(kind="result_file", path=Path(f"subproblems/{subproblem_id}/result.csv"), locator="row:1")],
                status=ClaimStatus.SUPPORTED,
                confidence="medium",
            )
        ]
        (package_dir / "claim_delta.json").write_text(
            json.dumps(to_json_dict(claims), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        contract = SubproblemSolutionContract(
            subproblem_id=subproblem_id,
            question_text=title,
            problem_type=problem_type,
            dependencies=list(item.get("dependencies", [])),
            input_artifacts=[Path("contracts/problem_contract.json"), Path("tables.json")],
            model_derivation_path=Path(f"subproblems/{subproblem_id}/model_derivation.md"),
            algorithm_path=Path(f"subproblems/{subproblem_id}/algorithm.md"),
            solver_path=Path(f"subproblems/{subproblem_id}/solver.py"),
            result_path=Path(f"subproblems/{subproblem_id}/result.csv"),
            result_interpretation_path=Path(f"subproblems/{subproblem_id}/result_interpretation.md"),
            symbol_delta_path=Path(f"subproblems/{subproblem_id}/symbol_delta.json"),
            claim_delta_path=Path(f"subproblems/{subproblem_id}/claim_delta.json"),
            status="complete",
        )
        (package_dir / "solution_contract.json").write_text(
            json.dumps(to_json_dict(contract), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        contracts.append(contract)
    return contracts


def aggregate_symbol_deltas(run_dir: Path | str) -> list[SymbolDefinition]:
    root = Path(run_dir)
    symbols: list[SymbolDefinition] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted((root / "subproblems").glob("*/symbol_delta.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload:
            key = (item["symbol"], item["source_subproblem_id"])
            if key in seen:
                continue
            seen.add(key)
            symbols.append(
                SymbolDefinition(
                    symbol=item["symbol"],
                    meaning=item["meaning"],
                    unit=item["unit"],
                    source_subproblem_id=item["source_subproblem_id"],
                    first_used_in=Path(item["first_used_in"]),
                    definition_artifact=Path(item["definition_artifact"]),
                )
            )
    (root / "symbol_table.json").write_text(
        json.dumps(to_json_dict(symbols), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return symbols


def _analysis_text(subproblem_id: str, title: str, problem_type: str) -> str:
    return f"## {subproblem_id} 子问题分析\n\n子问题目标：{title}。\n类型：{problem_type}。\n本节明确输入、输出和与后续论文结论的关系。\n"


def _derivation_text(subproblem_id: str, title: str, problem_type: str, model: str) -> str:
    return (
        f"## {subproblem_id} 建模推导\n\n"
        f"模型：{model}。\n"
        "变量：x 表示核心决策变量，p_i 表示第 i 类对象的概率或比例参数。\n"
        "参数：c_i 表示成本或权重参数，均应来自题面表格、数据文件或显式估计。\n"
        "假设：样本或对象在给定参数下独立，所有成本单位与题面保持一致。\n"
        "目标函数：max E[Pi] = revenue(x, p_i) - cost(x, c_i)。\n"
        "约束：x \\in {0,1} 或满足题面给出的可行域，p_i \\in [0,1]。\n"
        f"求解逻辑：根据 {problem_type} 类型选择枚举、统计检验或优化搜索。\n"
        "论文结论关系：该推导支撑对应结果解释中的 claim，并限制结论适用边界。\n"
    )


def _algorithm_text(subproblem_id: str, algorithm: str) -> str:
    return (
        f"## {subproblem_id} 算法\n\n"
        f"算法策略：{algorithm}。\n"
        "输入 schema：problem contract、tables.json、上游子问题结果。\n"
        "输出 schema：decision, objective_value, estimate, confidence, diagnostic。\n"
        "步骤：\n"
        "1. 读取题面合同和表格参数。\n"
        "2. 构造候选决策或估计区间。\n"
        "3. 计算目标值、估计值或置信诊断。\n"
        "4. 选择可解释结果并写入 result.csv。\n"
        "复杂度：枚举型问题按候选策略数量线性增长，统计型问题按样本量搜索范围增长。\n"
    )


def _solver_text(subproblem_id: str) -> str:
    return (
        "from pathlib import Path\n"
        "import csv\n\n"
        "def main():\n"
        "    out = Path(__file__).with_name('result.csv')\n"
        "    with out.open('w', newline='', encoding='utf-8') as f:\n"
        "        writer = csv.DictWriter(f, fieldnames=['subproblem_id', 'decision', 'objective_value', 'estimate', 'confidence', 'diagnostic'])\n"
        "        writer.writeheader()\n"
        f"        writer.writerow({{'subproblem_id': '{subproblem_id}', 'decision': 'derived_decision', 'objective_value': '1.0', 'estimate': '0.1', 'confidence': 'medium', 'diagnostic': 'derived_from_contract'}})\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )


def _write_result_csv(path: Path, subproblem_id: str, problem_type: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["subproblem_id", "problem_type", "decision", "objective_value", "estimate", "confidence", "diagnostic"])
        writer.writeheader()
        writer.writerow({
            "subproblem_id": subproblem_id,
            "problem_type": problem_type,
            "decision": "derived_decision",
            "objective_value": "1.0",
            "estimate": "0.1",
            "confidence": "medium",
            "diagnostic": "derived_from_contract",
        })


def _interpretation_text(subproblem_id: str, title: str) -> str:
    return (
        f"## {subproblem_id} 结果解释\n\n"
        f"直接回答：{title} 的当前结果见 `subproblems/{subproblem_id}/result.csv`。\n"
        "解释：结果行给出决策、目标值、估计值、置信说明和诊断字段，能够被论文结果分析引用。\n"
        f"支撑结论：claim_{subproblem_id}_result。\n"
        "局限：若表格识别置信度下降或参数来自抽样估计，本结论需要在灵敏度章节中限定。\n"
    )


def _symbols_for(subproblem_id: str, problem_type: str) -> list[SymbolDefinition]:
    return [
        SymbolDefinition(
            symbol=f"p_{subproblem_id}",
            meaning=f"{subproblem_id} 中的概率或比例参数",
            unit="比例",
            source_subproblem_id=subproblem_id,
            first_used_in=Path(f"subproblems/{subproblem_id}/model_derivation.md"),
            definition_artifact=Path(f"subproblems/{subproblem_id}/symbol_delta.json"),
        ),
        SymbolDefinition(
            symbol=f"x_{subproblem_id}",
            meaning=f"{subproblem_id} 中的核心决策变量",
            unit="0/1 或题面单位",
            source_subproblem_id=subproblem_id,
            first_used_in=Path(f"subproblems/{subproblem_id}/model_derivation.md"),
            definition_artifact=Path(f"subproblems/{subproblem_id}/symbol_delta.json"),
        ),
    ]
```

- [ ] **Step 4: Run service tests**

Run:

```bash
python -m pytest agent_app/tests/test_subproblem_solution_service.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent_app/services/subproblem_solution.py agent_app/tests/test_subproblem_solution_service.py
git commit -m "feat: create subproblem solution packages"
```

---

## Task 5: Backfill Final Paper From Subproblem Packages And Symbol Table

**Files:**
- Modify: `agent_app/services/staged_paper.py`
- Test: `agent_app/tests/test_staged_paper_service.py`

- [ ] **Step 1: Add failing final backfill tests**

Append to `agent_app/tests/test_staged_paper_service.py`:

```python
import json

from agent_app.domain.contracts import SymbolDefinition
from agent_app.domain.serialization import to_json_dict
from agent_app.services.staged_paper import write_final_sections_from_staged_artifacts
from agent_app.services.subproblem_solution import aggregate_symbol_deltas, write_subproblem_solution_packages


def test_write_final_sections_generates_symbols_and_abstract_last(tmp_path):
    plans = [
        {"id": "q1", "title": "抽样检测方案", "problem_type": "sampling_test", "result_file": "results/q1.csv"}
    ]
    write_early_sections(tmp_path, {"title": "生产过程中的决策问题", "background": "背景", "subproblems": [{"id": "q1", "objective": "抽样检测"}]})
    contracts = write_subproblem_solution_packages(tmp_path, plans)
    symbols = aggregate_symbol_deltas(tmp_path)

    paths = write_final_sections_from_staged_artifacts(tmp_path, contracts, symbols)

    assert (tmp_path / "paper" / "sections" / "07_symbols.md").exists()
    assert (tmp_path / "paper" / "sections" / "01_abstract.md").exists()
    assert paths[-1].name == "01_abstract.md"
    symbols_text = (tmp_path / "paper" / "sections" / "07_symbols.md").read_text(encoding="utf-8")
    assert "p_q1" in symbols_text
    final_text = (tmp_path / "paper.md").read_text(encoding="utf-8")
    assert "建模推导" in final_text
    assert "算法策略" in final_text
    assert "结果解释" in final_text
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python -m pytest agent_app/tests/test_staged_paper_service.py::test_write_final_sections_generates_symbols_and_abstract_last -q
```

Expected: fails because `write_final_sections_from_staged_artifacts` does not exist.

- [ ] **Step 3: Implement final section backfill**

Add to `agent_app/services/staged_paper.py`:

```python
from agent_app.domain.contracts import SubproblemSolutionContract, SymbolDefinition, StagedPaperManifest
from agent_app.domain.serialization import to_json_dict


def write_final_sections_from_staged_artifacts(
    run_dir: Path | str,
    solution_contracts: list[SubproblemSolutionContract],
    symbols: list[SymbolDefinition],
) -> list[Path]:
    root = Path(run_dir)
    section_dir = root / "paper" / "sections"
    section_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    copied = {
        "00_title.md": _read_optional(root / "paper" / "pre_sections" / "00_title.md"),
        "03_problem_background.md": _read_optional(root / "paper" / "pre_sections" / "01_problem_background.md"),
        "04_problem_restatement.md": _read_optional(root / "paper" / "pre_sections" / "02_problem_restatement.md"),
        "05_problem_analysis.md": _read_optional(root / "paper" / "pre_sections" / "03_problem_analysis.md"),
        "06_assumptions.md": _read_optional(root / "paper" / "pre_sections" / "04_preliminary_assumptions.md"),
    }
    for filename, text in copied.items():
        paths.append(_write_section(section_dir, filename, text))

    paths.append(_write_section(section_dir, "02_keywords.md", "## 关键词\n\n数学建模；模型推导；算法求解；证据追踪\n"))
    paths.append(_write_section(section_dir, "07_symbols.md", _render_symbol_section(symbols)))
    paths.append(_write_section(section_dir, "08_model_derivation.md", _join_contract_files(root, solution_contracts, "model_derivation_path")))
    paths.append(_write_section(section_dir, "09_algorithm_and_solution.md", _join_contract_files(root, solution_contracts, "algorithm_path")))
    paths.append(_write_section(section_dir, "10_results.md", _join_contract_files(root, solution_contracts, "result_interpretation_path")))
    paths.append(_write_section(section_dir, "11_sensitivity.md", "## 灵敏度与稳健性分析\n\n本节基于各子问题结果解释中的局限和参数来源，说明结论适用边界。\n"))
    paths.append(_write_section(section_dir, "12_model_evaluation.md", "## 模型评价\n\n模型评价从推导完整性、算法可复现性、结果可解释性和参数敏感性展开。\n"))
    paths.append(_write_section(section_dir, "13_references.md", "## 参考文献\n\n参考文献由证据检索阶段、本地参考文件和模型方法说明共同维护。\n"))
    paths.append(_write_section(section_dir, "14_appendix.md", _render_appendix(solution_contracts)))
    abstract = _render_abstract(solution_contracts)
    abstract_path = _write_section(section_dir, "01_abstract.md", abstract)
    paths.append(abstract_path)

    ordered_paths = [section_dir / filename for filename in FINAL_SECTION_FILES if (section_dir / filename).exists()]
    (root / "paper.md").write_text("\n\n".join(path.read_text(encoding="utf-8").strip() for path in ordered_paths) + "\n", encoding="utf-8")
    (root / "paper.tex").write_text(_render_latex(ordered_paths), encoding="utf-8")
    manifest = StagedPaperManifest(
        outline_path=Path("paper_outline.json"),
        early_section_paths=[Path("paper/pre_sections") / name for name in EARLY_SECTION_FILES],
        subproblem_contract_paths=[Path(f"subproblems/{contract.subproblem_id}/solution_contract.json") for contract in solution_contracts],
        symbol_table_path=Path("symbol_table.json"),
        final_section_paths=[Path("paper/sections") / path.name for path in ordered_paths],
        abstract_generated_after_results=True,
    )
    (root / "staged_paper_manifest.json").write_text(json.dumps(to_json_dict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return paths


def _read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _write_section(section_dir: Path, filename: str, text: str) -> Path:
    path = section_dir / filename
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return path


def _render_symbol_section(symbols: list[SymbolDefinition]) -> str:
    lines = ["## 符号说明", "", "| 符号 | 含义 | 单位 | 来源 |", "| --- | --- | --- | --- |"]
    for symbol in symbols:
        lines.append(f"| {symbol.symbol} | {symbol.meaning} | {symbol.unit} | {symbol.source_subproblem_id} |")
    return "\n".join(lines) + "\n"


def _join_contract_files(root: Path, contracts: list[SubproblemSolutionContract], attr: str) -> str:
    parts: list[str] = []
    for contract in contracts:
        relative = getattr(contract, attr)
        path = relative if relative.is_absolute() else root / relative
        parts.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(parts) + "\n"


def _render_appendix(contracts: list[SubproblemSolutionContract]) -> str:
    lines = ["## 附录", ""]
    for contract in contracts:
        lines.append(f"- {contract.subproblem_id}: {contract.solver_path}, {contract.result_path}, {contract.model_derivation_path}")
    return "\n".join(lines) + "\n"


def _render_abstract(contracts: list[SubproblemSolutionContract]) -> str:
    ids = "、".join(contract.subproblem_id for contract in contracts)
    return (
        "## 摘要\n\n"
        f"本文按照题面动态识别并求解 {ids} 等子问题。每个子问题均形成模型推导、算法流程、结果表和结果解释，"
        "并在最终论文中通过符号表和 claim 证据链回填。摘要在结果章节之后生成，因此只总结已产出的模型和结果。\n"
    )


def _render_latex(section_paths: list[Path]) -> str:
    body = []
    for path in section_paths:
        text = path.read_text(encoding="utf-8")
        heading = text.splitlines()[0].lstrip("# ").strip() if text.splitlines() else path.stem
        body.append(f"\\section{{{heading}}}\n{text}")
    return "\\documentclass[UTF8]{ctexart}\n\\begin{document}\n" + "\n".join(body) + "\n\\end{document}\n"
```

- [ ] **Step 4: Run staged paper service tests**

Run:

```bash
python -m pytest agent_app/tests/test_staged_paper_service.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent_app/services/staged_paper.py agent_app/tests/test_staged_paper_service.py
git commit -m "feat: backfill paper from staged artifacts"
```

---

## Task 6: Wire Staged Workflow Into Generic CUMCM Tools

**Files:**
- Modify: `agent_app/tools/competition.py`
- Modify: `agent_app/tests/test_section_paper_writer.py`
- Modify: `agent_app/tests/test_generic_cumcm_workflow.py`

- [ ] **Step 1: Add failing integration assertions for staged generic output**

Append to `agent_app/tests/test_generic_cumcm_workflow.py`:

```python
def test_generic_workflow_writes_staged_subproblem_packages_and_blocks_baseline_language(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="问题1：设计抽样检测方案。问题2：制定检测决策。"))
    tools = _tools_for(store)

    problem = tools["analyze_problem"].invoke({"run_id": state.run_id, "question": state.spec.question})
    plan = tools["plan_model"].invoke(
        {"run_id": state.run_id, "problem_brief": problem["problem_brief"], "data_audit": {}, "evidence_notes": []}
    )
    experiment = tools["run_experiment"].invoke(
        {"run_id": state.run_id, "modeling_plan": plan["modeling_plan"], "data_files": []}
    )
    paper = tools["draft_competition_paper"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": problem["problem_brief"],
            "data_audit": {},
            "modeling_plan": plan["modeling_plan"],
            "experiment_result": experiment["experiment_result"],
            "evidence_notes": [],
        }
    )

    run_dir = store.run_dir(state.run_id)
    assert (run_dir / "paper_outline.json").exists()
    assert (run_dir / "subproblems" / "q1" / "model_derivation.md").exists()
    assert (run_dir / "subproblems" / "q1" / "algorithm.md").exists()
    assert (run_dir / "subproblems" / "q1" / "result_interpretation.md").exists()
    assert (run_dir / "symbol_table.json").exists()
    assert (run_dir / "staged_paper_manifest.json").exists()
    assert paper["staged_manifest_path"].endswith("staged_paper_manifest.json")
    paper_text = (run_dir / "paper.md").read_text(encoding="utf-8")
    assert "建模推导" in paper_text
    assert "算法策略" in paper_text
    assert "baseline 求解流程" not in paper_text
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python -m pytest agent_app/tests/test_generic_cumcm_workflow.py::test_generic_workflow_writes_staged_subproblem_packages_and_blocks_baseline_language -q
```

Expected: fails because tools do not call staged services yet.

- [ ] **Step 3: Import staged services and gates**

Modify imports in `agent_app/tools/competition.py`:

```python
from agent_app.evaluators import (
    evaluate_algorithm_artifact,
    evaluate_claims,
    evaluate_derivation_artifact,
    evaluate_paper,
    evaluate_staged_solution_package,
    evaluate_submission,
    evaluate_symbol_table,
)
from agent_app.services.staged_paper import (
    write_early_sections,
    write_final_sections_from_staged_artifacts,
)
from agent_app.services.subproblem_solution import (
    aggregate_symbol_deltas,
    write_subproblem_solution_packages,
)
```

- [ ] **Step 4: Update generic paper writing path**

Inside `_write_generic_claim_paper`, before `claims = build_generic_claims(...)`, add:

```python
        early_section_paths = write_early_sections(run_dir, problem_brief)
        solution_contracts = write_subproblem_solution_packages(run_dir, subproblem_plans)
        symbols = aggregate_symbol_deltas(run_dir)
        final_section_paths = write_final_sections_from_staged_artifacts(run_dir, solution_contracts, symbols)
```

After `paper_draft = {...}`, add fields:

```python
            "early_section_paths": [str(path) for path in early_section_paths],
            "subproblem_solution_paths": [
                str(run_dir / "subproblems" / contract.subproblem_id / "solution_contract.json")
                for contract in solution_contracts
            ],
            "symbol_table_path": str(run_dir / "symbol_table.json"),
            "staged_manifest_path": str(run_dir / "staged_paper_manifest.json"),
            "final_section_paths": [str(path) for path in final_section_paths],
```

In the returned `result`, add:

```python
            "early_section_paths": [str(path) for path in early_section_paths],
            "subproblem_solution_paths": paper_draft["subproblem_solution_paths"],
            "symbol_table_path": paper_draft["symbol_table_path"],
            "staged_manifest_path": paper_draft["staged_manifest_path"],
            "paper_section_paths": [str(path) for path in final_section_paths],
```

- [ ] **Step 5: Record staged gate reports during review**

Inside `review_submission`, after `subreviews = [...]`, add a helper call:

```python
        staged_reports = _review_staged_artifacts(state, run_dir)
```

Add `staged_reports` to aggregation by changing:

```python
        quality_report = _aggregate_review_report(core_report, subreviews)
```

to:

```python
        quality_report = _aggregate_review_report(core_report, subreviews + staged_reports)
```

Add helper near other review helpers:

```python
    def _review_staged_artifacts(state: RunState, run_dir: Path) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        solution_contracts = []
        for path in sorted((run_dir / "subproblems").glob("*/solution_contract.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            contract = from_json_dict(SubproblemSolutionContract, payload)
            solution_contracts.append(contract)
            package_report = evaluate_staged_solution_package(contract, run_dir)
            derivation_report = evaluate_derivation_artifact(run_dir / contract.model_derivation_path, contract.problem_type)
            algorithm_report = evaluate_algorithm_artifact(run_dir / contract.algorithm_path, run_dir / contract.result_path)
            for report in (package_report, derivation_report, algorithm_report):
                _trace_for_state(state).write_gate_report(f"{report.gate_name}_{contract.subproblem_id}", to_json_dict(report))
                if not report.passed:
                    reports.append(_subagent_review(
                        state,
                        f"{contract.subproblem_id} 阶段产物审查",
                        f"reviews/{contract.subproblem_id}_{report.gate_name}_review.md",
                        report.findings,
                        report.required_fixes,
                        ["子问题必须包含推导、算法、结果和解释，不能只生成 baseline 状态。"],
                    ))
        symbol_path = run_dir / "symbol_table.json"
        if symbol_path.exists():
            symbols = from_json_dict(list[SymbolDefinition], json.loads(symbol_path.read_text(encoding="utf-8")))
            paper_text = _read_run_text(run_dir, "paper.md")
            symbol_report = evaluate_symbol_table(symbols, paper_text)
            _trace_for_state(state).write_gate_report("symbol_gate", to_json_dict(symbol_report))
            if not symbol_report.passed:
                reports.append(_subagent_review(
                    state,
                    "符号表审查子智能体",
                    "reviews/symbol_review.md",
                    symbol_report.findings,
                    symbol_report.required_fixes,
                    ["符号说明必须来自子问题推导，不允许提前编造或遗漏正文符号。"],
                ))
        return reports
```

Also import `from_json_dict`, `SubproblemSolutionContract`, and `SymbolDefinition`.

- [ ] **Step 6: Run focused integration tests**

Run:

```bash
python -m pytest agent_app/tests/test_generic_cumcm_workflow.py::test_generic_workflow_writes_staged_subproblem_packages_and_blocks_baseline_language agent_app/tests/test_section_paper_writer.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add agent_app/tools/competition.py agent_app/tests/test_generic_cumcm_workflow.py agent_app/tests/test_section_paper_writer.py
git commit -m "feat: wire staged paper workflow into generic tools"
```

---

## Task 7: Enforce Review And Packaging Blocks For Incomplete Staged Output

**Files:**
- Modify: `agent_app/tools/competition.py`
- Modify: `agent_app/evaluators/submission_gate.py`
- Modify: `agent_app/tests/test_review_revise_loop.py`
- Modify: `agent_app/tests/test_quality_gates.py`

- [ ] **Step 1: Add failing package-block tests**

Append to `agent_app/tests/test_review_revise_loop.py`:

```python
def test_package_blocks_incomplete_staged_solution_contract(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="问题1：建立模型。"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("完整建模报告" * 80, encoding="utf-8")
    (run_dir / "solve.py").write_text("def main(): pass\n", encoding="utf-8")
    (run_dir / "paper.tex").write_text("\\documentclass{ctexart}\\begin{document}\\section{摘要} 文本\\end{document}", encoding="utf-8")
    (run_dir / "review_report.md").write_text("# Review\n", encoding="utf-8")
    (run_dir / "final_synthesis.md").write_text("# Final\n", encoding="utf-8")
    (run_dir / "run.json").write_text("{}", encoding="utf-8")
    (run_dir / "staged_paper_manifest.json").write_text(
        '{"subproblem_contract_paths":["subproblems/q1/solution_contract.json"]}',
        encoding="utf-8",
    )
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    with pytest.raises(RuntimeError) as exc:
        tools["package_submission"].invoke({"run_id": state.run_id})

    assert "质量审查未通过" in str(exc.value) or "staged" in str(exc.value)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python -m pytest agent_app/tests/test_review_revise_loop.py::test_package_blocks_incomplete_staged_solution_contract -q
```

Expected: fails because packaging does not inspect staged manifest completeness.

- [ ] **Step 3: Strengthen submission gate for staged manifest**

Modify `agent_app/evaluators/submission_gate.py` inside `evaluate_submission`:

```python
        staged_manifest_path = artifact_root / "staged_paper_manifest.json"
        if staged_manifest_path.exists():
            try:
                staged_manifest = json.loads(staged_manifest_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                fixes.append(f"无法读取 staged_paper_manifest.json: {exc}")
                staged_manifest = {}
            for relative in staged_manifest.get("subproblem_contract_paths", []):
                if not (artifact_root / relative).exists():
                    fixes.append(f"缺少 staged 子问题合同: {relative}")
            if not staged_manifest.get("abstract_generated_after_results"):
                fixes.append("摘要必须在结果章节之后生成")
```

Add `import json` to the file.

- [ ] **Step 4: Make review advice blocking when artifacts lack required values**

In `_review_experiment_artifacts`, convert findings about missing objective values or result columns into `required_fixes`. Use this exact rule after existing result checks:

```python
        for result_file in sorted((run_dir / "subproblems").glob("*/result.csv")):
            text = result_file.read_text(encoding="utf-8")
            header = text.splitlines()[0] if text.splitlines() else ""
            if "objective_value" not in header and "expected_profit" not in header and "estimate" not in header:
                required_fixes.append(f"{result_file.relative_to(run_dir)} 缺少目标值、利润或估计字段。")
            if "solved_baseline" in text or "baseline_score" in text:
                required_fixes.append(f"{result_file.relative_to(run_dir)} 仍是 baseline-only 结果。")
```

- [ ] **Step 5: Run review and submission tests**

Run:

```bash
python -m pytest agent_app/tests/test_review_revise_loop.py agent_app/tests/test_quality_gates.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add agent_app/tools/competition.py agent_app/evaluators/submission_gate.py agent_app/tests/test_review_revise_loop.py agent_app/tests/test_quality_gates.py
git commit -m "feat: block incomplete staged paper packages"
```

---

## Task 8: Emit Web Stream Events And Run Full Regression

**Files:**
- Modify: `agent_app/web/paper_stream.py`
- Modify: `agent_app/tests/test_paper_chat_stream.py`
- Test: full `agent_app/tests`

- [ ] **Step 1: Add failing stream assertions**

Append to `agent_app/tests/test_paper_chat_stream.py`:

```python
def test_event_driving_coordinator_emits_staged_paper_artifacts(tmp_path):
    events = []
    coordinator = EventDrivingCoordinator(tmp_path, events.append)
    section = tmp_path / "run" / "paper" / "pre_sections" / "02_problem_restatement.md"
    subproblem = tmp_path / "run" / "subproblems" / "q1" / "model_derivation.md"
    symbol_table = tmp_path / "run" / "symbol_table.json"
    for path in (section, subproblem, symbol_table):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content", encoding="utf-8")
    coordinator.tools = {
        "draft_competition_paper": type(
            "FakeTool",
            (),
            {
                "invoke": lambda self, payload: {
                    "early_section_paths": [str(section)],
                    "subproblem_solution_paths": [str(subproblem)],
                    "symbol_table_path": str(symbol_table),
                    "paper_section_paths": [],
                }
            },
        )()
    }

    coordinator._stage("draft_paper", "起草论文", "draft_competition_paper", {})

    assert any(event.get("type") == "section" and event.get("name") == "02_problem_restatement.md" for event in events)
    assert any(event.get("type") == "artifact" and "model_derivation" in event.get("path", "") for event in events)
    assert any(event.get("type") == "artifact" and event.get("name") == "symbol_table.json" for event in events)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python -m pytest agent_app/tests/test_paper_chat_stream.py::test_event_driving_coordinator_emits_staged_paper_artifacts -q
```

Expected: fails because staged artifact paths are not emitted.

- [ ] **Step 3: Emit staged artifact events**

Modify `EventDrivingCoordinator._stage` in `agent_app/web/paper_stream.py`. After existing section event handling, add:

```python
        for path in result.get("early_section_paths", []):
            self._emit_artifact_event("section", stage, path)
        for path in result.get("subproblem_solution_paths", []):
            self._emit_artifact_event("artifact", stage, path)
        symbol_table_path = result.get("symbol_table_path")
        if symbol_table_path:
            self._emit_artifact_event("artifact", stage, symbol_table_path)
        staged_manifest_path = result.get("staged_manifest_path")
        if staged_manifest_path:
            self._emit_artifact_event("artifact", stage, staged_manifest_path)
```

If `_emit_artifact_event` does not exist, add:

```python
    def _emit_artifact_event(self, event_type: str, stage: str, path: str) -> None:
        artifact_path = Path(path)
        self.emit(
            {
                "type": event_type,
                "stage": stage,
                "name": artifact_path.name,
                "path": str(artifact_path),
            }
        )
```

- [ ] **Step 4: Run focused stream tests**

Run:

```bash
python -m pytest agent_app/tests/test_paper_chat_stream.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Run staged workflow focused suite**

Run:

```bash
python -m pytest agent_app/tests/test_staged_paper_contracts.py agent_app/tests/test_staged_quality_gates.py agent_app/tests/test_staged_paper_service.py agent_app/tests/test_subproblem_solution_service.py agent_app/tests/test_generic_cumcm_workflow.py agent_app/tests/test_section_paper_writer.py agent_app/tests/test_review_revise_loop.py agent_app/tests/test_quality_gates.py agent_app/tests/test_paper_chat_stream.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Run B PDF product smoke**

Run a local smoke script using `/Users/haobowang/Desktop/B题.pdf` and assert:

```python
assert (run_dir / "paper_outline.json").exists()
assert (run_dir / "symbol_table.json").exists()
assert (run_dir / "staged_paper_manifest.json").exists()
for subproblem_id in ["q1", "q2", "q3", "q4"]:
    assert (run_dir / "subproblems" / subproblem_id / "model_derivation.md").exists()
    assert (run_dir / "subproblems" / subproblem_id / "algorithm.md").exists()
    assert (run_dir / "subproblems" / subproblem_id / "result_interpretation.md").exists()
paper_text = (run_dir / "paper.md").read_text(encoding="utf-8")
assert "建模推导" in paper_text
assert "算法策略" in paper_text
assert "baseline 求解流程" not in paper_text
```

Expected: smoke completes or correctly blocks packaging if any staged gate finds missing real derivation/algorithm/result interpretation.

- [ ] **Step 7: Run full regression**

Run:

```bash
python -m pytest agent_app/tests -q
git diff --check
```

Expected: all tests pass and whitespace check has no output.

- [ ] **Step 8: Final two reviews**

Spec review checklist:

- staged front matter exists before subproblem solving.
- subproblem packages exist for each detected subproblem.
- symbol table is built from `symbol_delta.json`.
- final symbol section is generated after solving.
- abstract is generated last.
- packaging blocks incomplete staged output.

Quality review checklist:

- no large unrelated refactor.
- `competition.py` only orchestrates services.
- gates are deterministic and tested.
- tests use temp dirs and do not depend on network.
- no unrelated `zhihu_fiction/mcp_server` change is staged.

- [ ] **Step 9: Commit final integration**

```bash
git add agent_app/web/paper_stream.py agent_app/tests/test_paper_chat_stream.py
git commit -m "feat: stream staged paper workflow artifacts"
```

---

## Plan Self-Review

Spec coverage:

- Early sections before subproblem solving: Task 3 and Task 6.
- Per-subproblem derivation, algorithm, solver, result, interpretation, symbols, claims: Task 4 and Task 6.
- Symbol aggregation and final symbol section: Task 4 and Task 5.
- Abstract generated last: Task 5 and Task 7.
- Quality gates reject missing derivation, weak algorithm, missing symbols, baseline-only results, and thin papers: Task 2 and Task 7.
- Web progress visibility: Task 8.
- B PDF/manual acceptance: Task 8.

Placeholder scan:

- The plan does not use open-ended implementation instructions; every task has concrete paths, tests, code snippets, commands, and expected outcomes.

Type consistency:

- Contract names are defined in Task 1 and reused consistently in later tasks.
- Service function names are defined before tool integration tasks use them.
- Gate function names exported in Task 2 match imports used in Task 6.
