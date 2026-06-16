from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_app.infra.paths import ensure_within


class ArtifactService:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir.resolve()
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, relative_path: str | Path) -> Path:
        candidate = (self.run_dir / relative_path).resolve()
        return ensure_within(candidate, self.run_dir)

    def write_text(self, relative_path: str | Path, content: str) -> Path:
        path = self.path_for(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, relative_path: str | Path, payload: dict[str, Any]) -> Path:
        return self.write_text(relative_path, json.dumps(payload, ensure_ascii=False, indent=2))

    def mkdir(self, relative_path: str | Path) -> Path:
        path = self.path_for(relative_path)
        path.mkdir(parents=True, exist_ok=True)
        return path
