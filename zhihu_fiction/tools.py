"""Compatibility alias for fiction LangChain tools."""

from __future__ import annotations

import sys

from zhihu_fiction.fiction import tools as _impl

sys.modules[__name__] = _impl
