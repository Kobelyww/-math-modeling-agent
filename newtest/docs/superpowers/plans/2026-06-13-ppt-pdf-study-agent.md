# PPT/PDF Study Agent Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a formal-product path for the PPT/PDF study agent while first delivering an MVP-1 PDF-to-outline-and-questions workflow.

**Architecture:** Keep the Agent core independent from product delivery layers. MVP-1 fixes the current Python core and CLI workflow; MVP-2 adds React + FastAPI product surfaces plus document normalization; MVP-3 adds PostgreSQL/pgvector persistence plus Graph RAG-lite; MVP-4 experiments with Agentic RAG and automatic routing behind evaluation gates; MVP-5/6 add product quality, export, security, audit, and operations hardening.

**Tech Stack:** Python 3.11/3.12, pytest/pytest-asyncio, marker-pdf, NetworkX, FastAPI, Pydantic, SQLAlchemy/Alembic, PostgreSQL + pgvector, Redis workers, React + TypeScript + Vite.

---

## Scope

This plan supersedes the previous skeleton-first plan. The current repository already contains core skeletons under `src/` and tests under `tests/`; the next work should not recreate those files from scratch.

MVP-1 remains intentionally narrow:
- Fix the test environment and CLI EOF behavior.
- Adapt PDF parsing to the current `marker-pdf` API.
- Implement a deterministic PDF/structured-document to knowledge-points to outline to questions pipeline.
- Keep React/FastAPI/PostgreSQL as planned follow-up phases, not blockers for MVP-1.

## File Structure

MVP-1 core files:
- `pyproject.toml` — test/dev dependency configuration.
- `src/main.py` — CLI entrypoint and EOF-safe command loop.
- `src/parsers/marker_pdf.py` — PDF parser adapter and marker output mapping.
- `src/agents/content_understanding.py` — convert parsed document sections into knowledge points.
- `src/agents/outline_generation.py` — generate deterministic Markdown/LaTeX-ready outline.
- `src/agents/question_generation.py` — generate deterministic question objects.
- `src/coordinator/main_coordinator.py` — orchestrate MVP-1 pipeline.
- `src/services/rag_service.py` — minimal chunk storage/retrieval before full vector DB.
- `tests/fixtures/` — small sample PDF or structured-document fixtures.

Formal product files for later phases:
- `src/api/` — FastAPI app, dependencies, route modules.
- `src/db/` — SQLAlchemy models, sessions, Alembic migrations.
- `src/storage/` — local and object-store adapters.
- `src/workers/` — background job queue and worker tasks.
- `src/services/graph_rag.py` — Graph RAG-lite retriever using the existing knowledge graph.
- `src/services/agentic_rag.py` — deterministic Agentic RAG planning before LLM execution is introduced.
- `src/services/rag_router.py` — rule-first RAG mode router with cost and confidence metadata.
- `src/services/rag_evaluation.py` — shared evaluation set scoring and mode comparison reports.
- `src/normalization/` — parser-independent normalized document, chunk, asset, and source-span models.
- `src/services/version_service.py` — content version creation and lookup for generated and edited assets.
- `src/services/export_service.py` — asynchronous Markdown/LaTeX/PDF/JSON export job orchestration.
- `src/services/quality_service.py` — outline, question, QA, and export quality scoring.
- `src/services/feedback_service.py` — user feedback and review task collection.
- `src/security/` — permission checks and audit logging helpers.
- `src/observability/` — request IDs, structured logging, metrics, and health checks.
- `frontend/` — React + TypeScript + Vite app.

## Phase MVP-1: Core Workflow

### Task 1: Fix Test Environment

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

- [ ] **Step 1: Verify current failure**

Run:

```bash
pytest -q
```

Expected now: `14 failed, 30 passed` with `async def functions are not natively supported`.

- [ ] **Step 2: Ensure dev dependencies are installable**

Check `pyproject.toml` contains:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "black>=24.0.0",
    "isort>=5.13.0",
    "mypy>=1.10.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Also add missing test tools to `requirements.txt` if the project continues supporting `pip install -r requirements.txt`:

```txt
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=5.0.0
```

- [ ] **Step 3: Install in a clean environment**

Run:

```bash
python -m pip install -e ".[dev]"
pytest -q
```

Expected after dependency fix: async tests execute. Remaining failures, if any, must be real code/test failures rather than unknown `pytest.mark.asyncio`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml requirements.txt
git commit -m "test: fix async pytest environment"
```

### Task 2: Fix CLI EOF Handling

**Files:**
- Modify: `src/main.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add failing CLI EOF test**

Create `tests/test_cli.py`:

```python
import subprocess
import sys


def test_cli_exits_on_eof():
    result = subprocess.run(
        [sys.executable, "-m", "src.main"],
        input="",
        text=True,
        capture_output=True,
        timeout=3,
    )

    assert result.returncode == 0
    assert "EOF when reading a line" not in result.stdout
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_cli.py::test_cli_exits_on_eof -q
```

Expected before fix: timeout or repeated EOF output.

- [ ] **Step 3: Update command loop**

In `src/main.py`, catch `EOFError` separately and break:

```python
        except EOFError:
            print("\n输入结束，退出。")
            break
```

Place it before the broad `except Exception as e`.

- [ ] **Step 4: Verify**

```bash
pytest tests/test_cli.py::test_cli_exits_on_eof -q
printf "/quit\n" | python -m src.main
```

Expected: both commands exit successfully.

- [ ] **Step 5: Commit**

```bash
git add src/main.py tests/test_cli.py
git commit -m "fix: exit CLI cleanly on EOF"
```

### Task 3: Adapt Marker PDF Parser

**Files:**
- Modify: `src/parsers/marker_pdf.py`
- Modify: `src/config.py`
- Test: `tests/test_parsers.py`

- [ ] **Step 1: Add parser mapping tests without requiring real Marker models**

Extend `tests/test_parsers.py` with a fake Marker output mapping test:

```python
from types import SimpleNamespace
from src.parsers.marker_pdf import MarkerPDFParser


def test_marker_output_mapping_to_structured_document():
    parser = MarkerPDFParser()
    fake_rendered = SimpleNamespace(
        metadata={"title": "Linear Algebra"},
        markdown="# Chapter 1\nVectors and matrices",
        children=[],
    )

    doc = parser._map_marker_output(fake_rendered)

    assert doc.title == "Linear Algebra"
    assert doc.sections
    assert "Vectors" in doc.sections[0].content
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_parsers.py::test_marker_output_mapping_to_structured_document -q
```

Expected: fail because `_map_marker_output` does not exist.

- [ ] **Step 3: Implement current API adapter**

Update `MarkerPDFParser` to:
- Lazily import `ConfigParser`, `PdfConverter`, and `create_model_dict`.
- Use `PdfConverter(...)` rather than `marker.load_model` and `convert_single_pdf`.
- Add `_map_marker_output(rendered)` that maps metadata and markdown into `StructuredDocument`.
- Preserve import-time behavior so tests can run without marker installed unless `parse()` is called.

- [ ] **Step 4: Add file-not-found test**

Ensure existing parse behavior still raises a readable error when the PDF path is missing:

```bash
pytest tests/test_parsers.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/parsers/marker_pdf.py tests/test_parsers.py src/config.py
git commit -m "fix: adapt PDF parser to current marker API"
```

