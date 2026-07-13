"""Compatibility exports for fiction skill distillation."""

from __future__ import annotations

from zhihu_fiction.distiller import Distiller, distill_aggregate, distill_single

__all__ = ["Distiller", "distill_aggregate", "distill_single"]
