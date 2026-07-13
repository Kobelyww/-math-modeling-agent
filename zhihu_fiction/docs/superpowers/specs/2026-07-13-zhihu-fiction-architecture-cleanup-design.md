# Zhihu Fiction Architecture Cleanup Design

## Goal

把 `zhihu_fiction` 从“功能已经很多但源码、运行数据、集成服务混在一起”的项目结构，整理成可以长期维护、测试、发布和继续扩展短剧业务的产品级模块架构。

本次重构只针对 `zhihu_fiction`。不移动、不修改 `agent_app`、`newtest`、`quant-trading`、`werewolf` 或仓库根目录其他实验项目。

## Current State

`zhihu_fiction` 当前已经具备小说生成、短剧改编、视频任务、Workspace、IP Memory、Web 工作台、发布包导出和知乎辅助发布能力，但目录边界仍然偏 demo：

- 根目录同时放置 `agents.py`、`pipeline.py`、`server.py`、`workspace_routes.py`、`scraper.py`、`exporter.py`、`config.py` 等业务、Web、配置和集成代码。
- `app/` 已经承接部分 FastAPI 工业化拆分，但旧入口和业务兼容模块仍散落在根目录。
- `drama/`、`workspace/`、`ip_memory/` 已经是清晰的领域模块，可以作为后续重构的基准。
- `data/`、`output/`、`.pytest_cache/`、`__pycache__/` 是运行数据或缓存，却和源码放在同一层。
- `data/auth/zhihu_session.json` 是本地登录态和敏感文件，必须明确排除在版本管理之外。
- `mcp_server/` 是嵌套 Git 仓库，第一阶段不能随意移动或纳入主项目提交。

## Non-Goals

本次架构清理不做以下事情：

- 不重写小说生成、短剧生成、DeepAgent、Human Loop 或视频生成业务逻辑。
- 不改变现有 Web API 路径、CLI 命令、环境变量名称或前端入口。
- 不删除用户本地运行数据、历史生成作品、知乎登录态或缓存。
- 不把 `mcp_server/` 合并进主包；只定义边界和后续处理方式。
- 不把整个 `LLM-Study` 改造成 monorepo。
- 不大规模一次性迁移所有文件；每个迁移阶段必须可测试、可回滚。

## Target Architecture

目标是逐步收敛到 `src` 风格的产品包结构，并把源码、运行数据、文档、测试和外部集成分开：

```text
zhihu_fiction/
  src/
    zhihu_fiction/
      core/
        config.py
        llm.py
        base.py
        tools.py
        errors.py
      fiction/
        agents.py
        orchestrator.py
        pipeline.py
        scraper.py
        distiller.py
        skills_store.py
      drama/
        adapter.py
        assets.py
        exporter.py
        models.py
        prompts.py
        stage_assets.py
        video.py
      workspace/
        models.py
        queue.py
        queue_backends.py
        repositories.py
        schemas.py
        services.py
      ip_memory/
        agent_graph.py
        consistency.py
        extraction.py
        models.py
        rendering.py
        repository.py
        trace.py
      publishing/
        base.py
        fanqie.py
        qidian.py
        zhihu.py
      integrations/
        zhihu_browser.py
        bailian_video.py
      web/
        factory.py
        dependencies.py
        settings.py
        security.py
        sse.py
        state.py
        routes/
        services/
      storage/
        pipeline_storage.py
        object_storage.py
  static/
  tests/
  docs/
  runtime/
  output/
  mcp_server/
```

第一阶段不要求立即创建完整 `src/` 结构。第一阶段的目标是建立迁移规则、保护运行数据，并让后续迁移有稳定路径。

## Module Boundaries

### `core`

负责跨业务通用能力：

- 环境变量读取和模型配置
- LLM client 创建
- 通用数据清洗和工具函数
- 通用异常、重试和结果包装

`core` 不依赖小说、短剧、Web 或发布模块。

### `fiction`

负责小说内容生产主链路：

- 热点采集
- 技能蒸馏
- 多 Agent 小说创作
- 小说评审、润色和续写
- 小说流水线编排

