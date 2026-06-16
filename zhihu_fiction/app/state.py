"""Runtime-only FastAPI application state."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field


@dataclass
class AppState:
    """Mutable runtime containers attached to a FastAPI app instance."""

    run_events: dict[str, asyncio.Queue] = field(default_factory=dict)
    run_progress: dict[str, dict] = field(default_factory=dict)
    video_events: dict[str, asyncio.Queue] = field(default_factory=dict)
    video_progress: dict[str, dict] = field(default_factory=dict)
    video_specs: dict[str, dict] = field(default_factory=dict)
    video_retry_jobs: dict[str, dict] = field(default_factory=dict)
    video_deepagent_specs: dict[str, dict] = field(default_factory=dict)
    video_deepagent_stage_tasks: dict[str, asyncio.Task] = field(default_factory=dict)
    video_lock: threading.Lock = field(default_factory=threading.Lock)
    video_deepagent_lock: threading.Lock = field(default_factory=threading.Lock)
    active_lock: threading.Lock = field(default_factory=threading.Lock)
    active_run_id: str | None = None
