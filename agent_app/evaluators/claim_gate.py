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