`fiction` 可以依赖 `core`、`workspace`、`ip_memory`，但不能直接依赖 FastAPI route。

### `drama`

负责小说到短剧的内容改编：

- 剧本转换
- 风格设计
- 剧情设计
- 人物参考和一致性
- 分镜和视频 prompt
- 视频任务 spec

`drama` 可以依赖 `core`、`workspace`、`ip_memory`，但不能直接持有 Web 全局状态。

### `workspace`

负责产品工作台领域模型和任务状态：

- Project
- Story
- DramaSession
- StageVersion
- VideoRun
- VideoAsset
- Review
- Queue

`workspace` 是业务状态中心，不直接调用外部模型 API。

### `ip_memory`

负责跨小说和短剧的一致性记忆：

- Story Bible
- Character Card
- World Fact
- Narrative Memory
- Style Guide
- Asset Binding

`ip_memory` 不直接负责生成内容，而是为 `fiction` 和 `drama` 提供可复用上下文。

### `publishing`

负责发布包和平台适配：

- 知乎
- 起点
- 番茄
- 后续可扩展抖音文案、小红书、视频号等

浏览器自动化不放在这里，浏览器自动化属于 `integrations`。

### `integrations`

负责外部系统调用：

- DeepSeek / 百炼 / DashScope 等模型 provider adapter
- 知乎浏览器辅助发布
- 后续视频模型、对象存储、内容安全、成本计费接口

原则是外部 API 细节不能泄漏到 `fiction`、`drama`、`workspace` 的领域模型里。

### `web`

负责 FastAPI 应用层：

- app factory
- route 注册
- request/response schema
- SSE
- auth/security
- Web runtime service

`web` 可以调用领域 service，但不能承载核心业务逻辑。

### `storage`

负责持久化实现：

- pipeline run storage
- workspace JSON repository
- object storage adapter
- local file backend
- 后续 SQL、Redis、MinIO backend

领域模块只依赖 repository/protocol，不直接关心本地文件或对象存储路径。

## Runtime Data Policy

运行数据需要从源码认知中剥离。短期仍保留现有路径，长期迁移到 `runtime/` 或外部 volume。

必须 gitignore：

```gitignore
zhihu_fiction/data/auth/
zhihu_fiction/data/workspace/
zhihu_fiction/data/objects/
zhihu_fiction/data/agent_traces/
zhihu_fiction/data/ip_memory/
zhihu_fiction/output/
zhihu_fiction/.pytest_cache/
zhihu_fiction/__pycache__/
zhihu_fiction/**/*.pyc
```

允许提交：

- `.env.example`
- `.env.production.example`
- 测试 fixture
- 文档示例
- schema 示例，但不能包含真实 cookie、token、API key 或用户生成作品全文。

## MCP Server Boundary

`zhihu_fiction/mcp_server/` 当前是嵌套 Git 仓库。第一阶段保持原位，不移动、不提交其内部文件。

后续有两个可选方向：

1. 独立仓库：作为知乎采集/发布 MCP 服务单独维护。
2. External integration：主项目只保留 README 链接、启动说明和 API contract。

除非单独批准，不把 `mcp_server` 合并进 `src/zhihu_fiction/integrations`。

## Migration Strategy

### Phase 1: Freeze and Guard

目标：不移动业务代码，先降低混乱和误提交风险。

- 新增本设计文档。
- 检查并补强 `.gitignore`。
- 新增 `zhihu_fiction/docs/architecture.md`，说明当前目录、目标目录和迁移规则。
- 在 README 中把“当前结构”和“目标结构/运行数据策略”区分开。
- 确认 `data/auth`、`output`、缓存和 agent traces 不会被提交。

验收标准：

- 没有源码移动。
- 没有敏感文件 staged。
- 文档能解释每个一级目录的职责。
- `python -m pytest zhihu_fiction/tests -q` 在可用环境下仍可运行。

### Phase 2: Core Extraction

目标：先抽离最底层、最少依赖的通用模块。

- `config.py` -> `core/config.py`
- `llm.py` -> `core/llm.py`
- `base.py` -> `core/base.py`
- `tools.py` -> `core/tools.py`
- 保留旧路径兼容 shim，避免一次性破坏导入。

