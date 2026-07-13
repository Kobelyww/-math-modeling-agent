"""Compatibility exports for fiction LangChain tools."""

from __future__ import annotations

from zhihu_fiction.fiction.tools import (
    OUTPUT_DIR,
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
    "OUTPUT_DIR",
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
