# Zhihu Fiction Industrial Backend Refactor Design

## Goal

把 `zhihu_fiction` 从单文件服务端 demo 结构重构为可长期演进的后端应用骨架，同时保持现有小说工作台、短剧工作台、Workspace API、DeepAgent/Human Loop、视频任务 API 的外部行为不变。

第一阶段只处理后端应用骨架，不做前端框架迁移、不强制启用 Redis/MinIO/SQL、不改变现有 API 路径。

## Current State

当前项目功能已经成型，但工业化边界不足：

- `zhihu_fiction/server.py` 约 1400 行，混合了 FastAPI app 初始化、静态页面路由、小说流水线 API、短剧 DeepAgent API、视频任务后台执行、全局运行状态和 infrastructure 状态。
- `workspace_routes.py` 已经是独立 router，说明项目已有模块化雏形。
- `drama/` 和 `workspace/` 已经存在领域模型、repository、service、queue/provider/asset 适配器。
- 测试覆盖健康，当前 `python -m pytest zhihu_fiction/tests -q` 为 `128 passed`。
- 现有 Web 服务运行入口依赖 `zhihu_fiction.server:app`，因此必须保持兼容。

## Non-Goals

本阶段不做以下事情：

- 不迁移前端到 Vite/Vue/React。
- 不改变 API 路径或响应结构。
- 不删除 JSONL/local 后端。
- 不要求 Redis、MinIO、MySQL/PostgreSQL 在本地可用。
- 不重写小说生成或短剧 DeepAgent prompt。
- 不做 UI 视觉大改。

## Target Architecture

新增 `zhihu_fiction/app/` 作为 FastAPI 应用层：

```text
zhihu_fiction/
  app/
    __init__.py
    factory.py
    dependencies.py
    state.py
    routes/
      __init__.py
      static.py
      stories.py
      pipeline.py
      drama_video.py
    services/
      __init__.py
      pipeline_runtime.py
      drama_video_runtime.py
```

`zhihu_fiction/server.py` 保留为兼容入口，但瘦身为：

```python
from .app.factory import create_app

app = create_app()
```

测试和部署仍然可以继续使用：

```bash
python -m uvicorn zhihu_fiction.server:app --host 127.0.0.1 --port 8010
```

## Module Responsibilities

### `app.factory`

负责创建 FastAPI app、挂载 middleware、注册 exception handler、注册 routers。

它不直接包含业务逻辑，不直接执行 DeepAgent，不直接读写故事文件。

### `app.dependencies`

负责创建和暴露共享依赖：

- settings
- skills store
- workspace repository/service/queue
- pipeline factory
- exporter factory
- infrastructure status provider

依赖必须可替换，方便测试 monkeypatch 和未来生产环境注入。

### `app.state`

集中管理原本散落在 `server.py` 的运行态：

- pipeline SSE queue/progress/active_run_id
- drama video SSE queue/progress/specs
- drama DeepAgent session cache/background task registry
- locks

此模块只保存运行态容器，不实现业务流程。

### `app.routes.static`

负责：

- `GET /`
- `GET /video`

只读取静态 HTML 文件并返回。

### `app.routes.stories`

负责：

- `GET /api/stories`
- `GET /api/stories/{story_path:path}`

故事目录扫描和安全路径校验可提取到小型 helper 或 service，避免路由直接包含复杂逻辑。

### `app.routes.pipeline`

负责小说流水线相关 API：

- `POST /api/run`
- `GET /api/stream/{run_id}`
- `POST /api/run/continue`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- scheduler/config/status 等已有小说工作台 API，如果仍在 `server.py` 中，由本模块接收。

后台执行细节放入 `app.services.pipeline_runtime`。

### `app.routes.drama_video`

负责短剧和视频相关 API：

- `POST /api/drama-video`
- `POST /api/drama-video/stage`
- `POST /api/drama-video/run`
- `GET /api/drama-video/stream/{run_id}`
- `POST /api/drama-video/deepagent/run`
- `POST /api/drama-video/deepagent/advance`
- `POST /api/drama-video/deepagent/confirm`
- `POST /api/drama-video/deepagent/revise`
- `GET /api/drama-video/deepagent/{run_id}`
- `GET /api/drama-video/deepagent/{run_id}/versions`
- `GET /api/drama-video/infrastructure`
- `POST /api/drama-video/package/export`

DeepAgent 后台推进和视频任务后台执行放入 `app.services.drama_video_runtime`。

### `app.services.pipeline_runtime`

负责：

