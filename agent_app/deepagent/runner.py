from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agent_app.config import APP_ROOT, Settings
from agent_app.domain.models import ArtifactRef, RunResult, RunSpec, RunStatus
from agent_app.llm import create_llm
from agent_app.services.run_store import RunStore


CoordinatorFactory = Callable[..., Any]


class CompetitionPaperRunner:
    def __init__(
        self,
        output_root: Path | str | None = None,
        settings: Settings | None = None,
        coordinator_factory: CoordinatorFactory | None = None,
    ) -> None:
        self.settings = settings
        self.output_root = Path(output_root) if output_root is not None else APP_ROOT / "outputs" / "runs"
        self.run_store = RunStore(self.output_root)
        self.coordinator_factory = coordinator_factory

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        output_root: Path | str | None = None,
        coordinator_factory: CoordinatorFactory | None = None,
    ) -> "CompetitionPaperRunner":
        return cls(output_root=output_root, settings=settings, coordinator_factory=coordinator_factory)

    def run(self, spec: RunSpec) -> RunResult:
        state = self.run_store.create_run(spec)
        run_dir = self.run_store.run_dir(state.run_id)
        state.status = RunStatus.RUNNING
        self.run_store.save_state(state)

        try:
            coordinator = self._create_coordinator()
            response = coordinator.invoke(
                {
                    "run_id": state.run_id,
                    "run_dir": str(run_dir),
                    "question": spec.question,
                    "data_files": [str(path) for path in spec.data_files],
                    "reference_files": [str(path) for path in spec.reference_files],
                }
            )
            state.status = RunStatus.COMPLETED
            summary = self._summarize_response(response)
        except Exception as exc:
            state.status = RunStatus.FAILED
            summary = str(exc)

        state.artifacts = self._collect_artifacts(run_dir)
        self.run_store.save_state(state)
        return RunResult(
            run_id=state.run_id,
            status=state.status,
            stage=state.stage,
            artifacts=state.artifacts,
            quality_reports=state.quality_reports,
            summary=summary,
        )

    def _create_coordinator(self) -> Any:
        if self.coordinator_factory is not None:
            return self.coordinator_factory(run_store=self.run_store, settings=self.settings)
        if self.settings is None:
            raise RuntimeError("CompetitionPaperRunner requires settings when no coordinator_factory is provided")

        from agent_app.deepagent.coordinator import create_competition_paper_agent

        llm = create_llm(self.settings)
        return create_competition_paper_agent(llm=llm, run_store=self.run_store)

    def _collect_artifacts(self, run_dir: Path) -> list[ArtifactRef]:
        return [
            ArtifactRef(
                name=path.name,
                path=path.relative_to(run_dir),
                kind=path.suffix.lower().lstrip("."),
            )
            for path in sorted(run_dir.iterdir())
            if path.is_file()
        ]

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
