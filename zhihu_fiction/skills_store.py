"""Compatibility alias for fiction skill-card storage."""

from __future__ import annotations

import sys

from zhihu_fiction.fiction import skills_store as _impl

sys.modules[__name__] = _impl