- 创建 pipeline
- 后台运行 pipeline
- SSE event queue 写入
- run history 读取

它不持有 FastAPI route 对象。

### `app.services.drama_video_runtime`

负责：

- 从故事文件构造 `WorkflowResult`
- 阶段草稿生成
- DeepAgent session 持久化
- Human Loop revision
- 视频 task spec 创建
- 视频任务后台执行
- 项目包导出

它可以依赖 `drama/`, `workspace/`, `orchestrator.py` 中已有领域能力，但路由层不再直接调用这些细节。

## Data Flow

### 小说生成

1. 路由接收 `/api/run`。
2. `pipeline_runtime` 创建 run id、注册 event queue。
3. 后台线程执行 `Pipeline.run(...)`。
4. 进度事件写入 SSE queue。
5. `/api/stream/{run_id}` 只负责消费 queue。

### 短剧 DeepAgent

1. 路由接收 `/api/drama-video/deepagent/run`。
2. `drama_video_runtime` 创建 session 并落库。
3. `/advance` 在 Web 端默认走 background 模式，立即返回 `generating`。
4. 后台生成阶段草稿，保存 session 和 stage version。
5. 前端通过 session/versions API 轮询得到草稿。
6. `/confirm` 保存确认稿，推进下一阶段或创建视频 run。

### 视频任务

1. 已确认 stage drafts 后创建 video run spec。
2. `/api/drama-video/stream/{run_id}` 首次连接时触发后台视频任务。
3. runtime 导出 prompt package、提交 provider、写 job store。
4. SSE 输出阶段进度和 final payload。

## Error Handling

统一保留现有错误语义：

- 缺少参数返回 400。
- 找不到故事、run、session 返回 404。
- 阶段顺序错误返回 409。
- LLM/短剧生成失败返回 500 或 session `failed`。
- 视频 provider 失败返回 502 或 SSE failed event。

后台任务失败必须写入持久状态，前端不能只依赖内存异常。

## Compatibility

必须保持：

- `from zhihu_fiction.server import app` 可用。
- `uvicorn zhihu_fiction.server:app` 可用。
- 所有现有路径不变。
- 测试中对 `server_mod.workspace_repo`、`server_mod.create_llm`、`server_mod._generate_video_stage_draft` 等 monkeypatch 的兼容性，需要通过兼容导出或调整测试中的注入点处理。

优先做兼容导出，避免一次重构同时大规模重写测试。

## Testing Strategy

重构必须保持测试绿灯：

```bash
python -m pytest zhihu_fiction/tests -q
git diff --check
```

新增测试重点：

- `create_app()` 注册所有关键路由。
- `zhihu_fiction.server:app` 仍可访问 `/`, `/video`, `/api/stories`, `/api/drama-video/infrastructure`。
- drama background advance 仍然非阻塞。
- pipeline stream 和 drama video stream 仍能返回 SSE。

实施中每移动一组路由后跑对应测试文件，避免一次性拆完再找线头。

## Migration Plan

### Step 1: Application Factory

创建 `app.factory`, `app.dependencies`, `app.state`，让 `server.py` 能通过 `create_app()` 创建当前等价 app。

### Step 2: Static And Stories Routes

先移动低风险路由：

- `/`
- `/video`
- `/api/stories`

### Step 3: Pipeline Runtime And Routes

移动小说生成、run history、SSE stream、continue chapter。

### Step 4: Drama Video Runtime And Routes

移动短剧 stage、DeepAgent、video stream、package export。

### Step 5: Compatibility Cleanup

保留必要兼容导出，删除重复 helper，确保 `server.py` 降为薄入口。

## Acceptance Criteria

- `server.py` 只保留 app 创建和兼容导出，目标少于 250 行。
- 所有现有测试通过。
- 新增 app factory/router 测试通过。
- 现有 Web 页面无需修改 URL 即可访问。
- 启动服务后 `/api/drama-video/infrastructure` 正常返回。
- `/api/drama-video/deepagent/advance` 的 background 模式继续立即返回 `generating`。

## Risks

- `server.py` 当前被测试大量 monkeypatch，直接移动函数会造成测试破裂。
- 全局内存状态如果拆散，SSE 和后台任务可能拿到不同 state 实例。
- 路由模块如果在 import 时初始化依赖，测试隔离会变差。

应对策略：

- 用 `AppState` 单例对象集中状态，所有 router 通过 dependency/factory 共享同一个实例。
- 保持 `server.py` 兼容导出一段时间。
- 每个步骤只移动一类路由，移动后立刻跑定向测试。
