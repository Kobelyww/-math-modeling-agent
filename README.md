# 数模 DeepAgent 论文生产系统

面向 MCM/ICM、国赛等数学建模竞赛的工业化论文生产工作流。系统以 DeepAgent 风格的多智能体编排为核心，将赛题理解、数据审计、模型规划、实验生成、论文起草、质量评审和提交包打包拆成可追踪、可审阅、可回滚的阶段。

当前仓库是从 `LLM-Study` 拆分出的独立项目，主代码位于 `agent_app/`。

## 当前能力

- **DeepAgent 论文工作流**：围绕 `CompetitionPaperRunner` 运行完整竞赛论文生产链路。
- **阶段产物审阅**：关键阶段会生成 review card，用户可确认继续、要求重写或停止。
- **依赖失效追踪**：前序阶段重写后，下游阶段产物会标记为 stale，避免混用旧版本产物。
- **流式 Web 体验**：通过 WebSocket 展示阶段事件、工具调用、审阅状态和产物生成进度。
- **多页面 Web 壳**：Dashboard、Paper Workflow、Review Center、Artifacts、Knowledge 分离，降低单页控制台复杂度。
- **PDF 输入与 RAG**：支持 PDF 题面抽取、知识库检索、Nature-style 写作和可视化资源。
- **多 Provider 配置**：支持 DeepSeek 和 Mimo OpenAI-compatible API。

## 项目结构

```text
agent_app/
├── deepagent/              # DeepAgent 协调、middleware、runner 集成
├── domain/                 # RunSpec、RunState、Artifact、阶段审阅等领域模型
├── services/               # run store、stage review、decision、pause/resume 服务
├── web/                    # FastAPI Web、WebSocket、Jinja templates、static assets
│   ├── templates/          # dashboard / paper / reviews / artifacts / knowledge
│   └── static/             # app.js / style.css
├── nature_skills/          # 数模论文写作、图表、PDF 处理资源
├── rag.py                  # 论文知识库检索
├── cli.py                  # CLI 入口
└── tests/                  # pytest 测试

docs/superpowers/
├── specs/                  # 需求与产品设计 spec
└── plans/                  # 分阶段实施计划
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制示例配置：

```bash
cp agent_app/.env.example agent_app/.env
```

按需配置 DeepSeek 或 Mimo：

```bash
# deepseek 或 mimo
LLM_PROVIDER=deepseek

# DeepSeek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro

# Mimo OpenAI-compatible
MIMO_API_KEY=sk-xxx
MIMO_API_BASE=https://api.xiaomimimo.com/v1
MIMO_MODEL=mimov2.5pro

DEEPSEEK_TEMPERATURE=0.3
DEEPSEEK_MAX_RETRIES=3
DEEPSEEK_RETRY_DELAY=1.0
DEEPSEEK_MAX_TOKENS=0

# 可选；未配置时默认复用当前 provider key
EMBEDDING_API_KEY=sk-xxx
```

不要提交 `.env` 或任何真实 API key。

### 3. 启动 Web 服务

```bash
uvicorn agent_app.web.main:app --reload
```

默认访问：

- `GET /`：工作台总览
- `GET /paper`：论文生产工作流
- `GET /reviews`：阶段审阅中心
- `GET /artifacts`：产物中心
- `GET /knowledge`：RAG 与 Nature Skills

### 4. 使用 CLI

```bash
python -m agent_app.cli
```

常用命令：

| 命令 | 说明 |
| --- | --- |
| `/attach <路径>` | 添加数据文件、参考文献或 PDF |
| `/paper <赛题>` | 启动论文生产工作流 |
| `/solve <问题>` | 兼容旧多智能体求解流程 |
| `/help` | 查看帮助 |
| `/exit` | 退出 |

## Web 工作流

1. 在 `/paper` 输入赛题、数据文件路径、参考文献路径或上传 PDF 题面。
2. 点击“开始论文生产”，WebSocket 会持续推送阶段事件。
3. 每个关键阶段产物进入审阅队列，用户确认后才继续。
4. 如果用户要求重写前序阶段，下游已生成产物会变为 stale。
5. 最终产物会写入 run 目录，可在产物中心查看。

输出目录：

```text
agent_app/output/runs/<run_id>/
```

典型产物包括：

- `run.json`
- 阶段审阅记录
- 实验代码和结果
- LaTeX/Markdown 论文草稿
- 最终提交包元数据

## 编程调用

```python
from agent_app import CompetitionPaperRunner, RunSpec, load_settings

settings = load_settings()
runner = CompetitionPaperRunner.from_settings(settings)

result = runner.run(RunSpec(question="建立交通流优化模型"))
print(result.run_id, result.status.value)
```

旧版 `Orchestrator` 仍作为 `/solve` 兼容路径保留。新功能优先使用 `CompetitionPaperRunner`、`RunStore` 和 stage review service。

## 测试

常用验证命令：

```bash
pytest agent_app/tests/test_stage_review_service.py \
  agent_app/tests/test_stage_review_pause_runner.py \
  agent_app/tests/test_stage_decision_service.py \
  agent_app/tests/test_web_stage_reviews.py \
  agent_app/tests/test_paper_chat_stream.py \
  agent_app/tests/test_web_pages.py -q
```

前端静态检查：

```bash
node --check agent_app/web/static/app.js
```

说明：仓库中仍保留旧版能力和迁移中的测试，完整测试集可能暴露历史快照差异。提交前至少运行与改动相关的 focused tests。

## 主要文档

- `docs/superpowers/specs/2026-06-16-agent-app-stage-review-dependency-design.md`
- `docs/superpowers/plans/2026-06-16-agent-app-stage-review-dependency.md`
- `docs/superpowers/specs/2026-06-16-agent-app-multipage-ui-design.md`
- `docs/superpowers/plans/2026-06-16-agent-app-multipage-ui.md`

## 开发状态

已完成：

- DeepAgent paper runner 基线
- 阶段审阅记录、决策、暂停/恢复
- 下游 stale 标记与决策冲突校验
- Paper chat streaming
- 多页面 Web shell

进行中：

- `/reviews`、`/artifacts`、`/knowledge` 的页面专属 JavaScript 拆分
- 只读 run state APIs：`/api/runs`、`/api/runs/{run_id}`、`/api/runs/{run_id}/stage-reviews`、`/api/runs/{run_id}/artifacts`
- 更完整的 artifact readiness 和历史版本查看

## License

MIT
