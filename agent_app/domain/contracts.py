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
