"""Tests for persisted short-drama video job recovery."""
from __future__ import annotations

from zhihu_fiction.app.services.drama_video_recovery import (
    drama_video_recovery_summary,
    mark_stale_video_jobs,
    recover_video_jobs_after_restart,
)
from zhihu_fiction.workspace.models import DramaProjectSession, DramaVideoJob, DramaVideoRun
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def test_mark_stale_video_jobs_marks_running_and_queued_jobs_failed(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_job(DramaVideoJob(
        id="video_1",
        kind="generate_video",
        run_id="video_1",
        status="running",
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="retry_1",
        kind="retry_shot",
        run_id="video_1",
        status="queued",
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="done_1",
        kind="refresh_status",
        run_id="video_1",
        status="completed",
    ))

    result = mark_stale_video_jobs(repo)

    assert result == {"failed": 2}
    assert repo.get_drama_video_job("video_1").status == "failed"
    assert repo.get_drama_video_job("retry_1").status == "failed"
    assert repo.get_drama_video_job("done_1").status == "completed"
    assert "service restarted" in repo.get_drama_video_job("video_1").error


def test_recover_video_jobs_after_restart_queues_refresh_for_submitted_runs(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    jobs_path = tmp_path / "package" / "video_jobs.jsonl"
    jobs_path.parent.mkdir()
    jobs_path.write_text(
        '{"provider":"bailian","provider_job_id":"task-1","shot_id":"shot_1","status":"PENDING"}\n',
        encoding="utf-8",
    )
    repo.save_drama_video_run(DramaVideoRun(
        id="video_submitted",
        story_path="故事/小说正文.md",
        status="running",
        jobs_path=str(jobs_path),
        package_dir=str(jobs_path.parent),
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="video_submitted",
        kind="generate_video",
        run_id="video_submitted",
        status="running",
    ))

    result = recover_video_jobs_after_restart(repo)

    assert result == {"refresh_queued": 1, "failed": 0}
    refresh_jobs = [
        job for job in repo.list_drama_video_jobs("video_submitted")
        if job.kind == "refresh_status"
    ]
    assert len(refresh_jobs) == 1
    assert refresh_jobs[0].status == "queued"
    assert refresh_jobs[0].payload == {"run_id": "video_submitted", "jobs_path": str(jobs_path)}
    assert repo.get_drama_video_run("video_submitted").status == "running"


def test_recover_video_jobs_after_restart_fails_unsubmitted_memory_jobs(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_run(DramaVideoRun(
        id="video_memory_only",
        story_path="故事/小说正文.md",
        status="queued",
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="video_memory_only",
        kind="generate_video",
        run_id="video_memory_only",
        status="queued",
    ))

    result = recover_video_jobs_after_restart(repo)

    assert result == {"refresh_queued": 0, "failed": 1}
    assert repo.get_drama_video_job("video_memory_only").status == "failed"
    assert repo.get_drama_video_run("video_memory_only").status == "failed"
    assert "interrupted before provider submission" in repo.get_drama_video_job("video_memory_only").error


def test_recover_video_jobs_after_restart_fails_orphan_inflight_jobs(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_job(DramaVideoJob(
        id="legacy_video_job",
        kind="generate_video",
        run_id="legacy_video_job",
        status="running",
    ))

    result = recover_video_jobs_after_restart(repo)

    assert result == {"refresh_queued": 0, "failed": 1}
    repaired = repo.get_drama_video_job("legacy_video_job")
    assert repaired.status == "failed"
    assert "service restarted" in repaired.error


def test_recovery_summary_reports_awaiting_and_running_sessions(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_waiting",
        project_id="project_1",
        story_path="story.md",
        status="awaiting_confirmation",
        pending_stage="script",
        updated_at="2026-06-15T01:00:00+00:00",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_generating",
        project_id="project_1",
        story_path="story.md",
        status="generating",
        pending_stage="style",
        updated_at="2026-06-15T01:02:00+00:00",
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="job_running",
        kind="generate_video",
        run_id="video_1",
        status="running",
        shot_id="shot_1",
        updated_at="2026-06-15T01:01:00+00:00",
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="job_queued",
        kind="refresh_status",
        run_id="video_1",
        status="queued",
        updated_at="2026-06-15T01:04:00+00:00",
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="job_failed",
        kind="generate_video",
        run_id="video_2",
        status="failed",
        shot_id="shot_2",
        updated_at="2026-06-15T01:03:00+00:00",
    ))

    summary = drama_video_recovery_summary(repo)

    assert summary["awaiting_confirmation_sessions"][0]["id"] == "deepagent_waiting"
    assert summary["generating_sessions"][0]["id"] == "deepagent_generating"
    assert [job["id"] for job in summary["running_jobs"]] == ["job_queued", "job_running"]
    assert summary["failed_jobs"][0]["id"] == "job_failed"
    assert summary["needs_attention_count"] == 5