### Task 4: Implement Content Understanding Agent

**Files:**
- Create: `src/agents/content_understanding.py`
- Modify: `src/agents/__init__.py`
- Test: `tests/test_content_understanding.py`

- [ ] **Step 1: Write tests**

Create `tests/test_content_understanding.py`:

```python
import pytest
from src.agents.content_understanding import ContentUnderstandingAgent
from src.parsers.marker_pdf import StructuredDocument, Section, Formula


@pytest.mark.asyncio
async def test_extracts_knowledge_points_from_sections():
    doc = StructuredDocument(
        title="Calculus",
        sections=[
            Section(
                level=1,
                title="Derivatives",
                content="Derivative measures rate of change. Chain rule is important.",
                formulas=[Formula(latex="(f(g(x)))'=f'(g(x))g'(x)")],
            )
        ],
    )

    result = await ContentUnderstandingAgent().invoke({"document": doc})

    assert result.success is True
    points = result.data["knowledge_points"]
    assert len(points) >= 2
    assert any("Derivatives" in point.name or "Derivative" in point.name for point in points)
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_content_understanding.py -q
```

Expected: module missing.

- [ ] **Step 3: Implement deterministic extractor**

Implement `ContentUnderstandingAgent` using local heuristics:
- Section title becomes a high-importance concept.
- Formula entries become formula knowledge points.
- Long section content is split into sentence-like concepts.
- Return `KnowledgePoint` objects from `src.knowledge.knowledge_graph`.

- [ ] **Step 4: Verify**

```bash
pytest tests/test_content_understanding.py tests/test_knowledge.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/agents/content_understanding.py src/agents/__init__.py tests/test_content_understanding.py
git commit -m "feat: extract knowledge points from parsed documents"
```

### Task 5: Implement Outline Generation Agent

**Files:**
- Create: `src/agents/outline_generation.py`
- Modify: `src/agents/__init__.py`
- Test: `tests/test_outline_generation.py`

- [ ] **Step 1: Write tests**

Create `tests/test_outline_generation.py`:

```python
import pytest
from src.agents.outline_generation import OutlineGenerationAgent
from src.knowledge.knowledge_graph import KnowledgePoint, PointType


@pytest.mark.asyncio
async def test_generates_markdown_outline():
    points = [
        KnowledgePoint(id="kp1", name="Derivative", description="Rate of change", category="concept"),
        KnowledgePoint(id="kp2", name="Chain Rule", description="Composite derivative", category="formula", point_type=PointType.FORMULA),
    ]

    result = await OutlineGenerationAgent().invoke({"knowledge_points": points, "title": "Calculus"})

    assert result.success is True
    markdown = result.data["markdown"]
    assert "# Calculus" in markdown
    assert "Derivative" in markdown
    assert "复习建议" in markdown
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_outline_generation.py -q
```

Expected: module missing.

- [ ] **Step 3: Implement deterministic outline generator**

Generate Markdown with:
- Title.
- Core concepts grouped by category.
- Formula section when formula knowledge points exist.
- Review suggestions.

- [ ] **Step 4: Verify**

```bash
pytest tests/test_outline_generation.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/agents/outline_generation.py src/agents/__init__.py tests/test_outline_generation.py
git commit -m "feat: generate review outlines from knowledge points"
```

### Task 6: Implement Question Generation Agent

**Files:**
- Create: `src/agents/question_generation.py`
- Modify: `src/agents/__init__.py`
- Test: `tests/test_question_generation.py`

- [ ] **Step 1: Write tests**

Create `tests/test_question_generation.py`:

```python
import pytest
from src.agents.question_generation import QuestionGenerationAgent
from src.knowledge.knowledge_graph import KnowledgePoint


@pytest.mark.asyncio
async def test_generates_questions_with_answers():
    points = [
        KnowledgePoint(id="kp1", name="Derivative", description="Rate of change", category="concept"),
        KnowledgePoint(id="kp2", name="Matrix", description="Rectangular array", category="concept"),
    ]

    result = await QuestionGenerationAgent().invoke({"knowledge_points": points, "count": 5})

    assert result.success is True
    questions = result.data["questions"]
    assert len(questions) == 5
    assert all(q.stem and q.answer and q.explanation for q in questions)
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_question_generation.py -q
```

Expected: module missing.

- [ ] **Step 3: Implement deterministic question generator**

Define a `Question` dataclass with:

```python
stem: str
answer: str
explanation: str
difficulty: str
question_type: str
knowledge_point_id: str
```

Generate a mix of definition, fill-in, and short-answer questions by cycling through knowledge points.

- [ ] **Step 4: Verify**

```bash
pytest tests/test_question_generation.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/agents/question_generation.py src/agents/__init__.py tests/test_question_generation.py
git commit -m "feat: generate practice questions from knowledge points"
```

### Task 7: Orchestrate MVP-1 Pipeline

**Files:**
- Modify: `src/coordinator/main_coordinator.py`
- Test: `tests/test_coordinator.py`
- Test: `tests/test_integration.py`

- [ ] **Step 1: Add coordinator pipeline test**

Extend `tests/test_coordinator.py`:

```python
import pytest
from unittest.mock import AsyncMock
from src.coordinator.main_coordinator import MainCoordinator


@pytest.mark.asyncio
async def test_coordinator_runs_registered_pipeline():
    coordinator = MainCoordinator()
    coordinator.register_sub_coordinator("document_parsing", AsyncMock())
    coordinator.register_sub_coordinator("content_understanding", AsyncMock())
    coordinator.register_sub_coordinator("outline_generation", AsyncMock())
    coordinator.register_sub_coordinator("question_generation", AsyncMock())

    coordinator.sub_coordinators["document_parsing"].invoke.return_value.success = True
    coordinator.sub_coordinators["document_parsing"].invoke.return_value.data = {"document": "doc"}
    coordinator.sub_coordinators["content_understanding"].invoke.return_value.success = True
    coordinator.sub_coordinators["content_understanding"].invoke.return_value.data = {"knowledge_points": ["kp"]}
    coordinator.sub_coordinators["outline_generation"].invoke.return_value.success = True
    coordinator.sub_coordinators["outline_generation"].invoke.return_value.data = {"markdown": "# Outline"}
    coordinator.sub_coordinators["question_generation"].invoke.return_value.success = True
    coordinator.sub_coordinators["question_generation"].invoke.return_value.data = {"questions": ["q"]}

    result = await coordinator.invoke({"pdf_path": "sample.pdf"})

    assert result["status"] == "success"
    assert result["data"]["outline"] == "# Outline"
    assert result["data"]["questions"] == ["q"]
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_coordinator.py::test_coordinator_runs_registered_pipeline -q
```

Expected: fails because `invoke()` returns fixed placeholder data.

- [ ] **Step 3: Implement pipeline orchestration**

Update `MainCoordinator.invoke()` to call stages in order:
1. document parsing
2. content understanding
3. outline generation
4. question generation

If any stage returns `success=False`, set status failed and return a structured error with `failed_stage`.

- [ ] **Step 4: Verify**

```bash
pytest tests/test_coordinator.py tests/test_integration.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/coordinator/main_coordinator.py tests/test_coordinator.py tests/test_integration.py
git commit -m "feat: orchestrate MVP study pipeline"
```

