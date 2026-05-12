from __future__ import annotations

import re
import time
from abc import ABC
from typing import Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

_RETRYABLE_PATTERNS = [
    re.compile(r"rate.?limit", re.I),
    re.compile(r"too many requests", re.I),
    re.compile(r"429"),
    re.compile(r"5\d\d"),
    re.compile(r"server error", re.I),
    re.compile(r"timeout", re.I),
    re.compile(r"connection", re.I),
    re.compile(r"network", re.I),
    re.compile(r"temporary", re.I),
    re.compile(r"unavailable", re.I),
    re.compile(r"overloaded", re.I),
]

_NON_RETRYABLE_PATTERNS = [
    re.compile(r"401"),
    re.compile(r"403"),
    re.compile(r"unauthorized", re.I),
    re.compile(r"forbidden", re.I),
    re.compile(r"invalid api key", re.I),
    re.compile(r"authentication", re.I),
    re.compile(r"400"),
    re.compile(r"invalid request", re.I),
    re.compile(r"model not found", re.I),
    re.compile(r"context length", re.I),
    re.compile(r"maximum context", re.I),
    re.compile(r"token limit", re.I),
]


def _is_retryable(error: Exception) -> bool:
    msg = str(error)
    for pattern in _NON_RETRYABLE_PATTERNS:
        if pattern.search(msg):
            return False
    for pattern in _RETRYABLE_PATTERNS:
        if pattern.search(msg):
            return True
    return True


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
                if not _is_retryable(exc):
                    raise RuntimeError(
                        f"Agent [{self.role}] non-retryable error: {exc}"
                    ) from exc
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (2 ** attempt)
                    print(f"[{self.role}] 重试 {attempt + 1}/{self.max_retries}（{wait:.0f}s 后）: {exc}")
                    time.sleep(wait)
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
                if not _is_retryable(exc):
                    raise RuntimeError(
                        f"Agent [{self.role}] non-retryable error: {exc}"
                    ) from exc
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (2 ** attempt)
                    print(f"[{self.role}] 重试 {attempt + 1}/{self.max_retries}（{wait:.0f}s 后）...")
                    time.sleep(wait)
        raise RuntimeError(
            f"Agent [{self.role}] failed after {self.max_retries} attempts: {last_error}"
        )