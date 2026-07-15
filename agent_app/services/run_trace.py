from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


REDACTED = "[REDACTED]"
SECRET_KEY_EXACT = {"apikey", "authorization"}
SECRET_KEY_PATTERNS = {"api_key", "token", "secret", "password", "private_key", "cookie"}
SECRET_TEXT_PATTERN = re.compile(r"\b(?:sk-[^\s\"']+|Bearer\s+[^\s\"']+)")


class RunTraceWriter:
    def __init__(self, run_dir: Path | str) -> None:
        self.run_dir = Path(run_dir)
        self.trace_dir = self.run_dir / "trace"

    def write_json(self, relative_path: str, payload: Any) -> Path:
        path = self._trace_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._redact(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def write_text(self, relative_path: str, content: str) -> Path:
        path = self._trace_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._redact_text(content), encoding="utf-8")
        return path

    def append_event(self, stage: str, payload: Any) -> Path:
        path = self._trace_path("stage_events.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "created_at": self._now(),
            "stage": stage,
            "payload": self._redact(payload),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return path

    def write_prompt(
        self,
        stage: str,
        role: str,
        model: str,
        messages: Any,
        output_schema: Any | None = None,
    ) -> Path:
        payload = {
            "stage": stage,
            "role": role,
            "model": model,
            "messages": messages,
        }
        if output_schema is not None:
            payload["output_schema"] = output_schema
        return self.write_json(f"prompts/{self._safe_name(stage)}.json", payload)

    def write_llm_output(self, stage: str, content: str) -> Path:
        suffix = "json" if content.lstrip().startswith("{") else "md"
        return self.write_text(f"llm_outputs/{self._safe_name(stage)}.{suffix}", content)

    def write_gate_report(self, gate_name: str, report: Any) -> Path:
        return self.write_json(f"gate_reports/{self._safe_name(gate_name)}.json", report)

    def _trace_path(self, relative_path: str) -> Path:
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("trace path must be relative and stay under trace/")
        candidate = self.trace_dir / path
        candidate.parent.mkdir(parents=True, exist_ok=True)
        trace_root = self.trace_dir.resolve()
        resolved_parent = candidate.parent.resolve()
        if resolved_parent != trace_root and trace_root not in resolved_parent.parents:
            raise ValueError("trace path must stay under trace/")
        if candidate.exists() and candidate.is_symlink():
            raise ValueError("trace path must not be a symlink")
        return candidate

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: REDACTED if self._is_secret_key(str(key)) else self._redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        if isinstance(value, tuple):
            return [self._redact(item) for item in value]
        if isinstance(value, str):
            return self._redact_text(value)
        return value

    @staticmethod
    def _redact_text(content: str) -> str:
        return SECRET_TEXT_PATTERN.sub(REDACTED, content)

    @staticmethod
    def _is_secret_key(key: str) -> bool:
        normalized = key.lower().replace("-", "_")
        return normalized in SECRET_KEY_EXACT or any(pattern in normalized for pattern in SECRET_KEY_PATTERNS)

    @staticmethod
    def _safe_name(name: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in name)
        return safe or "unnamed"

    @staticmethod
    def _now() -> str:
        return datetime.now().replace(microsecond=0).isoformat()