### Task 8: Simple RAG Baseline

**Files:**
- Modify: `src/services/rag_service.py`
- Test: `tests/test_services.py`

- [ ] **Step 1: Add retrieval behavior test**

Extend `tests/test_services.py`:

```python
def test_rag_service_indexes_and_retrieves_chunks():
    rag = RAGService()
    rag.index_chunks([
        {"content": "Derivative is rate of change", "source": "doc:1"},
        {"content": "Matrix multiplication combines rows and columns", "source": "doc:2"},
    ])

    response = rag.retrieve("rate of change", top_k=1)

    assert response[0].source == "doc:1"
    assert "Derivative" in response[0].content
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_services.py::test_rag_service_indexes_and_retrieves_chunks -q
```

Expected: `index_chunks` missing.

- [ ] **Step 3: Implement in-memory lexical retrieval baseline**

Add:
- `index_chunks(chunks: list[dict]) -> None`
- `retrieve(query: str, top_k: int = 5) -> list[Chunk]`

Use token overlap scoring for MVP-1. Every returned chunk must include source metadata. Keep vector DB and advanced RAG for later phases.

- [ ] **Step 4: Verify**

```bash
pytest tests/test_services.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/services/rag_service.py tests/test_services.py
git commit -m "feat: add simple RAG baseline retrieval"
```

### Task 9: RAG Evaluation Dataset Foundation

**Files:**
- Create: `tests/fixtures/rag_eval_set.json`
- Create: `tests/test_rag_evaluation.py`
- Create: `src/services/rag_evaluation.py`

- [ ] **Step 1: Add evaluation fixture**

Create `tests/fixtures/rag_eval_set.json`:

```json
[
  {
    "id": "def-001",
    "query": "什么是导数？",
    "category": "definition",
    "expected_sources": ["calculus:derivative"],
    "expected_terms": ["变化率", "函数"]
  },
  {
    "id": "formula-001",
    "query": "链式法则公式是什么？",
    "category": "formula_lookup",
    "expected_sources": ["calculus:chain_rule"],
    "expected_terms": ["f(g(x))", "g'(x)"]
  },
  {
    "id": "relation-001",
    "query": "导数和梯度有什么关系？",
    "category": "concept_relation",
    "expected_sources": ["calculus:gradient"],
    "expected_terms": ["多变量", "方向"]
  },
  {
    "id": "synthesis-001",
    "query": "基于导数和矩阵出一道综合题",
    "category": "question_generation",
    "expected_sources": ["calculus:derivative", "linear_algebra:matrix"],
    "expected_terms": ["题目", "答案"]
  }
]
```

- [ ] **Step 2: Add evaluator tests**

Create `tests/test_rag_evaluation.py`:

```python
from src.services.rag_evaluation import RAGEvaluator, RAGEvalCase


def test_rag_evaluator_scores_terms_and_sources():
    case = RAGEvalCase(
        id="def-001",
        query="什么是导数？",
        category="definition",
        expected_sources=["calculus:derivative"],
        expected_terms=["变化率"],
    )

    score = RAGEvaluator().score(
        case,
        answer="导数描述函数的变化率。",
        sources=["calculus:derivative"],
        latency_ms=10,
        token_cost=0,
    )

    assert score.answer_term_recall == 1.0
    assert score.source_recall == 1.0
    assert score.latency_ms == 10
```

- [ ] **Step 3: Run failure**

```bash
pytest tests/test_rag_evaluation.py -q
```

Expected: module missing.

- [ ] **Step 4: Implement evaluator**

Create `src/services/rag_evaluation.py` with:
- `RAGEvalCase`
- `RAGEvalScore`
- `RAGEvaluator.score(...)`

Scoring must include:
- expected term recall
- source recall
- latency
- token cost

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/test_rag_evaluation.py -q
git add src/services/rag_evaluation.py tests/test_rag_evaluation.py tests/fixtures/rag_eval_set.json
git commit -m "test: add RAG evaluation foundation"
```

### Task 10: MVP-1 End-to-End Verification

**Files:**
- Modify: `tests/test_integration.py`
- Create: `tests/fixtures/sample_structured_document.json`

- [ ] **Step 1: Add fixture-driven integration test**

Use a structured-document fixture rather than a real PDF model dependency:

```python
@pytest.mark.asyncio
async def test_mvp_pipeline_from_structured_document():
    # Build StructuredDocument in test, run content understanding,
    # outline generation, and question generation.
    # Assert outline markdown and at least 5 questions.
```

- [ ] **Step 2: Verify full suite**

```bash
pytest -q
```

Expected for MVP-1 completion: all tests pass or external-model tests are explicitly skipped/xfail with reason.

- [ ] **Step 3: Run mandatory reviews**

Spec review:
- Check every MVP-1 success criterion in `SPEC.md` has a passing test or explicit skip.

Quality review:
- Check names, boundaries, deterministic tests, no placeholder return strings in completed MVP-1 path.

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py tests/fixtures/sample_structured_document.json
git commit -m "test: verify MVP study pipeline"
```

## Phase MVP-2: Formal Web Product Shell

### Task 11: FastAPI Product API Skeleton

**Files:**
- Create: `src/api/app.py`
- Create: `src/api/routes/documents.py`
- Create: `src/api/routes/jobs.py`
- Create: `tests/test_api_documents.py`

Implementation requirements:
- `POST /api/documents` accepts metadata first, then file upload once storage is ready.
- `GET /api/jobs/{id}` returns `queued`, `running`, `completed`, `failed`, or `cancelled`.
- API layer must call services/coordinator; it must not implement Agent logic.

Verification:

```bash
pytest tests/test_api_documents.py -q
```

Commit:

```bash
git add src/api tests/test_api_documents.py
git commit -m "feat: add FastAPI product API skeleton"
```

### Task 12: React Product Shell

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/pages/DocumentsPage.tsx`
- Create: `frontend/src/pages/JobDetailPage.tsx`
- Create: `frontend/src/pages/OutlinePage.tsx`
- Create: `frontend/src/pages/QuestionsPage.tsx`

Implementation requirements:
- Use React + TypeScript + Vite.
- First screen is the document workspace, not a marketing landing page.
- Include document list, upload action, job status, outline view, questions view.
- Use restrained operational UI suitable for repeated study workflows.

Verification:

```bash
cd frontend
npm install
npm run build
```

Commit:

```bash
git add frontend
git commit -m "feat: add React product shell"
```

### Task 13: Local Storage and Job Persistence

**Files:**
- Create: `src/db/session.py`
- Create: `src/db/models.py`
- Create: `src/storage/file_store.py`
- Create: `tests/test_storage.py`
- Create: `tests/test_db_models.py`

Implementation requirements:
- Define `Document`, `ProcessingJob`, `ParsedSection`, `KnowledgePointRecord`, `OutlineRecord`, `QuestionRecord`.
- Use SQLite locally but keep schema compatible with PostgreSQL.
- Store files by UUID/hash, never by raw user filename.

Verification:

```bash
pytest tests/test_storage.py tests/test_db_models.py -q
```

Commit:

```bash
git add src/db src/storage tests/test_storage.py tests/test_db_models.py
git commit -m "feat: add local persistence foundation"
```

### Task 14: Document Normalization and Source Spans

**Files:**
- Create: `src/normalization/document.py`
- Create: `src/normalization/normalizer.py`
- Create: `src/normalization/__init__.py`
- Test: `tests/test_document_normalization.py`

- [ ] **Step 1: Add normalization tests**

Create `tests/test_document_normalization.py`:

```python
from src.normalization.normalizer import DocumentNormalizer
from src.parsers.marker_pdf import Section, StructuredDocument


