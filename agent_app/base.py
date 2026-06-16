from __future__ import annotations

import logging
import re
import time
from abc import ABC
from typing import Any, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

logger = logging.getLogger(__name__)


def sanitize_str(text: str) -> str:
    """Remove lone surrogates and other unsafe chars that break UTF-8 encoding.

    Lone surrogates (U+D800–U+DFFF) are invalid in UTF-8 and will crash
    LangChain/httpx when sending to the LLM API. Call this on any string
    that came from external input before passing it to an LLM.
    """
    if not isinstance(text, str):
        return str(text)
    try:
        return text.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text.encode("utf-8", errors="replace").decode("utf-8")


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
    re.compile(r"surrogates not allowed", re.I),
    re.compile(r"utf-8.*codec can't", re.I),
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
            SystemMessage(content=sanitize_str(self.system_prompt)),
            HumanMessage(content=sanitize_str(user_prompt)),
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

    @staticmethod
    def _extract_reasoning(chunk: Any) -> str:
        """Extract reasoning/thinking content from a streaming chunk.

        DeepSeek models emit reasoning_content in additional_kwargs during
        the thinking phase. Other models may use different keys.
        """
        if chunk is None:
            return ""
        additional = getattr(chunk, "additional_kwargs", None) or {}
        return str(additional.get("reasoning_content", ""))

    def stream(
        self,
        user_prompt: str,
        on_token: Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
    ) -> str:
        messages = [
            SystemMessage(content=sanitize_str(self.system_prompt)),
            HumanMessage(content=sanitize_str(user_prompt)),
        ]
        parts: list[str] = []
        last_error: Exception | None = None
        last_response = None
        for attempt in range(self.max_retries):
            try:
                for chunk in self.llm.stream(messages):
                    last_response = chunk
                    # Yield thinking content if available (DeepSeek reasoning)
                    thinking = self._extract_reasoning(chunk)
                    if thinking and on_thinking:
                        on_thinking(thinking)
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

    # ── Tool-calling support ───────────────────────────────────────────

    def invoke_with_tools(
        self,
        user_prompt: str,
        tools: list,
        max_tool_rounds: int = 3,
    ) -> str:
        """Invoke with a tool-calling loop (ReAct-style).

        Uses deepseek-chat (V3) internally to avoid the DeepSeek V4
        reasoning_content echoing requirement that breaks multi-turn
        tool calling. The agent still benefits from the full system
        prompt and skill context.
        """
        # Use V3 for reliable multi-turn tool calling
        from langchain_deepseek import ChatDeepSeek

        parent = self.llm
        api_key = getattr(parent, "api_key", None) or getattr(parent, "openai_api_key", None)
        api_base = getattr(parent, "api_base", None) or getattr(parent, "openai_api_base", None) or ""
        kwargs: dict = {"model": "deepseek-chat", "api_key": api_key}
        if api_base:
            kwargs["api_base"] = api_base
        tool_llm = ChatDeepSeek(**kwargs).bind_tools(tools)

        messages = [
            SystemMessage(content=sanitize_str(self.system_prompt)),
            HumanMessage(content=sanitize_str(user_prompt)),
        ]

        full_output: list[str] = []
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

        for _round in range(max_tool_rounds + 1):
            response = tool_llm.invoke(messages)
            usage = extract_token_usage(response)
            total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
            total_usage["completion_tokens"] += usage.get("completion_tokens", 0)
            self._last_usage = total_usage.copy()

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                result = normalize_llm_content(response.content)
                full_output.append(result)
                return "".join(full_output)

            messages.append(response)
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                tool_id = tc.get("id", "")

                result_str = _execute_tool_safe(tool_name, tool_args)
                full_output.append(
                    f"\n[工具调用: {tool_name}({_fmt_args(tool_args)})]\n"
                )
                messages.append(ToolMessage(
                    content=str(result_str),
                    tool_call_id=tool_id,
                ))

        # Max rounds — force final answer
        final = tool_llm.invoke(messages)
        usage = extract_token_usage(final)
        total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        total_usage["completion_tokens"] += usage.get("completion_tokens", 0)
        self._last_usage = total_usage.copy()
        result = normalize_llm_content(final.content)
        full_output.append(result)
        return "".join(full_output)


# ─── Tool execution helpers ──────────────────────────────────────────────

_TOOL_EXECUTORS: dict[str, callable] = {}


def register_tool_executor(name: str, fn: callable) -> None:
    """Register a tool function for use in invoke_with_tools."""
    _TOOL_EXECUTORS[name] = fn


def _execute_tool_safe(name: str, args: dict) -> str:
    """Execute a registered tool by name, returning a safe string result."""
    fn = _TOOL_EXECUTORS.get(name)
    if fn is None:
        return f"Tool '{name}' not available"
    try:
        result = fn.invoke(args) if hasattr(fn, "invoke") else fn(**args)
        return str(result)
    except Exception as exc:
        return f"Tool error: {exc}"


def _fmt_args(args: dict) -> str:
    """Format tool args for display."""
    items = [f"{k}={repr(v)[:50]}" for k, v in (args or {}).items()]
    return ", ".join(items)
