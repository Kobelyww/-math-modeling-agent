from __future__ import annotations

import re
from pathlib import Path


_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def ensure_within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"path outside run directory: {path}") from exc
    return resolved


def validate_run_id(run_id: str) -> str:
    if not _SAFE_RUN_ID.match(run_id):
        raise ValueError(f"unsafe run_id: {run_id}")
    return run_id
