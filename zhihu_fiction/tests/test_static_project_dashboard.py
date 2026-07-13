"""Static contract tests for the project dashboard workbench."""
from __future__ import annotations

from pathlib import Path


STATIC_INDEX = Path(__file__).resolve().parents[1] / "static" / "index.html"


def _html() -> str:
    return STATIC_INDEX.read_text(encoding="utf-8")


def test_main_dashboard_loads_project_and_task_center_apis():
    html = _html()

    assert "loadProjects()" in html
    assert "loadTaskCenter()" in html
    assert "loadCostCenter()" in html
    assert "fetch('/api/projects')" in html
    assert "fetch('/api/tasks')" in html
    assert "/api/costs/summary" in html
    assert "projectDashboard" in html
    assert "taskCenter" in html
    assert "costCenter" in html


def test_project_workspace_view_markers_exist():
    html = _html()

    for marker in (
        "project-workbench",
        "project-dashboard",
        "project-timeline",
        "project-asset-library",
        "project-review-list",
        "project-rework-list",
        "openProjectWorkbench(project)",
        "closeProjectWorkbench()",
        "loadProjectWorkspace(project.id)",
        "loadProjectTimeline(project.id)",
    ):
        assert marker in html


def test_project_workbench_shows_production_status_summary():
    html = _html()

    for marker in (
        "project-production-status",
        "productionStatus()",
        "projectWorkspace.production_status",
        "productionStatus().next_action_label",
        "productionStatus().recommended_run_id",
        "productionStatus().export_ready_count",
        "productionStatus().pending_rework_count",
        "productionStatus().awaiting_review_count",
        "继续推荐会话",
    ):
        assert marker in html


def test_project_workbench_shows_release_readiness_blockers():
    html = _html()

    for marker in (
        "project-release-readiness",
        "productionStatus().release_ready",
        "productionStatus().release_blockers",
        "productionStatus().release_action_label",
        "发布就绪",
        "发布阻塞",
        "releaseBlockers()",
        "blocker.code",
        "blocker.count",
    ):
        assert marker in html


def test_project_workbench_shows_release_manifest_summary():
    html = _html()

    for marker in (
        "project-release-manifest",
        "releaseManifest()",
        "projectWorkspace.release_manifest",
        "releaseManifest().release_package",
        "releaseManifest().recommended_run_id",
        "releaseManifest().release_package_run_id",
        "发布交付清单",
        "当前项目包",
        "包所属 Run",
        "复制清单",
        "copyReleaseManifest()",
        "下载发布包",
        "确认交付",
        "downloadReleasePackage()",
        "confirmProjectRelease()",
    ):
        assert marker in html


def test_project_workbench_shows_release_cost_guardrail():
    html = _html()

    for marker in (
        "project-release-cost-guardrail",
        "releaseCostGuardrail()",
        "releaseManifest().cost_guardrail",
        "estimated_total_cny",
        "spent_today_cny",
        "remaining_today_cny",
        "within_budget",
        "成本预估",
        "今日已花费",
        "预算状态",
    ):
        assert marker in html


def test_project_workbench_shows_release_history():
    html = _html()

    for marker in (
        "project-release-history",
        "projectWorkspace.release_history",
        "releaseHistory()",
        "最近交付",
        "release.package_id",
        "release.run_id",
        "release.status",
        "查看详情",
        "loadReleaseDetail(release)",
        "releaseAuditDetail",
        "project-release-detail",
    ):
        assert marker in html


def test_project_workbench_shows_release_integrity_checks():
    html = _html()

    for marker in (
        "project-release-integrity",
        "releaseIntegrity()",
        "releaseIntegrityChecks()",
        "releaseAuditDetail?.integrity",
        "releaseIntegrity().status",
        "releaseIntegrity().summary?.passed",
        "check.label",
        "check.message",
        "完整性校验",
    ):
        assert marker in html
    assert 'x-data="{ integrity: releaseIntegrity() }"' not in html


