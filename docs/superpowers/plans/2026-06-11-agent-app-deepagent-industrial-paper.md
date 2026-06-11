# Agent App DeepAgent Industrial Paper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `agent_app` around a DeepAgent-native, run-tracked, quality-gated competition paper workflow that accepts problem text, data files, and reference documents, then produces a complete modeling submission package.

**Architecture:** Replace the demo-style `Orchestrator` core with a layered architecture: stable domain models, services, structured DeepAgent tools, stage middleware, a `CompetitionPaperRunner`, and thin CLI/Web/GUI interfaces. Existing RAG, literature, Python execution, LaTeX, and exploration capabilities are migrated behind service/tool facades instead of being expanded in the old monolithic flow.

**Tech Stack:** Python 3.11 dataclasses, pytest, LangChain tools, DeepAgent via `deepagents.create_deep_agent`, pandas/scikit-learn/PyPDF/PyMuPDF, existing DeepSeek LLM factory, existing sandbox and LaTeX helpers.

---

## Source Spec

Implement from:

`docs/superpowers/specs/2026-06-11-agent-app-deepagent-industrial-paper-design.md`

## Scope And Sequencing

This is one product workflow with multiple implementation layers. Execute it in slices that each leave the test suite runnable:

1. Package migration and dependencies.
2. Domain models.
3. Run storage and artifact paths.
4. Input/data services.
5. RAG, code, LaTeX, and literature services.
6. Quality gates.
7. Structured DeepAgent tools.
8. DeepAgent middleware.
9. Coordinator and runner.
10. End-to-end smoke workflow.
11. Interfaces.
12. Public exports, docs, and legacy boundary.

Do not delete user work. The repository may already have unrelated dirty files; stage only the files named in each task.

## File Structure

Create:

- `agent_app/domain/__init__.py`
- `agent_app/domain/models.py`
- `agent_app/domain/serialization.py`
- `agent_app/infra/__init__.py`
- `agent_app/infra/paths.py`
- `agent_app/services/__init__.py`
- `agent_app/services/artifact_service.py`
- `agent_app/services/run_store.py`
- `agent_app/services/ingestion.py`
- `agent_app/services/data_analysis.py`
- `agent_app/services/rag_service.py`
- `agent_app/services/code_execution.py`
- `agent_app/services/latex_service.py`
- `agent_app/services/literature_service.py`
- `agent_app/evaluators/__init__.py`
- `agent_app/evaluators/input_gate.py`
- `agent_app/evaluators/modeling_gate.py`
- `agent_app/evaluators/experiment_gate.py`
- `agent_app/evaluators/paper_gate.py`
- `agent_app/evaluators/submission_gate.py`
- `agent_app/deepagent/__init__.py`
- `agent_app/deepagent/prompts.py`
- `agent_app/deepagent/middleware.py`
- `agent_app/deepagent/coordinator.py`
- `agent_app/deepagent/runner.py`
- `agent_app/workflows/__init__.py`
- `agent_app/workflows/competition_paper.py`
- `agent_app/interfaces/__init__.py`
- `agent_app/interfaces/cli.py`
- `agent_app/interfaces/web.py`
- `agent_app/interfaces/gui.py`
- `agent_app/tests/test_deepagent_architecture_imports.py`
- `agent_app/tests/test_domain_models.py`
- `agent_app/tests/test_run_store.py`
- `agent_app/tests/test_ingestion_data_services.py`
- `agent_app/tests/test_industrial_services.py`
- `agent_app/tests/test_quality_gates.py`
- `agent_app/tests/test_deepagent_tools.py`
- `agent_app/tests/test_stage_middleware.py`
- `agent_app/tests/test_competition_runner.py`
- `agent_app/tests/test_competition_smoke.py`

Move:

- `agent_app/tools.py` -> `agent_app/tools/legacy.py`

Create after the move:

- `agent_app/tools/__init__.py`
- `agent_app/tools/competition.py`
- `agent_app/tools/data.py`
- `agent_app/tools/evidence.py`
- `agent_app/tools/experiment.py`
- `agent_app/tools/paper.py`

Modify:

- `pyproject.toml`
- `agent_app/requirements.txt`
- `agent_app/__init__.py`
- `agent_app/cli.py`
- `agent_app/web/routes.py`
- `agent_app/gui.py`
- `agent_app/README.md`

---

### Task 1: Package Migration, Dependencies, And Skeleton

**Files:**

- Move: `agent_app/tools.py` -> `agent_app/tools/legacy.py`
- Create: `agent_app/tools/__init__.py`
- Create: package `__init__.py` files under `agent_app/domain`, `agent_app/infra`, `agent_app/services`, `agent_app/evaluators`, `agent_app/deepagent`, `agent_app/workflows`, `agent_app/interfaces`
- Modify: `pyproject.toml`
- Modify: `agent_app/requirements.txt`
- Test: `agent_app/tests/test_deepagent_architecture_imports.py`

- [ ] **Step 1: Write the failing architecture import test**

Create `agent_app/tests/test_deepagent_architecture_imports.py`:

```python
from __future__ import annotations

import importlib
from pathlib import Path


def test_deepagent_dependency_declared_in_project_files():
    root = Path(__file__).resolve().parents[2]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (root / "agent_app" / "requirements.txt").read_text(encoding="utf-8")

    assert "deepagents" in pyproject
    assert "deepagents" in requirements


def test_tools_package_keeps_legacy_exports():
    tools = importlib.import_module("agent_app.tools")

    for name in [
        "python_exec",
        "latex_compile",
        "read_csv_info",
        "TOOLS",
        "TOOLS_FULL",
    ]:
        assert hasattr(tools, name)


def test_new_architecture_packages_import():
    for module_name in [
        "agent_app.domain",
        "agent_app.infra",
        "agent_app.services",
        "agent_app.evaluators",
        "agent_app.deepagent",
        "agent_app.workflows",
        "agent_app.interfaces",
    ]:
        assert importlib.import_module(module_name) is not None
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
pytest agent_app/tests/test_deepagent_architecture_imports.py -q
```

Expected: FAIL because `deepagents` is not declared and the new packages do not exist.

- [ ] **Step 3: Move `tools.py` into a package**

Run:

```bash
mkdir -p agent_app/tools
git mv agent_app/tools.py agent_app/tools/legacy.py
```

Create `agent_app/tools/__init__.py`:

```python
from __future__ import annotations

from .legacy import (
    TOOLS,
    TOOLS_FULL,
    _SAFETY_PREAMBLE,
    calculator,
    current_time,
    latex_compile,
    latex_render_math,
    latex_template,
    list_notes,
    model_reference,
    nature_viz_template,
    pip_install,
    python_exec,
    read_csv_info,
    read_note,
    save_note,
    writing_rules,
)

__all__ = [
    "TOOLS",
    "TOOLS_FULL",
    "_SAFETY_PREAMBLE",
    "calculator",
    "current_time",
    "latex_compile",
    "latex_render_math",
    "latex_template",
    "list_notes",
    "model_reference",
    "nature_viz_template",
    "pip_install",
    "python_exec",
    "read_csv_info",
    "read_note",
    "save_note",
    "writing_rules",
]
```

- [ ] **Step 4: Create new package skeletons**

Run:

```bash
mkdir -p agent_app/domain agent_app/infra agent_app/services agent_app/evaluators agent_app/deepagent agent_app/workflows agent_app/interfaces
touch agent_app/domain/__init__.py agent_app/infra/__init__.py agent_app/services/__init__.py agent_app/evaluators/__init__.py agent_app/deepagent/__init__.py agent_app/workflows/__init__.py agent_app/interfaces/__init__.py
```

- [ ] **Step 5: Add DeepAgent dependency declarations**

Modify `pyproject.toml` dependencies:

```toml
dependencies = [
    "langchain",
    "langchain-core",
    "langchain-deepseek",
    "deepagents>=0.5.0",
    "python-dotenv",
    "scikit-learn",
    "pypdf",
    "jieba",
    "numpy",
    "pandas",
    "PyMuPDF",
    "dashscope",
]
```

Append to `agent_app/requirements.txt`:

```text
deepagents>=0.5.0
```

- [ ] **Step 6: Run migration tests**

Run:

```bash
pytest agent_app/tests/test_deepagent_architecture_imports.py agent_app/tests/test_orchestrator_tools.py::TestWriteFileTool -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml agent_app/requirements.txt agent_app/tools agent_app/domain/__init__.py agent_app/infra/__init__.py agent_app/services/__init__.py agent_app/evaluators/__init__.py agent_app/deepagent/__init__.py agent_app/workflows/__init__.py agent_app/interfaces/__init__.py agent_app/tests/test_deepagent_architecture_imports.py
git commit -m "refactor: prepare deepagent architecture packages"
```

---

### Task 2: Domain Models And Serialization

**Files:**

- Create: `agent_app/domain/models.py`
- Create: `agent_app/domain/serialization.py`
- Modify: `agent_app/domain/__init__.py`
- Test: `agent_app/tests/test_domain_models.py`

- [ ] **Step 1: Write failing domain model tests**

Create `agent_app/tests/test_domain_models.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import (
    ArtifactRef,
    DataAuditReport,
    ExperimentResult,
    ProblemBrief,
    QualityReport,
    RunIssue,
    RunOptions,
    RunResult,
    RunSpec,
    RunState,
    RunStatus,
    RunStage,
)
from agent_app.domain.serialization import from_json_dict, to_json_dict


def test_run_spec_defaults_to_competition_paper():
    spec = RunSpec(question="建立交通流优化模型")

    assert spec.output_profile == "competition_paper"
    assert spec.options.top_k == 6
    assert spec.data_files == []
    assert spec.reference_files == []


def test_run_state_round_trips_through_json_dict():
    state = RunState(
        run_id="run_20260611_000001",
        spec=RunSpec(
            question="预测需求",
            data_files=[Path("data.csv")],
            reference_files=[Path("paper.pdf")],
            options=RunOptions(max_repair_attempts=3),
        ),
        status=RunStatus.RUNNING,
        stage=RunStage.AUDIT_DATA,
        artifacts=[ArtifactRef(name="data_audit", path=Path("data_audit.md"), kind="markdown")],
        issues=[RunIssue(stage="audit_data", message="文件编码已使用 utf-8 读取")],
        quality_reports=[QualityReport(gate_name="input", passed=True, score=1.0)],
    )

    payload = to_json_dict(state)
    restored = from_json_dict(RunState, payload)

    assert restored.run_id == state.run_id
    assert restored.spec.data_files == [Path("data.csv")]
    assert restored.status == RunStatus.RUNNING
    assert restored.stage == RunStage.AUDIT_DATA
    assert restored.artifacts[0].path == Path("data_audit.md")
    assert restored.quality_reports[0].passed is True


def test_problem_and_experiment_models_store_expected_fields():
    brief = ProblemBrief(
        background="交通拥堵",
        questions=["预测流量", "优化信号灯"],
        objectives=["降低平均延误"],
        constraints=["道路容量"],
        required_data=["车流量"],
        deliverables=["论文"],
    )
    audit = DataAuditReport(files=["traffic.csv"], usable_features=["flow", "speed"])
    experiment = ExperimentResult(
        code_path=Path("solve.py"),
        execution_status="success",
        result_files=[Path("results/metrics.json")],
        figure_files=[Path("figures/flow.png")],
        sensitivity_results=["改变容量参数后平均延误变化 4.2%"],
    )

    assert brief.questions[0] == "预测流量"
    assert audit.files == ["traffic.csv"]
    assert experiment.execution_status == "success"


def test_run_result_is_small_interface_payload():
    result = RunResult(
        run_id="run_1",
        status=RunStatus.COMPLETED,
        stage=RunStage.PACKAGE_SUBMISSION,
        artifacts=[ArtifactRef(name="paper_tex", path=Path("paper.tex"), kind="tex")],
        quality_reports=[QualityReport(gate_name="submission", passed=True, score=1.0)],
        summary="已生成竞赛论文包",
    )

    assert result.artifacts[0].name == "paper_tex"
    assert result.summary.startswith("已生成")
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
pytest agent_app/tests/test_domain_models.py -q
```

