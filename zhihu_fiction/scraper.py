"""Compatibility alias for Zhihu topic scraping."""

from __future__ import annotations

import sys

from zhihu_fiction.fiction import scraper as _impl

sys.modules[__name__] = _impl
