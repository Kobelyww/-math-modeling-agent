# Zhihu Fiction Web Drama Workflow Smoke Phase 6r

## Goal

Protect the single-project short-drama workbench flow from a user experience dead end after a stage is confirmed.

## Problem

After a user confirmed the `script` stage, the session moved to `ready_for_next_stage`, but the project workspace `next_action` returned `none`. The backend knew the next stage was `style`, yet the workbench did not expose a clear next action.

## Scope

- Add a Web API smoke test for the project short-drama loop.
- Cover DeepAgent loop start, project workspace next action, stage confirmation, human revision, final video run creation, versions, and trace events.
- Fix only the project workspace next-action derivation.
- Do not change model prompts, video provider calls, persistence backends, or frontend layout in this phase.

## Implementation

1. Add `test_web_drama_workflow_smoke.py` with a mocked DeepAgent/video model path.
2. Make the project stage summary infer the next unconfirmed stage when the session is `ready_for_next_stage`.
3. Return a `generate_stage` next action for that state.

## Verification

- `python -m pytest zhihu_fiction/tests/test_web_drama_workflow_smoke.py -q`
- `python -m pytest zhihu_fiction/tests/test_project_workspace_api.py zhihu_fiction/tests/test_drama_video_deepagent_flow.py zhihu_fiction/tests/test_server_drama_video.py zhihu_fiction/tests/test_web_drama_workflow_smoke.py -q`

## Review Checklist

### Spec Review

- [x] The smoke test follows the real FastAPI routes.
- [x] The test covers the user transition from stage confirmation to the next generation action.
- [x] The final video step creates a queued run without calling the real provider.
- [x] The change is limited to next-action derivation and test coverage.

### Quality Review

- [x] The fix reuses existing `_next_project_stage()` logic.
- [x] The smoke test uses isolated repositories and temporary story files.
- [x] No API keys, cookies, generated output, or runtime data are committed.
- [x] Existing project, DeepAgent, and video route tests remain green.