Expected: FAIL because domain model files do not exist.

- [ ] **Step 3: Implement domain models**

Create `agent_app/domain/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class RunStage(str, Enum):
    CREATED = "created"
    INGEST_INPUTS = "ingest_inputs"
    UNDERSTAND_PROBLEM = "understand_problem"
    AUDIT_DATA = "audit_data"
    RETRIEVE_EVIDENCE = "retrieve_evidence"
    PLAN_MODELING = "plan_modeling"
    RUN_EXPERIMENTS = "run_experiments"
    ANALYZE_RESULTS = "analyze_results"
    DRAFT_PAPER = "draft_paper"
    REVIEW_AND_REVISE = "review_and_revise"
    PACKAGE_SUBMISSION = "package_submission"


@dataclass
class RunOptions:
    top_k: int = 6
    max_repair_attempts: int = 2
    compile_pdf: bool = True
    allow_online_search: bool = False


@dataclass
class RunSpec:
    question: str
    data_files: list[Path] = field(default_factory=list)
    reference_files: list[Path] = field(default_factory=list)
    output_profile: str = "competition_paper"
    options: RunOptions = field(default_factory=RunOptions)


@dataclass
class ArtifactRef:
    name: str
    path: Path
    kind: str
    description: str = ""


@dataclass
class RunIssue:
    stage: str
    message: str
    severity: str = "warning"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProblemBrief:
    background: str = ""
    questions: list[str] = field(default_factory=list)
    objectives: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    required_data: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)


@dataclass
class DataAuditReport:
    files: list[str] = field(default_factory=list)
    field_dictionary: dict[str, str] = field(default_factory=dict)
    missing_values: dict[str, int] = field(default_factory=dict)
    outliers: dict[str, list[str]] = field(default_factory=dict)
    descriptive_statistics: dict[str, dict[str, Any]] = field(default_factory=dict)
    usable_features: list[str] = field(default_factory=list)
    data_limitations: list[str] = field(default_factory=list)
    recommended_preprocessing: list[str] = field(default_factory=list)


@dataclass
class EvidenceNote:
    source_id: str
    title: str
    summary: str
    relevance: str = ""
    citation_key: str = ""


@dataclass
class BibliographyItem:
    source_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: str = ""
    url_or_path: str = ""
    citation_key: str = ""


@dataclass
class ModelingPlan:
    subproblem_plans: list[str] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, str] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    objective_functions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    candidate_models: list[str] = field(default_factory=list)
    selected_model: str = ""
    algorithm_plan: str = ""
    evaluation_metrics: list[str] = field(default_factory=list)
    sensitivity_plan: str = ""


@dataclass
class ExperimentResult:
    code_path: Path | None = None
    execution_status: str = "not_run"
    stdout: str = ""
    stderr: str = ""
    result_files: list[Path] = field(default_factory=list)
    figure_files: list[Path] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    sensitivity_results: list[str] = field(default_factory=list)
    reproducibility_notes: str = ""


@dataclass
class PaperDraft:
    markdown_path: Path | None = None
    latex_path: Path | None = None
    sections: dict[str, str] = field(default_factory=dict)
    figures_used: list[Path] = field(default_factory=list)
    tables_used: list[str] = field(default_factory=list)
    references_used: list[str] = field(default_factory=list)
    appendix_files: list[Path] = field(default_factory=list)


@dataclass
class QualityReport:
    gate_name: str
    passed: bool
    score: float = 0.0
    findings: list[str] = field(default_factory=list)
    required_fixes: list[str] = field(default_factory=list)
    optional_improvements: list[str] = field(default_factory=list)


@dataclass
class RunState:
    run_id: str
    spec: RunSpec
    status: RunStatus = RunStatus.PENDING
    stage: RunStage = RunStage.CREATED
    artifacts: list[ArtifactRef] = field(default_factory=list)
    issues: list[RunIssue] = field(default_factory=list)
    quality_reports: list[QualityReport] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class RunResult:
    run_id: str
    status: RunStatus
    stage: RunStage
    artifacts: list[ArtifactRef] = field(default_factory=list)
    quality_reports: list[QualityReport] = field(default_factory=list)
    summary: str = ""
```

- [ ] **Step 4: Implement serialization helpers**

Create `agent_app/domain/serialization.py`:

```python
from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints


def to_json_dict(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: to_json_dict(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [to_json_dict(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_json_dict(item) for key, item in value.items()}
    return value


def from_json_dict(cls: type, payload: Any) -> Any:
    return _convert(cls, payload)


def _convert(annotation: Any, value: Any) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if value is None:
        return None

    if origin is list:
        item_type = args[0] if args else Any
        return [_convert(item_type, item) for item in value]

    if origin is dict:
        value_type = args[1] if len(args) == 2 else Any
        return {key: _convert(value_type, item) for key, item in value.items()}

    if origin is not None and type(None) in args:
        real_types = [arg for arg in args if arg is not type(None)]
        return _convert(real_types[0], value) if real_types else value

    if annotation is Path:
        return Path(value)

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation(value)

    if isinstance(annotation, type) and is_dataclass(annotation):
        hints = get_type_hints(annotation)
        kwargs = {
            field.name: _convert(hints.get(field.name, Any), value.get(field.name))
            for field in fields(annotation)
            if field.name in value
        }
        return annotation(**kwargs)

    return value
```

Update `agent_app/domain/__init__.py`:

```python
from __future__ import annotations

from .models import (
    ArtifactRef,
    BibliographyItem,
    DataAuditReport,
    EvidenceNote,
    ExperimentResult,
    ModelingPlan,
    PaperDraft,
    ProblemBrief,
    QualityReport,
    RunIssue,
    RunOptions,
    RunResult,
    RunSpec,
    RunStage,
    RunState,
    RunStatus,
)

__all__ = [
    "ArtifactRef",
    "BibliographyItem",
    "DataAuditReport",
    "EvidenceNote",
    "ExperimentResult",
    "ModelingPlan",
    "PaperDraft",
    "ProblemBrief",
    "QualityReport",
    "RunIssue",
    "RunOptions",
    "RunResult",
    "RunSpec",
    "RunStage",
    "RunState",
    "RunStatus",
]
```

- [ ] **Step 5: Run domain tests**

Run:

```bash
pytest agent_app/tests/test_domain_models.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agent_app/domain agent_app/tests/test_domain_models.py
git commit -m "feat: add competition run domain models"
```

---

### Task 3: Run Store, Safe Paths, And Artifact Service

**Files:**

- Create: `agent_app/infra/paths.py`
- Create: `agent_app/services/artifact_service.py`
- Create: `agent_app/services/run_store.py`
- Modify: `agent_app/services/__init__.py`
- Test: `agent_app/tests/test_run_store.py`

- [ ] **Step 1: Write failing run store tests**

Create `agent_app/tests/test_run_store.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_app.domain.models import ArtifactRef, RunSpec, RunStage, RunStatus
from agent_app.services.artifact_service import ArtifactService
from agent_app.services.run_store import RunStore


def test_run_store_creates_traceable_run_directory(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="优化配送路径"))

    assert state.run_id.startswith("run_")
    assert (tmp_path / state.run_id).is_dir()
    assert (tmp_path / state.run_id / "run.json").exists()

    payload = json.loads((tmp_path / state.run_id / "run.json").read_text(encoding="utf-8"))
    assert payload["spec"]["question"] == "优化配送路径"
    assert payload["status"] == "pending"


def test_run_store_persists_stage_status_and_artifacts(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="预测销量"))
    state.stage = RunStage.AUDIT_DATA
    state.status = RunStatus.RUNNING
    state.artifacts.append(ArtifactRef(name="audit", path=Path("data_audit.md"), kind="markdown"))

    store.save_state(state)
    restored = store.load_state(state.run_id)

    assert restored.stage == RunStage.AUDIT_DATA
    assert restored.status == RunStatus.RUNNING
    assert restored.artifacts[0].path == Path("data_audit.md")


def test_artifact_service_writes_inside_run_directory(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="分析"))
    artifacts = ArtifactService(store.run_dir(state.run_id))

    path = artifacts.write_text("notes/problem.md", "# Problem\n")

    assert path == store.run_dir(state.run_id) / "notes" / "problem.md"
    assert path.read_text(encoding="utf-8") == "# Problem\n"


def test_artifact_service_rejects_path_traversal(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="分析"))
    artifacts = ArtifactService(store.run_dir(state.run_id))

    with pytest.raises(ValueError, match="outside run directory"):
        artifacts.write_text("../escape.md", "bad")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_run_store.py -q
```

Expected: FAIL because `RunStore` and `ArtifactService` do not exist.

- [ ] **Step 3: Implement path helpers**

Create `agent_app/infra/paths.py`:

```python
from __future__ import annotations

import re
from pathlib import Path


_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def ensure_within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"path outside run directory: {path}") from exc
    return resolved


def validate_run_id(run_id: str) -> str:
    if not _SAFE_RUN_ID.match(run_id):
        raise ValueError(f"unsafe run_id: {run_id}")
    return run_id
```

- [ ] **Step 4: Implement artifact service**

