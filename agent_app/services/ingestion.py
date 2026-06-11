from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from agent_app.domain.models import RunSpec
from agent_app.services.artifact_service import ArtifactService


class InputIngestionService:
    def __init__(self, artifacts: ArtifactService) -> None:
        self.artifacts = artifacts

    def ingest(self, spec: RunSpec) -> dict[str, Any]:
        self.artifacts.write_text("question.md", spec.question.strip() + "\n")
        data_entries = [self._copy_input(path, "inputs/data") for path in spec.data_files]
        reference_entries = [self._copy_input(path, "inputs/references") for path in spec.reference_files]
        manifest = {
            "question_file": "question.md",
            "data_files": data_entries,
            "reference_files": reference_entries,
            "output_profile": spec.output_profile,
            "options": {
                "top_k": spec.options.top_k,
                "max_repair_attempts": spec.options.max_repair_attempts,
                "compile_pdf": spec.options.compile_pdf,
                "allow_online_search": spec.options.allow_online_search,
            },
        }
        self.artifacts.write_json("inputs_manifest.json", manifest)
        return manifest

    def _copy_input(self, source: Path, target_dir: str) -> dict[str, Any]:
        source = Path(source).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(str(source))
        target = self.artifacts.path_for(Path(target_dir) / source.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        rel = target.relative_to(self.artifacts.run_dir)
        return {
            "name": source.name,
            "path": str(rel),
            "size": target.stat().st_size,
            "suffix": source.suffix.lower(),
        }
