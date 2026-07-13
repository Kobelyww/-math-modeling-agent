"""Compatibility alias for fiction agent orchestration."""

from __future__ import annotations

import sys

from zhihu_fiction.fiction import agents as _impl

sys.modules[__name__] = _impl
