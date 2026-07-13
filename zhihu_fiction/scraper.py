"""Compatibility exports for Zhihu topic scraping."""

from __future__ import annotations

from zhihu_fiction.fiction.scraper import (
    CACHE_DIR,
    CACHE_TTL,
    REQUEST_DELAY,
    SCRAPED_DIR,
    SESSION,
    ZHIHU_API_BASE,
    fetch_question_answers,
    list_scraped_files,
    load_scraped_file,
    manual_entry,
    save_scraped_content,
    scrape_zhihu_hot,
    search_zhihu_topic,
)

__all__ = [
    "CACHE_DIR",
    "CACHE_TTL",
    "REQUEST_DELAY",
    "SCRAPED_DIR",
    "SESSION",
    "ZHIHU_API_BASE",
    "fetch_question_answers",
    "list_scraped_files",
    "load_scraped_file",
    "manual_entry",
    "save_scraped_content",
    "scrape_zhihu_hot",
    "search_zhihu_topic",
]