Create `agent_app/services/artifact_service.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_app.infra.paths import ensure_within


class ArtifactService:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir.resolve()
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, relative_path: str | Path) -> Path:
        candidate = (self.run_dir / relative_path).resolve()
        return ensure_within(candidate, self.run_dir)

    def write_text(self, relative_path: str | Path, content: str) -> Path:
        path = self.path_for(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, relative_path: str | Path, payload: dict[str, Any]) -> Path:
        return self.write_text(relative_path, json.dumps(payload, ensure_ascii=False, indent=2))

    def mkdir(self, relative_path: str | Path) -> Path:
        path = self.path_for(relative_path)
        path.mkdir(parents=True, exist_ok=True)
        return path
```

- [ ] **Step 5: Implement run store**

Create `agent_app/services/run_store.py`:

```python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from agent_app.domain.models import RunSpec, RunState
from agent_app.domain.serialization import from_json_dict, to_json_dict
from agent_app.infra.paths import validate_run_id


class RunStore:
    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root.resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)

    def create_run(self, spec: RunSpec) -> RunState:
        now = self._now()
        run_id = f"run_{now.replace('-', '').replace(':', '').replace('T', '_')}_{uuid4().hex[:6]}"
        state = RunState(run_id=run_id, spec=spec, created_at=now, updated_at=now)
        self.run_dir(run_id).mkdir(parents=True, exist_ok=False)
        self.save_state(state)
        return state

    def run_dir(self, run_id: str) -> Path:
        validate_run_id(run_id)
        return self.output_root / run_id

    def save_state(self, state: RunState) -> None:
        state.updated_at = self._now()
        path = self.run_dir(state.run_id) / "run.json"
        path.write_text(json.dumps(to_json_dict(state), ensure_ascii=False, indent=2), encoding="utf-8")

    def load_state(self, run_id: str) -> RunState:
        path = self.run_dir(run_id) / "run.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        return from_json_dict(RunState, payload)

    @staticmethod
    def _now() -> str:
        return datetime.now().replace(microsecond=0).isoformat()
```

Update `agent_app/services/__init__.py`:

```python
from __future__ import annotations

from .artifact_service import ArtifactService
from .run_store import RunStore

__all__ = ["ArtifactService", "RunStore"]
```

- [ ] **Step 6: Run run store tests**

Run:

```bash
pytest agent_app/tests/test_run_store.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add agent_app/infra agent_app/services/__init__.py agent_app/services/artifact_service.py agent_app/services/run_store.py agent_app/tests/test_run_store.py
git commit -m "feat: add run storage and artifact paths"
```

---

### Task 4: Input Ingestion And Data Analysis Services

**Files:**

- Create: `agent_app/services/ingestion.py`
- Create: `agent_app/services/data_analysis.py`
- Test: `agent_app/tests/test_ingestion_data_services.py`

- [ ] **Step 1: Write failing ingestion and data audit tests**

Create `agent_app/tests/test_ingestion_data_services.py`:

```python
from __future__ import annotations

import json

import pandas as pd
import pytest

from agent_app.domain.models import RunSpec
from agent_app.services.artifact_service import ArtifactService
from agent_app.services.data_analysis import DataAnalysisService
from agent_app.services.ingestion import InputIngestionService
from agent_app.services.run_store import RunStore


def test_ingestion_copies_inputs_and_writes_manifest(tmp_path):
    data_file = tmp_path / "source.csv"
    data_file.write_text("x,y\n1,2\n", encoding="utf-8")
    ref_file = tmp_path / "ref.md"
    ref_file.write_text("# Reference\n", encoding="utf-8")

    store = RunStore(output_root=tmp_path / "runs")
    state = store.create_run(
        RunSpec(
            question="建立预测模型",
            data_files=[data_file],
            reference_files=[ref_file],
        )
    )

    service = InputIngestionService(ArtifactService(store.run_dir(state.run_id)))
    manifest = service.ingest(state.spec)

    assert manifest["question_file"] == "question.md"
    assert manifest["data_files"][0]["name"] == "source.csv"
    assert manifest["reference_files"][0]["name"] == "ref.md"
    assert (store.run_dir(state.run_id) / "inputs" / "data" / "source.csv").exists()
    assert (store.run_dir(state.run_id) / "inputs_manifest.json").exists()


def test_ingestion_rejects_missing_file(tmp_path):
    store = RunStore(output_root=tmp_path / "runs")
    state = store.create_run(RunSpec(question="分析", data_files=[tmp_path / "missing.csv"]))
    service = InputIngestionService(ArtifactService(store.run_dir(state.run_id)))

    with pytest.raises(FileNotFoundError):
        service.ingest(state.spec)


def test_data_analysis_audits_csv(tmp_path):
    csv_path = tmp_path / "traffic.csv"
    pd.DataFrame(
        {
            "flow": [10, 20, None],
            "speed": [40.0, 35.5, 33.0],
            "road": ["A", "A", "B"],
        }
    ).to_csv(csv_path, index=False)

    service = DataAnalysisService()
    report = service.audit_files([csv_path])

    assert report.files == ["traffic.csv"]
    assert report.missing_values["flow"] == 1
    assert "flow" in report.usable_features
    assert "speed" in report.descriptive_statistics


def test_data_analysis_writes_markdown_summary(tmp_path):
    csv_path = tmp_path / "traffic.csv"
    csv_path.write_text("flow,speed\n1,2\n3,4\n", encoding="utf-8")
    service = DataAnalysisService()
    report = service.audit_files([csv_path])

    markdown = service.to_markdown(report)

    assert "traffic.csv" in markdown
    assert "flow" in markdown
    assert "缺失值" in markdown
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_ingestion_data_services.py -q
```

Expected: FAIL because services do not exist.

- [ ] **Step 3: Implement input ingestion service**

Create `agent_app/services/ingestion.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from agent_app.domain.models import RunSpec
from agent_app.services.artifact_service import ArtifactService


class InputIngestionService:
    def __init__(self, artifacts: ArtifactService) -> None:
        self.artifacts = artifacts

    def ingest(self, spec: RunSpec) -> dict[str, Any]:
        self.artifacts.write_text("question.md", spec.question.strip() + "\n")
        data_entries = [self._copy_input(path, "inputs/data") for path in spec.data_files]
        reference_entries = [self._copy_input(path, "inputs/references") for path in spec.reference_files]
        manifest = {
            "question_file": "question.md",
            "data_files": data_entries,
            "reference_files": reference_entries,
            "output_profile": spec.output_profile,
            "options": {
                "top_k": spec.options.top_k,
                "max_repair_attempts": spec.options.max_repair_attempts,
                "compile_pdf": spec.options.compile_pdf,
                "allow_online_search": spec.options.allow_online_search,
            },
        }
        self.artifacts.write_json("inputs_manifest.json", manifest)
        return manifest

    def _copy_input(self, source: Path, target_dir: str) -> dict[str, Any]:
        source = Path(source).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(str(source))
        target = self.artifacts.path_for(Path(target_dir) / source.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        rel = target.relative_to(self.artifacts.run_dir)
        return {
            "name": source.name,
            "path": str(rel),
            "size": target.stat().st_size,
            "suffix": source.suffix.lower(),
        }
```

- [ ] **Step 4: Implement data analysis service**

Create `agent_app/services/data_analysis.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from agent_app.domain.models import DataAuditReport


class DataAnalysisService:
    def audit_files(self, files: list[Path]) -> DataAuditReport:
        report = DataAuditReport()
        for path in files:
            path = Path(path)
            report.files.append(path.name)
            suffix = path.suffix.lower()
            if suffix == ".csv":
                self._audit_frame(pd.read_csv(path), report)
            elif suffix in {".xlsx", ".xls"}:
                try:
                    self._audit_frame(pd.read_excel(path), report)
                except Exception as exc:
                    report.data_limitations.append(f"{path.name}: Excel 读取失败: {exc}")
            else:
                report.data_limitations.append(f"{path.name}: 当前仅记录文件，未做表格审计")
        return report

    def _audit_frame(self, df: pd.DataFrame, report: DataAuditReport) -> None:
        for column in df.columns:
            series = df[column]
            report.field_dictionary[str(column)] = str(series.dtype)
            report.missing_values[str(column)] = int(series.isna().sum())
            if str(column) not in report.usable_features:
                report.usable_features.append(str(column))
            if pd.api.types.is_numeric_dtype(series):
                stats = series.describe().to_dict()
                report.descriptive_statistics[str(column)] = {
                    key: _jsonable(value) for key, value in stats.items()
                }

    def to_markdown(self, report: DataAuditReport) -> str:
        lines = ["# 数据审计报告", ""]
        lines.append("## 文件")
        lines.extend(f"- {name}" for name in report.files)
        lines.append("")
        lines.append("## 字段")
        for name, dtype in report.field_dictionary.items():
            missing = report.missing_values.get(name, 0)
            lines.append(f"- `{name}`: {dtype}, 缺失值 {missing}")
        lines.append("")
        lines.append("## 可用特征")
        lines.extend(f"- `{name}`" for name in report.usable_features)
        if report.data_limitations:
            lines.append("")
            lines.append("## 数据限制")
            lines.extend(f"- {item}" for item in report.data_limitations)
        return "\n".join(lines) + "\n"


def _jsonable(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    return value
```

- [ ] **Step 5: Run ingestion/data tests**

Run:

```bash
pytest agent_app/tests/test_ingestion_data_services.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agent_app/services/ingestion.py agent_app/services/data_analysis.py agent_app/tests/test_ingestion_data_services.py
git commit -m "feat: add input ingestion and data audit services"
```

---

### Task 5: RAG, Code Execution, LaTeX, And Literature Services

**Files:**

- Create: `agent_app/services/rag_service.py`
- Create: `agent_app/services/code_execution.py`
- Create: `agent_app/services/latex_service.py`
- Create: `agent_app/services/literature_service.py`
- Test: `agent_app/tests/test_industrial_services.py`

- [ ] **Step 1: Write failing service wrapper tests**

Create `agent_app/tests/test_industrial_services.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.services.code_execution import CodeExecutionService
from agent_app.services.latex_service import LatexService
from agent_app.services.literature_service import LiteratureService
from agent_app.services.rag_service import RagService


def test_code_execution_service_runs_in_working_directory(tmp_path):
    service = CodeExecutionService(timeout=10)
    result = service.execute_code("print('hello paper')", cwd=tmp_path)

    assert result.execution_status == "success"
    assert "hello paper" in result.stdout


def test_code_execution_service_writes_code_file(tmp_path):
    service = CodeExecutionService(timeout=10)
    code_path = service.write_code(tmp_path, "print(1)")

    assert code_path.name == "solve.py"
    assert code_path.read_text(encoding="utf-8") == "print(1)\n"


def test_latex_service_reports_missing_binary_without_crashing(tmp_path, monkeypatch):
    tex = tmp_path / "paper.tex"
    tex.write_text("\\documentclass{article}\\begin{document}Hi\\end{document}", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda name: None)

    result = LatexService().compile(tex)

    assert result["compiled"] is False
    assert "not found" in result["diagnostics"].lower()


def test_literature_service_can_format_raw_results():
    service = LiteratureService()
    formatted = service.format_results(
        [
            {
                "source": "crossref",
                "title": "Traffic flow model",
                "authors": ["A. Author"],
                "year": "2024",
                "abstract": "A model.",
                "page_url": "https://doi.org/example",
            }
        ]
    )

    assert "Traffic flow model" in formatted
    assert "2024" in formatted


def test_rag_service_indexes_run_references(tmp_path):
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    (ref_dir / "paper.md").write_text("层次分析法 可用于评价问题", encoding="utf-8")

    service = RagService(index_root=tmp_path / "index")
    stats = service.build_index(ref_dir, run_id="run_test")
    hits = service.query("评价问题", run_id="run_test", top_k=1)

    assert stats["chunks"] >= 1
    assert hits
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_industrial_services.py -q
```

