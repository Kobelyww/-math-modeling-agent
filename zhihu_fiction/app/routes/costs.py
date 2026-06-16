"""Cost center API routes."""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request

router = APIRouter()


@router.get("/api/costs/summary")
async def get_cost_summary(
    req: Request,
    date: str | None = Query(None),
    project_id: str | None = Query(None),
):
    repo = req.app.state.dependencies.workspace_repo
    day = _cost_day(date)
    entries = _filter_cost_entries(
        repo.list_cost_ledger_entries(project_id=project_id),
        date=day,
    )
    effective_entries = repo.list_effective_cost_ledger_entries_for_day(
        day,
        project_id=project_id,
    )
    covered_estimates = repo.list_covered_video_estimate_entries_for_day(
        day,
        project_id=project_id,
    )
    ledger_total = _money(_sum_amounts(effective_entries))
    covered_estimate_total = _money(_sum_amounts(covered_estimates))
    estimated_total = _money(sum(
        float(entry.amount_cny or 0.0)
        for entry in entries
        if entry.estimated
    ))
    actual_total = _money(sum(
        float(entry.amount_cny or 0.0)
        for entry in entries
        if not entry.estimated
    ))
    env_spend = _today_env_spend(day)
    daily_budget = _optional_float_env("ZH_DAILY_BUDGET_CNY")
    spent_today = _money(env_spend + ledger_total)
    remaining = _money(max(0.0, (daily_budget or 0.0) - spent_today)) if daily_budget is not None else 0.0

    return {
        "currency": "CNY",
        "date": day,
        "entry_count": len(entries),
        "estimated_total_cny": estimated_total,
        "actual_total_cny": actual_total,
        "ledger_total_cny": ledger_total,
        "covered_estimate_total_cny": covered_estimate_total,
        "covered_estimate_count": len(covered_estimates),
        "covered_estimates": [entry.to_dict() for entry in covered_estimates],
        "env_spend_cny": _money(env_spend),
        "spent_today_cny": spent_today,
        "daily_budget_cny": daily_budget or 0.0,
        "remaining_today_cny": remaining,
        "configured": daily_budget is not None,
        "by_source": _sum_by(effective_entries, "source"),
        "by_project": _sum_by(effective_entries, "project_id"),
    }


@router.get("/api/costs/ledger")
async def list_cost_ledger(
    req: Request,
    project_id: str | None = Query(None),
    release_id: str | None = Query(None),
    date: str | None = Query(None),
):
    repo = req.app.state.dependencies.workspace_repo
    entries = repo.list_cost_ledger_entries(project_id=project_id, release_id=release_id)
    if date:
        entries = _filter_cost_entries(entries, date=_cost_day(date))
    return {"entries": [entry.to_dict() for entry in entries]}


def _filter_cost_entries(entries: list, *, date: str) -> list:
    return [
        entry for entry in entries
        if str(entry.created_at or "")[:10] == date
    ]


def _cost_day(value: str | None) -> str:
    if value and str(value).strip():
        return str(value).strip()[:10]
    return datetime.now(timezone.utc).date().isoformat()


def _today_env_spend(day: str) -> float:
    today = datetime.now(timezone.utc).date().isoformat()
    if day != today:
        return 0.0
    return _float_env("ZH_TODAY_SPEND_CNY", 0.0)


def _sum_by(entries: list, field: str) -> dict:
    totals: dict[str, float] = defaultdict(float)
    for entry in entries:
        key = str(getattr(entry, field, "") or "unknown")
        totals[key] += float(entry.amount_cny or 0.0)
    return {
        key: _money(value)
        for key, value in sorted(totals.items())
    }


def _sum_amounts(entries: list) -> float:
    return sum(float(entry.amount_cny or 0.0) for entry in entries)


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _optional_float_env(name: str) -> float | None:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _money(value: float) -> float:
    return round(float(value or 0.0), 2)
