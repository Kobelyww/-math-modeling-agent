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


class AssetKind(str, Enum):
    QUESTION = "question"
    DATA = "data"
    REFERENCE = "reference"
    IMAGE = "image"
    OTHER = "other"


class AssetStatus(str, Enum):
    UPLOADED = "uploaded"
    VALIDATED = "validated"
    REJECTED = "rejected"
    DELETED = "deleted"


@dataclass
class RunOptions:
    top_k: int = 6
    max_repair_attempts: int = 2
    compile_pdf: bool = True
    allow_online_search: bool = False
    workflow_mode: str = "production"
    benchmark_id: str = ""


@dataclass
class InputAsset:
    asset_id: str
    original_name: str
    stored_path: Path
    kind: AssetKind
    status: AssetStatus
    size: int
    suffix: str
    content_type: str = ""
    created_at: str = ""
    deleted_at: str = ""
    validation_error: str = ""


@dataclass
class AssetManifest:
    asset_ids: list[str] = field(default_factory=list)
    data_files: list[Path] = field(default_factory=list)
    reference_files: list[Path] = field(default_factory=list)


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
