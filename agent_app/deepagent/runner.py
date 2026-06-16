from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agent_app.config import APP_ROOT, Settings
from agent_app.domain.models import ArtifactRef, RunResult, RunSpec, RunStatus
from agent_app.llm import create_llm
from agent_app.services.run_store import RunStore


CoordinatorFactory = Callable[..., Any]
ARTIFACT_KIND_BY_EXTENSION = {
    ".md": "markdown",
    ".py": "python",
    ".tex": "latex",
    ".json": "json",
}


class CompetitionPaperRunner:
    def __init__(
        self,
        output_root: Path | str | None = None,
        settings: Settings | None = None,
        coordinator_factory: CoordinatorFactory | None = None,
        event_handler: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.settings = settings
        self.output_root = Path(output_root) if output_root is not None else APP_ROOT / "output" / "runs"
        self.run_store = RunStore(self.output_root)
        self.coordinator_factory = coordinator_factory
        self.event_handler = event_handler

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        output_root: Path | str | None = None,
        coordinator_factory: CoordinatorFactory | None = None,
        event_handler: Callable[[dict[str, Any]], None] | None = None,
    ) -> "CompetitionPaperRunner":
        return cls(
            output_root=output_root,
            settings=settings,
            coordinator_factory=coordinator_factory,
            event_handler=event_handler,
        )

    def run(self, spec: RunSpec) -> RunResult:
        state = self.run_store.create_run(spec)
        run_dir = self.run_store.run_dir(state.run_id)
        state.status = RunStatus.RUNNING
        self.run_store.save_state(state)

        try:
            coordinator = self._create_coordinator()
            response = coordinator.invoke(self._build_coordinator_payload(state.run_id, run_dir, spec))
            state = self.run_store.load_state(state.run_id)
            state.status = RunStatus.COMPLETED
            summary = self._summarize_response(response)
        except Exception as exc:
            state = self._load_latest_state(state)
            state.status = RunStatus.FAILED
            summary = str(exc)

        state.artifacts = self._collect_artifacts(run_dir)
        if state.status == RunStatus.COMPLETED and not self._has_core_submission_artifacts(state.artifacts):
            state.status = RunStatus.PARTIAL
        self.run_store.save_state(state)
        return RunResult(
            run_id=state.run_id,
            status=state.status,
            stage=state.stage,
            artifacts=state.artifacts,
            quality_reports=state.quality_reports,
            summary=summary,
        )

    def _build_coordinator_payload(self, run_id: str, run_dir: Path, spec: RunSpec) -> dict[str, Any]:
        data_files = [str(path) for path in spec.data_files]
        reference_files = [str(path) for path in spec.reference_files]
        question = self._build_user_instruction(run_id, run_dir, spec, data_files, reference_files)
        return {
            "messages": [{"role": "user", "content": question}],
            "run_id": run_id,
            "run_dir": str(run_dir),
            "question": question,
            "data_files": data_files,
            "reference_files": reference_files,
        }

    def _build_user_instruction(
        self,
        run_id: str,
        run_dir: Path,
        spec: RunSpec,
        data_files: list[str],
        reference_files: list[str],
    ) -> str:
        data_block = "\n".join(f"- {path}" for path in data_files) or "- 无"
        reference_block = "\n".join(f"- {path}" for path in reference_files) or "- 无"
        return (
            "请严格执行数学建模竞赛论文生产工作流，并使用工具完成每个阶段，不要只给聊天式建议。\n\n"
            f"run_id: {run_id}\n"
            f"run_dir: {run_dir}\n\n"
            "## 用户赛题 / 研究任务\n"
            f"{spec.question}\n\n"
            "## 数据文件\n"
            f"{data_block}\n\n"
            "## 参考文件\n"
            f"{reference_block}\n\n"
            "## 必须按顺序调用的工具\n"
            "1. ingest_inputs\n"
            "2. analyze_problem\n"
            "3. audit_data\n"
            "4. retrieve_evidence\n"
            "5. plan_model\n"
            "6. run_experiment\n"
            "7. draft_competition_paper\n"
            "8. review_submission\n"
            "9. package_submission\n\n"
            "每个工具调用都必须传入上面的 run_id。最终只总结 run 目录中真实存在的产物。"
        )

    def _create_coordinator(self) -> Any:
        if self.coordinator_factory is not None:
            return self.coordinator_factory(
                run_store=self.run_store,
                settings=self.settings,
                event_handler=self.event_handler,
            )
        if self.settings is None:
            raise RuntimeError("CompetitionPaperRunner requires settings when no coordinator_factory is provided")

        from agent_app.deepagent.coordinator import create_competition_paper_agent

        llm = create_llm(self.settings)
        return create_competition_paper_agent(
            llm=llm,
            run_store=self.run_store,
            event_handler=self.event_handler,
        )

    def _collect_artifacts(self, run_dir: Path) -> list[ArtifactRef]:
        return [
            ArtifactRef(
                name=path.name,
                path=path.relative_to(run_dir),
                kind=self._artifact_kind(path),
            )
            for path in sorted(run_dir.rglob("*"))
            if path.is_file()
        ]

    def _artifact_kind(self, path: Path) -> str:
        extension = path.suffix.lower()
        return ARTIFACT_KIND_BY_EXTENSION.get(extension, extension.lstrip("."))

    def _has_core_submission_artifacts(self, artifacts: list[ArtifactRef]) -> bool:
        names = {artifact.path.name for artifact in artifacts}
        return {"modeling_report.md", "solve.py", "paper.tex"}.issubset(names)

    def _load_latest_state(self, state: Any) -> Any:
        try:
            return self.run_store.load_state(state.run_id)
        except Exception:
            return state

    def _summarize_response(self, response: Any) -> str:
        if isinstance(response, dict):
            messages = response.get("messages")
            if isinstance(messages, list) and messages:
                last_message = messages[-1]
                if isinstance(last_message, dict):
                    content = last_message.get("content")
                    if content is not None:
                        return str(content)
                content = getattr(last_message, "content", None)
                if content is not None:
                    return str(content)
        return str(response)
