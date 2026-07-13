"""Compatibility exports for fiction production pipelines."""

from __future__ import annotations

from zhihu_fiction.fiction.pipeline import (
    CHECKPOINT_DIR,
    RUN_DIR,
    SCHEDULE_FILE,
    MODERATE_PROMPT,
    TOPIC_SELECTOR_PROMPT,
    Pipeline,
    PublisherProtocol,
    RunResult,
    ScraperProtocol,
    StageRecord,
    TopicSelectorProtocol,
    moderate_content,
    select_topic,
)

__all__ = [
    "CHECKPOINT_DIR",
    "RUN_DIR",
    "SCHEDULE_FILE",
    "MODERATE_PROMPT",
    "TOPIC_SELECTOR_PROMPT",
    "Pipeline",
    "PublisherProtocol",
    "RunResult",
    "ScraperProtocol",
    "StageRecord",
    "TopicSelectorProtocol",
    "moderate_content",
    "select_topic",
]
