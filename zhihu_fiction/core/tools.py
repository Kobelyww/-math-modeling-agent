"""Compatibility exports for standalone LangChain tools."""

from __future__ import annotations

from zhihu_fiction.tools import (
    TOOLS,
    current_time,
    list_scraped,
    list_skills,
    read_scraped,
    read_skill,
    save_article,
    scrape_hot,
    search_topic,
)

__all__ = [
    "TOOLS",
    "current_time",
    "list_scraped",
    "list_skills",
    "read_scraped",
    "read_skill",
    "save_article",
    "scrape_hot",
    "search_topic",
]