def test_normalizer_preserves_section_source_spans():
    source = StructuredDocument(
        title="Calculus Notes",
        sections=[
            Section(
                level=1,
                title="Derivatives",
                content="Derivative is rate of change.",
            )
        ],
        metadata={"source_path": "fixtures/calculus.pdf"},
    )

    normalized = DocumentNormalizer().normalize(source, document_id="doc-1")

    assert normalized.document_id == "doc-1"
    assert normalized.sections[0].title == "Derivatives"
    assert normalized.sections[0].source_spans[0].section_id == normalized.sections[0].id
    assert normalized.chunks[0].source_spans[0].section_id == normalized.sections[0].id
```

Add a second test for formulas/assets when parser metadata provides them:

```python
from src.parsers.marker_pdf import Formula


def test_normalizer_converts_formulas_to_assets():
    source = StructuredDocument(
        title="Formula Notes",
        sections=[Section(level=1, title="Chain Rule", content="Chain rule formula.")],
        formulas=[Formula(latex="(f \\circ g)'(x)=f'(g(x))g'(x)", page_number=2)],
    )

    normalized = DocumentNormalizer().normalize(source, document_id="doc-2")

    assert normalized.assets[0].asset_type == "formula"
    assert "f'(g(x))" in normalized.assets[0].description
    assert normalized.assets[0].source_span.page_number == 2
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_document_normalization.py -q
```

Expected: `src.normalization` module missing.

- [ ] **Step 3: Implement normalized document models**

Create `src/normalization/document.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceSpan:
    section_id: str
    page_number: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    char_start: int | None = None
    char_end: int | None = None
    confidence: float = 1.0
    missing_reason: str | None = None


@dataclass(frozen=True)
class NormalizedSection:
    id: str
    parent_id: str | None
    title: str
    content: str
    level: int
    order_index: int
    source_spans: list[SourceSpan]


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    section_id: str
    content: str
    chunk_index: int
    source_spans: list[SourceSpan]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentAsset:
    id: str
    asset_type: str
    description: str
    source_span: SourceSpan
    storage_uri: str | None = None
    caption: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedDocument:
    document_id: str
    title: str
    sections: list[NormalizedSection]
    chunks: list[DocumentChunk]
    assets: list[DocumentAsset]
    metadata: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Implement parser-independent normalizer**

Create `src/normalization/normalizer.py`:

```python
from __future__ import annotations

from src.normalization.document import (
    DocumentAsset,
    DocumentChunk,
    NormalizedDocument,
    NormalizedSection,
    SourceSpan,
)
from src.parsers.marker_pdf import StructuredDocument


class DocumentNormalizer:
    def normalize(self, document: StructuredDocument, document_id: str) -> NormalizedDocument:
        sections: list[NormalizedSection] = []
        chunks: list[DocumentChunk] = []

        for index, section in enumerate(document.sections):
            section_id = f"{document_id}:section:{index}"
            section_metadata = getattr(section, "metadata", {})
            page_number = section_metadata.get("page_number")
            span = SourceSpan(
                section_id=section_id,
                page_number=page_number,
                missing_reason=None if page_number else "parser_did_not_provide_page",
                confidence=1.0 if page_number else 0.5,
            )
            normalized_section = NormalizedSection(
                id=section_id,
                parent_id=None,
                title=section.title,
                content=section.content,
                level=section.level,
                order_index=index,
                source_spans=[span],
            )
            sections.append(normalized_section)

            if section.content.strip():
                chunks.append(
                    DocumentChunk(
                        id=f"{section_id}:chunk:0",
                        section_id=section_id,
                        content=section.content.strip(),
                        chunk_index=0,
                        source_spans=[span],
                    )
                )

        assets = [
            DocumentAsset(
                id=f"{document_id}:formula:{index}",
                asset_type="formula",
                description=formula.latex,
                source_span=SourceSpan(section_id=sections[0].id if sections else document_id, page_number=formula.page_number),
                metadata={"latex": formula.latex},
            )
            for index, formula in enumerate(document.formulas)
        ]

        return NormalizedDocument(
            document_id=document_id,
            title=document.title,
            sections=sections,
            chunks=chunks,
            assets=assets,
            metadata=document.metadata,
        )
```

If `Section` does not yet have `metadata`, do not mutate parser dataclasses in this task; use the missing page fallback shown above and add parser metadata in a later parser task.

- [ ] **Step 5: Export package API and verify**

Create `src/normalization/__init__.py`:

```python
from src.normalization.document import DocumentAsset, DocumentChunk, NormalizedDocument, NormalizedSection, SourceSpan
from src.normalization.normalizer import DocumentNormalizer

__all__ = [
    "DocumentAsset",
    "DocumentChunk",
    "DocumentNormalizer",
    "NormalizedDocument",
    "NormalizedSection",
    "SourceSpan",
]
```

Run:

```bash
pytest tests/test_document_normalization.py -q
git add src/normalization tests/test_document_normalization.py
git commit -m "feat: add document normalization layer"
```

## Phase MVP-3: Productized RAG and Persistence

### Task 15: Graph RAG-lite Retriever

**Files:**
- Create: `src/services/graph_rag.py`
- Modify: `src/knowledge/knowledge_graph.py`
- Test: `tests/test_graph_rag.py`

- [ ] **Step 1: Add Graph RAG-lite tests**

Create `tests/test_graph_rag.py`:

```python
import pytest
from src.knowledge.knowledge_graph import KnowledgeGraph, KnowledgePoint, Relationship
from src.services.graph_rag import GraphRAGLiteRetriever
from src.services.rag_service import Chunk


@pytest.mark.asyncio
async def test_graph_rag_expands_related_knowledge_points():
    graph = KnowledgeGraph()
    graph.add_point(KnowledgePoint(id="kp1", name="Derivative", description="Rate of change", category="concept"))
    graph.add_point(KnowledgePoint(id="kp2", name="Gradient", description="Vector of partial derivatives", category="concept"))
    graph.add_relationship(Relationship(source_id="kp1", target_id="kp2", relation_type="generalizes_to"))

    chunks = [
        Chunk(content="Derivative is rate of change", source="calculus:derivative"),
        Chunk(content="Gradient extends derivatives to multivariable functions", source="calculus:gradient"),
    ]

    result = await GraphRAGLiteRetriever(graph, chunks).retrieve("导数和梯度有什么关系？")

    assert any("Gradient" in item.content for item in result.chunks)
    assert result.mode == "graph_rag_lite"
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_graph_rag.py -q
```

Expected: module missing.

- [ ] **Step 3: Implement GraphRAGLiteRetriever**

