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
        data_files, reference_files = self._validate_inputs(spec)
        self.artifacts.write_text("question.md", spec.question.strip() + "\n")
        data_entries = [self._copy_input(path, "inputs/data") for path in data_files]
        reference_entries = [self._copy_input(path, "inputs/references") for path in reference_files]
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

    def _validate_inputs(self, spec: RunSpec) -> tuple[list[Path], list[Path]]:
        data_files = self._resolve_group(spec.data_files)
        reference_files = self._resolve_group(spec.reference_files)
        self._reject_duplicate_names(data_files)
        self._reject_duplicate_names(reference_files)
        return data_files, reference_files

    def _resolve_group(self, files: list[Path]) -> list[Path]:
        resolved = []
        for source in files:
            path = Path(source).expanduser().resolve()
            if not path.exists() or not path.is_file():
                raise FileNotFoundError(str(path))
            resolved.append(path)
        return resolved

    def _reject_duplicate_names(self, files: list[Path]) -> None:
        seen = set()
        for source in files:
            if source.name in seen:
                raise ValueError(f"duplicate input filename: {source.name}")
            seen.add(source.name)

    def _copy_input(self, source: Path, target_dir: str) -> dict[str, Any]:
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
