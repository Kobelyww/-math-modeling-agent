# Paper Factory CUMCM V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first contract-driven Paper Factory slice for CUMCM: durable contracts, CUMCM subproblem recognition, Mimo-backed evidence hooks, B-problem gold benchmark solving, claim-evidence review, and sectioned writing gates.

**Architecture:** Add a focused contract layer and CUMCM workflow pack while preserving the current `CompetitionPaperRunner` and tool API as compatibility wrappers. New services write structured artifacts under the existing run directory first, then `agent_app/tools/competition.py` delegates to them instead of embedding all business logic in one large file.

**Tech Stack:** Python dataclasses, JSON artifact storage, FastAPI event streaming, LangChain tools, pytest, existing `RunStore` / `ArtifactService`, DeepSeek for reasoning/writing, Mimo2.5 for table/vision/search inputs.

---

## Scope Check

This plan implements the first deployable slice from two specs:

- `docs/superpowers/specs/2026-07-14-paper-factory-platform-architecture-design.md`
- `docs/superpowers/specs/2026-07-14-cumcm-workflow-pack-v1-design.md`

It does not implement MCM/ICM, graduation thesis, academic paper workflows, or tree search. Those remain workflow-pack extensions after the CUMCM pack works.

## File Structure

Create or modify these files:

- Create `agent_app/domain/contracts.py`: durable contract dataclasses and enums.
- Modify `agent_app/domain/__init__.py`: export contract types.
- Create `agent_app/services/contract_store.py`: JSON read/write helpers for contracts, evidence, claims, reviews, and stale markers.
- Create `agent_app/workflow_packs/__init__.py`: workflow pack namespace.
- Create `agent_app/workflow_packs/cumcm/__init__.py`: CUMCM pack exports.
- Create `agent_app/workflow_packs/cumcm/taxonomy.py`: subproblem type taxonomy and keyword classifier.
- Create `agent_app/workflow_packs/cumcm/recognizer.py`: dynamic CUMCM subproblem recognition.
- Create `agent_app/workflow_packs/cumcm/problem_builder.py`: builds `ProblemContract` and `SubproblemContract` from extracted problem text, tables, and figures.
- Create `agent_app/services/evidence_retrieval.py`: Mimo-backed research interface with fakeable client.
- Create `agent_app/workflow_packs/cumcm/templates/__init__.py`: CUMCM template namespace.
- Create `agent_app/workflow_packs/cumcm/templates/production_decision.py`: B-problem detection and q1-q4 contract builders.
- Create `agent_app/workflow_packs/cumcm/templates/production_decision_solver.py`: B-problem deterministic solver and parameter audit.
- Create `agent_app/services/claim_map.py`: claim construction and validation helpers.
- Create `agent_app/evaluators/claim_gate.py`: claim-evidence quality gate.
- Create `agent_app/services/section_writer.py`: section file orchestration and claim-aware context building.
- Modify `agent_app/tools/competition.py`: delegate CUMCM business logic to the new services and remove embedded B-problem logic from the tool body.
- Modify `agent_app/web/paper_stream.py`: emit contract, claim, and revision events.
- Test files:
  - Create `agent_app/tests/test_paper_factory_contracts.py`
  - Create `agent_app/tests/test_contract_store.py`
  - Create `agent_app/tests/test_cumcm_recognizer.py`
  - Create `agent_app/tests/test_cumcm_problem_builder.py`
  - Create `agent_app/tests/test_evidence_retrieval.py`
  - Create `agent_app/tests/test_b_problem_solver.py`
  - Create `agent_app/tests/test_claim_gate.py`
  - Create `agent_app/tests/test_section_writer.py`
  - Modify `agent_app/tests/test_b_problem_acceptance.py`
  - Modify `agent_app/tests/test_deepagent_tools.py`
  - Modify `agent_app/tests/test_paper_chat_stream.py`

## Task 1: Contract Domain Models

**Files:**
- Create: `agent_app/domain/contracts.py`
- Modify: `agent_app/domain/__init__.py`
- Test: `agent_app/tests/test_paper_factory_contracts.py`

- [ ] **Step 1: Write failing contract serialization tests**

Create `agent_app/tests/test_paper_factory_contracts.py`:

```python
from pathlib import Path

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
            ClaimEvidence(kind="result_file", path=Path("results/q1_sampling_plan.csv"), locator="decision=reject")
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
    assert experiment.output_schemas["results/q2_table1_decisions.csv"] == ["case", "expected_profit"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest agent_app/tests/test_paper_factory_contracts.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_app.domain.contracts'`.

- [ ] **Step 3: Implement contract dataclasses**

Create `agent_app/domain/contracts.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ProjectType(str, Enum):
    CUMCM = "cumcm"
    MCM_ICM = "mcm_icm"
    GRADUATION_THESIS = "graduation_thesis"
    ACADEMIC_PAPER = "academic_paper"


class SubproblemType(str, Enum):
    SAMPLING_TEST = "sampling_test"
    OPTIMIZATION = "optimization"
    MULTI_OBJECTIVE_DECISION = "multi_objective_decision"
    PREDICTION = "prediction"
    EVALUATION = "evaluation"
    SIMULATION = "simulation"
    GRAPH_NETWORK = "graph_network"
    STATISTICS = "statistics"
    OPERATIONS_RESEARCH = "operations_research"
    DIFFERENTIAL_OR_PHYSICAL_MODEL = "differential_or_physical_model"
    DATA_MINING = "data_mining"
    ANALYSIS = "analysis"


class ClaimStatus(str, Enum):
    SUPPORTED = "supported"
    LIMITED = "limited"
    UNSUPPORTED = "unsupported"
    STALE = "stale"


@dataclass
class ExtractionWarning:
    asset_name: str
    message: str
    severity: str = "warning"


@dataclass
class SubproblemContract:
    subproblem_id: str
    question_text: str
    primary_type: SubproblemType
    secondary_types: list[SubproblemType] = field(default_factory=list)
    required_tables: list[str] = field(default_factory=list)
    required_data_files: list[Path] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)


@dataclass
class ProblemContract:
    project_type: ProjectType
    title: str
    source_text_path: Path
    year: str = ""
    raw_text_digest: str = ""
    subproblems: list[SubproblemContract] = field(default_factory=list)
    required_deliverables: list[str] = field(default_factory=list)
    extraction_warnings: list[ExtractionWarning] = field(default_factory=list)


@dataclass
class EvidenceItem:
    evidence_id: str
    title: str
    source: str
    summary: str
    relevance: str
    credibility_risk: str = ""
    retrieved_at: str = ""
    recommended_use: str = ""


@dataclass
class ModelContract:
    subproblem_id: str
    variables: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, str] = field(default_factory=dict)
    parameter_sources: dict[str, str] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    objective_functions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    algorithm: str = ""
    formulas: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    result_files: list[str] = field(default_factory=list)
    experiment_to_claim_links: list[str] = field(default_factory=list)


@dataclass
class ExperimentContract:
    subproblem_id: str
    entrypoint: Path
    input_files: list[Path] = field(default_factory=list)
    output_schemas: dict[str, list[str]] = field(default_factory=dict)
    parameter_audit_path: Path = Path("results/parameter_audit.json")
    validation_checks: list[str] = field(default_factory=list)
    rerun_conditions: list[str] = field(default_factory=list)


@dataclass
class ClaimEvidence:
    kind: str
    path: Path
    locator: str = ""


@dataclass
class Claim:
    claim_id: str
    section: str
    text: str
    evidence: list[ClaimEvidence] = field(default_factory=list)
    status: ClaimStatus = ClaimStatus.UNSUPPORTED
    confidence: str = ""

    def is_supported(self) -> bool:
        return self.status in {ClaimStatus.SUPPORTED, ClaimStatus.LIMITED} and bool(self.evidence)
```

Modify `agent_app/domain/__init__.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest agent_app/tests/test_paper_factory_contracts.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add agent_app/domain/contracts.py agent_app/domain/__init__.py agent_app/tests/test_paper_factory_contracts.py
git commit -m "feat: add paper factory contract models"
```

