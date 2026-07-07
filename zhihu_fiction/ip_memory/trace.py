"""File-backed Agent DAG trace records."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zhihu_fiction.ip_memory.models import utc_now_iso


@dataclass(slots=True)
class AgentTraceEvent:
    run_id: str
    node_id: str
    stage: str
    event: str
    memory_snapshot: str = "sha256:empty"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    review: dict[str, Any] = field(default_factory=dict)
    human_decision: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "node_id": self.node_id,
            "stage": self.stage,
            "event": self.event,
            "memory_snapshot": self.memory_snapshot,
            "tool_calls": list(self.tool_calls),
            "review": dict(self.review),
            "human_decision": dict(self.human_decision),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any] | "AgentTraceEvent",
    ) -> "AgentTraceEvent":
        if isinstance(data, cls):
            return data
        return cls(
            run_id=str(data.get("run_id") or ""),
            node_id=str(data.get("node_id") or ""),
            stage=str(data.get("stage") or ""),
            event=str(data.get("event") or ""),
            memory_snapshot=str(data.get("memory_snapshot") or "sha256:empty"),
            tool_calls=_dict_list(data.get("tool_calls")),
            review=_dict_value(data.get("review")),
            human_decision=_dict_value(data.get("human_decision")),
            metadata=_dict_value(data.get("metadata")),
            created_at=str(data.get("created_at") or utc_now_iso()),
        )


class AgentTraceStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def append(self, event: AgentTraceEvent) -> AgentTraceEvent:
        path = self._path_for_run(event.run_id)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def list(self, run_id: str) -> list[AgentTraceEvent]:
        path = self._path_for_run(run_id)
        if not path.exists():
            return []
        events: list[AgentTraceEvent] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(data, dict):
                    continue
                events.append(AgentTraceEvent.from_dict(data))
        return events

    def _path_for_run(self, run_id: str) -> Path:
        return self.root / f"{_safe_run_filename(run_id)}.jsonl"


def _safe_run_filename(run_id: str) -> str:
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:16]
    safe = "".join(
        char if char.isascii() and (char.isalnum() or char in {"-", "_"}) else "_"
        for char in run_id
    ).strip("_")
    if not safe:
        safe = "run"
    return f"{safe[:48]}-{digest}"


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
