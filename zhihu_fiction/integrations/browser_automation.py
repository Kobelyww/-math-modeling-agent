"""Compatibility exports for browser automation publishing."""

from __future__ import annotations

from zhihu_fiction.automator import Automator, AutomatorError, LoginTimeout

__all__ = ["Automator", "AutomatorError", "LoginTimeout"]
