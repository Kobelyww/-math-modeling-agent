"""Compatibility exports for fiction workflow orchestration."""

from __future__ import annotations

from zhihu_fiction.orchestrator import StageResult, WorkflowResult, run_coordinator

__all__ = ["StageResult", "WorkflowResult", "run_coordinator"]
