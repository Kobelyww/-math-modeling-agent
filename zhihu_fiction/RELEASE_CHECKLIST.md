# zhihu_fiction V1 Release Checklist

## Data And Storage

- [ ] SQLite is enabled with `ZH_WORKSPACE_BACKEND=sqlite`.
- [ ] SQLite path is outside temporary directories.
- [ ] Local object storage or MinIO bucket is configured.
- [ ] Runtime data, `.env`, auth files, workspace files, object files, and generated output are ignored by git.

## Production Reliability

- [ ] DeepAgent sessions survive service restart.
- [ ] VideoRun and VideoJob records survive service restart.
- [ ] Failed stages show readable errors.
- [ ] Failed video shots can retry without resubmitting successful shots.
- [ ] Operation logs record confirm, revise, retry, cancel, recover, and export actions.
- [ ] 服务重启恢复 has been tested on one active project.

## Consistency

- [ ] 一致性 profile is generated for a project.
- [ ] Characters, world facts, visual style, narrative constraints, and asset bindings are visible in the workspace.
- [ ] Storyboard and video prompts reference the consistency profile.

## Cost Control

- [ ] 成本确认 is required before every video API call.
- [ ] Daily budget is configured with `ZH_DAILY_BUDGET_CNY`.
- [ ] Cost center explains estimated, actual, and covered estimate entries.
- [ ] Retry also requires cost confirmation.

## Web QA

- [ ] Project list shows status and pending action.
- [ ] Single-project workspace shows stage, human-loop controls, consistency, assets, costs, and logs.
- [ ] Task center shows running, failed, and waiting tasks.
- [ ] Cost center shows budget and coverage explanation.
