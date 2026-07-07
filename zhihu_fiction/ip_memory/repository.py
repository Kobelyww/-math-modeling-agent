"""File-backed repository for IP memory snapshots."""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from zhihu_fiction.ip_memory.models import (
    AssetBinding,
    CharacterCard,
    Foreshadowing,
    IPMemory,
    NarrativeMemory,
    StoryBible,
    StyleGuide,
    WorldFact,
    utc_now_iso,
)


_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


class IPMemoryRepository:
    def __init__(self, root: Path):
        self.root = Path(root)

    def project_dir(self, project_id: str) -> Path:
        return self.root / self._safe_project_id(project_id)

    def memory_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "memory.json"

    def load(self, project_id: str) -> IPMemory | None:
        path = self.memory_path(project_id)
        if not path.exists():
            return None
        return IPMemory.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, memory: IPMemory, patch_note: str = "") -> IPMemory:
        project_path = self.project_dir(memory.project_id)
        versions_path = project_path / "versions"
        project_path.mkdir(parents=True, exist_ok=True)
        versions_path.mkdir(parents=True, exist_ok=True)

        memory.updated_at = utc_now_iso()
        payload = memory.to_dict()
        self._write_json_atomic(project_path / "memory.json", payload)

        version_payload = {
            "patch_note": patch_note,
            "saved_at": memory.updated_at,
            "snapshot_hash": self.snapshot_hash(memory),
            "memory": payload,
        }
        version_name = self._version_name()
        self._write_json_atomic(versions_path / version_name, version_payload)
        return memory

    def apply_patch(self, project_id: str, patch: dict[str, Any]) -> IPMemory:
        memory = self.load(project_id) or IPMemory(project_id=project_id)
        patch_data = dict(patch or {})

        if isinstance(patch_data.get("story_bible"), dict):
            memory.story_bible = _merge_model(
                memory.story_bible,
                patch_data["story_bible"],
                StoryBible,
            )
        if isinstance(patch_data.get("style_guide"), dict):
            memory.style_guide = _merge_model(
                memory.style_guide,
                patch_data["style_guide"],
                StyleGuide,
            )
        if isinstance(patch_data.get("narrative_memory"), dict):
            memory.narrative_memory = _merge_model(
                memory.narrative_memory,
                patch_data["narrative_memory"],
                NarrativeMemory,
            )

        _append_models(
            memory.characters,
            _validated_patch_list(patch_data, "characters"),
            CharacterCard,
        )
        _append_models(
            memory.world_facts,
            _validated_patch_list(patch_data, "world_facts"),
            WorldFact,
        )
        _append_models(
            memory.foreshadowing,
            _validated_patch_list(patch_data, "foreshadowing"),
            Foreshadowing,
        )
        _append_models(
            memory.asset_bindings,
            _validated_patch_list(patch_data, "asset_bindings"),
            AssetBinding,
        )

        patch_note = str(patch_data.get("patch_note", "patch"))
        return self.save(memory, patch_note=patch_note)

    def snapshot_hash(self, memory: IPMemory | None) -> str:
        if memory is None:
            return "sha256:empty"
        payload = json.dumps(
            memory.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_project_id(project_id: str) -> str:
        raw = str(project_id or "").strip()
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        prefix = _SAFE_ID_RE.sub("-", raw).strip("._-") or "default"
        max_prefix = 120 - len(digest) - 1
        prefix = prefix[:max_prefix].strip("._-") or "default"
        return f"{prefix}-{digest}"

    @staticmethod
    def _version_name() -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{stamp}-{uuid4().hex[:8]}.json"

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
        temp_path = None
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)


def _validated_patch_list(patch: dict[str, Any], key: str) -> list[dict[str, Any]] | None:
    if key not in patch:
        return None
    values = patch[key]
    if not isinstance(values, list):
        raise ValueError(f"{key} must be a list of objects")
    for index, item in enumerate(values):
        if not isinstance(item, dict):
            raise ValueError(f"{key}[{index}] must be an object")
    return values


def _append_models(
    target: list[Any],
    values: list[dict[str, Any]] | None,
    model: type[Any],
) -> None:
    if values is None:
        return
    target.extend(model.from_dict(item) for item in values)


def _merge_model(current: Any, patch: dict[str, Any], model: type[Any]) -> Any:
    payload = current.to_dict()
    payload.update(patch)
    return model.from_dict(payload)