def test_project_workbench_shows_release_cost_ledger_audit():
    html = _html()

    for marker in (
        "project-release-cost-ledger",
        "releaseCostLedger()",
        "releaseCostLedgerSummary()",
        "releaseAuditDetail?.cost_ledger",
        "releaseAuditDetail?.cost_ledger_summary",
        "estimated_total_cny",
        "actual_total_cny",
        "total_cny",
        "成本账本",
    ):
        assert marker in html


def test_task_center_ui_uses_unified_task_actions():
    html = _html()

    assert "unifiedTasks" in html
    assert "retryUnifiedTask(task)" in html
    assert "cancelUnifiedTask(task)" in html
    assert "'/api/tasks/'+encodeURIComponent(task.id)+'/retry'" in html
    assert "'/api/tasks/'+encodeURIComponent(task.id)+'/cancel'" in html


def test_cost_center_ui_shows_summary_and_ledger():
    html = _html()

    for marker in (
        "cost-center",
        "成本中心",
        "costCenter",
        "costLedger",
        "loadCostCenter()",
        "costCenterDate",
        "costCenterProjectId",
        "costSummary()",
        "filteredCostLedger()",
        "/api/costs/ledger",
        "spent_today_cny",
        "remaining_today_cny",
        "by_source",
    ):
        assert marker in html


def test_project_dashboard_links_to_video_workspace_without_embedding_controls():
    html = _html()

    assert "openVideoForProject()" in html
    assert "new URL('/video', window.location.origin)" in html
    assert "url.searchParams.set('project_id', this.selectedProject.id)" in html
    assert "url.searchParams.set('story_path', story.body_path)" in html
    assert "startDramaVideoRun()" not in html
    assert "connectVideoStream(" not in html


def test_project_dashboard_links_to_short_drama_workspace_and_next_action():
    html = _html()

    assert "next_action" in html
    assert "workspaceNextActionLabel()" in html
    assert "workspaceNextActionKind()" in html
    assert "executeWorkspaceNextAction()" in html
    assert "workspaceNextAction().kind === 'generate_stage'" in html
    assert "url.searchParams.set('run_id', action.target_id)" in html
    assert "url.searchParams.set('stage', action.stage)" in html
    assert "/video" in html
    assert "待确认" in html
    assert "待生成" in html


def test_project_timeline_titles_cover_drama_production_events():
    html = _html()

    for marker in (
        "item.kind === 'drama_session'",
        "item.kind === 'drama_stage_version'",
        "item.kind === 'drama_video_run'",
        "item.kind === 'drama_project_package'",
    ):
        assert marker in html


def test_project_asset_library_uses_unified_assets():
    html = _html()

    assert "projectAssets()" in html
    assert "projectWorkspace.assets" in html
    assert "this.projectWorkspace.assets || this.projectWorkspace.video_assets" in html
    assert "asset.source" in html


def test_project_asset_library_has_filter_and_preview_controls():
    html = _html()

    for marker in (
        "assetFilter",
        "selectedAsset",
        "assetKinds()",
        "filteredProjectAssets()",
        "selectProjectAsset(asset)",
        "assetPreviewText(selectedAsset)",
        "project-asset-preview",
    ):
        assert marker in html


def test_project_asset_library_shows_summary_and_review_actions():
    html = _html()

    for marker in (
        "assets_summary",
        "assetSummary()",
        "assetSourceCounts()",
        "assetReviewCounts()",
        "assetReviewDecision(asset)",
        "copyAssetPrompt(selectedAsset)",
        "待审核资产",
        "需修改",
        "复制文本",
    ):
        assert marker in html


def test_project_asset_library_can_submit_asset_reviews():
    html = _html()

    for marker in (
        "reviewProjectAsset(",
        "'/api/projects/' + encodeURIComponent(this.selectedProject.id) + '/assets/reviews'",
        "decision: decision",
        "target_kind: asset.review_target_kind",
        "target_id: asset.id",
        "批准",
        "要求修改",
        "驳回",
    ):
        assert marker in html


