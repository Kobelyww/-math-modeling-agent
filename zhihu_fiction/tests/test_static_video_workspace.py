"""Static contract tests for the video production workspace."""
from __future__ import annotations

from pathlib import Path


STATIC_VIDEO = Path(__file__).resolve().parents[1] / "static" / "video.html"


def _html() -> str:
    return STATIC_VIDEO.read_text(encoding="utf-8")


def test_video_workspace_restores_project_query_context():
    html = _html()

    assert "new URLSearchParams(window.location.search)" in html
    assert "this.projectId = params.get('project_id') || ''" in html
    assert "this.initialStoryPath = params.get('story_path') || ''" in html
    assert "this.initialRunId = params.get('run_id') || ''" in html
    assert "await this.openInitialStoryWorkspace()" in html
    assert "openInitialStoryWorkspace()" in html


def test_video_workspace_can_restore_deepagent_session_by_run_id():
    html = _html()

    assert "restoreDeepAgentSessionByRunId(" in html
    assert "'/api/drama-video/deepagent/' + encodeURIComponent(this.initialRunId)" in html
    assert "'/api/drama-video/deepagent/' + encodeURIComponent(runId) + '/versions'" in html
    assert "applyDeepAgentSession(" in html


def test_video_workspace_run_id_restore_does_not_require_story_selection():
    html = _html()

    assert "await this.openInitialRunWorkspace(this.initialRunId)" in html
    assert "async openInitialRunWorkspace(runId)" in html
    assert "this.resetVideoWorkspaceState(null)" in html
    assert "this.restoreDeepAgentSessionByRunId(runId)" in html


def test_video_workspace_run_id_restore_reloads_project_side_panels():
    html = _html()
    section = html[
        html.index("async openInitialRunWorkspace(runId)"):
        html.index("async openInitialStoryWorkspace()")
    ]

    assert "this.resetVideoWorkspaceState(null)" in section
    assert "this.loadProjectWorkspace()" in section
    assert "this.loadCostCoverage()" in section


def test_video_workspace_run_id_restore_uses_session_project_context():
    html = _html()
    restore_section = html[
        html.index("async openInitialRunWorkspace(runId)"):
        html.index("async openInitialStoryWorkspace()")
    ]
    apply_section = html[
        html.index("applyDeepAgentSession(session"):
        html.index("async restoreDeepAgentSessionByRunId(runId)")
    ]

    assert "await this.restoreDeepAgentSessionByRunId(runId)" in restore_section
    assert restore_section.index("await this.restoreDeepAgentSessionByRunId(runId)") < restore_section.index("this.loadProjectWorkspace()")
    assert "this.projectId = session.project_id || this.projectId" in apply_section


def test_video_workspace_rebinds_story_from_restored_session_path():
    html = _html()

    assert "restoredStoryPath: ''" in html
    assert "storyForPath(path)" in html
    assert "this.restoredStoryPath = session.story_path || this.restoredStoryPath" in html
    assert "const sessionStory = this.storyForPath(session.story_path)" in html
    assert "this.selectedStory = sessionStory" in html
    assert "activeStoryPath()" in html


def test_video_workspace_versions_failure_does_not_block_session_restore():
    html = _html()

    assert "loadDeepAgentVersionsForRun(runId)" in html
    assert "this.applyDeepAgentSession(" in html
    assert "this.stageVersions = await this.loadDeepAgentVersionsForRun(this.initialRunId)" in html
    assert "this.stageVersions = []" in html
    assert "版本历史加载失败" in html


def test_video_run_request_includes_project_id():
    html = _html()

    assert "project_id: this.projectId || ''" in html
    assert "const storyPath = this.activeStoryPath()" in html
    assert "story_path: storyPath" in html
    assert "'/api/drama-video/run'," in html


def test_deepagent_start_requests_include_project_id():
    html = _html()

    assert "fetch('/api/drama-video/deepagent/loop'" in html
    assert "fetch('/api/drama-video/deepagent/run'" in html
    assert html.count("project_id: this.projectId || ''") >= 3


def test_video_workspace_confirms_cost_guardrail_overrides():
    html = _html()

    assert "requestJsonWithCostConfirmation(" in html
    assert "confirmCostOverride(" in html
    assert "confirm_cost: true" in html
    assert "预算不足，是否继续生成视频？" in html
    assert "已取消付费视频生成" in html
    assert "cost_guardrail" in html
    assert "requires_confirmation" in html
    assert html.count("requestJsonWithCostConfirmation(") >= 4
    assert "'/api/drama-video/run'," in html
    assert "'/api/drama-video/run/' + encodeURIComponent(this.runId) + '/retry'" in html
    assert "'/api/drama-video/deepagent/confirm'," in html


def test_video_workspace_mentions_consistency_and_human_loop_controls():
    html = _html()

    assert "一致性档案" in html
    assert "确认并继续" in html
    assert "要求修改" in html
    assert "操作日志" in html
    assert "成本覆盖" in html
