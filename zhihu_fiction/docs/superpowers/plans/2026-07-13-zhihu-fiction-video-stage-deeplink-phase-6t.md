# Zhihu Fiction Video Stage Deeplink Phase 6t

## Goal

Make `/video` honor the `stage` query parameter passed by the project workbench next-action button.

## Problem

The project workbench can now route `generate_stage` and `confirm_stage` actions to `/video` with `run_id` and `stage`, but the video workbench only restored `project_id`, `story_path`, and `run_id`. It did not select the intended stage after landing.

## Scope

- Parse `stage` from the URL query.
- Accept only known workflow stages.
- Prefer the URL stage when restoring a non-video-started DeepAgent session.
- Keep `video_started` sessions pinned to the `video` stage.

## Implementation

1. Extend the static video workspace contract tests for `stage`.
2. Add `initialStage` state.
3. Add `normalizeStageParam(stage)` using the existing workflow stage list.
4. Apply `initialStage` during session restore while preserving the video-started override.

## Verification

- `python -m pytest zhihu_fiction/tests/test_static_video_workspace.py -q`
- `python -m pytest zhihu_fiction/tests/test_static_project_dashboard.py zhihu_fiction/tests/test_static_video_workspace.py zhihu_fiction/tests/test_web_drama_workflow_smoke.py -q`
- `node` inline script parse check for `index.html` and `video.html`

## Review Checklist

### Spec Review

- [x] `/video?stage=...` is parsed from the URL.
- [x] Invalid stage names are ignored.
- [x] Restored sessions land on the intended stage.
- [x] Completed video sessions still open on the video stage.

### Quality Review

- [x] Stage validation reuses the existing workflow stage list.
- [x] The change is limited to video workspace deep-link handling and tests.
- [x] No secrets, cookies, generated output, or runtime data are committed.
- [x] Static contracts and JS parsing checks pass.