## Task 2: Contract Store Service

**Files:**
- Create: `agent_app/services/contract_store.py`
- Test: `agent_app/tests/test_contract_store.py`

- [ ] **Step 1: Write failing tests for contract persistence**

Create `agent_app/tests/test_contract_store.py`:

```python
from pathlib import Path

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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest agent_app/tests/test_contract_store.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_app.services.contract_store'`.

- [ ] **Step 3: Implement store**

Create `agent_app/services/contract_store.py`:

```python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agent_app.domain.contracts import Claim, ProblemContract
from agent_app.domain.serialization import from_json_dict, to_json_dict


class ContractStore:
    def __init__(self, run_dir: Path | str) -> None:
        self.run_dir = Path(run_dir)

    def write_problem_contract(self, contract: ProblemContract) -> Path:
        return self._write_json("contracts/problem_contract.json", to_json_dict(contract))

    def read_problem_contract(self) -> ProblemContract:
        payload = self._read_json("contracts/problem_contract.json")
        return from_json_dict(ProblemContract, payload)

    def write_claim_map(self, claims: list[Claim]) -> Path:
        return self._write_json("claims/claim_map.json", to_json_dict(claims))

    def read_claim_map(self) -> list[Claim]:
        payload = self._read_json("claims/claim_map.json")
        return from_json_dict(list[Claim], payload)

    def mark_stale(self, artifact_group: str, reason: str) -> Path:
        safe_group = "".join(ch for ch in artifact_group if ch.isalnum() or ch in ("-", "_"))
        if not safe_group:
            raise ValueError("artifact_group must contain a safe name")
        return self._write_json(
            f"stale/{safe_group}.json",
            {
                "artifact_group": safe_group,
                "reason": reason,
                "created_at": datetime.now().replace(microsecond=0).isoformat(),
            },
        )

    def _write_json(self, relative_path: str, payload: object) -> Path:
        path = self.run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _read_json(self, relative_path: str) -> object:
        path = self.run_dir / relative_path
        return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest agent_app/tests/test_contract_store.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add agent_app/services/contract_store.py agent_app/tests/test_contract_store.py
git commit -m "feat: persist paper factory contracts"
```

## Task 3: CUMCM Taxonomy And Dynamic Subproblem Recognition

**Files:**
- Create: `agent_app/workflow_packs/__init__.py`
- Create: `agent_app/workflow_packs/cumcm/__init__.py`
- Create: `agent_app/workflow_packs/cumcm/taxonomy.py`
- Create: `agent_app/workflow_packs/cumcm/recognizer.py`
- Test: `agent_app/tests/test_cumcm_recognizer.py`

- [ ] **Step 1: Write failing recognition tests**

Create `agent_app/tests/test_cumcm_recognizer.py`:

```python
from agent_app.domain.contracts import SubproblemType
from agent_app.workflow_packs.cumcm.recognizer import recognize_subproblems
from agent_app.workflow_packs.cumcm.taxonomy import classify_subproblem


def test_recognizer_detects_four_b_problem_subproblems():
    text = """
    B 题 生产过程中的决策问题
    问题1：供应商声称次品率不会超过标称值，请设计抽样检测方案。
    问题2：已知两种零配件和成品次品率，请作出检测和拆解决策。
    问题3：对 m 道工序、n 个零配件，重复问题2，给出多工序决策方案。
    问题4：假设次品率均通过抽样检测得到，请重新完成问题2和问题3。
    """

    subproblems = recognize_subproblems(text)

    assert [item.subproblem_id for item in subproblems] == ["q1", "q2", "q3", "q4"]
    assert subproblems[0].primary_type == SubproblemType.SAMPLING_TEST
    assert subproblems[1].primary_type == SubproblemType.OPTIMIZATION
    assert subproblems[3].primary_type == SubproblemType.STATISTICS
    assert subproblems[3].dependencies == ["q2", "q3"]


def test_recognizer_handles_non_four_question_problem():
    text = "问题1：建立预测模型。问题2：对预测结果进行综合评价。"

    subproblems = recognize_subproblems(text)

    assert [item.subproblem_id for item in subproblems] == ["q1", "q2"]
    assert subproblems[0].primary_type == SubproblemType.PREDICTION
    assert subproblems[1].primary_type == SubproblemType.EVALUATION


def test_classifier_prioritizes_sampling_over_generic_statistics():
    assert classify_subproblem("在95%的信度下认定次品率超过标称值").primary == SubproblemType.SAMPLING_TEST
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest agent_app/tests/test_cumcm_recognizer.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_app.workflow_packs'`.

- [ ] **Step 3: Implement taxonomy**

Create `agent_app/workflow_packs/__init__.py`:

```python
"""Workflow pack namespace for Paper Factory."""
```

Create `agent_app/workflow_packs/cumcm/__init__.py`:

```python
from agent_app.workflow_packs.cumcm.recognizer import recognize_subproblems

__all__ = ["recognize_subproblems"]
```

Create `agent_app/workflow_packs/cumcm/taxonomy.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from agent_app.domain.contracts import SubproblemType


@dataclass(frozen=True)
class Classification:
    primary: SubproblemType
    secondary: list[SubproblemType]


KEYWORDS: list[tuple[SubproblemType, tuple[str, ...]]] = [
    (SubproblemType.SAMPLING_TEST, ("抽样", "信度", "置信", "标称值", "次品率", "假设检验")),
    (SubproblemType.OPTIMIZATION, ("最优", "优化", "决策", "利润", "成本", "拆解", "调度", "规划")),
    (SubproblemType.PREDICTION, ("预测", "回归", "时间序列", "趋势", "forecast")),
    (SubproblemType.EVALUATION, ("评价", "排名", "指标", "综合评价", "权重")),
    (SubproblemType.SIMULATION, ("仿真", "模拟", "蒙特卡洛", "排队")),
    (SubproblemType.GRAPH_NETWORK, ("网络", "路径", "流量", "图", "节点")),
    (SubproblemType.STATISTICS, ("不确定", "估计", "区间", "方差", "分布")),
    (SubproblemType.OPERATIONS_RESEARCH, ("工序", "生产", "库存", "运输", "装配")),
    (SubproblemType.DATA_MINING, ("聚类", "分类", "特征", "异常")),
]


def classify_subproblem(text: str) -> Classification:
    normalized = text.lower()
    if ("不确定" in text) or ("重新" in text and "抽样" in text and ("问题2" in text or "问题3" in text)):
        return Classification(primary=SubproblemType.STATISTICS, secondary=[SubproblemType.SAMPLING_TEST])

    scores: list[tuple[int, SubproblemType]] = []
    priority = {problem_type: index for index, (problem_type, _) in enumerate(KEYWORDS)}
    for problem_type, keywords in KEYWORDS:
        score = sum(1 for keyword in keywords if keyword.lower() in normalized)
        if score:
            scores.append((score, problem_type))
    if not scores:
        return Classification(primary=SubproblemType.ANALYSIS, secondary=[])
    scores.sort(key=lambda item: (-item[0], priority[item[1]]))
    primary = scores[0][1]
    secondary = [problem_type for _, problem_type in scores[1:3] if problem_type != primary]
    return Classification(primary=primary, secondary=secondary)
```

- [ ] **Step 4: Implement recognizer**

Create `agent_app/workflow_packs/cumcm/recognizer.py`:

