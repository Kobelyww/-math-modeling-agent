from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import QualityReport


def evaluate_input(question: str, manifest_path: Path) -> QualityReport:
    fixes: list[str] = []

    if not question.strip():
        fixes.append("赛题文本不能为空")
    if not manifest_path.exists():
        fixes.append(f"缺少输入清单: {manifest_path.name}")

    passed = not fixes
    return QualityReport(
        gate_name="input",
        passed=passed,
        score=1.0 if passed else 0.0,
        required_fixes=fixes,
    )