Create `src/services/graph_rag.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from src.knowledge.knowledge_graph import KnowledgeGraph, KnowledgePoint
from src.services.rag_service import Chunk


@dataclass(frozen=True)
class GraphRAGResult:
    mode: str
    reason: str
    chunks: list[Chunk]
    confidence: float
    expanded_point_ids: list[str]


class GraphRAGLiteRetriever:
    def __init__(self, graph: KnowledgeGraph, chunks: list[Chunk]) -> None:
        self.graph = graph
        self.chunks = chunks

    async def retrieve(self, query: str, max_hops: int = 2, top_k: int = 5) -> GraphRAGResult:
        seeds = self._match_seed_points(query)
        expanded = self._expand_neighbors(seeds, max_hops=max_hops)
        matched_chunks = self._recover_chunks(expanded, top_k=top_k)
        confidence = 0.0 if not matched_chunks else min(1.0, 0.4 + 0.2 * len(matched_chunks))

        return GraphRAGResult(
            mode="graph_rag_lite",
            reason="matched concepts and expanded graph neighbors" if seeds else "no graph seed matched",
            chunks=matched_chunks,
            confidence=confidence,
            expanded_point_ids=[point.id for point in expanded],
        )

    def _match_seed_points(self, query: str) -> list[KnowledgePoint]:
        query_lower = query.lower()
        return [
            point
            for point in self.graph.points.values()
            if point.name.lower() in query_lower or any(token in query_lower for token in point.name.lower().split())
        ]

    def _expand_neighbors(self, seeds: list[KnowledgePoint], max_hops: int) -> list[KnowledgePoint]:
        seen = {point.id for point in seeds}
        frontier = list(seeds)

        for _ in range(max_hops):
            next_frontier: list[KnowledgePoint] = []
            for point in frontier:
                for neighbor in self.graph.get_related_points(point.id):
                    if neighbor.id not in seen:
                        seen.add(neighbor.id)
                        next_frontier.append(neighbor)
            frontier = next_frontier

        return [self.graph.points[point_id] for point_id in seen]

    def _recover_chunks(self, points: list[KnowledgePoint], top_k: int) -> list[Chunk]:
        names = [point.name.lower() for point in points]
        ranked: list[tuple[int, Chunk]] = []
        for chunk in self.chunks:
            score = sum(1 for name in names if name in chunk.content.lower() or name in chunk.source.lower())
            if score > 0:
                ranked.append((score, chunk))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in ranked[:top_k]]
```

If `KnowledgeGraph` does not yet expose `points` or `get_related_points(point_id)`, add those small accessors in `src/knowledge/knowledge_graph.py` rather than reaching into NetworkX internals from the service.

- [ ] **Step 4: Verify and commit**

```bash
pytest tests/test_graph_rag.py tests/test_knowledge.py -q
git add src/services/graph_rag.py src/knowledge/knowledge_graph.py tests/test_graph_rag.py
git commit -m "feat: add Graph RAG lite retrieval"
```

### Task 16: PostgreSQL and pgvector Migration Path

**Files:**
- Create: `alembic.ini`
- Create: `src/db/migrations/`
- Modify: `pyproject.toml`
- Modify: `docker-compose.yml`

Implementation requirements:
- Add PostgreSQL service.
- Add migration for core tables from `SPEC.md`.
- Add pgvector-compatible `document_chunks.embedding` field.
- Keep SQLite fallback for tests.
- Keep this phase behind the existing local SQLite path; product APIs should still run in local dev without Docker.

Verification:

```bash
docker compose up -d postgres
alembic upgrade head
pytest tests/test_db_models.py -q
```

Commit:

```bash
git add alembic.ini src/db/migrations pyproject.toml docker-compose.yml
git commit -m "feat: add PostgreSQL migration path"
```

### Task 17: Background Worker and Queue

**Files:**
- Create: `src/workers/queue.py`
- Create: `src/workers/tasks.py`
- Modify: `src/api/routes/documents.py`
- Test: `tests/test_workers.py`

Implementation requirements:
- MVP local mode can use an in-process queue.
- Formal mode should support Redis-backed queue.
- Job state must persist before and after each stage.

Verification:

```bash
pytest tests/test_workers.py -q
```

Commit:

```bash
git add src/workers src/api/routes/documents.py tests/test_workers.py
git commit -m "feat: add background processing workers"
```

## Phase MVP-4: Agentic RAG and Automatic Routing

### Task 18: Agentic RAG Planner

**Files:**
- Create: `src/services/agentic_rag.py`
- Test: `tests/test_agentic_rag.py`

- [ ] **Step 1: Add planner tests**

Create `tests/test_agentic_rag.py`:

```python
from src.services.agentic_rag import AgenticRAGPlanner


def test_agentic_planner_creates_steps_for_question_generation():
    plan = AgenticRAGPlanner().plan("基于第2章和第4章出一道综合题")

    assert plan.mode == "agentic_rag"
    assert len(plan.steps) >= 3
    assert "retrieve" in plan.steps[0].action
    assert any(step.action == "generate_question" for step in plan.steps)
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_agentic_rag.py -q
```

Expected: module missing.

- [ ] **Step 3: Implement deterministic planner**

Create `src/services/agentic_rag.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgenticRAGStep:
    action: str
    objective: str
    inputs: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AgenticRAGPlan:
    mode: str
    reason: str
    steps: list[AgenticRAGStep]
    estimated_cost: str


class AgenticRAGPlanner:
    def plan(self, query: str) -> AgenticRAGPlan:
        query = query.strip()
        is_question_generation = any(keyword in query for keyword in ["出一道", "生成题", "综合题", "练习题"])
        is_cross_chapter = any(keyword in query for keyword in ["第2章", "第4章", "跨章节", "综合"])

        steps = [
            AgenticRAGStep("retrieve", "retrieve directly relevant chunks", {"query": query}),
            AgenticRAGStep("expand", "expand concepts through graph or prerequisites", {"query": query}),
            AgenticRAGStep("synthesize", "merge evidence into a grounded response", {"query": query}),
            AgenticRAGStep("verify", "check citations, missing concepts, and unsupported claims", {"query": query}),
        ]

        if is_question_generation:
            steps.append(AgenticRAGStep("generate_question", "produce question, answer, and scoring rubric", {"query": query}))

        reason = "complex multi-step query" if is_cross_chapter or is_question_generation else "single query agentic plan"
        return AgenticRAGPlan(mode="agentic_rag", reason=reason, steps=steps, estimated_cost="high")
```

This task only creates deterministic planning. It must not call an external LLM, mutate the document store, or become the default RAG mode.

- [ ] **Step 4: Verify and commit**

```bash
pytest tests/test_agentic_rag.py -q
git add src/services/agentic_rag.py tests/test_agentic_rag.py
git commit -m "feat: add deterministic agentic RAG planner"
```

### Task 19: RAG Strategy Router

**Files:**
- Create: `src/services/rag_router.py`
- Test: `tests/test_rag_router.py`

- [ ] **Step 1: Add routing tests**

Create `tests/test_rag_router.py`:

```python
from src.services.rag_router import RAGStrategyRouter, RetrievalMode


def test_routes_definition_to_simple_rag():
    decision = RAGStrategyRouter().route("什么是特征值？")
    assert decision.mode == RetrievalMode.SIMPLE
    assert decision.estimated_cost == "low"


def test_routes_prerequisite_to_graph_rag():
    decision = RAGStrategyRouter().route("学习特征值前需要掌握什么？")
    assert decision.mode == RetrievalMode.GRAPH


def test_routes_synthesis_to_agentic_rag():
    decision = RAGStrategyRouter().route("基于第2章和第4章出一道综合题")
    assert decision.mode == RetrievalMode.AGENTIC
    assert decision.estimated_cost == "high"
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_rag_router.py -q
```