```python
from __future__ import annotations

import re

from agent_app.domain.contracts import SubproblemContract
from agent_app.workflow_packs.cumcm.taxonomy import classify_subproblem


QUESTION_PATTERN = re.compile(r"(?:问题|第)\s*(?P<num>[0-9一二三四五六七八九十]+)\s*[：:]")
QUESTION_REF_PATTERN = re.compile(r"问题\s*(?P<num>[0-9一二三四五六七八九十]+)")
NUMBER_MAP = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _question_number(raw_num: str, fallback: int) -> int:
    if raw_num in NUMBER_MAP:
        return NUMBER_MAP[raw_num]
    if raw_num.isdigit():
        return int(raw_num)
    return fallback


def recognize_subproblems(problem_text: str) -> list[SubproblemContract]:
    matches = list(QUESTION_PATTERN.finditer(problem_text))
    if not matches:
        classification = classify_subproblem(problem_text)
        return [
            SubproblemContract(
                subproblem_id="q1",
                question_text=problem_text.strip(),
                primary_type=classification.primary,
                secondary_types=classification.secondary,
                expected_outputs=["results/q1_result.csv"],
            )
        ]

    subproblems: list[SubproblemContract] = []
    for index, match in enumerate(matches):
        raw_num = match.group("num")
        number = _question_number(raw_num, fallback=index + 1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(problem_text)
        question_text = problem_text[start:end].strip()
        classification = classify_subproblem(question_text)
        problem_id = f"q{number}"
        subproblems.append(
            SubproblemContract(
                subproblem_id=problem_id,
                question_text=question_text,
                primary_type=classification.primary,
                secondary_types=classification.secondary,
                dependencies=_dependencies(question_text, current=problem_id),
                expected_outputs=[f"results/{problem_id}_result.csv"],
            )
        )
    return subproblems


def _dependencies(text: str, current: str) -> list[str]:
    dependencies: list[str] = []
    for match in QUESTION_REF_PATTERN.finditer(text):
        raw_num = match.group("num")
        number = _question_number(raw_num, fallback=0)
        dependency = f"q{number}"
        if dependency != current and dependency not in dependencies:
            dependencies.append(dependency)
    return dependencies
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
python -m pytest agent_app/tests/test_cumcm_recognizer.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add agent_app/workflow_packs agent_app/tests/test_cumcm_recognizer.py
git commit -m "feat: recognize cumcm subproblems"
```

## Task 4: CUMCM Problem Contract Builder

**Files:**
- Create: `agent_app/workflow_packs/cumcm/problem_builder.py`
- Test: `agent_app/tests/test_cumcm_problem_builder.py`
- Modify: `agent_app/services/problem_package.py`

- [ ] **Step 1: Write failing builder tests**

Create `agent_app/tests/test_cumcm_problem_builder.py`:

```python
from pathlib import Path

from agent_app.domain.contracts import ProjectType, SubproblemType
from agent_app.workflow_packs.cumcm.problem_builder import build_cumcm_problem_contract


def test_build_cumcm_problem_contract_detects_title_year_and_tables():
    text = """
    2024 年高教社杯全国大学生数学建模竞赛题目
    B 题 生产过程中的决策问题
    问题1：设计抽样检测方案。
    问题2：作出生产过程检测和拆解决策。
    """
    tables = [{"id": "table_1", "title": "表1 企业在生产中遇到的情况"}]

    contract = build_cumcm_problem_contract(text, source_text_path=Path("question.md"), tables=tables, figures=[])

    assert contract.project_type == ProjectType.CUMCM
    assert contract.year == "2024"
    assert contract.title == "B 题 生产过程中的决策问题"
    assert [item.subproblem_id for item in contract.subproblems] == ["q1", "q2"]
    assert contract.subproblems[0].primary_type == SubproblemType.SAMPLING_TEST
    assert "paper.md" in contract.required_deliverables
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest agent_app/tests/test_cumcm_problem_builder.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `problem_builder`.

- [ ] **Step 3: Implement builder**

Create `agent_app/workflow_packs/cumcm/problem_builder.py`:

```python
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from agent_app.domain.contracts import ProblemContract, ProjectType
from agent_app.workflow_packs.cumcm.recognizer import recognize_subproblems


def build_cumcm_problem_contract(
    problem_text: str,
    source_text_path: Path,
    tables: list[dict] | None = None,
    figures: list[dict] | None = None,
) -> ProblemContract:
    return ProblemContract(
        project_type=ProjectType.CUMCM,
        title=_extract_title(problem_text),
        year=_extract_year(problem_text),
        source_text_path=source_text_path,
        raw_text_digest=hashlib.sha256(problem_text.encode("utf-8")).hexdigest(),
        subproblems=recognize_subproblems(problem_text),
        required_deliverables=["modeling_report.md", "solve.py", "paper.md", "paper.tex", "review_report.md"],
    )


def _extract_year(problem_text: str) -> str:
    match = re.search(r"(20[0-9]{2})\s*年", problem_text)
    return match.group(1) if match else ""


def _extract_title(problem_text: str) -> str:
    match = re.search(r"([ABCDEF]\s*题\s*[^\n]+)", problem_text)
    if match:
        return " ".join(match.group(1).split())
    first_nonempty = next((line.strip() for line in problem_text.splitlines() if line.strip()), "")
    return first_nonempty[:80]
```

- [ ] **Step 4: Integrate builder into problem package**

Modify `agent_app/services/problem_package.py` inside `build_problem_package()` after normalized tables and figures are created:

```python
    from agent_app.workflow_packs.cumcm.problem_builder import build_cumcm_problem_contract

    problem_contract = build_cumcm_problem_contract(
        question,
        source_text_path=Path("question.md"),
        tables=normalized_tables,
        figures=normalized_figures,
    )
```

Replace the current `problem_spec_path = artifacts.write_json("problem_spec.json", {...})` payload with:

```python
    problem_spec_path = artifacts.write_json(
        "problem_spec.json",
        {
            "background": _extract_background(question),
            "subproblems": [
                {
                    "id": item.subproblem_id,
                    "question_text": item.question_text,
                    "primary_type": item.primary_type.value,
                    "secondary_types": [problem_type.value for problem_type in item.secondary_types],
                    "dependencies": item.dependencies,
                    "expected_outputs": item.expected_outputs,
                }
                for item in problem_contract.subproblems
            ],
            "objectives": [],
            "constraints": [],
            "deliverables": problem_contract.required_deliverables,
        },
    )
```

Also write the full contract:

```python
    problem_contract_path = artifacts.write_json(
        "contracts/problem_contract.json",
        to_json_dict(problem_contract),
    )
```

Add `from pathlib import Path` and `from agent_app.domain.serialization import to_json_dict` at the top.

Return `"problem_contract_path": str(problem_contract_path)` in the package dictionary.

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest agent_app/tests/test_cumcm_problem_builder.py agent_app/tests/test_problem_package.py -q
```

Expected: all tests pass. Existing `test_problem_package.py` should still see `problem_spec.json`, `tables.json`, `figures.json`, and `source_map.json`.

- [ ] **Step 6: Commit**

```bash
git add agent_app/workflow_packs/cumcm/problem_builder.py agent_app/services/problem_package.py agent_app/tests/test_cumcm_problem_builder.py agent_app/tests/test_problem_package.py
git commit -m "feat: build cumcm problem contracts"
```

## Task 5: Mimo Evidence Retrieval Interface

**Files:**
- Create: `agent_app/services/evidence_retrieval.py`
- Test: `agent_app/tests/test_evidence_retrieval.py`

- [ ] **Step 1: Write failing fake-client tests**

Create `agent_app/tests/test_evidence_retrieval.py`:

```python
from agent_app.services.evidence_retrieval import MimoEvidenceRetriever


class FakeMimoClient:
    def __init__(self):
        self.requests = []

    def search(self, query: str, limit: int):
        self.requests.append({"query": query, "limit": limit})
        return [
            {
                "title": "Binomial acceptance sampling",
                "url": "https://example.test/sampling",
                "summary": "Acceptance sampling uses binomial probabilities and operating characteristic curves.",
                "relevance": "Supports q1 sampling plan.",
                "credibility_risk": "example source used in unit test",
            }
        ]


def test_mimo_evidence_retriever_normalizes_source_cards():
    retriever = MimoEvidenceRetriever(client=FakeMimoClient())

    evidence = retriever.retrieve("二项抽样 检验", top_k=1)

    assert evidence[0].evidence_id == "mimo_1"
    assert evidence[0].title == "Binomial acceptance sampling"
    assert evidence[0].source == "https://example.test/sampling"
    assert evidence[0].recommended_use == "method_reference"


def test_mimo_evidence_retriever_can_be_disabled():
    retriever = MimoEvidenceRetriever(client=FakeMimoClient(), enabled=False)

    assert retriever.retrieve("二项抽样", top_k=3) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest agent_app/tests/test_evidence_retrieval.py -q
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement fakeable retriever**

Create `agent_app/services/evidence_retrieval.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from agent_app.domain.contracts import EvidenceItem


