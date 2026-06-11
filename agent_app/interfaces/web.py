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