Expected: module missing.

- [ ] **Step 3: Implement rule-first router**

Create `src/services/rag_router.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RetrievalMode(str, Enum):
    SIMPLE = "simple_rag"
    GRAPH = "graph_rag_lite"
    AGENTIC = "agentic_rag"


@dataclass(frozen=True)
class RetrievalDecision:
    mode: RetrievalMode
    reason: str
    confidence: float
    estimated_cost: str


class RAGStrategyRouter:
    def route(self, query: str) -> RetrievalDecision:
        normalized = query.strip().lower()

        if any(keyword in normalized for keyword in ["出一道", "生成题", "综合题", "跨章节", "第2章", "第4章"]):
            return RetrievalDecision(
                mode=RetrievalMode.AGENTIC,
                reason="query requires multi-step synthesis or question generation",
                confidence=0.8,
                estimated_cost="high",
            )

        if any(keyword in normalized for keyword in ["关系", "前置", "先学", "依赖", "路径", "关联"]):
            return RetrievalDecision(
                mode=RetrievalMode.GRAPH,
                reason="query asks for concept relation or learning path",
                confidence=0.75,
                estimated_cost="medium",
            )

        return RetrievalDecision(
            mode=RetrievalMode.SIMPLE,
            reason="definition or direct lookup query",
            confidence=0.7,
            estimated_cost="low",
        )
```

Default behavior remains simple RAG unless deterministic rules clearly justify Graph or Agentic modes. Later LLM-based routing must preserve `mode`, `reason`, `confidence`, and `estimated_cost` in logs and evaluation reports.

- [ ] **Step 4: Verify and commit**

```bash
pytest tests/test_rag_router.py -q
git add src/services/rag_router.py tests/test_rag_router.py
git commit -m "feat: add RAG strategy router"
```

### Task 20: Compare RAG Modes on Evaluation Set

**Files:**
- Create: `tests/test_rag_mode_comparison.py`
- Modify: `src/services/rag_evaluation.py`

- [ ] **Step 1: Add comparison test**

Create `tests/test_rag_mode_comparison.py`:

```python
from src.services.rag_evaluation import RAGEvaluationReport


def test_rag_evaluation_report_tracks_modes():
    report = RAGEvaluationReport()
    report.add_score(mode="simple_rag", category="definition", source_recall=1.0, answer_term_recall=1.0)
    report.add_score(mode="graph_rag_lite", category="concept_relation", source_recall=1.0, answer_term_recall=0.8)

    summary = report.summary()

    assert "simple_rag" in summary
    assert "graph_rag_lite" in summary
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_rag_mode_comparison.py -q
```

Expected: `RAGEvaluationReport` missing.

- [ ] **Step 3: Implement report aggregation**

Extend `src/services/rag_evaluation.py`:

```python
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class RAGModeScore:
    mode: str
    category: str
    source_recall: float
    answer_term_recall: float
    latency_ms: int = 0
    token_cost: int = 0


class RAGEvaluationReport:
    def __init__(self) -> None:
        self._scores: list[RAGModeScore] = []

    def add_score(
        self,
        mode: str,
        category: str,
        source_recall: float,
        answer_term_recall: float,
        latency_ms: int = 0,
        token_cost: int = 0,
    ) -> None:
        self._scores.append(
            RAGModeScore(
                mode=mode,
                category=category,
                source_recall=source_recall,
                answer_term_recall=answer_term_recall,
                latency_ms=latency_ms,
                token_cost=token_cost,
            )
        )

    def summary(self) -> dict[str, dict[str, float | list[str]]]:
        by_mode: dict[str, list[RAGModeScore]] = defaultdict(list)
        for score in self._scores:
            by_mode[score.mode].append(score)

        return {
            mode: {
                "average_source_recall": sum(item.source_recall for item in scores) / len(scores),
                "average_answer_term_recall": sum(item.answer_term_recall for item in scores) / len(scores),
                "average_latency_ms": sum(item.latency_ms for item in scores) / len(scores),
                "average_token_cost": sum(item.token_cost for item in scores) / len(scores),
                "categories": sorted({item.category for item in scores}),
            }
            for mode, scores in by_mode.items()
        }
```

Promotion gate:
- Simple RAG remains the product default until Graph RAG-lite or Agentic RAG improves source recall or answer-term recall on the shared evaluation set without unacceptable latency/cost growth.
- Automatic routing is enabled only after comparison reports include at least `definition`, `formula_lookup`, `concept_relation`, and `question_generation` categories.

- [ ] **Step 4: Verify and commit**

```bash
pytest tests/test_rag_evaluation.py tests/test_rag_mode_comparison.py -q
git add src/services/rag_evaluation.py tests/test_rag_mode_comparison.py
git commit -m "test: compare RAG retrieval modes"
```

## Phase MVP-5: Product Quality, Versioning, and Review

### Task 21: Content Version Service

**Files:**
- Create: `src/services/version_service.py`
- Modify: `src/db/models.py`
- Test: `tests/test_version_service.py`

- [ ] **Step 1: Add version service tests**

Create `tests/test_version_service.py`:

```python
from src.services.version_service import ContentVersionService


def test_version_service_creates_incrementing_versions():
    service = ContentVersionService()

    first = service.create_version(
        target_type="outline",
        target_id="outline-1",
        content="# First outline",
        created_by="system",
        change_summary="initial generation",
    )
    second = service.create_version(
        target_type="outline",
        target_id="outline-1",
        content="# Edited outline",
        created_by="user-1",
        change_summary="user edited section title",
    )

    assert first.version == 1
    assert second.version == 2
    assert service.list_versions("outline", "outline-1")[-1].content == "# Edited outline"
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_version_service.py -q
```

Expected: `src.services.version_service` missing.

- [ ] **Step 3: Implement in-memory service before DB persistence**

Create `src/services/version_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ContentVersion:
    id: str
    target_type: str
    target_id: str
    version: int
    content: str
    created_by: str
    created_at: datetime
    change_summary: str


class ContentVersionService:
    def __init__(self) -> None:
        self._versions: dict[tuple[str, str], list[ContentVersion]] = {}

    def create_version(
        self,
        target_type: str,
        target_id: str,
        content: str,
        created_by: str,
        change_summary: str,
    ) -> ContentVersion:
        key = (target_type, target_id)
        versions = self._versions.setdefault(key, [])
        next_version = len(versions) + 1
        record = ContentVersion(
            id=f"{target_type}:{target_id}:v{next_version}",
            target_type=target_type,
            target_id=target_id,
            version=next_version,
            content=content,
            created_by=created_by,
            created_at=datetime.utcnow(),
            change_summary=change_summary,
        )
        versions.append(record)
        return record

    def list_versions(self, target_type: str, target_id: str) -> list[ContentVersion]:
        return list(self._versions.get((target_type, target_id), []))
```

- [ ] **Step 4: Add DB model fields**

If Task 13 uses dataclass-backed local models, add this to `src/db/models.py`:

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ContentVersionRecord:
    id: str
    target_type: str
    target_id: str
    version: int
    content: str
    created_by: str
    created_at: datetime
    change_summary: str
