# Zhihu Fiction Studio

`zhihu_fiction` 是一个面向爆款故事创作的多智能体内容生产系统。它围绕“热点抓取 → 技能蒸馏 → 多 Agent 创作 → 评审改写 → 多平台发布包导出/辅助发布”构建，适合用来探索知乎短篇、网文开篇、平台化故事内容和 AI 写作工作流。

## 功能概览

- **热点采集**：抓取知乎热榜、搜索话题，支持手动录入兜底。
- **技能蒸馏**：从热门内容中提炼题材、开篇钩子、反转节奏、互动引导等创作技能。
- **多 Agent 创作**：由选题分析、大纲规划、正文创作、润色、评审、发布方案等角色协作完成作品。
- **质量评审与改写**：按开篇钩子、节奏、人设、逻辑、情绪张力、金句密度等维度审稿，并可触发定向修改。
- **多章节支持**：支持续写和多章节创作，自动携带前文上下文。
- **多平台发布包**：可导出知乎盐选、起点、番茄等平台适配的标题、简介、标签和正文格式。
- **短剧 Prompt 包**：可将已生成小说转换为 10 集以内的短剧分集剧本、角色/场景一致性设定、镜头表和视频生成提示词，为后续接入视频生成模型做准备。
- **Web 工作台**：提供 FastAPI 服务、SSE 流式进度、运行历史、作品查看、技能库和定时任务接口。
- **浏览器辅助发布**：支持基于 Playwright 的知乎辅助发布流程。

## 项目结构

```text
zhihu_fiction/
├── agents.py             # DeepAgent 工具函数、系统提示词、评审 Agent
├── automator_zhihu.py    # 知乎浏览器辅助发布
├── base.py               # 内容规范化、基础工具
├── cli.py                # 交互式命令行入口
├── config.py             # 环境变量和模型配置
├── distiller.py          # 爆款内容技能蒸馏
├── exporter.py           # 多平台发布包导出
├── llm.py                # LLM 创建逻辑
├── orchestrator.py       # Coordinator 调用和工作流兼容封装
├── pipeline.py           # 自动化流水线、调度、检查点、内容安全
├── scraper.py            # 知乎热榜/搜索/手动录入采集
├── server.py             # FastAPI Web 服务和 SSE 接口
├── skills_store.py       # 技能库存取
├── tools.py              # 辅助工具
├── publishers/           # 知乎、起点、番茄发布包适配器
├── static/               # Web 前端静态资源
├── tests/                # 单元测试
├── data/                 # 抓取数据、技能库、认证状态等运行数据
└── output/               # 生成作品、发布包、流水线记录
```

## 安装与准备

建议从仓库根目录执行命令。

```bash
pip install -r zhihu_fiction/requirements.txt
```

如果需要使用浏览器辅助发布：

```bash
playwright install chromium
```

## 环境变量

在仓库根目录或 `zhihu_fiction/` 下创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_API_BASE=
DEEPSEEK_TEMPERATURE=0.7
DEEPSEEK_MAX_RETRIES=3

