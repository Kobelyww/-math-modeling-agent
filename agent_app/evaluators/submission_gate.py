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
    artifact_names = {artifact.path.name for artifact in artifacts}
    missing = sorted(REQUIRED_FILES - artifact_names)
    fixes = [f"缺少交付物: {name}" for name in missing]
    passed = not missing

    return QualityReport(
        gate_name="submission",
        passed=passed,
        score=1.0 if passed else max(0.0, 1.0 - len(missing) / len(REQUIRED_FILES)),
        required_fixes=fixes,
    )
