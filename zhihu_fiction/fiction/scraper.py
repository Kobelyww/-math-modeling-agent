"""Compatibility exports for Zhihu topic scraping."""

from __future__ import annotations

from zhihu_fiction.scraper import (
    fetch_question_answers,
    list_scraped_files,
    load_scraped_file,
    manual_entry,
    save_scraped_content,
    scrape_zhihu_hot,
    search_zhihu_topic,
)

__all__ = [
    "fetch_question_answers",
    "list_scraped_files",
    "load_scraped_file",
    "manual_entry",
    "save_scraped_content",
    "scrape_zhihu_hot",
    "search_zhihu_topic",
]