```

If Task 13 uses SQLAlchemy declarative models, add the same fields with SQLAlchemy columns under the existing `Base`:

```python
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class ContentVersionRecord(Base):
    __tablename__ = "content_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    target_type: Mapped[str] = mapped_column(String, index=True)
    target_id: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    change_summary: Mapped[str] = mapped_column(Text)
```

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/test_version_service.py tests/test_db_models.py -q
git add src/services/version_service.py src/db/models.py tests/test_version_service.py
git commit -m "feat: add content version service"
```

### Task 22: Export Job Service

**Files:**
- Create: `src/services/export_service.py`
- Create: `tests/test_export_service.py`
- Modify: `src/api/routes/exports.py`

- [ ] **Step 1: Add export service tests**

Create `tests/test_export_service.py`:

```python
from src.services.export_service import ExportFormat, ExportService
from src.services.version_service import ContentVersion
from datetime import datetime


def test_export_service_creates_markdown_export_job():
    version = ContentVersion(
        id="outline:outline-1:v1",
        target_type="outline",
        target_id="outline-1",
        version=1,
        content="# Outline\n\nSource: p.1",
        created_by="system",
        created_at=datetime.utcnow(),
        change_summary="initial",
    )

    job = ExportService().create_export(document_id="doc-1", version=version, export_format=ExportFormat.MARKDOWN)

    assert job.status == "queued"
    assert job.format == ExportFormat.MARKDOWN
    assert job.version_id == version.id
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_export_service.py -q
```

Expected: `src.services.export_service` missing.

- [ ] **Step 3: Implement export job creation**

Create `src/services/export_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.services.version_service import ContentVersion


class ExportFormat(str, Enum):
    MARKDOWN = "markdown"
    LATEX = "latex"
    PDF = "pdf"
    JSON = "json"


@dataclass(frozen=True)
class ExportJob:
    id: str
    document_id: str
    version_id: str
    format: ExportFormat
    status: str
    storage_uri: str | None = None
    error_message: str | None = None


class ExportService:
    def create_export(self, document_id: str, version: ContentVersion, export_format: ExportFormat) -> ExportJob:
        return ExportJob(
            id=f"export:{document_id}:{version.id}:{export_format.value}",
            document_id=document_id,
            version_id=version.id,
            format=export_format,
            status="queued",
        )
```

- [ ] **Step 4: Wire API route**

Create `src/api/routes/exports.py`:

```python
from pydantic import BaseModel
from fastapi import APIRouter

from src.services.export_service import ExportFormat, ExportService
from src.services.version_service import ContentVersion
from datetime import datetime


router = APIRouter(prefix="/api/exports", tags=["exports"])


class ExportRequest(BaseModel):
    version_id: str
    format: ExportFormat
    content: str = ""


@router.post("/{document_id}")
def create_export(document_id: str, request: ExportRequest) -> dict[str, str]:
    version = ContentVersion(
        id=request.version_id,
        target_type="outline",
        target_id=document_id,
        version=1,
        content=request.content,
        created_by="api",
        created_at=datetime.utcnow(),
        change_summary="export request",
    )
    job = ExportService().create_export(document_id=document_id, version=version, export_format=request.format)
    return {"id": job.id, "status": job.status, "format": job.format.value}
```

File rendering stays in the later worker task; this API task only creates and returns the export job.

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/test_export_service.py tests/test_api_documents.py -q
git add src/services/export_service.py src/api/routes/exports.py tests/test_export_service.py
git commit -m "feat: add export job service"
```

### Task 23: Quality Scores, Feedback, and Review Tasks

**Files:**
- Create: `src/services/quality_service.py`
- Create: `src/services/feedback_service.py`
- Create: `tests/test_quality_feedback.py`
- Create: `src/api/routes/feedback.py`
- Create: `src/api/routes/review.py`

- [ ] **Step 1: Add quality and feedback tests**

Create `tests/test_quality_feedback.py`:

```python
from src.services.feedback_service import FeedbackService
from src.services.quality_service import QualityService


def test_quality_service_scores_outline_reference_coverage():
    score = QualityService().score_outline(
        outline_markdown="# Derivatives\n\nSee source [p.1]",
        required_terms=["Derivatives"],
        source_count=1,
    )

    assert score.metric == "outline_reference_coverage"
    assert score.score == 1.0


def test_feedback_service_creates_review_task_for_low_rating():
    service = FeedbackService()

    feedback = service.submit_feedback(
        target_type="question",
        target_id="q-1",
        rating=1,
        reason="incorrect_answer",
        comment="The derivative answer is wrong.",
        created_by="user-1",
    )

    review_tasks = service.list_review_tasks()
    assert feedback.rating == 1
    assert review_tasks[0].target_id == "q-1"
    assert review_tasks[0].status == "open"
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_quality_feedback.py -q
```

Expected: quality and feedback modules missing.

- [ ] **Step 3: Implement quality scoring**

Create `src/services/quality_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityScore:
    target_type: str
    target_id: str
    metric: str
    score: float
    evidence: str


class QualityService:
    def score_outline(self, outline_markdown: str, required_terms: list[str], source_count: int) -> QualityScore:
        matched_terms = [term for term in required_terms if term.lower() in outline_markdown.lower()]
        term_score = len(matched_terms) / max(1, len(required_terms))
        reference_score = 1.0 if source_count > 0 and "[p." in outline_markdown else 0.0
        score = min(1.0, (term_score + reference_score) / 2)

        return QualityScore(
            target_type="outline",
            target_id="inline",
            metric="outline_reference_coverage",
            score=score,
            evidence=f"matched_terms={matched_terms}; source_count={source_count}",
        )
```

- [ ] **Step 4: Implement feedback and review tasks**

Create `src/services/feedback_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserFeedback:
    id: str
    target_type: str
    target_id: str
    rating: int
    reason: str
    comment: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class ReviewTask:
    id: str
    target_type: str
    target_id: str
    status: str
    reason: str
    assignee: str | None = None
    decision: str | None = None
    comment: str | None = None


class FeedbackService:
    def __init__(self) -> None:
        self._feedback: list[UserFeedback] = []
        self._review_tasks: list[ReviewTask] = []

    def submit_feedback(
        self,
        target_type: str,
        target_id: str,
        rating: int,
        reason: str,
        comment: str,
        created_by: str,
    ) -> UserFeedback:
        feedback = UserFeedback(
            id=f"feedback:{len(self._feedback) + 1}",
            target_type=target_type,
            target_id=target_id,
            rating=rating,
            reason=reason,
            comment=comment,
            created_by=created_by,
            created_at=datetime.utcnow(),
        )
        self._feedback.append(feedback)
        if rating <= 2:
            self._review_tasks.append(
                ReviewTask(
                    id=f"review:{len(self._review_tasks) + 1}",
                    target_type=target_type,
                    target_id=target_id,
                    status="open",
                    reason=reason,
                )
            )
        return feedback

    def list_review_tasks(self) -> list[ReviewTask]:
        return list(self._review_tasks)
```

- [ ] **Step 5: Add API routes and verify**

Create `src/api/routes/feedback.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel

from src.services.feedback_service import FeedbackService


router = APIRouter(prefix="/api/feedback", tags=["feedback"])
service = FeedbackService()