验收标准：

- 原有 import 路径仍可用。
- 新 import 路径可用。
- 配置、LLM、基础工具相关测试通过。

### Phase 3: Fiction Domain Extraction

目标：把小说生成主链路从根目录收敛到 `fiction`。

- `agents.py` -> `fiction/agents.py`
- `orchestrator.py` -> `fiction/orchestrator.py`
- `pipeline.py` -> `fiction/pipeline.py`
- `scraper.py` -> `fiction/scraper.py`
- `distiller.py` -> `fiction/distiller.py`
- `skills_store.py` -> `fiction/skills_store.py`

验收标准：

- CLI 小说生成入口可用。
- Web 小说生成入口可用。
- pipeline、agents、skills 相关测试通过。

### Phase 4: Web Boundary Cleanup

目标：让 Web 层只做 HTTP 和运行时协调。

- `server.py` 保留为兼容入口。
- `workspace_routes.py` 迁入 `web/routes/workspace.py` 或通过 shim 暴露。
- `app/` 中已有 factory/routes/services 逐步迁到 `web/`。
- Web route 不直接实现小说/短剧核心生成逻辑。

验收标准：

- `uvicorn zhihu_fiction.server:app` 可用。
- `/`、`/video`、小说 API、短剧 API、workspace API 路径不变。
- SSE 行为不变。

### Phase 5: Integration and Storage Cleanup

目标：把外部 provider 和持久化实现从业务流程中隔离。

- `automator.py`、`automator_zhihu.py` 迁入 `integrations/`。
- 百炼/DashScope 视频调用封装为 provider adapter。
- `pipeline_storage.py` 迁入 `storage/`。
- 本地 JSON/file backend 与未来 SQL/Redis/MinIO backend 通过接口隔离。

验收标准：

- 无 API key 泄漏到前端。
- 视频 provider 可 mock。
- storage backend 可替换。

### Phase 6: Src Layout Switch

目标：正式切换到 `src/zhihu_fiction` 包结构。

- 调整 package metadata 和测试路径。
- 保留一轮兼容 shim。
- 更新 README、部署文档、Docker、测试命令。

验收标准：

- 从仓库根目录运行测试通过。
- Docker/uvicorn 启动路径通过。
- 旧入口在过渡期仍可给出清晰 deprecation warning。

## Compatibility Rules

每个阶段必须遵守：

- 外部 API 路径不变。
- CLI 命令不变。
- `uvicorn zhihu_fiction.server:app` 不变。
- 已有测试如果需要调整，只能调整 import 注入点，不能降低行为断言。
- 每次迁移必须保留旧模块 shim，至少一个阶段后再考虑删除。
- 不使用 `git add .`；只精确 stage 本次相关文件。

## Review Requirements

按照项目规则，每个实现任务完成后必须进行两轮审查：

1. Spec 审查：对照本设计和后续 implementation plan，检查是否遗漏、越界或改变外部行为。
2. 质量审查：检查命名、模块边界、导入循环、测试覆盖、敏感文件和运行数据处理。

两轮审查都通过后，才能进入下一个迁移任务。

## Risks

- 大规模移动文件会打断大量 import，因此必须分阶段加 shim。
- `mcp_server` 是嵌套 Git 仓库，误操作会污染提交或破坏独立历史。
- `data/auth` 包含登录态，任何 broad staging 都可能造成安全问题。
- 前端静态页面可能硬编码 API 路径，Web 迁移必须保持路径不变。
- 当前测试可能 monkeypatch 旧模块路径，迁移时需要兼容导出或同步调整测试注入点。

## Success Criteria

完成整体架构重构后，项目应该满足：

- 新开发者能在 10 分钟内理解每个一级目录职责。
- 小说、短剧、Web、Workspace、IP Memory、发布、外部集成边界清楚。
- 运行数据、缓存、登录态与源码分离。
- 单个业务模块可以独立测试。
- 后续接入 SQL、Redis、MinIO、更多视频模型时，不需要继续扩大根目录混乱。
- 现有用户入口和 API 行为保持兼容。
