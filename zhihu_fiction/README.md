# Zhihu Fiction

`zhihu_fiction` 是一个面向网文创作的本地工作流子项目，包含知乎热点素材抓取、选题、创作、审核、导出和 Web 工作台能力。

## Web 服务

启动开发服务：

```bash
uvicorn zhihu_fiction.server:app --reload --port 8000
```

默认页面位于 `/`，前端静态资源由 `zhihu_fiction/static/index.html` 提供。

Web API：

- `POST /api/run`：启动一次创作流水线。
- `GET /api/stream/{run_id}`：通过 SSE 订阅运行进度。
- `POST /api/run/continue`：基于已有正文续写章节。
- `GET /api/runs`：列出历史运行记录。
- `GET /api/runs/{run_id}`：查看单次运行记录。
- `GET /api/stories`：列出已生成的故事。
- `GET /api/stories/{story_path}`：读取故事正文。
- `GET /api/skills/genres`：列出可用流派技能。
- `GET /api/skills/{genre}`：读取指定流派技能卡。
- `GET /api/scheduler`：查看定时任务状态。
- `POST /api/scheduler/start`：启动定时任务。
- `POST /api/scheduler/stop`：停止定时任务。
- `/api/workspace/*`：Workspace 业务工作台 API。

## Workspace 业务工作台

Workspace 将一次性创作流程扩展为本地内容生产闭环：

```text
素材库 → 选题卡 → 任务队列 → 审核草稿 → 发布包
```

核心页面：

- **素材**：录入、导入、筛选创作素材。
- **选题卡**：把一条或多条素材整理成可批准的创作 brief。
- **任务**：查看排队、运行、失败和待审核任务。
- **审核**：轻量编辑标题、简介、标签和正文。
- **发布包**：从审核后的草稿生成平台发布包并确认导出。

Workspace API 位于 `/api/workspace/*`。第一版使用 `zhihu_fiction/data/workspace/` 下的 JSONL/JSON 文件存储，不需要数据库。

主要接口：

- `GET /api/workspace/materials`：列出素材。
- `POST /api/workspace/materials/import-scraped`：导入抓取素材。
- `POST /api/workspace/materials/manual`：手动录入素材。
- `PATCH /api/workspace/materials/{material_id}`：更新素材。
- `GET /api/workspace/topic-cards`：列出选题卡。
- `POST /api/workspace/topic-cards`：创建选题卡。
- `PATCH /api/workspace/topic-cards/{card_id}`：更新选题卡。
- `POST /api/workspace/topic-cards/{card_id}/approve`：批准选题卡。
- `POST /api/workspace/topic-cards/{card_id}/create-task`：从选题卡创建任务。
- `GET /api/workspace/tasks`：列出任务。
- `POST /api/workspace/tasks/{task_id}/retry`：重试任务。
- `POST /api/workspace/tasks/{task_id}/cancel`：取消任务。
- `GET /api/workspace/drafts`：列出审核草稿。
- `GET /api/workspace/drafts/{task_id}`：读取审核草稿。
- `PATCH /api/workspace/drafts/{task_id}`：更新审核草稿。
- `POST /api/workspace/drafts/{task_id}/ready`：标记草稿可发布。
- `GET /api/workspace/packages`：列出发布包。
- `POST /api/workspace/packages/generate`：生成发布包。
- `POST /api/workspace/packages/{package_id}/confirm`：确认发布包导出。
- `GET /api/workspace/packages/{package_id}/files`：查看发布包文件信息。
