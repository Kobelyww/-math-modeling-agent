from __future__ import annotations

import logging
import re
import time
from abc import ABC
from typing import Any, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


def normalize_llm_content(content: Any) -> str:
    """规范化 LLM 响应内容为纯字符串（供所有模块复用）。"""
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


def extract_token_usage(response: Any) -> dict[str, int]:
    """从 LangChain LLM 响应中提取实际 token 消耗。

    兼容 DeepSeek（response_metadata.token_usage）和 OpenAI 格式（usage_metadata）。
    返回 {"prompt_tokens": int, "completion_tokens": int}。
    """
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    if not response:
        return usage

    # LangChain >= 0.3: usage_metadata
    meta = getattr(response, "usage_metadata", None) or {}
    if isinstance(meta, dict):
        usage["prompt_tokens"] = int(meta.get("input_tokens", 0))
        usage["completion_tokens"] = int(meta.get("output_tokens", 0))

    # DeepSeek via LangChain: response_metadata.token_usage
    resp_meta = getattr(response, "response_metadata", None) or {}
    if isinstance(resp_meta, dict):
        token_usage = resp_meta.get("token_usage", {})
        if isinstance(token_usage, dict):
            if not usage["prompt_tokens"]:
                usage["prompt_tokens"] = int(token_usage.get("prompt_tokens", 0))
            if not usage["completion_tokens"]:
                usage["completion_tokens"] = int(token_usage.get("completion_tokens", 0))

    return usage


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
        self._last_usage: dict[str, int] = {}

    @property
    def last_usage(self) -> dict[str, int]:
        """最近一次 LLM 调用的 token 消耗。"""
        return self._last_usage

    def invoke(self, user_prompt: str) -> str:
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt),
        ]
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self.llm.invoke(messages)
                self._last_usage = extract_token_usage(response)
                return normalize_llm_content(response.content)
            except Exception as exc:
                last_error = exc
                if not _is_retryable(exc):
                    raise RuntimeError(
                        f"Agent [{self.role}] non-retryable error: {exc}"
                    ) from exc
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (2 ** attempt)
                    logger.warning("[%s] 重试 %d/%d（%ds 后）: %s", self.role, attempt + 1, self.max_retries, int(wait), exc)
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
        last_response = None
        for attempt in range(self.max_retries):
            try:
                for chunk in self.llm.stream(messages):
                    last_response = chunk
                    token = normalize_llm_content(chunk.content)
                    if not token:
                        continue
                    parts.append(token)
                    if on_token:
                        on_token(token)
                self._last_usage = extract_token_usage(last_response)
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
                    logger.warning("[%s] 重试 %d/%d（%ds 后）...", self.role, attempt + 1, self.max_retries, int(wait))
                    time.sleep(wait)
        raise RuntimeError(
            f"Agent [{self.role}] failed after {self.max_retries} attempts: {last_error}"
        )