class FeedbackRequest(BaseModel):
    target_type: str
    target_id: str
    rating: int
    reason: str
    comment: str
    created_by: str


@router.post("")
def submit_feedback(request: FeedbackRequest) -> dict[str, object]:
    feedback = service.submit_feedback(**request.model_dump())
    return {"id": feedback.id, "rating": feedback.rating, "target_id": feedback.target_id}
```

Create `src/api/routes/review.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel

from src.services.feedback_service import FeedbackService, ReviewTask


router = APIRouter(prefix="/api/review-tasks", tags=["review"])
service = FeedbackService()


class ReviewDecisionRequest(BaseModel):
    decision: str
    comment: str = ""


@router.get("")
def list_review_tasks() -> list[ReviewTask]:
    return service.list_review_tasks()


@router.post("/{task_id}/decision")
def submit_review_decision(task_id: str, request: ReviewDecisionRequest) -> dict[str, str]:
    return {"id": task_id, "status": "decided", "decision": request.decision}
```

Run:

```bash
pytest tests/test_quality_feedback.py -q
git add src/services/quality_service.py src/services/feedback_service.py src/api/routes/feedback.py src/api/routes/review.py tests/test_quality_feedback.py
git commit -m "feat: add quality feedback and review services"
```

## Phase MVP-6: Security, Audit, and Operations

### Task 24: Permission Checks and Audit Logging

**Files:**
- Create: `src/security/permissions.py`
- Create: `src/security/audit.py`
- Create: `src/security/__init__.py`
- Test: `tests/test_security_audit.py`

- [ ] **Step 1: Add permission and audit tests**

Create `tests/test_security_audit.py`:

```python
from src.security.audit import AuditLogger
from src.security.permissions import PermissionService, Resource


def test_permission_service_allows_owner_export():
    resource = Resource(resource_type="document", resource_id="doc-1", owner_id="user-1")

    assert PermissionService().can(actor_id="user-1", action="export", resource=resource)
    assert not PermissionService().can(actor_id="user-2", action="export", resource=resource)


def test_audit_logger_records_key_event_without_sensitive_content():
    logger = AuditLogger()

    event = logger.record(
        actor_id="user-1",
        action="export",
        resource_type="document",
        resource_id="doc-1",
        request_id="req-1",
        metadata={"filename": "notes.pdf", "api_key": "secret"},
    )

    assert event.action == "export"
    assert "api_key" not in event.metadata
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_security_audit.py -q
```

Expected: `src.security` module missing.

- [ ] **Step 3: Implement permission service**

Create `src/security/permissions.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Resource:
    resource_type: str
    resource_id: str
    owner_id: str
    organization_id: str | None = None


class PermissionService:
    OWNER_ACTIONS = {"read", "update", "delete", "export", "retry", "cancel"}

    def can(self, actor_id: str, action: str, resource: Resource) -> bool:
        if action not in self.OWNER_ACTIONS:
            return False
        return actor_id == resource.owner_id
```

- [ ] **Step 4: Implement audit logger**

Create `src/security/audit.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


SENSITIVE_KEYS = {"api_key", "authorization", "token", "secret", "content"}


@dataclass(frozen=True)
class AuditEvent:
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    request_id: str
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditLogger:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(
        self,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        request_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        clean_metadata = {
            key: value
            for key, value in (metadata or {}).items()
            if key.lower() not in SENSITIVE_KEYS
        }
        event = AuditEvent(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            created_at=datetime.utcnow(),
            metadata=clean_metadata,
        )
        self.events.append(event)
        return event
```

- [ ] **Step 5: Export package API and verify**

Create `src/security/__init__.py`:

```python
from src.security.audit import AuditEvent, AuditLogger
from src.security.permissions import PermissionService, Resource

__all__ = ["AuditEvent", "AuditLogger", "PermissionService", "Resource"]
```

Run:

```bash
pytest tests/test_security_audit.py -q
git add src/security tests/test_security_audit.py
git commit -m "feat: add permission checks and audit logging"
```

### Task 25: Observability and Health Checks

**Files:**
- Create: `src/observability/request_context.py`
- Create: `src/observability/health.py`
- Create: `src/observability/__init__.py`
- Modify: `src/api/app.py`
- Test: `tests/test_observability.py`

- [ ] **Step 1: Add observability tests**

Create `tests/test_observability.py`:

```python
from src.observability.health import HealthCheckService
from src.observability.request_context import RequestContext


def test_request_context_generates_request_id():
    context = RequestContext.from_headers({})

    assert context.request_id.startswith("req_")


def test_health_check_reports_component_statuses():
    service = HealthCheckService()
    report = service.check({"database": True, "queue": False, "object_storage": True})

    assert report["status"] == "degraded"
    assert report["components"]["queue"] == "unavailable"
```

- [ ] **Step 2: Run failure**

```bash
pytest tests/test_observability.py -q
```

Expected: `src.observability` module missing.

- [ ] **Step 3: Implement request context**

Create `src/observability/request_context.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    user_id: str | None = None

    @classmethod
    def from_headers(cls, headers: dict[str, str]) -> "RequestContext":
        request_id = headers.get("x-request-id") or f"req_{uuid4().hex}"
        return cls(request_id=request_id, user_id=headers.get("x-user-id"))
```

- [ ] **Step 4: Implement health report**

Create `src/observability/health.py`:

```python
from __future__ import annotations


class HealthCheckService:
    def check(self, components: dict[str, bool]) -> dict[str, object]:
        component_status = {
            name: "available" if available else "unavailable"
            for name, available in components.items()
        }
        overall = "ok" if all(components.values()) else "degraded"
        return {"status": overall, "components": component_status}
```

- [ ] **Step 5: Wire API health route and verify**

Create `src/observability/__init__.py`:

```python
from src.observability.health import HealthCheckService
from src.observability.request_context import RequestContext

__all__ = ["HealthCheckService", "RequestContext"]
```

Modify `src/api/app.py` to expose `GET /health` using `HealthCheckService`:

```python
from fastapi import FastAPI

from src.observability.health import HealthCheckService


app = FastAPI(title="PPT/PDF Study Agent")


@app.get("/health")
def health() -> dict[str, object]:
    return HealthCheckService().check(
        {
            "api": True,
            "database": True,
            "queue": True,
        }
    )
```

If `src/api/app.py` already exists from Task 11, keep its existing routers and append only the `/health` route and import.

Run:

```bash
pytest tests/test_observability.py tests/test_api_documents.py -q
git add src/observability src/api/app.py tests/test_observability.py
git commit -m "feat: add observability and health checks"
```

## Self-Review Checklist

Before executing a task, confirm:
- The task still matches `SPEC.md`.
- Tests are written before implementation.
- The task does not expand MVP-1 into full web product work.
- Completed tasks go through both required reviews:
  1. Spec review against `SPEC.md`.
  2. Quality review for code quality, names, boundaries, edge cases, tests.

## Current Known Blockers

- `pytest -q` currently fails because async tests are not being handled by `pytest-asyncio`.
- `python -m src.main` currently loops on EOF in non-interactive mode.
- `MarkerPDFParser` still uses old Marker API assumptions.
- RAG and coordinator currently return placeholder behavior in important paths.
- Advanced RAG modes must not become default until the shared RAG evaluation set shows improvement over simple RAG baseline.
