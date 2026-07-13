# Zhihu Fiction Project Next Action UI Phase 6s

## Goal

Make the project workbench consume the backend `next_action` contract after a short-drama stage is confirmed.

## Problem

The backend now exposes `generate_stage` when a DeepAgent session is ready for the next stage, but the main project workbench only rendered a passive label and kept the useful action hidden behind a generic recommended-session button.

## Scope

- Update the project workbench next-action label.
- Add an explicit "执行下一步" button.
- Route `confirm_stage` and `generate_stage` actions to the `/video` workbench with `project_id`, `story_path`, `run_id`, and `stage`.
- Do not duplicate DeepAgent generation controls inside the main dashboard.

## Implementation

1. Extend the static project dashboard contract test for `generate_stage`.
2. Add `workspaceNextActionKind()` and `workspaceNextActionLabel()`.
3. Add `executeWorkspaceNextAction()` and `openVideoForWorkspaceAction()`.
4. Extract `videoWorkspaceUrl()` so both existing and new entry points share URL construction.

## Verification

- `python -m pytest zhihu_fiction/tests/test_static_project_dashboard.py::test_project_dashboard_links_to_short_drama_workspace_and_next_action -q`
- `python -m pytest zhihu_fiction/tests/test_static_project_dashboard.py zhihu_fiction/tests/test_web_drama_workflow_smoke.py zhihu_fiction/tests/test_project_workspace_api.py zhihu_fiction/tests/test_drama_video_deepagent_flow.py -q`

## Review Checklist

### Spec Review

- [x] The main dashboard consumes the backend `next_action` contract.
- [x] `generate_stage` routes to the video workbench instead of duplicating video controls.
- [x] Existing recommended-session navigation remains available.
- [x] The change stays within project workbench UX and static contract tests.

### Quality Review

- [x] URL construction is shared by old and new entry points.
- [x] `run_id` and `stage` are preserved when the action comes from the backend.
- [x] No secrets, generated output, cookies, or runtime data are committed.
- [x] Related static and workflow tests remain green.