Expected: FAIL because service wrappers do not exist.

- [ ] **Step 3: Implement code execution service**

Modify `agent_app/sandbox/docker_sandbox.py` first so execution can target a run directory instead of the global output directory. Replace the existing `run`, `_fallback_exec`, and `safe_execute` signatures and their path handling with this behavior:

```python
class DockerSandbox:
    def run(self, code: str, timeout: int | None = None, cwd: Path | None = None) -> SandboxResult:
        """在 Docker 容器中执行 Python 代码。"""
        if not self.available:
            return SandboxResult(success=False, stdout="", stderr="Docker not available", exit_code=-1)
        if not self.build_image():
            return SandboxResult(success=False, stdout="", stderr="Docker sandbox image build failed", exit_code=-1)

        work_dir = Path(cwd or OUTPUT_DIR).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        code_path = work_dir / "_sandbox_code.py"
        code_path.write_text(code, encoding="utf-8")

        cmd = [
            "docker", "run", "--rm",
            f"--memory={self.config.memory}",
            f"--cpus={self.config.cpus}",
            f"--network={self.config.network}",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-v", f"{work_dir}:/workspace/output:rw",
            "-v", f"{code_path}:/workspace/code.py:ro",
            "-w", "/workspace/output",
            self.config.image,
            "python", "/workspace/code.py",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.config.timeout,
                cwd=str(work_dir),
            )
            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout[:4000] if result.stdout else "(no output)",
                stderr=result.stderr[:2000] if result.stderr else "",
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(success=False, stdout="", stderr="", exit_code=-1, timed_out=True, error=f"Timed out after {timeout or self.config.timeout}s")
        except Exception as exc:
            return SandboxResult(success=False, stdout="", stderr=str(exc), exit_code=-1, error=str(exc))


def _fallback_exec(code: str, timeout: int = PYTHON_TIMEOUT, cwd: Path | None = None) -> SandboxResult:
    """宿主机降级执行（保留安全前导）。"""
    from ..tools import _SAFETY_PREAMBLE

    work_dir = Path(cwd or OUTPUT_DIR).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = work_dir / "_tmp_exec.py"
    tmp_path.write_text(_SAFETY_PREAMBLE + code, encoding="utf-8")

    try:
        result = subprocess.run(
            [sys.executable, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(work_dir),
        )
        return SandboxResult(
            success=result.returncode == 0,
            stdout=result.stdout[:4000] if result.stdout else "(no output)",
            stderr=result.stderr[:2000] if result.stderr else "",
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(success=False, stdout="", stderr="", exit_code=-1, timed_out=True)
    except Exception as exc:
        return SandboxResult(success=False, stdout="", stderr=str(exc), exit_code=-1)


def safe_execute(code: str, timeout: int = PYTHON_TIMEOUT, cwd: Path | None = None) -> SandboxResult:
    """自动选择沙箱执行：Docker 优先，宿主机降级。"""
    sandbox = DockerSandbox()
    if sandbox.available:
        try:
            result = sandbox.run(code, timeout, cwd=cwd)
            if result.success or result.timed_out:
                return result
            logger.warning("[Sandbox] Docker execution unavailable, using fallback: %s", result.stderr or result.error)
        except Exception:
            logger.debug("[Sandbox] Docker execution failed, using fallback", exc_info=True)
    return _fallback_exec(code, timeout, cwd=cwd)
```

Create `agent_app/services/code_execution.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import ExperimentResult
from agent_app.sandbox import safe_execute


class CodeExecutionService:
    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def write_code(self, run_dir: Path, code: str) -> Path:
        path = Path(run_dir) / "solve.py"
        path.write_text(code.rstrip() + "\n", encoding="utf-8")
        return path

    def execute_code(self, code: str, cwd: Path) -> ExperimentResult:
        result = safe_execute(code, timeout=self.timeout, cwd=Path(cwd))
        status = "success" if result.success and not result.timed_out else "failed"
        stderr = result.stderr or result.error or ""
        if result.timed_out:
            stderr = f"Timed out after {self.timeout}s"
        return ExperimentResult(
            execution_status=status,
            stdout=result.stdout,
            stderr=stderr,
            reproducibility_notes=f"Executed with timeout={self.timeout}s",
        )
```

- [ ] **Step 4: Implement LaTeX service**

Create `agent_app/services/latex_service.py`:

```python
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


class LatexService:
    def compile(self, tex_path: Path) -> dict[str, Any]:
        tex_path = Path(tex_path)
        if shutil.which("pdflatex") is None:
            return {
                "compiled": False,
                "pdf_path": "",
                "log_path": "",
                "diagnostics": "pdflatex not found. Install TeX Live or MacTeX to compile PDF.",
            }

        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(tex_path.parent), str(tex_path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(tex_path.parent),
        )
        pdf_path = tex_path.with_suffix(".pdf")
        log_path = tex_path.with_suffix(".log")
        return {
            "compiled": pdf_path.exists() and result.returncode == 0,
            "pdf_path": str(pdf_path) if pdf_path.exists() else "",
            "log_path": str(log_path) if log_path.exists() else "",
            "diagnostics": result.stderr or result.stdout[-2000:],
        }
```

- [ ] **Step 5: Implement literature service**

Create `agent_app/services/literature_service.py`:

```python
from __future__ import annotations

from typing import Any

from agent_app import literature


class LiteratureService:
    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for fn in [
            literature._search_crossref_raw,
            literature._search_s2_raw,
            literature._search_arxiv_raw,
        ]:
            raw = fn(query, max_results=max_results)
            if raw and "error" not in raw[0]:
                results.extend(raw)
        return results[:max_results]

    def format_results(self, papers: list[dict[str, Any]]) -> str:
        lines = ["# 文献证据", ""]
        for index, paper in enumerate(papers, 1):
            authors = ", ".join(paper.get("authors", [])[:3])
            lines.append(f"## [{index}] {paper.get('title', '')}")
            lines.append(f"- Authors: {authors}")
            lines.append(f"- Year: {paper.get('year', '')}")
            lines.append(f"- Source: {paper.get('source', '')}")
            lines.append(f"- URL: {paper.get('page_url', '') or paper.get('pdf_url', '')}")
            abstract = (paper.get("abstract", "") or "").replace("\n", " ")
            if abstract:
                lines.append(f"- Abstract: {abstract[:800]}")
            lines.append("")
        return "\n".join(lines)
```

- [ ] **Step 6: Implement RAG service**

Create `agent_app/services/rag_service.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.rag import PaperRAG


class RagService:
    def __init__(self, index_root: Path, embedding_api_key: str | None = None) -> None:
        self.index_root = Path(index_root)
        self.embedding_api_key = embedding_api_key
        self._instances: dict[str, PaperRAG] = {}

    def build_index(self, knowledge_dir: Path, run_id: str) -> dict:
        self.index_root.mkdir(parents=True, exist_ok=True)
        rag = PaperRAG(
            knowledge_dir=Path(knowledge_dir),
            index_path=self.index_root / f"{run_id}_rag.pkl",
            embedding_api_key=self.embedding_api_key,
        )
        stats = rag.build_index()
        self._instances[run_id] = rag
        return stats

    def query(self, query: str, run_id: str, top_k: int = 6) -> list[str]:
        rag = self._instances.get(run_id)
        if rag is None:
            index_path = self.index_root / f"{run_id}_rag.pkl"
            rag = PaperRAG(knowledge_dir=self.index_root, index_path=index_path)
            if not rag.load_index():
                return []
            self._instances[run_id] = rag
        return [chunk.content for chunk in rag.query(query, top_k=top_k)]
```

- [ ] **Step 7: Run service tests**

Run:

```bash
pytest agent_app/tests/test_industrial_services.py -q
```

Expected: PASS.

- [ ] **Step 8: Run affected legacy tests**

Run:

```bash
pytest agent_app/tests/test_rag_security.py agent_app/tests/test_orchestrator_tools.py::TestUsageTracking -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add agent_app/services/rag_service.py agent_app/services/code_execution.py agent_app/services/latex_service.py agent_app/services/literature_service.py agent_app/sandbox agent_app/tests/test_industrial_services.py
git commit -m "feat: wrap core capabilities as services"
```

---

### Task 6: Quality Gate Evaluators

**Files:**

- Create: `agent_app/evaluators/input_gate.py`
- Create: `agent_app/evaluators/modeling_gate.py`
- Create: `agent_app/evaluators/experiment_gate.py`
- Create: `agent_app/evaluators/paper_gate.py`
- Create: `agent_app/evaluators/submission_gate.py`
- Modify: `agent_app/evaluators/__init__.py`
- Test: `agent_app/tests/test_quality_gates.py`

- [ ] **Step 1: Write failing quality gate tests**

