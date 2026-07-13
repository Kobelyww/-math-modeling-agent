"""Compatibility alias for fiction workflow orchestration."""

from __future__ import annotations

import sys

from zhihu_fiction.fiction import orchestrator as _impl

sys.modules[__name__] = _impl
