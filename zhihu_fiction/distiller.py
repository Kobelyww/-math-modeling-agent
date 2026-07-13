"""Compatibility alias for fiction skill distillation."""

from __future__ import annotations

import sys

from zhihu_fiction.fiction import distiller as _impl

sys.modules[__name__] = _impl
