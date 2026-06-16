"""Production infrastructure status helpers."""
from __future__ import annotations

import os

from ...drama.stage_assets import estimate_video_cost


def infrastructure_status(dependencies) -> dict:
    default_unit_price = float(os.getenv("ZH_VIDEO_UNIT_PRICE_CNY", "0") or "0")
    asset_backend = (os.getenv("ZH_ASSET_BACKEND") or "local").strip().lower() or "local"
    web_settings = getattr(dependencies, "web_settings", None)
    cors_origins = getattr(web_settings, "cors_origins", ["*"])
    return {
        "app_env": getattr(web_settings, "app_env", "development"),
        "auth_required": bool(getattr(web_settings, "require_auth", False)),
        "cors_mode": "wildcard" if cors_origins == ["*"] else "restricted",
        "workspace_backend": getattr(dependencies.workspace_repo, "backend", "jsonl"),
        "queue_backend": getattr(dependencies.queue_backend, "backend", "local"),
        "asset_backend": asset_backend,
        "video_job_recovery": getattr(dependencies, "video_job_recovery", {"refresh_queued": 0, "failed": 0}),
        "video_provider": os.getenv("ZH_VIDEO_PROVIDER", "bailian"),
        "creative_model": "deepseek-v4-pro",
        "video_model": os.getenv("BAILIAN_VIDEO_MODEL", "wanx2.1-t2v-turbo"),
        "cost_guardrail": {
            "shot_limit_default": 1,
            "shot_limit_max": 20,
            "billable_stage": "video",
            "estimate": estimate_video_cost(
                shot_count=1,
                seconds_per_shot=6,
                unit_price_cny=default_unit_price,
            ),
        },
    }
