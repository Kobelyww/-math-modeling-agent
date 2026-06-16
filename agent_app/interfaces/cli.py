from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agent_app.domain.models import RunSpec


DATA_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".png", ".jpg", ".jpeg", ".pdf"}
REFERENCE_EXTENSIONS = {".md", ".txt", ".pdf", ".bib"}


@dataclass
class AttachmentBuffer:
    paths: list[Path] = field(default_factory=list)

    def attach(self, path: Path | str) -> None:
        resolved = Path(path)
        if resolved not in self.paths:
            self.paths.append(resolved)


def build_run_spec(question: str, attachments: AttachmentBuffer) -> RunSpec:
    data_files: list[Path] = []
    reference_files: list[Path] = []
    for path in attachments.paths:
        extension = path.suffix.lower()
        if extension in REFERENCE_EXTENSIONS:
            reference_files.append(path)
        elif extension in DATA_EXTENSIONS:
            data_files.append(path)
    return RunSpec(question=question, data_files=data_files, reference_files=reference_files)