# 可选：百炼/DashScope 视频生成。读取优先级：
# DASHSCOPE_API_KEY -> BAILIAN_API_KEY -> EMBEDDING_API_KEY
EMBEDDING_API_KEY=your_bailian_api_key
BAILIAN_VIDEO_MODEL=wanx2.1-t2v-turbo
BAILIAN_VIDEO_SIZE=1280*720
```

可选的 Agent 温度配置：

```env
DEEPSEEK_TOPIC_ANALYZER_TEMPERATURE=0.7
DEEPSEEK_OUTLINE_PLANNER_TEMPERATURE=0.7
DEEPSEEK_DRAFT_WRITER_TEMPERATURE=0.8
DEEPSEEK_POLISHER_TEMPERATURE=0.7
DEEPSEEK_REVIEWER_TEMPERATURE=0.3
DEEPSEEK_SYNTHESIZER_TEMPERATURE=0.5
```

## 命令行使用

启动交互式 CLI：

```bash
python -m zhihu_fiction.cli
```

常用命令：

```text
/scrape                 抓取知乎热榜
/search <关键词>        搜索知乎话题
/manual                 手动录入热门内容
/files                  查看已抓取文件
/distill                从已抓取内容蒸馏创作技能
/distill_file <文件>    蒸馏指定文件
/skills                 查看技能库题材
/skill <题材>           查看指定题材技能卡
/create <主题>          完整多 Agent 创作
/fast <主题>            快速创作
/polish <主题>          精打磨模式
/stream <主题>          流式输出创作过程
/outputs                查看已生成作品
/load <文件名>          加载历史作品
/continue               基于已加载作品续写下一章
/publish                导出最近作品的多平台发布包
/publish <主题>         创作并导出发布包
/drama                  将最近/已加载小说转成短剧视频 Prompt 包
/drama_video [数量]     生成 Prompt 包并提交百炼视频任务，默认 1 个镜头
/autopublish            浏览器辅助发布到知乎
/mode <模式>            设置创作模式：fast、polish、full
/genre <题材>           设置目标题材
/help                   查看帮助
/exit                   退出
```

推荐流程：

```text
/scrape
/distill
/genre 悬疑
/create 一个密室逃脱中发现同伴是凶手的故事
/publish
```

短剧 Prompt 包流程：

```text
/create 一个适合短剧改编的复仇爽文
/drama
```

百炼视频任务流程：

```text
/create 一个适合短剧改编的复仇爽文
/drama_video
/drama_video 3
```

`/drama_video` 会先生成短剧 Prompt 包，再把前 N 个镜头提交到阿里云百炼/DashScope 视频生成接口。默认只提交 1 个镜头，避免一次性消耗过多额度。任务 ID 和状态会写入输出目录下的 `video_jobs.jsonl`。

输出目录示例：

```text
zhihu_fiction/output/<story>/短剧视频Prompt包_<timestamp>/
├── manifest.json
├── 改编方案.md
├── 角色一致性设定.md
├── 分集剧本.md
├── 镜头表.json
├── 视频生成Prompts.md
└── video_jobs.jsonl       # 仅 /drama_video 生成
```

`/drama` 只生成视频模型 Prompt 包，不调用视频生成 API。`/drama_video` 会提交百炼异步视频任务；后续可根据 `provider_job_id` 查询状态并下载生成视频。

## Web 服务使用

启动 FastAPI 服务：

```bash
uvicorn zhihu_fiction.server:app --reload
```

浏览器打开本地服务首页即可使用小说创作工作台。短剧视频生产使用独立页面：

```text
http://127.0.0.1:8000/video
```

`/video` 会列出已生成小说，可设置提交镜头数量并调用百炼异步视频任务。默认只提交 1 个镜头，任务 ID、状态和 `video_jobs.jsonl` 路径会显示在右侧结果栏。

主要接口：

```text
GET  /                         Web 首页
GET  /video                    短剧视频生产页面
POST /api/run                  启动一次创作任务
GET  /api/stream/{run_id}      订阅 SSE 流式进度
POST /api/run/continue         续写任务
GET  /api/runs                 查看运行历史
GET  /api/runs/{run_id}        查看单次运行详情
GET  /api/stories              查看生成作品列表
GET  /api/stories/{story_path} 查看作品内容
POST /api/drama-video          为指定作品提交百炼短剧视频任务
GET  /api/skills/genres        查看技能库题材
GET  /api/skills/{genre}       查看指定题材技能卡
GET  /api/scheduler            查看调度状态
POST /api/scheduler/start      启动定时创作
POST /api/scheduler/stop       停止定时创作
GET  /api/workspace/materials  查看 Workspace 素材库
```

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

Workspace API 位于 `/api/workspace/*`。历史 JSONL/JSON 文件存储仍作为兼容路径保留；V1 本地单机生产模式默认使用 SQLite，配置见下方“本地单机生产模式”。

主要接口：

```text
GET  /api/workspace/materials
POST /api/workspace/materials/import-scraped
POST /api/workspace/materials/manual
PATCH /api/workspace/materials/{material_id}
GET  /api/workspace/topic-cards
POST /api/workspace/topic-cards
PATCH /api/workspace/topic-cards/{card_id}
POST /api/workspace/topic-cards/{card_id}/approve
POST /api/workspace/topic-cards/{card_id}/create-task
GET  /api/workspace/tasks
POST /api/workspace/tasks/{task_id}/retry
POST /api/workspace/tasks/{task_id}/cancel
GET  /api/workspace/drafts
GET  /api/workspace/drafts/{task_id}
PATCH /api/workspace/drafts/{task_id}
POST /api/workspace/drafts/{task_id}/ready
GET  /api/workspace/packages
POST /api/workspace/packages/generate
POST /api/workspace/packages/{package_id}/confirm
GET  /api/workspace/packages/{package_id}/files
```

## 本地单机生产模式

V1 推荐使用 SQLite 作为工作台主存储，本地对象目录保存图片、视频和发布包。

```bash
cp zhihu_fiction/.env.example .env
python -m pytest zhihu_fiction/tests -q
uvicorn zhihu_fiction.server:app --reload
```

打开：

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/video
```

视频生成前会展示成本估算并要求人工确认。

## 短剧视频生产基础设施

默认本地单机模式使用本地内存队列、本地文件对象存储、SQLite workspace 持久化：

- `ZH_VIDEO_QUEUE_BACKEND=memory`
- `ZH_OBJECT_STORAGE_BACKEND=local`
- `ZH_WORKSPACE_BACKEND=sqlite`

生产环境可以逐步切换：

- Redis 队列：设置 `ZH_VIDEO_QUEUE_BACKEND=redis` 和 `REDIS_URL`
- MinIO 对象存储：设置 `ZH_OBJECT_STORAGE_BACKEND=minio`、`MINIO_ENDPOINT`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`、`MINIO_BUCKET`
- SQLite workspace：设置 `ZH_WORKSPACE_BACKEND=sqlite` 和 `ZH_WORKSPACE_SQLITE_PATH`

生产环境需要单独启动视频 worker，用于消费 Redis 中的短剧视频任务：

```bash
python -m zhihu_fiction.app.services.drama_video_worker
```

当前视频模型默认使用阿里云百炼/DashScope，可用 `EMBEDDING_API_KEY`、`DASHSCOPE_API_KEY` 或 `BAILIAN_API_KEY` 提供 API Key。

## 数据与输出

常见运行目录：

```text
zhihu_fiction/data/scraped/       抓取和手动录入的热门内容
zhihu_fiction/data/auth/          浏览器发布登录状态
zhihu_fiction/output/             生成的小说、发布包和中间结果
zhihu_fiction/output/.pipeline/   自动流水线运行历史、检查点和调度文件
```

`data/auth/` 可能包含平台登录状态，提交代码或分享项目时需要避免泄露。

## 发布与合规注意事项

- 抓取逻辑优先使用公开热榜接口，失败时可用搜索或手动录入兜底。
- 浏览器辅助发布依赖平台页面结构和账号状态，可能因平台改版或风控失效。
- 自动发布前建议人工检查标题、正文、标签、版权来源和平台规则。
- 短剧 Prompt 包是视频生成前的策划和分镜资产，接入视频模型前仍需要人工检查角色一致性、内容安全、版权来源和平台规则。
- 生成内容已经包含基础内容安全润色，但不能替代人工审核。
- 不建议把 Web 服务直接暴露到公网；如需部署，应增加认证、收紧 CORS、隐藏内部异常信息。

## 测试

运行当前项目测试：

```bash
pytest zhihu_fiction/tests
```

建议在修改以下模块后至少运行相关测试：

- `agents.py`：Agent 工具、提示词、输出格式
- `orchestrator.py`：Coordinator 输出解析和多章节上下文
- `pipeline.py`：自动流水线、评审改写、检查点和调度
- `exporter.py` / `publishers/`：发布包元数据和平台格式化
- `server.py`：API、SSE、运行状态和调度接口

## 当前适合继续改进的方向

1. **补齐结构化评审输出**：让 Reviewer 输出 JSON，便于统计、自动重写和质量看板。
2. **强化技能库版本管理**：按题材、平台、结构类型沉淀可复用创作技能。
3. **完善 Web 生产闭环**：加入任务队列、作品编辑、发布前人工确认和运行失败重试。
4. **加强测试覆盖**：增加 Fake LLM 端到端测试、发布器 mock 测试和 SSE API 测试。
5. **收紧生产安全配置**：区分开发/生产环境，限制 CORS，隐藏异常细节，保护登录状态文件。
6. **扩展业务边界**：从知乎短篇扩展到小红书故事、公众号故事、短剧脚本和网文开篇生成。

## 推荐业务定位

短期建议定位为：**AI 爆款故事生产与分发工作台**。

知乎可以作为第一个验证渠道，但系统能力更适合沉淀为跨平台内容生产工具：用热点和爆款样本做选题决策，用技能库复用创作方法，用多 Agent 工作流完成生产、评审、改写和发布包生成。
