"""Compatibility alias for fiction production pipelines."""

from __future__ import annotations

import sys

from zhihu_fiction.fiction import pipeline as _impl
from zhihu_fiction.fiction.pipeline import (
    APP_ROOT,
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
    "APP_ROOT",
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

sys.modules[__name__] = _impl
