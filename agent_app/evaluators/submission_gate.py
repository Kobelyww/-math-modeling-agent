from __future__ import annotations

import json
from pathlib import Path

from agent_app.domain.contracts import SubproblemSolutionContract
from agent_app.domain.models import ArtifactRef, QualityReport
from agent_app.domain.serialization import from_json_dict
from agent_app.evaluators.staged_quality import evaluate_staged_solution_package

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


def _is_under_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _manifest_contract_display(raw_path: object, artifact_root: Path) -> str:
    try:
        path = Path(raw_path)
    except TypeError:
        return str(raw_path)
    if path.is_absolute():
        try:
            return str(path.resolve(strict=False).relative_to(artifact_root))
        except ValueError:
            return str(path)
    return str(path)


def staged_manifest_fixes(artifact_root: Path) -> list[str]:
    fixes: list[str] = []
    manifest_path = artifact_root / "staged_paper_manifest.json"
    if not manifest_path.exists():
        return fixes

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"无法读取 staged_paper_manifest.json: {exc}"]
    if not isinstance(payload, dict):
        return ["无法读取 staged_paper_manifest.json: expected object"]

    if "subproblem_contract_paths" not in payload:
        fixes.append(
            "staged_paper_manifest.json 的 subproblem_contract_paths 至少包含一个 staged 子问题合同"
        )
    else:
        contract_paths = payload["subproblem_contract_paths"]
        if not isinstance(contract_paths, list):
            fixes.append("staged_paper_manifest.json 的 subproblem_contract_paths 必须是列表")
        elif not contract_paths:
            fixes.append(
                "staged_paper_manifest.json 的 subproblem_contract_paths 至少包含一个 staged 子问题合同"
            )
        else:
            for raw_path in contract_paths:
                display_path = _manifest_contract_display(raw_path, artifact_root)
                try:
                    relative_path = Path(raw_path)
                except TypeError:
                    fixes.append(f"缺少 staged 子问题合同: {display_path}")
                    continue
                contract_path = (
                    relative_path.resolve(strict=False)
                    if relative_path.is_absolute()
                    else (artifact_root / relative_path).resolve(strict=False)
                )
                if (
                    not _is_under_root(contract_path, artifact_root)
                    or not contract_path.is_file()
                ):
                    fixes.append(f"缺少 staged 子问题合同: {display_path}")

    if payload.get("abstract_generated_after_results") is not True:
        fixes.append("摘要必须在结果章节之后生成")
    return fixes


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

        fixes.extend(staged_manifest_fixes(artifact_root.resolve(strict=False)))
        fixes.extend(_staged_solution_contract_fixes(artifact_root))

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


def _staged_solution_contract_fixes(artifact_root: Path) -> list[str]:
    fixes: list[str] = []
    subproblem_root = artifact_root / "subproblems"
    if not subproblem_root.exists():
        return fixes

    for contract_path in sorted(subproblem_root.glob("*/solution_contract.json")):
        relative_contract_path = contract_path.relative_to(artifact_root)
        try:
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            contract = from_json_dict(SubproblemSolutionContract, payload)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            fixes.append(f"无法读取子问题求解合同: {relative_contract_path} ({exc})")
            continue

        report = evaluate_staged_solution_package(contract, artifact_root)
        if not report.passed:
            detail = "；".join(report.required_fixes[:4])
            if detail:
                fixes.append(
                    f"{contract.subproblem_id} 子问题求解包未通过门禁: {detail}"
                )
            else:
                fixes.append(f"{contract.subproblem_id} 子问题求解包未通过门禁")
    return fixes
