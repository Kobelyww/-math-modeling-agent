from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any


class DeepSeekGenerationService:
    """Small typed wrapper around an injected LangChain-compatible chat model."""

    def __init__(self, chat_model: Any) -> None:
        self.chat_model = chat_model

    def generate_json(self, role: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        content = _strip_fenced_code(self._invoke_content(messages))
        try:
            parsed = json.loads(content)
        except JSONDecodeError as exc:
            raise ValueError(f"{role} response is not valid JSON: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{role} response JSON must be an object")
        return parsed

    def generate_markdown(self, role: str, messages: list[dict[str, str]]) -> str:
        return self._invoke_content(messages).strip()

    def _invoke_content(self, messages: list[dict[str, str]]) -> str:
        copied_messages = [dict(message) for message in messages]
        result = self.chat_model.invoke(copied_messages)
        content = getattr(result, "content", result)
        if content is None:
            return ""
        return str(content)


def _strip_fenced_code(content: str) -> str:
    text = content.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if not lines or not lines[0].strip().startswith("```"):
        return text
    if len(lines) > 1 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return "\n".join(lines[1:]).strip()