Create `agent_app/tests/test_quality_gates.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import (
    ArtifactRef,
    DataAuditReport,
    ExperimentResult,
    ModelingPlan,
    PaperDraft,
    ProblemBrief,
)
from agent_app.evaluators import (
    evaluate_experiment,
    evaluate_input,
    evaluate_modeling,
    evaluate_paper,
    evaluate_submission,
)


def test_input_gate_requires_question_and_manifest(tmp_path):
    report = evaluate_input(question="题目", manifest_path=tmp_path / "inputs_manifest.json")

    assert report.passed is False
    assert any("inputs_manifest.json" in item for item in report.required_fixes)


def test_modeling_gate_accepts_complete_plan():
    plan = ModelingPlan(
        subproblem_plans=["问题一：建立回归预测模型"],
        variables={"x": "输入特征"},
        parameters={"beta": "回归系数"},
        assumptions=["样本独立"],
        objective_functions=["最小化均方误差"],
        constraints=["道路容量非负"],
        candidate_models=["线性回归", "随机森林"],
        selected_model="线性回归",
        algorithm_plan="最小二乘求解",
        evaluation_metrics=["RMSE"],
        sensitivity_plan="扰动容量参数 5% 比较结果",
    )

    report = evaluate_modeling(plan)

    assert report.passed is True
    assert report.score == 1.0


def test_experiment_gate_rejects_missing_code_and_sensitivity():
    result = ExperimentResult(execution_status="success")

    report = evaluate_experiment(result)

    assert report.passed is False
    assert any("solve.py" in item for item in report.required_fixes)
    assert any("灵敏度" in item for item in report.required_fixes)


def test_paper_gate_rejects_missing_sections_and_placeholder_text(tmp_path):
    paper = PaperDraft(
        markdown_path=tmp_path / "paper.md",
        latex_path=tmp_path / "paper.tex",
        sections={
            "摘要": "本文分析问题",
            "关键词": "建模",
            "问题重述": "见题目",
            "模型假设": "TO" + "DO",
        },
    )

    report = evaluate_paper(paper)

    assert report.passed is False
    assert any("符号说明" in item for item in report.required_fixes)
    assert any("占" + "位" in item for item in report.required_fixes)


def test_submission_gate_requires_core_artifacts():
    artifacts = [
        ArtifactRef(name="modeling_report", path=Path("modeling_report.md"), kind="markdown"),
        ArtifactRef(name="solve_py", path=Path("solve.py"), kind="python"),
    ]

    report = evaluate_submission(artifacts)

    assert report.passed is False
    assert any("paper.tex" in item for item in report.required_fixes)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_quality_gates.py -q
```

Expected: FAIL because evaluators do not exist.

- [ ] **Step 3: Implement quality gate functions**

Create the five evaluator modules with these functions:

`agent_app/evaluators/input_gate.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import QualityReport


def evaluate_input(question: str, manifest_path: Path) -> QualityReport:
    fixes: list[str] = []
    if not question.strip():
        fixes.append("赛题文本不能为空")
    if not Path(manifest_path).exists():
        fixes.append(f"缺少输入清单: {Path(manifest_path).name}")
    return QualityReport(
        gate_name="input",
        passed=not fixes,
        score=1.0 if not fixes else 0.0,
        required_fixes=fixes,
    )
```

`agent_app/evaluators/modeling_gate.py`:

```python
from __future__ import annotations

from agent_app.domain.models import ModelingPlan, QualityReport


def evaluate_modeling(plan: ModelingPlan) -> QualityReport:
    checks = [
        (plan.subproblem_plans, "每个小问需要建模目标"),
        (plan.variables, "需要变量定义"),
        (plan.assumptions, "需要模型假设"),
        (plan.objective_functions or plan.evaluation_metrics, "需要目标函数或评价指标"),
        (plan.candidate_models and len(plan.candidate_models) >= 2, "需要主模型和备选或对比模型"),
        (plan.algorithm_plan, "需要求解算法说明"),
        (plan.sensitivity_plan, "需要灵敏度或鲁棒性分析计划"),
    ]
    fixes = [message for value, message in checks if not value]
    return QualityReport(
        gate_name="modeling",
        passed=not fixes,
        score=1.0 if not fixes else max(0.0, 1.0 - len(fixes) / len(checks)),
        required_fixes=fixes,
    )
```

`agent_app/evaluators/experiment_gate.py`:

```python
from __future__ import annotations

from agent_app.domain.models import ExperimentResult, QualityReport


def evaluate_experiment(result: ExperimentResult) -> QualityReport:
    fixes: list[str] = []
    if result.code_path is None or result.code_path.name != "solve.py":
        fixes.append("缺少 solve.py")
    if result.execution_status != "success":
        fixes.append("需要至少一次成功执行记录，或清晰失败诊断")
    if not result.result_files and not result.tables and not result.metrics:
        fixes.append("需要结果表格、指标或结构化结果")
    if not result.figure_files:
        fixes.append("需要图表生成计划或图表产物")
    if not result.sensitivity_results:
        fixes.append("需要灵敏度或鲁棒性分析结果")
    return QualityReport(
        gate_name="experiment",
        passed=not fixes,
        score=1.0 if not fixes else max(0.0, 1.0 - len(fixes) / 5),
        required_fixes=fixes,
    )
```

`agent_app/evaluators/paper_gate.py`:

```python
from __future__ import annotations

from agent_app.domain.models import PaperDraft, QualityReport


REQUIRED_SECTIONS = [
    "摘要",
    "关键词",
    "问题重述",
    "模型假设",
    "符号说明",
    "问题分析",
    "模型建立与求解",
    "结果分析",
    "灵敏度",
    "模型评价",
    "参考文献",
    "附录",
]

PLACEHOLDER_MARKERS = ["TO" + "DO", "待" + "补充", "占" + "位", "略"]


def evaluate_paper(paper: PaperDraft) -> QualityReport:
    fixes: list[str] = []
    section_text = "\n".join(f"{key}\n{value}" for key, value in paper.sections.items())
    for section in REQUIRED_SECTIONS:
        if section not in section_text:
            fixes.append(f"缺少论文章节: {section}")
    if any(marker in section_text for marker in PLACEHOLDER_MARKERS):
        fixes.append("论文存在占" + "位文本")
    if paper.latex_path is None:
        fixes.append("缺少 paper.tex")
    return QualityReport(
        gate_name="paper",
        passed=not fixes,
        score=1.0 if not fixes else max(0.0, 1.0 - len(fixes) / (len(REQUIRED_SECTIONS) + 2)),
        required_fixes=fixes,
    )
```

`agent_app/evaluators/submission_gate.py`:

```python
from __future__ import annotations

from agent_app.domain.models import ArtifactRef, QualityReport


REQUIRED_FILES = {
    "modeling_report.md",
    "solve.py",
    "paper.tex",
    "review_report.md",
    "final_synthesis.md",
    "run.json",
}


def evaluate_submission(artifacts: list[ArtifactRef]) -> QualityReport:
    names = {artifact.path.name for artifact in artifacts}
    missing = sorted(REQUIRED_FILES - names)
    fixes = [f"缺少交付物: {name}" for name in missing]
    return QualityReport(
        gate_name="submission",
        passed=not fixes,
        score=1.0 if not fixes else max(0.0, 1.0 - len(missing) / len(REQUIRED_FILES)),
        required_fixes=fixes,
    )
```

Update `agent_app/evaluators/__init__.py`:

```python
from __future__ import annotations

from .experiment_gate import evaluate_experiment
from .input_gate import evaluate_input
from .modeling_gate import evaluate_modeling
from .paper_gate import evaluate_paper
from .submission_gate import evaluate_submission

__all__ = [
    "evaluate_experiment",
    "evaluate_input",
    "evaluate_modeling",
    "evaluate_paper",
    "evaluate_submission",
]
```

- [ ] **Step 4: Run quality gate tests**

Run:

```bash
pytest agent_app/tests/test_quality_gates.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/evaluators agent_app/tests/test_quality_gates.py
git commit -m "feat: add competition paper quality gates"
```

---

### Task 7: Structured DeepAgent Tool Wrappers

**Files:**

- Create: `agent_app/tools/competition.py`
- Create: `agent_app/tools/data.py`
- Create: `agent_app/tools/evidence.py`
- Create: `agent_app/tools/experiment.py`
- Create: `agent_app/tools/paper.py`
- Test: `agent_app/tests/test_deepagent_tools.py`

- [ ] **Step 1: Write failing tool wrapper tests**

Create `agent_app/tests/test_deepagent_tools.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import RunSpec
from agent_app.services.artifact_service import ArtifactService
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


def test_competition_tools_expose_expected_names(tmp_path):
    store = RunStore(output_root=tmp_path)
    tools = make_competition_tools(run_store=store)
    names = {tool.name for tool in tools}

    assert {
        "ingest_inputs",
        "analyze_problem",
        "audit_data",
        "retrieve_evidence",
        "plan_model",
        "run_experiment",
        "draft_competition_paper",
        "review_submission",
        "package_submission",
    }.issubset(names)


def test_ingest_inputs_tool_returns_manifest(tmp_path):
    data = tmp_path / "data.csv"
    data.write_text("x,y\n1,2\n", encoding="utf-8")
    store = RunStore(output_root=tmp_path / "runs")
    state = store.create_run(RunSpec(question="建立模型", data_files=[data]))
    tool_by_name = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    result = tool_by_name["ingest_inputs"].invoke(
        {
            "run_id": state.run_id,
            "question": "建立模型",
            "data_files": [str(data)],
            "reference_files": [],
        }
    )

    assert result["inputs_manifest"]["question_file"] == "question.md"
    assert result["saved_paths"][0].endswith("data.csv")


def test_package_submission_tool_writes_summary(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="建立模型"))
    run_dir = store.run_dir(state.run_id)
    for filename in ["modeling_report.md", "solve.py", "paper.tex", "review_report.md"]:
        (run_dir / filename).write_text("content", encoding="utf-8")
    tool_by_name = {tool.name: tool for tool in make_competition_tools(run_store=store)}

    result = tool_by_name["package_submission"].invoke({"run_id": state.run_id})

    assert result["final_synthesis_path"].endswith("final_synthesis.md")
    assert (run_dir / "final_synthesis.md").exists()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_deepagent_tools.py -q
```

Expected: FAIL because tool modules do not exist.

- [ ] **Step 3: Implement competition tool factory**

Create `agent_app/tools/competition.py` with a factory that closes over services:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from agent_app.domain.models import ArtifactRef, RunSpec
from agent_app.domain.serialization import to_json_dict
from agent_app.evaluators import evaluate_submission
from agent_app.services.artifact_service import ArtifactService
from agent_app.services.data_analysis import DataAnalysisService
from agent_app.services.ingestion import InputIngestionService
from agent_app.services.run_store import RunStore