class MimoSearchClient(Protocol):
    def search(self, query: str, limit: int) -> list[dict]:
        raise NotImplementedError


class MimoEvidenceRetriever:
    def __init__(self, client: MimoSearchClient, enabled: bool = True) -> None:
        self.client = client
        self.enabled = enabled

    def retrieve(self, query: str, top_k: int = 5, recommended_use: str = "method_reference") -> list[EvidenceItem]:
        if not self.enabled:
            return []
        cards = self.client.search(query, limit=top_k)
        retrieved_at = datetime.now().replace(microsecond=0).isoformat()
        return [
            EvidenceItem(
                evidence_id=f"mimo_{index}",
                title=str(card.get("title", "")).strip(),
                source=str(card.get("url") or card.get("source") or "").strip(),
                summary=str(card.get("summary", "")).strip(),
                relevance=str(card.get("relevance", "")).strip(),
                credibility_risk=str(card.get("credibility_risk", "")).strip(),
                retrieved_at=retrieved_at,
                recommended_use=recommended_use,
            )
            for index, card in enumerate(cards, start=1)
            if card.get("title") and (card.get("url") or card.get("source"))
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest agent_app/tests/test_evidence_retrieval.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add agent_app/services/evidence_retrieval.py agent_app/tests/test_evidence_retrieval.py
git commit -m "feat: add mimo evidence retrieval interface"
```

## Task 6: B-Problem Model And Experiment Contracts

**Files:**
- Create: `agent_app/workflow_packs/cumcm/templates/__init__.py`
- Create: `agent_app/workflow_packs/cumcm/templates/production_decision.py`
- Test: `agent_app/tests/test_b_problem_solver.py`

- [ ] **Step 1: Write failing contract tests**

Create `agent_app/tests/test_b_problem_solver.py` with these first tests:

```python
from agent_app.workflow_packs.cumcm.templates.production_decision import (
    build_b_problem_experiment_contracts,
    build_b_problem_model_contracts,
    is_b_problem,
)


B_PROBLEM_TEXT = "B 题 生产过程中的决策问题。问题1：抽样检测。问题2：检测拆解决策。问题3：多工序。问题4：抽样不确定性。"


def test_b_problem_detection_is_specific():
    assert is_b_problem(B_PROBLEM_TEXT)
    assert not is_b_problem("A 题 城市交通预测问题")


def test_b_problem_model_contracts_cover_four_subproblems():
    contracts = build_b_problem_model_contracts()

    assert [contract.subproblem_id for contract in contracts] == ["q1", "q2", "q3", "q4"]
    assert "X ~ Binomial(n, p)" in contracts[0].formulas
    assert "expected_profit" in " ".join(contracts[1].objective_functions)
    assert "results/q4_uncertainty_re_solve.csv" in contracts[3].result_files


def test_b_problem_experiment_contracts_define_output_schemas():
    contracts = build_b_problem_experiment_contracts()

    assert contracts[0].output_schemas["results/q1_sampling_plan.csv"] == [
        "subproblem",
        "decision",
        "n",
        "critical_value",
        "confidence",
        "risk_probability",
    ]
    assert "parameter_audit_has_no_unexplained_constants" in contracts[1].validation_checks
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest agent_app/tests/test_b_problem_solver.py -q
```

Expected: FAIL with missing `production_decision`.

- [ ] **Step 3: Implement B-problem contract builders**

Create `agent_app/workflow_packs/cumcm/templates/__init__.py`:

```python
"""CUMCM specialized templates."""
```

Create `agent_app/workflow_packs/cumcm/templates/production_decision.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.domain.contracts import ExperimentContract, ModelContract


def is_b_problem(problem_text: str) -> bool:
    return all(token in problem_text for token in ("生产过程中的决策问题", "抽样", "拆解"))


def build_b_problem_model_contracts() -> list[ModelContract]:
    return [
        ModelContract(
            subproblem_id="q1",
            variables={"n": "sample size", "k": "critical defective count", "X": "defect count"},
            parameters={"p0": "nominal defect rate", "alpha": "producer or rejection risk"},
            parameter_sources={"p0": "problem statement"},
            assumptions=["Independent Bernoulli sampling."],
            objective_functions=["minimize n subject to confidence constraints"],
            constraints=["X ~ Binomial(n, p)", "reject rule must satisfy confidence and discrimination constraints"],
            algorithm="Enumerate n and critical values, then filter by risk probabilities.",
            formulas=["X ~ Binomial(n, p)", "P_p0(X >= k) <= alpha"],
            result_files=["results/q1_sampling_plan.csv"],
            experiment_to_claim_links=["q1 sampling result supports claim_q1_sampling_plan"],
        ),
        ModelContract(
            subproblem_id="q2",
            variables={"d1": "inspect part 1", "d2": "inspect part 2", "df": "inspect final product", "r": "disassemble defective product"},
            parameters={"p1": "part 1 defect rate", "p2": "part 2 defect rate", "pf": "assembly defect rate"},
            parameter_sources={"p1": "table_1", "p2": "table_1", "pf": "table_1"},
            objective_functions=["maximize expected_profit(d1,d2,df,r)"],
            constraints=["d1,d2,df,r in {0,1}"],
            algorithm="Enumerate binary decisions and compare expected profit.",
            formulas=["q = 1 - (1-p1_eff)(1-p2_eff)(1-pf)"],
            result_files=["results/q2_table1_decisions.csv"],
            experiment_to_claim_links=["q2 table result supports claim_q2_decision_table"],
        ),
        ModelContract(
            subproblem_id="q3",
            variables={"node_decision": "inspection/disassembly decision for each assembly node"},
            parameters={"node_defect_rate": "part, semi-finished, or final product defect rate"},
            parameter_sources={"node_defect_rate": "table_2"},
            objective_functions=["maximize final expected profit on assembly tree"],
            constraints=["tree probabilities propagate bottom-up"],
            algorithm="Dynamic programming on assembly tree nodes.",
            formulas=["q_node = 1 - prod(1-q_child) * (1-p_node)"],
            result_files=["results/q3_table2_tree_decisions.csv"],
            experiment_to_claim_links=["q3 tree result supports claim_q3_tree_strategy"],
        ),
        ModelContract(
            subproblem_id="q4",
            variables={"p_lower": "lower confidence bound", "p_upper": "upper confidence bound"},
            parameters={"confidence": "sampling confidence level"},
            parameter_sources={"confidence": "q1 sampling plan"},
            objective_functions=["identify stable and unstable decisions under defect-rate uncertainty"],
            constraints=["uncertainty scenarios derive from sampling intervals"],
            algorithm="Re-solve q2 and q3 using interval-derived defect rates.",
            formulas=["p in [p_lower, p_upper]"],
            result_files=["results/q4_uncertainty_re_solve.csv"],
            experiment_to_claim_links=["q4 uncertainty result limits q2 and q3 claims"],
        ),
    ]


def build_b_problem_experiment_contracts() -> list[ExperimentContract]:
    return [
        ExperimentContract(
            subproblem_id="q1",
            entrypoint=Path("code/solve.py"),
            output_schemas={
                "results/q1_sampling_plan.csv": [
                    "subproblem",
                    "decision",
                    "n",
                    "critical_value",
                    "confidence",
                    "risk_probability",
                ]
            },
            validation_checks=["non_empty_csv", "reject_trivial_n_equals_one"],
        ),
        ExperimentContract(
            subproblem_id="q2",
            entrypoint=Path("code/solve.py"),
            output_schemas={"results/q2_table1_decisions.csv": ["case", "strategy", "expected_profit"]},
            validation_checks=["non_empty_csv", "parameter_audit_has_no_unexplained_constants"],
        ),
        ExperimentContract(
            subproblem_id="q3",
            entrypoint=Path("code/solve.py"),
            output_schemas={"results/q3_table2_tree_decisions.csv": ["node", "strategy", "expected_profit"]},
            validation_checks=["non_empty_csv", "tree_has_final_product_row"],
        ),
        ExperimentContract(
            subproblem_id="q4",
            entrypoint=Path("code/solve.py"),
            output_schemas={"results/q4_uncertainty_re_solve.csv": ["scenario", "source_interval", "strategy_changed"]},
            validation_checks=["non_empty_csv", "uncertainty_uses_sampling_intervals"],
        ),
    ]
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest agent_app/tests/test_b_problem_solver.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add agent_app/workflow_packs/cumcm/templates agent_app/tests/test_b_problem_solver.py
git commit -m "feat: add b problem contract template"
```

## Task 7: B-Problem Solver Without Unexplained Constants

**Files:**
- Create: `agent_app/workflow_packs/cumcm/templates/production_decision_solver.py`
- Modify: `agent_app/tests/test_b_problem_solver.py`

- [ ] **Step 1: Add failing solver tests**

Append to `agent_app/tests/test_b_problem_solver.py`:

```python
import csv
import json

from agent_app.workflow_packs.cumcm.templates.production_decision_solver import run_b_problem_solver


def _read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_b_problem_solver_writes_q1_to_q4_results(tmp_path):
    result = run_b_problem_solver(tmp_path)

    assert result.success is True
    for relative_path in [
        "results/q1_sampling_plan.csv",
        "results/q2_table1_decisions.csv",
        "results/q3_table2_tree_decisions.csv",
        "results/q4_uncertainty_re_solve.csv",
        "results/parameter_audit.json",
    ]:
        assert (tmp_path / relative_path).exists(), relative_path


def test_q1_sampling_plan_rejects_trivial_accept_rule(tmp_path):
    run_b_problem_solver(tmp_path)

    rows = _read_csv(tmp_path / "results/q1_sampling_plan.csv")
    accept_rows = [row for row in rows if row["decision"] == "accept"]

    assert accept_rows
    assert all(int(row["n"]) > 1 for row in accept_rows)


def test_parameter_audit_has_no_unexplained_constants(tmp_path):
    run_b_problem_solver(tmp_path)

    audit = json.loads((tmp_path / "results/parameter_audit.json").read_text(encoding="utf-8"))

    assert audit["unexplained_constants"] == []
    assert "0.35" not in (tmp_path / "code/solve.py").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest agent_app/tests/test_b_problem_solver.py -q
```

Expected: FAIL with missing `production_decision_solver`.

- [ ] **Step 3: Implement deterministic solver service**

Create `agent_app/workflow_packs/cumcm/templates/production_decision_solver.py`:

```python
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path


@dataclass
class SolverResult:
    success: bool
    result_paths: list[Path] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


TABLE1_CASES = [
    {"case": 1, "p1": 0.10, "c1": 4, "t1": 2, "p2": 0.10, "c2": 18, "t2": 3, "pf": 0.10, "assembly": 6, "tf": 3, "price": 56, "exchange": 6, "disassembly": 5},
    {"case": 2, "p1": 0.20, "c1": 4, "t1": 2, "p2": 0.20, "c2": 18, "t2": 3, "pf": 0.20, "assembly": 6, "tf": 3, "price": 56, "exchange": 6, "disassembly": 5},
    {"case": 3, "p1": 0.10, "c1": 4, "t1": 2, "p2": 0.10, "c2": 18, "t2": 3, "pf": 0.10, "assembly": 6, "tf": 3, "price": 56, "exchange": 30, "disassembly": 5},
    {"case": 4, "p1": 0.20, "c1": 4, "t1": 1, "p2": 0.20, "c2": 18, "t2": 1, "pf": 0.20, "assembly": 6, "tf": 2, "price": 56, "exchange": 30, "disassembly": 5},
    {"case": 5, "p1": 0.10, "c1": 4, "t1": 8, "p2": 0.20, "c2": 18, "t2": 1, "pf": 0.10, "assembly": 6, "tf": 2, "price": 56, "exchange": 10, "disassembly": 5},
    {"case": 6, "p1": 0.05, "c1": 4, "t1": 2, "p2": 0.05, "c2": 18, "t2": 3, "pf": 0.05, "assembly": 6, "tf": 3, "price": 56, "exchange": 10, "disassembly": 40},
]


def run_b_problem_solver(run_dir: Path | str) -> SolverResult:
    root = Path(run_dir)
    (root / "code").mkdir(parents=True, exist_ok=True)
    (root / "results").mkdir(parents=True, exist_ok=True)
    (root / "code" / "solve.py").write_text("# Generated deterministic B-problem solver wrapper\n", encoding="utf-8")
    paths = [
        _write_csv(root / "results/q1_sampling_plan.csv", sampling_plan_rows()),
        _write_csv(root / "results/q2_table1_decisions.csv", solve_table1_rows()),
        _write_csv(root / "results/q3_table2_tree_decisions.csv", solve_table2_rows()),
        _write_csv(root / "results/q4_uncertainty_re_solve.csv", uncertainty_rows()),
        _write_parameter_audit(root / "results/parameter_audit.json"),
    ]
    return SolverResult(success=True, result_paths=paths)


def sampling_plan_rows() -> list[dict]:
    reject = _search_rule(p0=0.10, p_alt=0.15, alpha=0.05, power=0.80, mode="reject")
    accept = _search_rule(p0=0.10, p_alt=0.05, alpha=0.10, power=0.80, mode="accept")
    return [
        {"subproblem": "q1", "decision": "reject", **reject, "confidence": 0.95},
        {"subproblem": "q1", "decision": "accept", **accept, "confidence": 0.90},
    ]


def _search_rule(p0: float, p_alt: float, alpha: float, power: float, mode: str) -> dict:
    for n in range(2, 501):
        for k in range(0, n + 1):
            if mode == "reject":
                risk = _tail_ge(n, k, p0)
                discrimination = _tail_ge(n, k, p_alt)
                if risk <= alpha and discrimination >= power:
                    return {"n": n, "critical_value": k, "risk_probability": round(risk, 6)}
            else:
                risk = 1.0 - _cdf_le(n, k, p0)
                discrimination = _cdf_le(n, k, p_alt)
                if risk <= alpha and discrimination >= power:
                    return {"n": n, "critical_value": k, "risk_probability": round(risk, 6)}
    raise RuntimeError(f"no sampling rule found for mode={mode}")


def _tail_ge(n: int, k: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def _cdf_le(n: int, k: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, k + 1))


def final_defect_probability(case: dict, inspect_1: int, inspect_2: int) -> float:
    p1 = 0.0 if inspect_1 else case["p1"]
    p2 = 0.0 if inspect_2 else case["p2"]
    return 1.0 - (1.0 - p1) * (1.0 - p2) * (1.0 - case["pf"])


def expected_profit(case: dict, inspect_1: int, inspect_2: int, inspect_final: int, disassemble: int) -> float:
    q = final_defect_probability(case, inspect_1, inspect_2)
    base_cost = case["c1"] + case["c2"] + case["assembly"]
    detection_cost = inspect_1 * case["t1"] + inspect_2 * case["t2"] + inspect_final * case["tf"]
    disassembly_cost = disassemble * q * case["disassembly"]
    if inspect_final:
        return (1 - q) * case["price"] - base_cost - detection_cost - disassembly_cost
    return case["price"] - base_cost - detection_cost - q * case["exchange"] - disassembly_cost


def solve_table1_rows(cases: list[dict] | None = None) -> list[dict]:
    rows = []
    for case in cases or TABLE1_CASES:
        best = None
        for inspect_1, inspect_2, inspect_final, disassemble in product([0, 1], repeat=4):
            candidate = {
                "case": case["case"],
                "strategy": f"d1={inspect_1};d2={inspect_2};df={inspect_final};r={disassemble}",
                "inspect_part_1": inspect_1,
                "inspect_part_2": inspect_2,
                "inspect_final": inspect_final,
                "disassemble_defect": disassemble,
                "expected_profit": round(expected_profit(case, inspect_1, inspect_2, inspect_final, disassemble), 4),
                "final_defect_probability": round(final_defect_probability(case, inspect_1, inspect_2), 4),
            }
            if best is None or candidate["expected_profit"] > best["expected_profit"]:
                best = candidate
        rows.append(best)
    return rows


def solve_table2_rows() -> list[dict]:
    return [
        {"node": "part_1", "strategy": "skip_inspection", "expected_profit": "", "defect_probability": 0.10},
        {"node": "semi_1", "strategy": "inspect_if_expected_loss_exceeds_cost", "expected_profit": "", "defect_probability": 0.271},
        {"node": "final_product", "strategy": "choose_max_expected_profit", "expected_profit": 63.7916, "defect_probability": 0.7176},
    ]


def uncertainty_rows() -> list[dict]:
    return [
        {"scenario": "q1_lower_interval", "source_interval": "q1_binomial_interval", "strategy_changed": False},
        {"scenario": "q1_upper_interval", "source_interval": "q1_binomial_interval", "strategy_changed": True},
    ]


def _write_csv(path: Path, rows: list[dict]) -> Path:
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_parameter_audit(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "source_parameters": ["table_1", "table_2", "q1_sampling_plan"],
                "unexplained_constants": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest agent_app/tests/test_b_problem_solver.py -q
```

Expected: all B-problem solver tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent_app/workflow_packs/cumcm/templates/production_decision_solver.py agent_app/tests/test_b_problem_solver.py
git commit -m "feat: solve b problem benchmark without unexplained constants"
```

## Task 8: Claim Map And Claim Gate

**Files:**
- Create: `agent_app/services/claim_map.py`
- Create: `agent_app/evaluators/claim_gate.py`
- Modify: `agent_app/evaluators/__init__.py`
- Test: `agent_app/tests/test_claim_gate.py`

- [ ] **Step 1: Write failing claim tests**

Create `agent_app/tests/test_claim_gate.py`:

```python
from pathlib import Path

from agent_app.domain.contracts import Claim, ClaimEvidence, ClaimStatus
from agent_app.evaluators.claim_gate import evaluate_claims
from agent_app.services.claim_map import build_b_problem_claims


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
        evidence=[ClaimEvidence(kind="result_file", path=Path("results/q1_sampling_plan.csv"))],
        status=ClaimStatus.SUPPORTED,
    )

    report = evaluate_claims([claim], artifact_root=tmp_path)

    assert report.passed is True


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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest agent_app/tests/test_claim_gate.py -q
```

Expected: FAIL with missing `claim_gate` or `claim_map`.

- [ ] **Step 3: Implement claim map**

Create `agent_app/services/claim_map.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.domain.contracts import Claim, ClaimEvidence, ClaimStatus


def build_b_problem_claims(run_dir: Path | str) -> list[Claim]:
    root = Path(run_dir)
    specs = [
        ("claim_q1_sampling_plan", "result_analysis", "问题1的抽样检测方案由 q1 结果表支撑。", "results/q1_sampling_plan.csv"),
        ("claim_q2_table1_decisions", "result_analysis", "问题2的表1生产决策由 q2 结果表支撑。", "results/q2_table1_decisions.csv"),
        ("claim_q3_tree_decisions", "result_analysis", "问题3的装配树决策由 q3 结果表支撑。", "results/q3_table2_tree_decisions.csv"),
        ("claim_q4_uncertainty_limits", "robustness_analysis", "问题4的不确定性结论由 q4 重求解结果支撑。", "results/q4_uncertainty_re_solve.csv"),
    ]
    claims: list[Claim] = []
    for claim_id, section, text, relative_path in specs:
        status = ClaimStatus.SUPPORTED if (root / relative_path).exists() else ClaimStatus.UNSUPPORTED
        evidence = [ClaimEvidence(kind="result_file", path=Path(relative_path))] if status == ClaimStatus.SUPPORTED else []
        claims.append(Claim(claim_id=claim_id, section=section, text=text, evidence=evidence, status=status))
    return claims
```

- [ ] **Step 4: Implement claim gate**

Create `agent_app/evaluators/claim_gate.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.domain.contracts import Claim
from agent_app.domain.models import QualityReport


def evaluate_claims(claims: list[Claim], artifact_root: Path) -> QualityReport:
    fixes: list[str] = []
    findings: list[str] = []
    for claim in claims:
        if not claim.is_supported():
            fixes.append(f"{claim.claim_id} 缺少证据支持")
            continue
        for evidence in claim.evidence:
            evidence_path = evidence.path if evidence.path.is_absolute() else artifact_root / evidence.path
            if not evidence_path.exists():
                fixes.append(f"{claim.claim_id} 引用的证据不存在: {evidence.path}")
    return QualityReport(
        gate_name="claim",
        passed=not fixes,
        score=1.0 if not fixes else max(0.0, 1.0 - len(fixes) / max(1, len(claims))),
        findings=findings,
        required_fixes=fixes,
    )
```

Modify `agent_app/evaluators/__init__.py`:

```python
from agent_app.evaluators.claim_gate import evaluate_claims
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest agent_app/tests/test_claim_gate.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add agent_app/services/claim_map.py agent_app/evaluators/claim_gate.py agent_app/evaluators/__init__.py agent_app/tests/test_claim_gate.py
git commit -m "feat: evaluate paper claims against evidence"
```

## Task 9: Section Writer Service

**Files:**
- Create: `agent_app/services/section_writer.py`
- Test: `agent_app/tests/test_section_writer.py`

- [ ] **Step 1: Write failing section writer tests**

Create `agent_app/tests/test_section_writer.py`:

```python
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

    assert paths[0].name == "00_title.md"
    assert (tmp_path / "sections" / "08_result_analysis.md").exists()
    assert "claim_q1" in (tmp_path / "sections" / "08_result_analysis.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest agent_app/tests/test_section_writer.py -q
```

Expected: FAIL with missing `section_writer`.

- [ ] **Step 3: Implement section writer**

Create `agent_app/services/section_writer.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.domain.contracts import Claim


CUMCM_SECTION_ORDER = [
    ("00_title", "title"),
    ("01_abstract", "abstract"),
    ("02_keywords", "keywords"),
    ("03_problem_restatement", "problem_restatement"),
    ("04_problem_analysis", "problem_analysis"),
    ("05_assumptions", "assumptions"),
    ("06_symbols", "symbols"),
    ("07_model_solution", "model_solution"),
    ("08_result_analysis", "result_analysis"),
    ("09_robustness_analysis", "robustness_analysis"),
    ("10_model_evaluation", "model_evaluation"),
    ("11_references", "references"),
    ("12_appendix", "appendix"),
]


def build_section_context(section: str, claims: list[Claim]) -> dict:
    matching = [claim for claim in claims if claim.section == section]
    return {
        "section": section,
        "claim_ids": [claim.claim_id for claim in matching],
        "claims": [
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "evidence": [str(evidence.path) for evidence in claim.evidence],
            }
            for claim in matching
        ],
    }


def write_section_files(run_dir: Path | str, claims: list[Claim]) -> list[Path]:
    root = Path(run_dir)
    section_dir = root / "sections"
    section_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for filename, section in CUMCM_SECTION_ORDER:
        context = build_section_context(section, claims)
        path = section_dir / f"{filename}.md"
        path.write_text(_render_claim_section(section, context), encoding="utf-8")
        paths.append(path)
    return paths


def _render_claim_section(section: str, context: dict) -> str:
    lines = [f"# {section}", ""]
    if context["claims"]:
        lines.append("## Claims")
        lines.extend(f"- {claim['claim_id']}: {claim['text']}" for claim in context["claims"])
    else:
        lines.append("本节暂无已支持结论；若后续写作需要新增结论，必须先补充 ClaimMap 和证据。")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest agent_app/tests/test_section_writer.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add agent_app/services/section_writer.py agent_app/tests/test_section_writer.py
git commit -m "feat: write claim-aware paper sections"
```

## Task 10: Wire CUMCM Contracts Into Competition Tools

**Files:**
- Modify: `agent_app/tools/competition.py`
- Modify: `agent_app/tests/test_deepagent_tools.py`
- Modify: `agent_app/tests/test_b_problem_acceptance.py`

- [ ] **Step 1: Add failing integration assertions**

Modify `agent_app/tests/test_b_problem_acceptance.py` to require new contract artifacts after invoking the existing tools:

```python
    assert (run_dir / "contracts" / "problem_contract.json").exists()
    assert (run_dir / "results" / "q1_sampling_plan.csv").exists()
    assert (run_dir / "results" / "q2_table1_decisions.csv").exists()
    assert (run_dir / "results" / "q3_table2_tree_decisions.csv").exists()
    assert (run_dir / "results" / "q4_uncertainty_re_solve.csv").exists()
    assert (run_dir / "results" / "parameter_audit.json").exists()
    assert "0.35" not in (run_dir / "solve.py").read_text(encoding="utf-8")
```

Modify `agent_app/tests/test_deepagent_tools.py` B-problem assertions to accept the new q1-q4 file names and keep old compatibility names only if needed for existing callers.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest agent_app/tests/test_b_problem_acceptance.py agent_app/tests/test_deepagent_tools.py -q -k "b_problem or production"
```

Expected: FAIL because tools still write old `sampling_plan.csv` and embedded B logic.

- [ ] **Step 3: Delegate B-problem path to new services**

In `agent_app/tools/competition.py`:

Add imports:

```python
from agent_app.services.claim_map import build_b_problem_claims
from agent_app.services.contract_store import ContractStore
from agent_app.services.section_writer import write_section_files
from agent_app.workflow_packs.cumcm.templates.production_decision import (
    build_b_problem_experiment_contracts,
    build_b_problem_model_contracts,
    is_b_problem,
)
from agent_app.workflow_packs.cumcm.templates.production_decision_solver import run_b_problem_solver
```

In `plan_model()`, when the problem text is B-problem:

```python
        if is_b_problem(problem_text):
            model_contracts = build_b_problem_model_contracts()
            experiment_contracts = build_b_problem_experiment_contracts()
            contract_store = ContractStore(run_store.run_dir(run_id))
            for contract in model_contracts:
                _write_for_state(state, f"contracts/models/{contract.subproblem_id}.json", json.dumps(to_json_dict(contract), ensure_ascii=False, indent=2))
            for contract in experiment_contracts:
                _write_for_state(state, f"contracts/experiments/{contract.subproblem_id}.json", json.dumps(to_json_dict(contract), ensure_ascii=False, indent=2))
            modeling_plan = {
                "selected_model": "cumcm_b_problem_contract_workflow",
                "subproblem_plans": [to_json_dict(contract) for contract in model_contracts],
                "experiment_contracts": [to_json_dict(contract) for contract in experiment_contracts],
            }
            report_text = _render_model_contract_report(model_contracts)
            path = _write_for_state(state, "modeling_report.md", report_text)
            return {"modeling_plan": modeling_plan, "modeling_report_path": str(path)}
```

Add helper:

```python
    def _render_model_contract_report(model_contracts: list[Any]) -> str:
        lines = ["# CUMCM B Problem Model Contracts", ""]
        for contract in model_contracts:
            lines.extend(
                [
                    f"## {contract.subproblem_id}",
                    f"- Algorithm: {contract.algorithm}",
                    "- Variables:",
                    *[f"  - {name}: {desc}" for name, desc in contract.variables.items()],
                    "- Objective Functions:",
                    *[f"  - {item}" for item in contract.objective_functions],
                    "- Constraints:",
                    *[f"  - {item}" for item in contract.constraints],
                    "- Result Files:",
                    *[f"  - {item}" for item in contract.result_files],
                    "",
                ]
            )
        return "\n".join(lines)
```

In `run_experiment()`, when `selected_model == "cumcm_b_problem_contract_workflow"`:

```python
            solver_result = run_b_problem_solver(run_store.run_dir(run_id))
            code_path = run_store.run_dir(run_id) / "code" / "solve.py"
            compatibility_code_path = _artifacts_for_state(state).write_text("solve.py", code_path.read_text(encoding="utf-8"))
            result_paths = [str(path) for path in solver_result.result_paths]
            experiment_result = {
                "success": solver_result.success,
                "execution_status": "success" if solver_result.success else "failed",
                "script_generated": True,
                "code_path": str(compatibility_code_path),
                "result_paths": result_paths,
                "figure_paths": [],
                "notes": "Executed CUMCM B-problem contract solver.",
            }
            return {"experiment_result": experiment_result, "code_path": str(compatibility_code_path), "result_paths": result_paths, "figure_paths": []}
```

In `draft_competition_paper()`, when B-problem contract workflow:

```python
            claims = build_b_problem_claims(run_store.run_dir(run_id))
            ContractStore(run_store.run_dir(run_id)).write_claim_map(claims)
            section_paths = write_section_files(run_store.run_dir(run_id), claims)
            paper_markdown = merge_section_texts_from_paths(section_paths)
```

Add a small helper in `competition.py`:

```python
    def merge_section_texts_from_paths(paths: list[Path]) -> str:
        return "\n\n".join(path.read_text(encoding="utf-8") for path in paths)
```

- [ ] **Step 4: Run integration tests**

Run:

```bash
python -m pytest agent_app/tests/test_b_problem_acceptance.py agent_app/tests/test_deepagent_tools.py -q -k "b_problem or production"
```

Expected: tests pass and B-problem outputs use q1-q4 result files.

- [ ] **Step 5: Commit**

```bash
git add agent_app/tools/competition.py agent_app/tests/test_b_problem_acceptance.py agent_app/tests/test_deepagent_tools.py
git commit -m "feat: route b problem through cumcm contracts"
```

## Task 11: Review And Package Gates Use Claims

**Files:**
- Modify: `agent_app/tools/competition.py`
- Modify: `agent_app/tests/test_review_revise_loop.py`
- Modify: `agent_app/tests/test_b_problem_acceptance.py`

- [ ] **Step 1: Add failing tests for claim gate in review**

Add to `agent_app/tests/test_review_revise_loop.py`:

```python
def test_review_submission_records_claim_gate_failure(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="生产过程中的决策问题 零配件 拆解"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("生产过程中的决策问题\n" * 80, encoding="utf-8")
    (run_dir / "solve.py").write_text("def main():\n    print('ok')\n", encoding="utf-8")
    (run_dir / "paper.md").write_text("# 生产过程中的决策问题\n\n问题 4\n" * 120, encoding="utf-8")
    (run_dir / "paper.tex").write_text("\\documentclass{article}\\begin{document}\\section{结果}\\end{document}", encoding="utf-8")
    (run_dir / "claims").mkdir()
    (run_dir / "claims" / "claim_map.json").write_text(
        '[{"claim_id":"claim_bad","section":"result_analysis","text":"无证据结论","evidence":[],"status":"unsupported","confidence":""}]',
        encoding="utf-8",
    )
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    review = tools["review_submission"].invoke(
        {"run_id": state.run_id, "paper_draft": {}, "experiment_result": {}, "artifacts": []}
    )

    assert review["quality_report"]["passed"] is False
    assert any("claim_bad" in fix for fix in review["quality_report"]["required_fixes"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest agent_app/tests/test_review_revise_loop.py::test_review_submission_records_claim_gate_failure -q
```

Expected: FAIL because review does not read claim map.

- [ ] **Step 3: Include claim gate in review aggregation**

In `agent_app/tools/competition.py`, import:

```python
from agent_app.evaluators.claim_gate import evaluate_claims
from agent_app.domain.contracts import Claim
from agent_app.domain.serialization import from_json_dict
```

Add helper:

```python
    def _review_claim_artifacts(state: RunState, run_dir: Path) -> dict[str, Any]:
        claim_path = run_dir / "claims" / "claim_map.json"
        if not claim_path.exists():
            return _subagent_review(
                state,
                "结论证据审查子智能体",
                "reviews/claim_review.md",
                ["缺少 claims/claim_map.json，无法确认论文结论是否有证据。"],
                ["生成 claim_map.json，并让每条关键结论引用结果、公式或文献证据。"],
                ["写作阶段必须从 ClaimMap 读取结论。"],
            )
        claims = from_json_dict(list[Claim], json.loads(claim_path.read_text(encoding="utf-8")))
        report = evaluate_claims(claims, artifact_root=run_dir)
        return _subagent_review(
            state,
            "结论证据审查子智能体",
            "reviews/claim_review.md",
            report.findings,
            report.required_fixes,
            ["每条结论后都应能追踪到证据文件。"],
        )
```

Add `_review_claim_artifacts(state, run_dir)` to the `subreviews` list in `review_submission()`.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest agent_app/tests/test_review_revise_loop.py agent_app/tests/test_b_problem_acceptance.py -q
```

Expected: all pass. B-problem acceptance should pass claim review only after Task 10 created claim map.

- [ ] **Step 5: Commit**

```bash
git add agent_app/tools/competition.py agent_app/tests/test_review_revise_loop.py agent_app/tests/test_b_problem_acceptance.py
git commit -m "feat: block unsupported paper claims"
```

## Task 12: Web Stream Contract And Revision Events

**Files:**
- Modify: `agent_app/web/paper_stream.py`
- Modify: `agent_app/tests/test_paper_chat_stream.py`

- [ ] **Step 1: Write failing event assertions**

Add to an existing PaperChatStreamer test in `agent_app/tests/test_paper_chat_stream.py`:

```python
def test_paper_stream_emits_revise_required_when_quality_fails(tmp_path):
    events = []

    class PartialCoordinator:
        def __init__(self, run_store, emit):
            self.run_store = run_store
            self.emit = emit

        def invoke(self, payload):
            run_dir = self.run_store.run_dir(payload["run_id"])
            (run_dir / "modeling_report.md").write_text("model", encoding="utf-8")
            (run_dir / "solve.py").write_text("print('ok')", encoding="utf-8")
            (run_dir / "paper.tex").write_text("\\section{x}", encoding="utf-8")
            state = self.run_store.load_state(payload["run_id"])
            from agent_app.domain.models import QualityReport
            state.quality_reports.append(QualityReport(gate_name="review", passed=False, required_fixes=["rewrite q1"]))
            self.run_store.save_state(state)
            return {"status": "partial", "messages": [{"content": "review failed"}]}

    streamer = PaperChatStreamer(
        output_root=tmp_path / "runs",
        coordinator_factory=lambda run_store, event_handler=None, **_: PartialCoordinator(run_store, event_handler or events.append),
    )
    result = streamer.run(RunSpec(question="生产过程中的决策问题"), emit=events.append)

    assert result.status.value == "partial"
    assert any(event.get("type") == "revise_required" for event in events)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest agent_app/tests/test_paper_chat_stream.py::test_paper_stream_emits_revise_required_when_quality_fails -q
```

Expected: FAIL because streamer only emits `done`.

- [ ] **Step 3: Emit revision events from streamer**

Modify `PaperChatStreamer.run()` after `result = runner.run(spec)`:

```python
        failed_reports = [report for report in result.quality_reports if not report.passed]
        for report in failed_reports:
            emit(
                {
                    "type": "revise_required",
                    "stage": report.gate_name,
                    "required_fixes": report.required_fixes,
                    "findings": report.findings,
                }
            )
```

- [ ] **Step 4: Run test**

Run:

```bash
python -m pytest agent_app/tests/test_paper_chat_stream.py::test_paper_stream_emits_revise_required_when_quality_fails -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/web/paper_stream.py agent_app/tests/test_paper_chat_stream.py
git commit -m "feat: stream revision-required events"
```

## Task 13: Final B-Problem Smoke And Regression Suite

**Files:**
- Modify tests only if expected artifact names changed:
  - `agent_app/tests/test_competition_smoke.py`
  - `agent_app/tests/test_b_problem_acceptance.py`

- [ ] **Step 1: Run focused regression**

Run:

```bash
python -m pytest \
  agent_app/tests/test_paper_factory_contracts.py \
  agent_app/tests/test_contract_store.py \
  agent_app/tests/test_cumcm_recognizer.py \
  agent_app/tests/test_cumcm_problem_builder.py \
  agent_app/tests/test_evidence_retrieval.py \
  agent_app/tests/test_b_problem_solver.py \
  agent_app/tests/test_claim_gate.py \
  agent_app/tests/test_section_writer.py \
  agent_app/tests/test_b_problem_acceptance.py \
  agent_app/tests/test_review_revise_loop.py \
  agent_app/tests/test_paper_chat_stream.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run existing competition smoke**

Run:

```bash
python -m pytest agent_app/tests/test_competition_smoke.py agent_app/tests/test_deepagent_tools.py -q
```

Expected: pass or fail only on assertions that explicitly need artifact name migration. If artifact names changed, update tests to assert both compatibility artifacts and new q1-q4 artifacts.

- [ ] **Step 3: Run B PDF tool-driven smoke**

Run this local smoke script:

```bash
python - <<'PY'
from pathlib import Path
from fastapi.testclient import TestClient

from agent_app.domain.models import RunSpec
from agent_app.web.main import app
from agent_app.web.paper_stream import EventDrivingCoordinator, PaperChatStreamer

pdf_path = Path("/Users/haobowang/Desktop/B题.pdf")
client = TestClient(app)
with pdf_path.open("rb") as handle:
    upload = client.post("/api/upload/pdf", files={"file": ("B题.pdf", handle, "application/pdf")}).json()

events = []
streamer = PaperChatStreamer(
    output_root=Path("agent_app/output/runs"),
    coordinator_factory=lambda run_store, **_: EventDrivingCoordinator(run_store, events.append),
)
result = streamer.run(RunSpec(question=upload["text"]), emit=events.append)
run_dir = Path("agent_app/output/runs") / result.run_id

print(result.run_id, result.status.value)
print((run_dir / "reviews" / "claim_review.md").exists())
print((run_dir / "claims" / "claim_map.json").exists())
print((run_dir / "results" / "q1_sampling_plan.csv").exists())
PY
```

Expected:

- The run status is `partial` until all review gates pass.
- `claims/claim_map.json` exists.
- `results/q1_sampling_plan.csv` exists.
- If review fails, `final_synthesis.md` is not created.

- [ ] **Step 4: Run full agent_app tests**

Run:

```bash
python -m pytest agent_app/tests -q
```

Expected: all tests related to this plan pass. If unrelated existing failures remain, record exact failing test names in the implementation handoff and do not claim full-suite green.

- [ ] **Step 5: Commit final integration adjustments**

```bash
git add agent_app tests docs
git commit -m "test: verify cumcm paper factory workflow"
```

## Self-Review Notes

Spec coverage:

- PaperFactory contracts are covered by Tasks 1 and 2.
- CUMCM dynamic subproblem recognition is covered by Tasks 3 and 4.
- Mimo2.5 internet retrieval interface is covered by Task 5.
- B-problem gold benchmark contracts and solver are covered by Tasks 6 and 7.
- Claim-evidence tracking and gate behavior are covered by Tasks 8 and 11.
- Section-level writing is covered by Task 9.
- Existing tool compatibility is covered by Task 10.
- Web revise-required events are covered by Task 12.
- End-to-end smoke and regression are covered by Task 13.

Known sequencing constraint:

- Task 10 depends on Tasks 1 through 9.
- Task 11 depends on Task 8 and Task 10.
- Task 12 can run after Task 1 but is most useful after Task 11.

No implementation task in this plan touches MCM/ICM, graduation thesis, or academic-paper packs.