def test_project_asset_review_uses_inline_dialog_instead_of_prompt():
    html = _html()

    for marker in (
        "assetReviewDialog",
        "openAssetReviewDialog(",
        "closeAssetReviewDialog()",
        "submitAssetReviewDialog()",
        "asset-review-dialog",
        "审核意见",
        "给 Agent 的修改方向",
        "agent_instruction",
    ):
        assert marker in html
    assert "window.prompt('审核意见'" not in html


def test_project_rework_requests_are_visible_and_executable():
    html = _html()

    for marker in (
        "projectWorkspace.rework_requests",
        "pendingReworkRequests()",
        "executeReworkRequest(",
        "project-rework-list",
        "执行返工",
        "fetch('/api/drama-video/deepagent/revise'",
        "feedback: request.instruction || request.comment",
    ):
        assert marker in html


def test_project_rework_execution_process_is_visible():
    html = _html()

    for marker in (
        "reworkExecution",
        "project-rework-execution",
        "reworkExecution.status",
        "reworkExecution.message",
        "reworkExecution.content",
        "正在返工",
        "返工完成",
        "rework_request",
    ):
        assert marker in html


def test_project_rework_completed_version_entry_points_exist():
    html = _html()

    for marker in (
        "project-rework-version-actions",
        "completed_stage_version_id",
        "completed_stage_version",
        "openCompletedReworkVersion(",
        "confirmReworkVersionAsDraft(",
        "requestReworkVersionChanges(",
        "查看返工版本",
        "确认为草稿",
        "再次请求修改",
    ):
        assert marker in html


def test_project_rework_completed_version_actions_keep_api_contracts():
    html = _html()

    for marker in (
        "completedReworkAsset(request)",
        "completedReworkVersion(request)",
        "asset.source === 'stage_version' && asset.id === request.completed_stage_version_id",
        "record: version",
        "fetch('/api/drama-video/deepagent/confirm'",
        "run_id: request.run_id",
        "stage: request.stage",
        "content: version.content",
        "this.openAssetReviewDialog(asset, 'changes_requested')",
    ):
        assert marker in html


def test_project_drama_package_export_panel_exists():
    html = _html()

    for marker in (
        "project-drama-package-panel",
        "projectWorkspace.drama_sessions",
        "projectDramaSessions()",
        "exportProjectDramaPackage(",
        "packageExportStatus",
        "短剧项目包",
        "可导出",
        "导出项目包",
        "已导出",
    ):
        assert marker in html


def test_project_drama_package_panel_can_resume_specific_session():
    html = _html()

    for marker in (
        "openVideoForProject(session)",
        "继续生产",
        "url.searchParams.set('run_id', session.id)",
        "const story = this.storyForDramaSession(session)",
        "storyForDramaSession(session)",
    ):
        assert marker in html


def test_project_drama_package_export_uses_existing_export_api():
    html = _html()

    for marker in (
        "fetch('/api/drama-video/package/export'",
        "run_id: session.id",
        "packageExportStatus[session.id]",
        "await this.loadProjectWorkspace(this.selectedProject.id)",
        "await this.loadProjectTimeline(this.selectedProject.id)",
    ):
        assert marker in html


def test_project_workspace_refresh_paths_preserve_drama_sessions():
    html = _html()

    assert "applyProjectWorkspace(data)" in html
    assert "drama_sessions: data.drama_sessions || []" in html
    assert html.count("this.projectWorkspace = this.applyProjectWorkspace(data)") >= 3


def test_project_drama_package_panel_shows_export_summary():
    html = _html()

    for marker in (
        "packageSummary(session)",
        "session.latest_package?.package_summary",
        "summary.available",
        "summary.stage_count",
        "summary.version_count",
        "summary.exported_at",
        "阶段覆盖",
        "版本数",
        "导出时间",
        "包摘要不可读取",
    ):
        assert marker in html