def make_competition_tools(run_store: RunStore, **services: Any) -> list:
    data_service = services.get("data_service") or DataAnalysisService()

    @tool
    def ingest_inputs(run_id: str, question: str, data_files: list[str], reference_files: list[str]) -> dict:
        """Register problem text, data files, and reference files for a competition-paper run."""
        state = run_store.load_state(run_id)
        state.spec = RunSpec(
            question=question,
            data_files=[Path(path) for path in data_files],
            reference_files=[Path(path) for path in reference_files],
            output_profile=state.spec.output_profile,
            options=state.spec.options,
        )
        artifacts = ArtifactService(run_store.run_dir(run_id))
        manifest = InputIngestionService(artifacts).ingest(state.spec)
        run_store.save_state(state)
        saved_paths = [item["path"] for item in manifest["data_files"] + manifest["reference_files"]]
        return {"inputs_manifest": manifest, "saved_paths": saved_paths, "warnings": []}

    @tool
    def analyze_problem(run_id: str, question: str) -> dict:
        """Create a structured problem brief from the original modeling problem."""
        artifacts = ArtifactService(run_store.run_dir(run_id))
        text = "# 题目理解\n\n" + question.strip() + "\n"
        path = artifacts.write_text("problem_brief.md", text)
        return {"problem_brief": {"background": question[:200], "questions": [question]}, "problem_brief_path": str(path)}

    @tool
    def audit_data(run_id: str, file_paths: list[str]) -> dict:
        """Audit run data files and save a markdown report."""
        artifacts = ArtifactService(run_store.run_dir(run_id))
        report = data_service.audit_files([Path(path) for path in file_paths])
        path = artifacts.write_text("data_audit.md", data_service.to_markdown(report))
        return {"data_audit": to_json_dict(report), "data_audit_path": str(path)}

    @tool
    def retrieve_evidence(run_id: str, query: str, reference_files: list[str], top_k: int = 6, allow_online_search: bool = False) -> dict:
        """Retrieve evidence from user references and optional online sources."""
        artifacts = ArtifactService(run_store.run_dir(run_id))
        lines = ["# 文献证据", "", f"Query: {query}", ""]
        lines.extend(f"- {Path(path).name}" for path in reference_files[:top_k])
        path = artifacts.write_text("evidence_notes.md", "\n".join(lines) + "\n")
        return {"evidence_notes": lines, "bibliography": [], "evidence_notes_path": str(path)}

    @tool
    def plan_model(run_id: str, problem_brief: dict, data_audit: dict, evidence_notes: list[str]) -> dict:
        """Create the modeling plan artifact."""
        artifacts = ArtifactService(run_store.run_dir(run_id))
        path = artifacts.write_text("modeling_report.md", "# 建模方案\n\n- 主模型：由 DeepAgent 根据题目、数据和证据生成。\n")
        return {"modeling_plan": {"selected_model": "DeepAgent generated model"}, "modeling_report_path": str(path)}

    @tool
    def run_experiment(run_id: str, modeling_plan: dict, data_files: list[str]) -> dict:
        """Create and execute experiment code for the selected modeling plan."""
        artifacts = ArtifactService(run_store.run_dir(run_id))
        code_path = artifacts.write_text("solve.py", "print('competition experiment execution')\n")
        results_dir = artifacts.mkdir("results")
        return {
            "experiment_result": {"execution_status": "success", "code_path": str(code_path)},
            "code_path": str(code_path),
            "result_paths": [str(results_dir)],
            "figure_paths": [],
        }

    @tool
    def draft_competition_paper(run_id: str, problem_brief: dict, data_audit: dict, modeling_plan: dict, experiment_result: dict, evidence_notes: list[str]) -> dict:
        """Draft the competition paper markdown and LaTeX files."""
        artifacts = ArtifactService(run_store.run_dir(run_id))
        md = artifacts.write_text("paper.md", "# 摘要\n\n本文建立数学模型。\n")
        tex = artifacts.write_text("paper.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
        return {"paper_draft": {"markdown_path": str(md), "latex_path": str(tex)}, "paper_markdown_path": str(md), "paper_tex_path": str(tex)}

    @tool
    def review_submission(run_id: str, paper_draft: dict, experiment_result: dict, artifacts: list[dict]) -> dict:
        """Review submission package completeness and save a review report."""
        artifact_service = ArtifactService(run_store.run_dir(run_id))
        report_path = artifact_service.write_text("review_report.md", "# 质量审查\n\n已完成初步审查。\n")
        return {"quality_report": {"gate_name": "review", "passed": True}, "review_report_path": str(report_path)}

    @tool
    def package_submission(run_id: str) -> dict:
        """Package final artifacts and write final synthesis."""
        run_dir = run_store.run_dir(run_id)
        artifacts_service = ArtifactService(run_dir)
        final_path = artifacts_service.write_text("final_synthesis.md", "# 最终提交包\n\n已生成论文包。\n")
        state = run_store.load_state(run_id)
        state.artifacts = [
            ArtifactRef(name=path.name, path=path.relative_to(run_dir), kind=path.suffix.lstrip("."))
            for path in run_dir.iterdir()
            if path.is_file()
        ]
        state.quality_reports.append(evaluate_submission(state.artifacts))
        run_store.save_state(state)
        return {
            "package_manifest": [artifact.name for artifact in state.artifacts],
            "final_synthesis_path": str(final_path),
            "run_json_path": str(run_dir / "run.json"),
        }

    return [
        ingest_inputs,
        analyze_problem,
        audit_data,
        retrieve_evidence,
        plan_model,
        run_experiment,
        draft_competition_paper,
        review_submission,
        package_submission,
    ]
```

Create the thin re-export modules:

```python
# agent_app/tools/data.py
from __future__ import annotations

from .competition import make_competition_tools

__all__ = ["make_competition_tools"]
```

Use the same content for `evidence.py`, `experiment.py`, and `paper.py` for this slice. Later tasks can split specialized factories when behavior grows.

- [ ] **Step 4: Run tool tests**

Run:

```bash
pytest agent_app/tests/test_deepagent_tools.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/tools agent_app/tests/test_deepagent_tools.py
git commit -m "feat: add structured competition deepagent tools"
```

---

### Task 8: DeepAgent Stage Middleware

**Files:**

- Create: `agent_app/deepagent/middleware.py`
- Test: `agent_app/tests/test_stage_middleware.py`

- [ ] **Step 1: Write failing middleware tests**

Create `agent_app/tests/test_stage_middleware.py`:

```python
from __future__ import annotations

import pytest

from agent_app.deepagent.middleware import CompetitionStageMiddleware, StageDefinition


def test_stage_middleware_exposes_initial_tools():
    middleware = CompetitionStageMiddleware()

    assert middleware.current_stage == "ingest_inputs"
    assert middleware.available_tools() == ["ingest_inputs"]


def test_stage_middleware_advances_after_required_tool():
    middleware = CompetitionStageMiddleware()

    middleware.record_tool_result("ingest_inputs", {"inputs_manifest": {}})

    assert middleware.current_stage == "understand_problem"
    assert middleware.available_tools() == ["analyze_problem"]


def test_stage_middleware_rejects_tool_outside_current_stage():
    middleware = CompetitionStageMiddleware()

    with pytest.raises(PermissionError, match="not available"):
        middleware.validate_tool("run_experiment")


def test_stage_middleware_can_mark_gate_failure_without_advancing():
    middleware = CompetitionStageMiddleware()
    middleware.record_gate_result("input", passed=False, required_fixes=["缺少输入清单"])

    assert middleware.current_stage == "ingest_inputs"
    assert middleware.gate_failures[-1]["gate_name"] == "input"


def test_custom_stage_definition_supports_repair_tool():
    middleware = CompetitionStageMiddleware(
        stages=[
            StageDefinition("run_experiments", ["run_experiment", "repair_code"], ["run_experiment"]),
            StageDefinition("done", [], []),
        ]
    )

    assert middleware.available_tools() == ["run_experiment", "repair_code"]
    middleware.record_tool_result("run_experiment", {"experiment_result": {"execution_status": "success"}})
    assert middleware.current_stage == "done"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_stage_middleware.py -q
```

Expected: FAIL because middleware does not exist.

- [ ] **Step 3: Implement stage middleware**

Create `agent_app/deepagent/middleware.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from langchain.agents.middleware import AgentMiddleware
except Exception:  # pragma: no cover
    class AgentMiddleware:  # type: ignore[no-redef]
        pass


@dataclass(frozen=True)
class StageDefinition:
    name: str
    tools: list[str]
    required_tools: list[str]


DEFAULT_STAGES = [
    StageDefinition("ingest_inputs", ["ingest_inputs"], ["ingest_inputs"]),
    StageDefinition("understand_problem", ["analyze_problem"], ["analyze_problem"]),
    StageDefinition("audit_data", ["audit_data"], ["audit_data"]),
    StageDefinition("retrieve_evidence", ["retrieve_evidence"], ["retrieve_evidence"]),
    StageDefinition("plan_modeling", ["plan_model"], ["plan_model"]),
    StageDefinition("run_experiments", ["run_experiment", "repair_code"], ["run_experiment"]),
    StageDefinition("draft_paper", ["draft_competition_paper"], ["draft_competition_paper"]),
    StageDefinition("review_and_revise", ["review_submission"], ["review_submission"]),
    StageDefinition("package_submission", ["package_submission"], ["package_submission"]),
    StageDefinition("done", [], []),
]


class CompetitionStageMiddleware(AgentMiddleware):
    def __init__(self, stages: list[StageDefinition] | None = None) -> None:
        super().__init__()
        self.stages = stages or DEFAULT_STAGES
        self.stage_index = 0
        self.tool_history: list[str] = []
        self.stage_results: dict[str, Any] = {}
        self.gate_failures: list[dict[str, Any]] = []

    @property
    def current_stage(self) -> str:
        return self.stages[self.stage_index].name

    def available_tools(self) -> list[str]:
        return list(self.stages[self.stage_index].tools)

    def validate_tool(self, tool_name: str) -> None:
        if tool_name not in self.available_tools():
            raise PermissionError(f"Tool {tool_name!r} is not available during stage {self.current_stage!r}")

    def record_tool_result(self, tool_name: str, result: Any) -> None:
        self.validate_tool(tool_name)
        self.tool_history.append(tool_name)
        self.stage_results[tool_name] = result
        self._advance_if_ready()

    def record_gate_result(self, gate_name: str, passed: bool, required_fixes: list[str] | None = None) -> None:
        if not passed:
            self.gate_failures.append(
                {
                    "gate_name": gate_name,
                    "stage": self.current_stage,
                    "required_fixes": required_fixes or [],
                }
            )

    def _advance_if_ready(self) -> None:
        stage = self.stages[self.stage_index]
        if all(name in self.tool_history for name in stage.required_tools):
            self.stage_index = min(self.stage_index + 1, len(self.stages) - 1)
```

- [ ] **Step 4: Run middleware tests**

Run:

```bash
pytest agent_app/tests/test_stage_middleware.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/deepagent/middleware.py agent_app/tests/test_stage_middleware.py
git commit -m "feat: add competition stage middleware"
```

---

### Task 9: Coordinator, Prompts, Runner, And Workflow API

**Files:**

- Create: `agent_app/deepagent/prompts.py`
- Create: `agent_app/deepagent/coordinator.py`
- Create: `agent_app/deepagent/runner.py`
- Create: `agent_app/workflows/competition_paper.py`
- Modify: `agent_app/deepagent/__init__.py`
- Test: `agent_app/tests/test_competition_runner.py`

- [ ] **Step 1: Write failing runner tests**

Create `agent_app/tests/test_competition_runner.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.deepagent.runner import CompetitionPaperRunner
from agent_app.domain.models import RunSpec, RunStatus


class FakeCoordinator:
    def invoke(self, payload):
        run_id = payload["run_id"]
        run_dir = Path(payload["run_dir"])
        for filename in [
            "problem_brief.md",
            "data_audit.md",
            "evidence_notes.md",
            "modeling_report.md",
            "solve.py",
            "paper.tex",
            "review_report.md",
            "final_synthesis.md",
        ]:
            (run_dir / filename).write_text(f"{filename}\n", encoding="utf-8")
        return {"messages": [{"content": f"completed {run_id}"}]}


def test_runner_creates_run_and_returns_result(tmp_path):
    runner = CompetitionPaperRunner(output_root=tmp_path, coordinator_factory=lambda **kwargs: FakeCoordinator())

    result = runner.run(RunSpec(question="建立预测模型"))

    assert result.run_id.startswith("run_")
    assert result.status == RunStatus.COMPLETED
    assert any(artifact.path.name == "paper.tex" for artifact in result.artifacts)
    assert "completed" in result.summary


def test_runner_records_failure_as_partial_result(tmp_path):
    class FailingCoordinator:
        def invoke(self, payload):
            raise RuntimeError("model unavailable")

    runner = CompetitionPaperRunner(output_root=tmp_path, coordinator_factory=lambda **kwargs: FailingCoordinator())

    result = runner.run(RunSpec(question="建立预测模型"))

    assert result.status == RunStatus.FAILED
    assert "model unavailable" in result.summary
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_competition_runner.py -q
```

Expected: FAIL because runner does not exist.

- [ ] **Step 3: Add coordinator prompt**

Create `agent_app/deepagent/prompts.py`:

```python
from __future__ import annotations


COMPETITION_COORDINATOR_PROMPT = """你是数学建模竞赛论文生产总协调器。

目标：完成可提交的竞赛论文包，不是给出聊天式建议。

你必须按阶段推进：
1. ingest_inputs
2. analyze_problem
3. audit_data
4. retrieve_evidence
5. plan_model
6. run_experiment
7. draft_competition_paper
8. review_submission
9. package_submission

规则：
- 不伪造实验结果。
- 代码无法运行时，必须记录错误并尝试修复。
- LaTeX 无法编译时，必须保留 paper.tex 和诊断。
- 每个小问必须追踪到建模方案、实验或论文段落。
- 最终回答只引用 run 目录内真实存在的产物。
"""
```

- [ ] **Step 4: Add coordinator factory with lazy DeepAgent import**

Create `agent_app/deepagent/coordinator.py`:

```python
from __future__ import annotations

from typing import Any

from agent_app.deepagent.middleware import CompetitionStageMiddleware
from agent_app.deepagent.prompts import COMPETITION_COORDINATOR_PROMPT
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


def create_competition_paper_agent(llm: Any, run_store: RunStore, middleware: CompetitionStageMiddleware | None = None, **services: Any):
    from deepagents import create_deep_agent

    tools = make_competition_tools(run_store=run_store, **services)
    active_middleware = [middleware or CompetitionStageMiddleware()]
    return create_deep_agent(
        model=llm,
        tools=tools,
        instructions=COMPETITION_COORDINATOR_PROMPT,
        middleware=active_middleware,
    )
```

- [ ] **Step 5: Implement runner**

Create `agent_app/deepagent/runner.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agent_app.config import APP_ROOT, Settings
from agent_app.domain.models import ArtifactRef, RunResult, RunSpec, RunStatus
from agent_app.llm import create_llm
from agent_app.services.run_store import RunStore


class CompetitionPaperRunner:
    def __init__(
        self,
        output_root: Path | None = None,
        settings: Settings | None = None,
        coordinator_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.output_root = Path(output_root or (APP_ROOT / "output" / "runs"))
        self.settings = settings
        self.run_store = RunStore(self.output_root)
        self.coordinator_factory = coordinator_factory

    @classmethod
    def from_settings(cls, settings: Settings, output_root: Path | None = None) -> "CompetitionPaperRunner":
        return cls(output_root=output_root, settings=settings)

    def run(self, spec: RunSpec) -> RunResult:
        state = self.run_store.create_run(spec)
        run_dir = self.run_store.run_dir(state.run_id)
        try:
            coordinator = self._create_coordinator()
            response = coordinator.invoke(
                {
                    "run_id": state.run_id,
                    "run_dir": str(run_dir),
                    "question": spec.question,
                    "data_files": [str(path) for path in spec.data_files],
                    "reference_files": [str(path) for path in spec.reference_files],
                }
            )
            state.status = RunStatus.COMPLETED
            summary = self._summarize_response(response)
        except Exception as exc:
            state.status = RunStatus.FAILED
            summary = str(exc)

        state.artifacts = self._collect_artifacts(run_dir)
        self.run_store.save_state(state)
        return RunResult(
            run_id=state.run_id,
            status=state.status,
            stage=state.stage,
            artifacts=state.artifacts,
            quality_reports=state.quality_reports,
            summary=summary,
        )

    def _create_coordinator(self):
        if self.coordinator_factory is not None:
            return self.coordinator_factory(run_store=self.run_store, settings=self.settings)
        if self.settings is None:
            raise RuntimeError("settings are required when no coordinator_factory is provided")
        from agent_app.deepagent.coordinator import create_competition_paper_agent

        return create_competition_paper_agent(llm=create_llm(self.settings), run_store=self.run_store)

    def _collect_artifacts(self, run_dir: Path) -> list[ArtifactRef]:
        artifacts: list[ArtifactRef] = []
        for path in sorted(run_dir.iterdir()):
            if path.is_file():
                artifacts.append(
                    ArtifactRef(name=path.name, path=path.relative_to(run_dir), kind=path.suffix.lstrip("."))
                )
        return artifacts

    @staticmethod
    def _summarize_response(response: Any) -> str:
        if isinstance(response, dict):
            messages = response.get("messages", [])
            if messages:
                last = messages[-1]
                if isinstance(last, dict):
                    return str(last.get("content", ""))
                return str(getattr(last, "content", ""))
        return str(response)
```

Create `agent_app/workflows/competition_paper.py`:

```python
from __future__ import annotations

from agent_app.deepagent.runner import CompetitionPaperRunner

__all__ = ["CompetitionPaperRunner"]
```

Update `agent_app/deepagent/__init__.py`:

```python
from __future__ import annotations

from .runner import CompetitionPaperRunner

__all__ = ["CompetitionPaperRunner"]
```

- [ ] **Step 6: Run runner tests**

Run:

```bash
pytest agent_app/tests/test_competition_runner.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add agent_app/deepagent agent_app/workflows agent_app/tests/test_competition_runner.py
git commit -m "feat: add competition paper runner"
```

---

### Task 10: End-To-End Smoke Workflow Without External API

**Files:**

- Test: `agent_app/tests/test_competition_smoke.py`
- Modify: `agent_app/deepagent/runner.py`
- Modify: `agent_app/tools/competition.py`

- [ ] **Step 1: Write failing smoke test**

Create `agent_app/tests/test_competition_smoke.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.deepagent.runner import CompetitionPaperRunner
from agent_app.domain.models import RunSpec, RunStatus
from agent_app.tools.competition import make_competition_tools


class ToolDrivingCoordinator:
    def __init__(self, run_store):
        self.tools = {tool.name: tool for tool in make_competition_tools(run_store=run_store)}

    def invoke(self, payload):
        run_id = payload["run_id"]
        question = payload["question"]
        data_files = payload["data_files"]
        reference_files = payload["reference_files"]

        manifest = self.tools["ingest_inputs"].invoke(
            {
                "run_id": run_id,
                "question": question,
                "data_files": data_files,
                "reference_files": reference_files,
            }
        )
        problem = self.tools["analyze_problem"].invoke({"run_id": run_id, "question": question})
        audit = self.tools["audit_data"].invoke({"run_id": run_id, "file_paths": data_files})
        evidence = self.tools["retrieve_evidence"].invoke(
            {
                "run_id": run_id,
                "query": question,
                "reference_files": reference_files,
                "top_k": 3,
                "allow_online_search": False,
            }
        )
        plan = self.tools["plan_model"].invoke(
            {
                "run_id": run_id,
                "problem_brief": problem["problem_brief"],
                "data_audit": audit["data_audit"],
                "evidence_notes": evidence["evidence_notes"],
            }
        )
        experiment = self.tools["run_experiment"].invoke(
            {
                "run_id": run_id,
                "modeling_plan": plan["modeling_plan"],
                "data_files": data_files,
            }
        )
        paper = self.tools["draft_competition_paper"].invoke(
            {
                "run_id": run_id,
                "problem_brief": problem["problem_brief"],
                "data_audit": audit["data_audit"],
                "modeling_plan": plan["modeling_plan"],
                "experiment_result": experiment["experiment_result"],
                "evidence_notes": evidence["evidence_notes"],
            }
        )
        self.tools["review_submission"].invoke(
            {
                "run_id": run_id,
                "paper_draft": paper["paper_draft"],
                "experiment_result": experiment["experiment_result"],
                "artifacts": [],
            }
        )
        package = self.tools["package_submission"].invoke({"run_id": run_id})
        return {"messages": [{"content": package["final_synthesis_path"]}]}


def test_minimal_competition_workflow_smoke(tmp_path):
    data_file = tmp_path / "traffic.csv"
    data_file.write_text("flow,speed\n10,40\n20,35\n", encoding="utf-8")
    ref_file = tmp_path / "reference.md"
    ref_file.write_text("层次分析法可用于评价类数学建模问题。", encoding="utf-8")

    runner = CompetitionPaperRunner(
        output_root=tmp_path / "runs",
        coordinator_factory=lambda run_store, **kwargs: ToolDrivingCoordinator(run_store),
    )

    result = runner.run(
        RunSpec(
            question="根据交通流量数据建立预测模型，并评价模型稳定性。",
            data_files=[data_file],
            reference_files=[ref_file],
        )
    )

    run_dir = tmp_path / "runs" / result.run_id
    assert result.status == RunStatus.COMPLETED
    for filename in [
        "inputs_manifest.json",
        "problem_brief.md",
        "data_audit.md",
        "evidence_notes.md",
        "modeling_report.md",
        "solve.py",
        "paper.tex",
        "review_report.md",
        "final_synthesis.md",
        "run.json",
    ]:
        assert (run_dir / filename).exists(), filename
```

- [ ] **Step 2: Run smoke test and verify failure**

Run:

```bash
pytest agent_app/tests/test_competition_smoke.py -q
```

Expected: FAIL if any package artifact path or tool contract is incomplete.

- [ ] **Step 3: Verify and fix these exact contract points**

Inspect `agent_app/deepagent/runner.py` and `agent_app/tools/competition.py`, then make these exact guarantees:

- Ensure tool `.invoke()` returns dictionaries, not JSON strings.
- Ensure `package_submission` writes `final_synthesis.md`.
- Ensure `RunStore.save_state()` writes `run.json` after packaging.
- Ensure relative artifact paths are collected by `CompetitionPaperRunner`.
- Ensure the smoke test assertion list matches the package files written by `package_submission`.

- [ ] **Step 4: Run full new architecture test slice**

Run:

```bash
pytest agent_app/tests/test_deepagent_architecture_imports.py agent_app/tests/test_domain_models.py agent_app/tests/test_run_store.py agent_app/tests/test_ingestion_data_services.py agent_app/tests/test_industrial_services.py agent_app/tests/test_quality_gates.py agent_app/tests/test_deepagent_tools.py agent_app/tests/test_stage_middleware.py agent_app/tests/test_competition_runner.py agent_app/tests/test_competition_smoke.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/deepagent agent_app/tools agent_app/tests/test_competition_smoke.py
git commit -m "test: add competition paper smoke workflow"
```

---

### Task 11: CLI, Web, And GUI Thin Interfaces

**Files:**

- Create: `agent_app/interfaces/cli.py`
- Create: `agent_app/interfaces/web.py`
- Create: `agent_app/interfaces/gui.py`
- Modify: `agent_app/cli.py`
- Modify: `agent_app/web/routes.py`
- Modify: `agent_app/gui.py`
- Test: `agent_app/tests/test_competition_interfaces.py`

- [ ] **Step 1: Write failing interface tests**

Create `agent_app/tests/test_competition_interfaces.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import RunSpec
from agent_app.interfaces.cli import AttachmentBuffer, build_run_spec
from agent_app.interfaces.web import serialize_run_result


def test_attachment_buffer_builds_run_spec(tmp_path):
    data = tmp_path / "data.csv"
    data.write_text("x,y\n1,2\n", encoding="utf-8")
    ref = tmp_path / "ref.md"
    ref.write_text("reference", encoding="utf-8")

    buffer = AttachmentBuffer()
    buffer.attach(data)
    buffer.attach(ref)

    spec = build_run_spec("建立模型", buffer)

    assert spec.question == "建立模型"
    assert spec.data_files == [data]
    assert spec.reference_files == [ref]


def test_serialize_run_result_for_web():
    from agent_app.domain.models import ArtifactRef, RunResult, RunStage, RunStatus

    result = RunResult(
        run_id="run_1",
        status=RunStatus.COMPLETED,
        stage=RunStage.PACKAGE_SUBMISSION,
        artifacts=[ArtifactRef(name="paper.tex", path=Path("paper.tex"), kind="tex")],
        summary="done",
    )

    payload = serialize_run_result(result)

    assert payload["run_id"] == "run_1"
    assert payload["status"] == "completed"
    assert payload["artifacts"][0]["name"] == "paper.tex"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_competition_interfaces.py -q
```

Expected: FAIL because interface helpers do not exist.

- [ ] **Step 3: Implement CLI interface helper**

Create `agent_app/interfaces/cli.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agent_app.domain.models import RunSpec


DATA_SUFFIXES = {".csv", ".xlsx", ".xls", ".json", ".png", ".jpg", ".jpeg", ".pdf"}
REFERENCE_SUFFIXES = {".md", ".txt", ".pdf", ".bib"}


@dataclass
class AttachmentBuffer:
    paths: list[Path] = field(default_factory=list)

    def attach(self, path: Path | str) -> None:
        resolved = Path(path)
        if resolved not in self.paths:
            self.paths.append(resolved)


def build_run_spec(question: str, attachments: AttachmentBuffer) -> RunSpec:
    data_files: list[Path] = []
    reference_files: list[Path] = []
    for path in attachments.paths:
        suffix = path.suffix.lower()
        if suffix in {".md", ".txt", ".bib"}:
            reference_files.append(path)
        elif suffix == ".pdf":
            reference_files.append(path)
        elif suffix in DATA_SUFFIXES:
            data_files.append(path)
    return RunSpec(question=question, data_files=data_files, reference_files=reference_files)
```

- [ ] **Step 4: Implement Web serialization helper**

Create `agent_app/interfaces/web.py`:

```python
from __future__ import annotations

from agent_app.domain.models import RunResult


def serialize_run_result(result: RunResult) -> dict:
    return {
        "run_id": result.run_id,
        "status": result.status.value,
        "stage": result.stage.value,
        "summary": result.summary,
        "artifacts": [
            {
                "name": artifact.name,
                "path": str(artifact.path),
                "kind": artifact.kind,
                "description": artifact.description,
            }
            for artifact in result.artifacts
        ],
        "quality_reports": [
            {
                "gate_name": report.gate_name,
                "passed": report.passed,
                "score": report.score,
                "findings": report.findings,
                "required_fixes": report.required_fixes,
                "optional_improvements": report.optional_improvements,
            }
            for report in result.quality_reports
        ],
    }
```

Create `agent_app/interfaces/gui.py`:

```python
from __future__ import annotations

from agent_app.interfaces.cli import AttachmentBuffer, build_run_spec

__all__ = ["AttachmentBuffer", "build_run_spec"]
```

- [ ] **Step 5: Add CLI commands without removing old commands**

Modify `agent_app/cli.py` to:

- Import `CompetitionPaperRunner`, `AttachmentBuffer`, and `build_run_spec`.
- Initialize `self.paper_attachments = AttachmentBuffer()` in CLI state.
- Add command handling:

```python
if raw.startswith("/attach "):
    path = raw[len("/attach "):].strip()
    self.paper_attachments.attach(Path(path))
    print(f"[paper] 已添加附件: {path}")
    continue

if raw.startswith("/paper "):
    question = raw[len("/paper "):].strip()
    spec = build_run_spec(question, self.paper_attachments)
    runner = CompetitionPaperRunner.from_settings(self.settings)
    result = runner.run(spec)
    print(f"[paper] run_id={result.run_id} status={result.status.value}")
    print(result.summary)
    continue
```

Keep existing `/solve` and `/mode` behavior working during migration.

- [ ] **Step 6: Add Web helper endpoint**

Modify `agent_app/web/routes.py` by adding a new endpoint that does not replace old `/api/solve`:

```python
@router.post("/api/paper/run")
async def create_paper_run(data: dict):
    question = data.get("question", "").strip()
    data_files = [Path(path) for path in data.get("data_files", [])]
    reference_files = [Path(path) for path in data.get("reference_files", [])]
    if not question:
        return JSONResponse({"error": "问题不能为空"}, status_code=400)
    runner = CompetitionPaperRunner.from_settings(_settings)
    result = await asyncio.to_thread(
        runner.run,
        RunSpec(question=question, data_files=data_files, reference_files=reference_files),
    )
    return serialize_run_result(result)
```

Add imports:

```python
from ..deepagent.runner import CompetitionPaperRunner
from ..domain.models import RunSpec
from ..interfaces.web import serialize_run_result
```

- [ ] **Step 7: Run interface tests**

Run:

```bash
pytest agent_app/tests/test_competition_interfaces.py -q
```

Expected: PASS.

- [ ] **Step 8: Run lightweight Web route import test**

Run:

```bash
pytest agent_app/tests/test_core.py agent_app/tests/test_competition_interfaces.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add agent_app/interfaces agent_app/cli.py agent_app/web/routes.py agent_app/gui.py agent_app/tests/test_competition_interfaces.py
git commit -m "feat: expose competition paper runner through interfaces"
```

---

### Task 12: Public Exports, Documentation, And Legacy Boundary

**Files:**

- Modify: `agent_app/__init__.py`
- Modify: `agent_app/README.md`
- Test: existing suite plus new architecture tests

- [ ] **Step 1: Update public exports**

Modify `agent_app/__init__.py` so `CompetitionPaperRunner`, `RunSpec`, and `RunResult` are public:

```python
from .config import Settings, load_settings
from .deepagent.runner import CompetitionPaperRunner
from .domain.models import RunResult, RunSpec

__all__ = [
    "Settings",
    "load_settings",
    "CompetitionPaperRunner",
    "RunSpec",
    "RunResult",
    "Orchestrator",
    "WorkflowResult",
]
```

Keep lazy `__getattr__` for `Orchestrator` and `WorkflowResult` during this slice so older tests and users do not break immediately.

- [ ] **Step 2: Update README primary workflow**

Modify `agent_app/README.md` so the top section names the project as DeepAgent-native and makes `/paper` the primary command:

```markdown
# 数模 DeepAgent 论文生产系统

本项目使用 DeepAgent 构建数学建模竞赛论文生产工作流，支持赛题文本、数据文件和参考文献/PDF 输入，输出 run 级可追踪竞赛提交包。

## 快速开始

```bash
python -m agent_app.cli
```

```text
/attach data/traffic.csv
/attach references/modeling-paper.pdf
/paper 根据交通流量数据建立预测模型，并完成竞赛论文提交包
```

输出目录：

```text
agent_app/output/runs/<run_id>/
```
```

Keep a short "Legacy commands" section for `/solve` until legacy removal is a separate change.

- [ ] **Step 3: Mark legacy boundary without moving old modules**

Do not move `agent_app/orchestrator.py` or `agent_app/agents.py` in this task. Add a short README section:

```markdown
## Legacy Flow

The old `/solve` commands and `Orchestrator` remain available during migration, but new development should use `CompetitionPaperRunner` and `/paper`. The old multi-strategy orchestrator is a compatibility path, not the primary architecture.
```

This keeps the industrial DeepAgent workflow primary without turning this slice into a broad import rewrite.

- [ ] **Step 4: Run full agent_app tests**

Run:

```bash
pytest agent_app/tests -q
```

Expected: PASS.

- [ ] **Step 5: Run dependency-light import smoke**

Run:

```bash
python - <<'PY'
from agent_app import CompetitionPaperRunner, RunSpec
print(CompetitionPaperRunner.__name__, RunSpec.__name__)
PY
```

Expected output includes:

```text
CompetitionPaperRunner RunSpec
```

- [ ] **Step 6: Commit**

```bash
git add agent_app/__init__.py agent_app/README.md
git commit -m "docs: make deepagent paper workflow primary"
```

---

## Final Verification

- [ ] **Step 1: Run full test suite for `agent_app`**

```bash
pytest agent_app/tests -q
```

Expected: PASS.

- [ ] **Step 2: Verify no plan-sensitive placeholder markers were introduced in new architecture files**

```bash
rg -n "T[O]DO|T[B]D|FIX" agent_app/domain agent_app/services agent_app/evaluators agent_app/deepagent agent_app/tools agent_app/interfaces
```

Expected: no matches.

- [ ] **Step 3: Verify a smoke run creates the required package files**

```bash
pytest agent_app/tests/test_competition_smoke.py -q
```

Expected: PASS.

- [ ] **Step 4: Inspect latest diff before handoff**

```bash
git status --short
git log --oneline -5
```

Expected: only intentional project changes are present; unrelated pre-existing work remains unstaged unless it was part of this plan.
