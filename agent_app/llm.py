from __future__ import annotations

from langchain_deepseek import ChatDeepSeek

from .config import Settings


def create_llm(settings: Settings, temperature: float | None = None,
               max_tokens: int | None = None) -> ChatDeepSeek:
    kwargs: dict = {
        "model": settings.model,
        "temperature": temperature if temperature is not None else settings.temperature,
        "api_key": settings.api_key,
    }
    if settings.api_base:
        kwargs["api_base"] = settings.api_base
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    return ChatDeepSeek(**kwargs)