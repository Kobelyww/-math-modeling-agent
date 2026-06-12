from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import RunResult


def resolve_paper_input_paths(values: list[str | Path], allowed_root: Path | str) -> list[Path]:
    root = Path(allowed_root).resolve()
    resolved_paths: list[Path] = []
    for value in values:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError(f"Paper input path is outside allowed input directory: {value}")
        resolved_paths.append(resolved)
    return resolved_paths


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
