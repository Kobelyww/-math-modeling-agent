from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from agent_app.domain.models import ArtifactRef, RunSpec, RunState
from agent_app.domain.serialization import to_json_dict
from agent_app.evaluators import evaluate_submission
from agent_app.services.artifact_service import ArtifactService
from agent_app.services.data_analysis import DataAnalysisService
from agent_app.services.ingestion import InputIngestionService
from agent_app.services.problem_package import build_problem_package
from agent_app.services.run_store import RunStore


def make_competition_tools(run_store: RunStore, **services: Any) -> list:
    data_service = services.get("data_service") or DataAnalysisService()
    generation_service = services.get("generation_service")

    def _load_state(run_id: str) -> RunState:
        return run_store.load_state(run_id)

    def _artifacts_for_state(state: RunState) -> ArtifactService:
        return ArtifactService(run_store.run_dir(state.run_id))

    def _artifacts(run_id: str) -> ArtifactService:
        state = _load_state(run_id)
        return _artifacts_for_state(state)

    def _write_for_state(state: RunState, relative_path: str, content: str) -> Path:
        return _artifacts_for_state(state).write_text(relative_path, content)

    def _kind_for_path(path: Path) -> str:
        return {
            ".md": "markdown",
            ".py": "python",
            ".tex": "latex",
            ".json": "json",
        }.get(path.suffix.lower(), path.suffix.lstrip("."))

    def _read_json_artifact(state: RunState, relative_path: str) -> dict[str, Any]:
        path = run_store.run_dir(state.run_id) / relative_path
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _planner_messages(
        state: RunState,
        problem_brief: dict[str, Any],
        data_audit: dict[str, Any],
        evidence_notes: list[str],
    ) -> list[dict[str, str]]:
        context = {
            "problem_spec.json": _read_json_artifact(state, "problem_spec.json"),
            "tables.json": _read_json_artifact(state, "tables.json"),
            "figures.json": _read_json_artifact(state, "figures.json"),
            "source_map.json": _read_json_artifact(state, "source_map.json"),
            "problem_brief": problem_brief,
            "data_audit": data_audit,
            "evidence_notes": evidence_notes,
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are the mathematical modeling planner. Return a JSON model plan and "
                    "a concise modeling report that maps experiments to paper conclusions."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(context, ensure_ascii=False, indent=2),
            },
        ]

    def _programmer_messages(
        state: RunState,
        modeling_plan: dict[str, Any],
        data_files: list[str],
    ) -> list[dict[str, str]]:
        context = {
            "modeling_plan": modeling_plan,
            "problem_spec.json": _read_json_artifact(state, "problem_spec.json"),
            "tables.json": _read_json_artifact(state, "tables.json"),
            "figures.json": _read_json_artifact(state, "figures.json"),
            "data_files": data_files,
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are the experiment programmer. Return only executable Python code "
                    "that writes all results under the results directory."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(context, ensure_ascii=False, indent=2),
            },
        ]

    def _strip_fenced_code_block(content: str) -> str:
        text = content.strip()
        if not text.startswith("```"):
            return text
        lines = text.splitlines()
        if len(lines) > 1 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
        return "\n".join(lines[1:]).strip()

    def _execute_generated_code(state: RunState, code: str) -> tuple[Path, subprocess.CompletedProcess[str]]:
        artifact_service = _artifacts_for_state(state)
        code_path = artifact_service.write_text("solve.py", code)
        completed = subprocess.run(
            [sys.executable, str(code_path)],
            cwd=run_store.run_dir(state.run_id),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return code_path, completed

    def _collect_result_paths(run_dir: Path) -> list[str]:
        results_dir = run_dir / "results"
        if not results_dir.exists():
            return []
        return [
            str(path)
            for path in sorted(results_dir.rglob("*"))
            if path.is_file()
        ]

    def _review_core_artifacts(artifacts: list[str]) -> dict[str, Any]:
        required = {"modeling_report.md", "solve.py", "paper.tex"}
        names = {Path(artifact).name for artifact in artifacts}
        missing = sorted(required - names)
        return {
            "gate_name": "review",
            "passed": not missing,
            "score": 1.0 if not missing else max(0.0, 1.0 - len(missing) / len(required)),
            "findings": [] if not missing else ["Required core artifacts are incomplete."],
            "required_fixes": [f"缺少交付物: {name}" for name in missing],
        }

    @tool("ingest_inputs")
    def ingest_inputs(
        run_id: str,
        question: str,
        data_files: list[str],
        reference_files: list[str],
    ) -> dict[str, Any]:
        """Ingest question, data files, and reference files into a run workspace."""
        state = run_store.load_state(run_id)
        state.spec = RunSpec(
            question=question,
            data_files=[Path(path) for path in data_files],
            reference_files=[Path(path) for path in reference_files],
            output_profile=state.spec.output_profile,
            options=state.spec.options,
        )
        artifact_service = _artifacts_for_state(state)
        manifest = InputIngestionService(artifact_service).ingest(state.spec)
        problem_package = build_problem_package(
            artifact_service,
            question=question,
        )
        run_store.save_state(state)
        saved_paths = [
            item["path"]
            for item in [*manifest["data_files"], *manifest["reference_files"]]
        ]
        return {
            "inputs_manifest": manifest,
            "problem_package": problem_package,
            "problem_package_paths": list(problem_package.values()),
            "saved_paths": saved_paths,
            "warnings": [],
        }

    @tool("analyze_problem")
    def analyze_problem(run_id: str, question: str) -> dict[str, Any]:
        """Create a deterministic problem brief from the competition question."""
        state = _load_state(run_id)
        brief = {
            "background": question[:200],
            "questions": [question],
            "objectives": ["建立可解释、可复现实证模型"],
            "constraints": ["使用本地输入文件", "记录假设与局限"],
            "deliverables": ["modeling_report.md", "solve.py", "paper.tex"],
        }
        path = _write_for_state(
            state,
            "problem_brief.md",
            "# Problem Brief\n\n"
            f"## Background\n{brief['background']}\n\n"
            "## Objectives\n- 建立可解释、可复现实证模型\n\n"
            "## Constraints\n- 使用本地输入文件\n- 记录假设与局限\n",
        )
        return {"problem_brief": brief, "problem_brief_path": str(path)}

    @tool("audit_data")
    def audit_data(run_id: str, file_paths: list[str]) -> dict[str, Any]:
        """Audit local data files and write a markdown data report."""
        state = _load_state(run_id)
        report = data_service.audit_files([Path(path) for path in file_paths])
        path = _write_for_state(state, "data_audit.md", data_service.to_markdown(report))
        return {"data_audit": to_json_dict(report), "data_audit_path": str(path)}

    @tool("retrieve_evidence")
    def retrieve_evidence(
        run_id: str,
        query: str,
        reference_files: list[str],
        top_k: int = 6,
        allow_online_search: bool = False,
    ) -> dict[str, Any]:
        """Collect local evidence notes from reference file names only."""
        state = _load_state(run_id)
        selected = [Path(path).name for path in reference_files[:top_k]]
        lines = [
            "# Evidence Notes",
            "",
            f"Query: {query}",
            "",
        ]
        lines.extend(f"- {name}" for name in selected)
        path = _write_for_state(state, "evidence_notes.md", "\n".join(lines) + "\n")
        warnings = []
        if allow_online_search:
            warnings.append("online search is not implemented in this local tool slice")
        return {
            "evidence_notes": lines,
            "bibliography": [],
            "evidence_notes_path": str(path),
            "warnings": warnings,
        }

    @tool("plan_model")
    def plan_model(
        run_id: str,
        problem_brief: dict[str, Any],
        data_audit: dict[str, Any],
        evidence_notes: list[str],
    ) -> dict[str, Any]:
        """Draft a modeling plan artifact from problem, data, and evidence context."""
        state = _load_state(run_id)
        if generation_service is not None:
            messages = _planner_messages(state, problem_brief, data_audit, evidence_notes)
            modeling_plan = generation_service.generate_json("modeling_planner", messages)
            report_text = generation_service.generate_markdown("modeling_planner", messages)
            artifact_service = _artifacts_for_state(state)
            model_plan_path = artifact_service.write_json("model_plan.json", modeling_plan)
            report_path = artifact_service.write_text("modeling_report.md", report_text)
            return {
                "modeling_plan": modeling_plan,
                "model_plan_path": str(model_plan_path),
                "modeling_report_path": str(report_path),
            }

        modeling_plan = {
            "selected_model": "DeepAgent generated model",
            "candidate_models": ["descriptive analysis", "baseline optimization"],
            "algorithm_plan": "Audit inputs, build a transparent baseline, report assumptions.",
            "evaluation_metrics": ["reproducibility", "data coverage", "interpretability"],
        }
        path = _write_for_state(
            state,
            "modeling_report.md",
            "# Modeling Plan\n\n"
            "## Selected Model\nDeepAgent generated model\n\n"
            "## Algorithm Plan\nAudit inputs, build a transparent baseline, report assumptions.\n",
        )
        return {"modeling_plan": modeling_plan, "modeling_report_path": str(path)}

    @tool("run_experiment")
    def run_experiment(
        run_id: str,
        modeling_plan: dict[str, Any],
        data_files: list[str],
    ) -> dict[str, Any]:
        """Write a reproducible placeholder experiment script and results directory."""
        state = _load_state(run_id)
        artifact_service = _artifacts_for_state(state)
        if generation_service is not None:
            messages = _programmer_messages(state, modeling_plan, data_files)
            code = _strip_fenced_code_block(generation_service.generate_markdown("programmer", messages))
            code_path, completed = _execute_generated_code(state, code)
            debug_attempted = False
            if completed.returncode != 0:
                debug_attempted = True
                debug_messages = [
                    *messages,
                    {"role": "assistant", "content": code},
                    {
                        "role": "user",
                        "content": (
                            "The generated code failed. Return a corrected complete Python script.\n\n"
                            f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}"
                        ),
                    },
                ]
                code = _strip_fenced_code_block(
                    generation_service.generate_markdown("code_debugger", debug_messages)
                )
                code_path, completed = _execute_generated_code(state, code)

            run_dir = run_store.run_dir(run_id)
            result_paths = _collect_result_paths(run_dir)
            experiment_result = {
                "success": completed.returncode == 0,
                "execution_status": "success" if completed.returncode == 0 else "failed",
                "script_generated": True,
                "code_path": str(code_path),
                "data_files": data_files,
                "result_paths": result_paths,
                "figure_paths": [],
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "debug_attempted": debug_attempted,
                "notes": "Executed DeepSeek programmer generated experiment script.",
                "reproducibility_notes": "Run solve.py from the run directory to regenerate results.",
            }
            manifest_path = artifact_service.write_json("experiment_manifest.json", experiment_result)
            return {
                "experiment_result": experiment_result,
                "experiment_manifest_path": str(manifest_path),
                "code_path": str(code_path),
                "result_paths": result_paths,
                "figure_paths": [],
            }

        code_path = artifact_service.write_text(
            "solve.py",
            "from pathlib import Path\n\n"
            "def main():\n"
            "    print('DeepAgent competition experiment placeholder')\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n",
        )
        results_dir = artifact_service.mkdir("results")
        experiment_result = {
            "success": False,
            "execution_status": "not_run",
            "script_generated": True,
            "code_path": str(code_path),
            "data_files": data_files,
            "result_paths": [str(results_dir)],
            "figure_paths": [],
            "notes": "Experiment script generated; execution is intentionally local-only.",
            "reproducibility_notes": "Execution is deferred; the generated script has not been run.",
        }
        return {
            "experiment_result": experiment_result,
            "code_path": str(code_path),
            "result_paths": [str(results_dir)],
            "figure_paths": [],
        }

    @tool("draft_competition_paper")
    def draft_competition_paper(
        run_id: str,
        problem_brief: dict[str, Any],
        data_audit: dict[str, Any],
        modeling_plan: dict[str, Any],
        experiment_result: dict[str, Any],
        evidence_notes: list[str],
    ) -> dict[str, Any]:
        """Draft markdown and LaTeX competition paper artifacts."""
        state = _load_state(run_id)
        markdown_path = _write_for_state(
            state,
            "paper.md",
            "# Competition Paper Draft\n\n"
            "## Abstract\nThis draft summarizes the local modeling workflow.\n\n"
            "## Method\nSee modeling_report.md.\n",
        )
        latex_path = _write_for_state(
            state,
            "paper.tex",
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\section*{Competition Paper Draft}\n"
            "This draft summarizes the local modeling workflow.\n"
            "\\end{document}\n",
        )
        paper_draft = {
            "markdown_path": str(markdown_path),
            "latex_path": str(latex_path),
            "sections": {
                "abstract": "This draft summarizes the local modeling workflow.",
                "method": "See modeling_report.md.",
            },
        }
        return {
            "paper_draft": paper_draft,
            "paper_markdown_path": str(markdown_path),
            "paper_tex_path": str(latex_path),
        }

    @tool("review_submission")
    def review_submission(
        run_id: str,
        paper_draft: dict[str, Any],
        experiment_result: dict[str, Any],
        artifacts: list[str],
    ) -> dict[str, Any]:
        """Review generated artifacts and write a lightweight quality report."""
        state = _load_state(run_id)
        quality_report = _review_core_artifacts(artifacts)
        lines = ["# Review Report", ""]
        if quality_report["passed"]:
            lines.append("- Required core artifacts are present for packaging.")
        else:
            lines.extend(f"- {fix}" for fix in quality_report["required_fixes"])
        path = _write_for_state(
            state,
            "review_report.md",
            "\n".join(lines) + "\n",
        )
        return {"quality_report": quality_report, "review_report_path": str(path)}

    @tool("package_submission")
    def package_submission(run_id: str) -> dict[str, Any]:
        """Package direct run artifacts and evaluate the submission manifest."""
        state = _load_state(run_id)
        run_dir = run_store.run_dir(run_id)
        final_synthesis_path = _write_for_state(
            state,
            "final_synthesis.md",
            "# Final Synthesis\n\n"
            "Structured DeepAgent competition artifacts are ready for review.\n",
        )
        state.artifacts = [
            ArtifactRef(
                name=path.name,
                path=path.relative_to(run_dir),
                kind=_kind_for_path(path),
            )
            for path in sorted(run_dir.iterdir())
            if path.is_file()
        ]
        state.quality_reports.append(evaluate_submission(state.artifacts))
        run_store.save_state(state)
        run_json_path = run_dir / "run.json"
        package_manifest = {
            "run_id": run_id,
            "artifacts": [to_json_dict(artifact) for artifact in state.artifacts],
        }
        return {
            "package_manifest": package_manifest,
            "final_synthesis_path": str(final_synthesis_path),
            "run_json_path": str(run_json_path),
        }

    return [
        ingest_inputs,
        analyze_problem,
        audit_data,
        retrieve_evidence,
        plan_model,
        run_experiment,
        draft_competition_paper,
        review_submission,
        package_submission,
    ]
