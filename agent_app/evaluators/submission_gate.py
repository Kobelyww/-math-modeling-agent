from __future__ import annotations

from pathlib import Path

from agent_app.domain.models import ArtifactRef, QualityReport

REQUIRED_FILES = {
    "modeling_report.md",
    "solve.py",
    "paper.tex",
    "review_report.md",
    "final_synthesis.md",
    "run.json",
}

B_PROBLEM_RESULT_FILES = {
    "results/q1_sampling_plan.csv",
    "results/q2_table1_decisions.csv",
    "results/q3_table2_tree_decisions.csv",
    "results/q4_uncertainty_re_solve.csv",
    "results/parameter_audit.json",
    "results/model_equations.md",
}


PLACEHOLDER_PHRASES = {
    "DeepAgent generated model",
    "DeepAgent competition experiment placeholder",
    "Competition Paper Draft",
    "This draft summarizes the local modeling workflow",
}


def _read_artifact_text(artifact: ArtifactRef, artifact_root: Path) -> str:
    path = artifact.path
    if not path.is_absolute():
        path = artifact_root / path
    return path.read_text(encoding="utf-8")


def evaluate_submission(
    artifacts: list[ArtifactRef],
    artifact_root: Path | None = None,
    require_benchmark_results: bool = False,
) -> QualityReport:
    artifact_names = {artifact.path.name for artifact in artifacts}
    missing = sorted(REQUIRED_FILES - artifact_names)
    fixes = [f"缺少交付物: {name}" for name in missing]
    findings: list[str] = []

    if artifact_root is not None:
        artifact_by_name = {artifact.path.name: artifact for artifact in artifacts}
        if require_benchmark_results:
            for relative_path in sorted(B_PROBLEM_RESULT_FILES):
                if not (artifact_root / relative_path).exists():
                    fixes.append(f"缺少 B 题子问题求解结果: {relative_path}")
        for name in ("modeling_report.md", "solve.py", "paper.tex"):
            artifact = artifact_by_name.get(name)
            if artifact is None:
                continue
            try:
                text = _read_artifact_text(artifact, artifact_root)
            except (OSError, UnicodeDecodeError) as exc:
                fixes.append(f"无法读取交付物: {name} ({exc})")
                continue
            matched = sorted(phrase for phrase in PLACEHOLDER_PHRASES if phrase in text)
            if matched:
                findings.append(f"{name} still contains placeholder content: {', '.join(matched)}")
                fixes.append(f"{name} 仍包含占位内容，需要基于题目数据重写")
            if name == "modeling_report.md" and len(text.strip()) < 800:
                fixes.append("modeling_report.md 内容过短，需要包含模型、变量、实验和结论映射")
            if name == "solve.py":
                if require_benchmark_results and ("def main" not in text or "expected_profit" not in text):
                    fixes.append("solve.py 缺少可复现实验主函数或关键结果计算")
                if not require_benchmark_results and (
                    "def main" not in text or ("subproblem_id" not in text and "expected_profit" not in text)
                ):
                    fixes.append("solve.py 缺少动态子问题 baseline 计算")
            if name == "paper.tex" and "\\section" not in text:
                fixes.append("paper.tex 缺少论文分节内容")

    passed = not missing
    if fixes:
        passed = False

    return QualityReport(
        gate_name="submission",
        passed=passed,
        score=1.0 if passed else max(0.0, 1.0 - len(fixes) / (len(REQUIRED_FILES) + 3)),
        findings=findings,
        required_fixes=fixes,
    )
