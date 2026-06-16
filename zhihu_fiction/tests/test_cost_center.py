"""Tests for the cost center API."""
from __future__ import annotations

from fastapi.testclient import TestClient

from zhihu_fiction.app.dependencies import AppDependencies
from zhihu_fiction.app.factory import create_app
from zhihu_fiction.app.routes import costs as costs_route
from zhihu_fiction.workspace.models import CostLedgerEntry
from zhihu_fiction.workspace.repositories import WorkspaceRepository


_REAL_DATETIME = costs_route.datetime


class FixedDatetime:
    @classmethod
    def now(cls, tz=None):
        return _REAL_DATETIME(2026, 6, 15, tzinfo=tz)


def test_cost_center_summary_reports_budget_and_totals(tmp_path, monkeypatch):
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "20")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "1.5")
    monkeypatch.setattr(costs_route, "datetime", FixedDatetime)
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_today_estimated",
        project_id="project_1",
        release_id="release_1",
        package_id="package_1",
        run_id="run_1",
        source="project_release_confirm",
        amount_cny=4.0,
        estimated=True,
        created_at="2026-06-15T01:00:00+00:00",
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_today_actual",
        project_id="project_2",
        release_id="release_2",
        package_id="package_2",
        run_id="run_2",
        source="provider_invoice",
        amount_cny=3.25,
        estimated=False,
        created_at="2026-06-15T02:00:00+00:00",
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_yesterday",
        project_id="project_1",
        release_id="release_old",
        package_id="package_old",
        run_id="run_old",
        source="project_release_confirm",
        amount_cny=9.0,
        estimated=True,
        created_at="2026-06-14T23:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/costs/summary", params={"date": "2026-06-15"})

    assert response.status_code == 200
    assert response.json() == {
        "currency": "CNY",
        "date": "2026-06-15",
        "entry_count": 2,
        "estimated_total_cny": 4.0,
        "actual_total_cny": 3.25,
        "ledger_total_cny": 7.25,
        "covered_estimate_total_cny": 0.0,
        "covered_estimate_count": 0,
        "covered_estimates": [],
        "env_spend_cny": 1.5,
        "spent_today_cny": 8.75,
        "daily_budget_cny": 20.0,
        "remaining_today_cny": 11.25,
        "configured": True,
        "by_source": {
            "project_release_confirm": 4.0,
            "provider_invoice": 3.25,
        },
        "by_project": {
            "project_1": 4.0,
            "project_2": 3.25,
        },
    }


def test_cost_center_summary_uses_provider_actual_over_video_estimate(tmp_path, monkeypatch):
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "10")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_video_run_estimate_video_1",
        project_id="project_1",
        release_id="video_run_video_1",
        package_id="video_run_video_1",
        run_id="video_1",
        source="video_run_estimate",
        amount_cny=3.0,
        estimated=True,
        created_at="2026-06-15T01:00:00+00:00",
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_provider_bailian_task_1",
        project_id="project_1",
        release_id="provider_task_1",
        package_id="video_1:shot_1",
        run_id="video_1",
        source="provider_bailian",
        amount_cny=2.5,
        estimated=False,
        created_at="2026-06-15T02:00:00+00:00",
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_video_run_estimate_video_2",
        project_id="project_1",
        release_id="video_run_video_2",
        package_id="video_run_video_2",
        run_id="video_2",
        source="video_run_estimate",
        amount_cny=1.0,
        estimated=True,
        created_at="2026-06-15T03:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/costs/summary", params={"date": "2026-06-15"})

    assert response.status_code == 200
    data = response.json()
    assert data["entry_count"] == 3
    assert data["estimated_total_cny"] == 4.0
    assert data["actual_total_cny"] == 2.5
    assert data["ledger_total_cny"] == 3.5
    assert data["spent_today_cny"] == 3.5
    assert data["remaining_today_cny"] == 6.5
    assert data["by_source"] == {
        "provider_bailian": 2.5,
        "video_run_estimate": 1.0,
    }
    assert data["by_project"] == {"project_1": 3.5}


def test_cost_center_summary_explains_covered_video_estimates(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_video_run_estimate_video_1",
        project_id="project_1",
        release_id="video_run_video_1",
        package_id="video_run_video_1",
        run_id="video_1",
        source="video_run_estimate",
        amount_cny=3.0,
        estimated=True,
        created_at="2026-06-15T01:00:00+00:00",
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_provider_bailian_task_1",
        project_id="project_1",
        release_id="provider_task_1",
        package_id="video_1:shot_1",
        run_id="video_1",
        source="provider_bailian",
        amount_cny=2.5,
        estimated=False,
        created_at="2026-06-15T02:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/costs/summary", params={"date": "2026-06-15"})

    assert response.status_code == 200
    data = response.json()
    assert data["covered_estimate_total_cny"] == 3.0
    assert data["covered_estimate_count"] == 1
    assert data["covered_estimates"][0]["id"] == "cost_video_run_estimate_video_1"


def test_cost_center_summary_does_not_apply_today_env_spend_to_other_dates(tmp_path, monkeypatch):
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "20")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "5")
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_yesterday",
        project_id="project_1",
        release_id="release_old",
        package_id="package_old",
        run_id="run_old",
        source="project_release_confirm",
        amount_cny=9.0,
        created_at="2026-06-14T23:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/costs/summary", params={"date": "2026-06-14"})

    assert response.status_code == 200
    data = response.json()
    assert data["env_spend_cny"] == 0.0
    assert data["spent_today_cny"] == 9.0
    assert data["remaining_today_cny"] == 11.0


def test_cost_center_ledger_filters_by_project_release_and_date(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_keep",
        project_id="project_1",
        release_id="release_1",
        package_id="package_1",
        run_id="run_1",
        source="project_release_confirm",
        amount_cny=4.0,
        created_at="2026-06-15T01:00:00+00:00",
        metadata={"shot_count": 5},
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_other_project",
        project_id="project_2",
        release_id="release_2",
        package_id="package_2",
        run_id="run_2",
        source="project_release_confirm",
        amount_cny=6.0,
        created_at="2026-06-15T02:00:00+00:00",
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_other_date",
        project_id="project_1",
        release_id="release_1",
        package_id="package_old",
        run_id="run_old",
        source="project_release_confirm",
        amount_cny=8.0,
        created_at="2026-06-14T01:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get(
        "/api/costs/ledger",
        params={"project_id": "project_1", "release_id": "release_1", "date": "2026-06-15"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "entries": [{
            "id": "cost_keep",
            "project_id": "project_1",
            "release_id": "release_1",
            "package_id": "package_1",
            "run_id": "run_1",
            "source": "project_release_confirm",
            "amount_cny": 4.0,
            "currency": "CNY",
            "estimated": True,
            "created_at": "2026-06-15T01:00:00+00:00",
            "metadata": {"shot_count": 5},
        }],
    }
