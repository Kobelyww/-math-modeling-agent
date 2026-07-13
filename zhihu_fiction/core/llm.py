"""LLM construction for Zhihu Fiction."""

from __future__ import annotations

from langchain_deepseek import ChatDeepSeek

from zhihu_fiction.core.config import Settings


def create_llm(settings: Settings, temperature: float | None = None) -> ChatDeepSeek:
    if not settings.api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")
    kwargs: dict = {
        "model": settings.model,
        "temperature": temperature if temperature is not None else settings.temperature,
        "api_key": settings.api_key,
    }
    if settings.api_base:
        kwargs["api_base"] = settings.api_base

    return ChatDeepSeek(**kwargs)

__all__ = ["create_llm"]
