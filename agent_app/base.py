from __future__ import annotations

import time
from abc import ABC
from typing import Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


class BaseAgent(ABC):
    role: str = "base"
    system_prompt: str = ""

    def __init__(self, llm: BaseChatModel, max_retries: int = 3) -> None:
        self.llm = llm
        self.max_retries = max_retries
        self.retry_delay = 1.0

    @staticmethod
    def _normalize_content(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(item))
            return "".join(parts)
        return str(content)

    def invoke(self, user_prompt: str) -> str:
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt),
        ]
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self.llm.invoke(messages)
                return self._normalize_content(response.content)
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
        raise RuntimeError(
            f"Agent [{self.role}] failed after {self.max_retries} attempts: {last_error}"
        )

    def stream(
        self,
        user_prompt: str,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt),
        ]
        parts: list[str] = []
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                for chunk in self.llm.stream(messages):
                    token = self._normalize_content(chunk.content)
                    if not token:
                        continue
                    parts.append(token)
                    if on_token:
                        on_token(token)
                return "".join(parts)
            except Exception as exc:
                last_error = exc
                parts.clear()
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
        raise RuntimeError(
            f"Agent [{self.role}] failed after {self.max_retries} attempts: {last_error}"
        )