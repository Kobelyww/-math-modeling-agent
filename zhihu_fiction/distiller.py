"""Compatibility exports for fiction skill distillation."""

from __future__ import annotations

from zhihu_fiction.fiction.distiller import (
    DISTILL_AGGREGATE_PROMPT,
    DISTILL_SINGLE_PROMPT,
    LEARN_FROM_STORY_PROMPT,
    MERGE_SKILL_PROMPT,
    SKILLS_DIR,
    Distiller,
    distill_aggregate,
    distill_single,
)

__all__ = [
    "DISTILL_AGGREGATE_PROMPT",
    "DISTILL_SINGLE_PROMPT",
    "Distiller",
    "LEARN_FROM_STORY_PROMPT",
    "MERGE_SKILL_PROMPT",
    "SKILLS_DIR",
    "distill_aggregate",
    "distill_single",
]
