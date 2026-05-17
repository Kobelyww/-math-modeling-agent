# 数模多智能体协作系统

基于 DeepSeek 大模型的数学建模竞赛多 Agent 协作框架，提供从**问题分析 → 模型建立 → 算法实现 → 论文写作 → 评审反思**的全流程自动化支持。

## 功能概览

- **7 个专业智能体**：数据 / 建模 / 编程 / 审码 / 写作 / 评审 / 总控，分工协作 + 因果追溯
- **4 种协作策略**：串行流水线、评审反思迭代（6 种可组合终止条件）、快速并行、流式输出
- **RAG 知识库**：TF-IDF + Embedding 混合检索，支持 PDF/MD/TXT，PDF 图像理解
- **长短时记忆系统**：STM 两段式 + 3 策略压缩 + LTM LLM 自动索引（scope/importance）+ 复合重排序召回
- **18 个工具**：Python 安全沙箱、LaTeX 编译、文献检索、数据分析、笔记管理
- **三界面**：CLI + Streamlit GUI + FastAPI Web（WebSocket 流式 + 健康检查）
- **Token 追踪**：捕获真实 LLM token 消耗，费用估算（DeepSeek V4 定价）
- **状态检查点**：WorkflowResult JSON 序列化/反序列化，支持中断恢复
- **容错恢复**：Agent 失败返回降级文本，保留部分结果不丢失
- **自动重试**：LLM 调用失败指数退避重试（区分可重试/不可重试错误）
- **智能体自进化**：Hermes 7 步 prompt 优化 + GEPA 遗传进化
- **65 个测试**：终止条件 / 记忆系统 / 压缩器 / 重试逻辑 / 自进化

## 项目结构

```
agent_app/
├── __init__.py              # 包入口，导出 Settings / Orchestrator / WorkflowResult
├── config.py                # 配置管理（.env / Agent 个性化温度配置）
├── llm.py                   # LLM 工厂（ChatDeepSeek）
├── base.py                  # Agent 基类（invoke / stream / 重试 / 错误分类）
├── agents.py                # 7 个专业 Agent + 工厂函数
├── orchestrator.py          # 编排器（4 策略 + 6 终止条件 + 检查点 + 费用估算）
├── conditions.py            # 6 种可组合终止条件（Token/超时/轮次/质量/外部）
├── tools.py                 # 工具集（18 个工具）
├── rag.py                   # 论文知识库（TF-IDF + Embedding 混合检索）
├── literature.py            # 学术文献检索（arXiv / Semantic Scholar / Crossref）
├── cli.py                   # 命令行入口
├── gui.py                   # Streamlit 图形界面入口
├── requirements.txt         # 依赖
├── output/                  # 输出目录（代码执行、LaTeX 编译结果）
├── notes/                   # 笔记存储
├── data/                    # RAG 索引存储
├── knowledge_base/          # PDF/MD 论文知识库
├── memory/                  # 长短时记忆系统
│   ├── short_term.py        # STM：两段式消息总线（compressed_prefix + recent_window）
│   ├── long_term.py         # LTM：SQLite + FTS5 持久化知识存储
│   ├── compressor.py        # 上下文压缩器：3 种策略（sliding_window / summarize / hierarchical）
│   ├── manager.py           # MemoryManager：协调 STM / LTM / 压缩
│   └── redis_backends.py    # Redis Stack 后端（RedisJSON + RediSearch）
├── evolution/               # 智能体自进化引擎
│   ├── evolve.py            # Hermes 风格 7 步进化管道
│   ├── evaluator.py         # 多维度适应度评估
│   ├── constraints.py       # 提示词约束验证
│   ├── gepa_optimizer.py    # GEPA 遗传进化优化器
│   └── tracker.py           # 进化追踪与历史记录
├── web/                     # Web 界面（FastAPI + WebSocket）
│   ├── main.py              # FastAPI 应用
│   ├── routes.py            # REST + WebSocket 路由
│   ├── templates/           # Jinja2 模板
│   └── static/              # CSS / JS
├── sandbox/
│   └── docker_sandbox.py    # 安全代码执行沙箱
├── nature_skills/           # Nature 期刊技能资源
│   ├── Rules/               # 学术写作规则、模型参考
│   ├── Viz_Templates/       # 9 个 Nature 风格 matplotlib 模板
│   └── Tools/               # PDF 提取工具
└── tests/
    ├── test_memory.py
    └── test_evolution.py
```

## 安装

```bash
# 1. 安装依赖
pip install -r agent_app/requirements.txt

# 2. 配置 API Key（在项目根目录创建 .env）
echo 'DEEPSEEK_API_KEY=your-key-here' > .env
echo 'DEEPSEEK_API_BASE=https://api.deepseek.com' >> .env

# 3. （可选）安装 LaTeX 编译支持
# macOS:  brew install --cask mactex
# Ubuntu: sudo apt install texlive-full
```

## 快速开始

### 图形界面（推荐）

```bash
streamlit run agent_app/gui.py
# 或
python agent_app/gui.py
```

### 命令行

```bash
python -m agent_app.cli
```

进入后可使用命令：

| 命令 | 说明 |
|------|------|
| `/solve <问题>` | 启动多智能体协作分析 |
| `/mode <模式>` | 切换策略：`sequential` / `review` / `parallel` |
| `/stream` | 流式输出模式 |
| `/chat` | 切换到单智能体对话 |
| `/help` | 显示帮助 |
| `/exit` | 退出 |

### 编程调用

```python
from agent_app import load_settings, Orchestrator
from agent_app.rag import PaperRAG

settings = load_settings()
rag = PaperRAG(knowledge_dir="knowledge_base", index_path="data/rag_index.pkl")
rag.load_index()

orch = Orchestrator(settings, rag=rag)

# 串行模式
result = orch.solve_sequential("建立交通流优化模型")

# 评审反射模式
result = orch.solve_with_review("建立交通流优化模型", max_review_rounds=2)

# 流式模式（实时输出每个 token）
result = orch.solve_stream(
    "建立交通流优化模型",
    on_modeling_token=lambda t: print(t, end=""),
    on_programming_token=lambda t: print(t, end=""),
    on_writing_token=lambda t: print(t, end=""),
    on_synthesis_token=lambda t: print(t, end=""),
)

# 查看结果
print(result.format_overview())
```

## 配置说明

`.env` 文件支持的配置项：

```bash
DEEPSEEK_API_KEY=sk-xxx                    # 必填
DEEPSEEK_API_BASE=https://api.deepseek.com # API 地址
DEEPSEEK_MODEL=deepseek-v4-pro             # 模型名称
DEEPSEEK_TEMPERATURE=0.3                   # 默认温度（0-1）
DEEPSEEK_MAX_RETRIES=3                     # 失败重试次数

# 按 Agent 自定义温度（可选）
DEEPSEEK_MODELER_TEMPERATURE=0.2
DEEPSEEK_REVIEWER_TEMPERATURE=0.1
DEEPSEEK_WRITER_TEMPERATURE=0.5
```

## 协作策略

| 策略 | 命令 | 流程 | 适用场景 |
|------|------|------|----------|
| **串行流水线** | `sequential` | 建模→编程→写作→总控 | 标准场景，稳定可靠 |
| **深度反思** | `review` | 每阶段输出后评审专家审核修改 | 追求方案质量 |
| **快速并行** | `parallel` | 建模先行，编程+写作并行 | 时间紧迫，追求速度 |
| **流式输出** | streaming | 同串行，但实时 token 级输出 | 需要实时反馈 |

## 六大智能体

| 智能体 | 角色 | 职责 |
|--------|------|------|
| **DataEngineerAgent** | 数据 | 数据清洗、特征工程、探索性分析、预处理规范 |
| **ModelerAgent** | 建模 | 问题抽象、变量定义、模型建立、求解思路 |
| **ProgrammerAgent** | 编程 | 算法设计、代码实现、数值实验、复杂度分析 |
| **WriterAgent** | 写作 | 论文结构、摘要撰写、图表设计、可读性优化 |
| **ReviewerAgent** | 评审 | 发现漏洞、评估合理性、提供改进建议 |
| **SynthesizerAgent** | 总控 | 整合方案、制定计划、风险识别、TODO 清单 |

## 工具清单（15 个）

### 基础工具
| 工具 | 说明 |
|------|------|
| `calculator` | 安全的算术表达式计算器 |
| `current_time` | 获取当前时间 |
| `save_note` | 保存 Markdown 笔记 |
| `read_note` | 读取笔记 |
| `list_notes` | 列出所有笔记 |

### Python / 数据工具
| 工具 | 说明 |
|------|------|
| `python_exec` | 在子进程中执行 Python 代码（30s 超时） |
| `read_csv_info` | 读取 CSV 文件的摘要和统计信息 |
| `pip_install` | 动态安装 Python 包 |

### LaTeX 工具
| 工具 | 说明 |
|------|------|
| `latex_template` | 生成数模竞赛论文 LaTeX 模板 |
| `latex_compile` | 编译 .tex 文档为 PDF |
| `latex_render_math` | 渲染单个数学公式为 PDF 预览 |

### 文献检索工具
| 工具 | 数据源 | 说明 |
|------|--------|------|
| `search_arxiv` | arXiv API | 检索英文论文，含 PDF 链接 |
| `search_semantic_scholar` | Semantic Scholar API | 中英文检索，含开放获取 PDF |
| `search_crossref` | Crossref API | 免费不限流，含 DOI 链接 |
| `fetch_paper_to_kb` | — | 下载论文 PDF 到知识库 |

## 知识库（RAG）

### 构建索引

```bash
python -c "
from agent_app.rag import PaperRAG
from pathlib import Path

rag = PaperRAG(
    knowledge_dir=Path('knowledge_base'),
    index_path=Path('agent_app/data/rag_index.pkl')
)
stats = rag.build_index()
print(f'已索引 {stats[\"files\"]} 个文件，{stats[\"chunks\"]} 个片段')
"
```

或在 GUI 侧边栏点击「重建 RAG 索引」。

### 检索测试

```python
# 中文检索使用 jieba 分词
hits = rag.query("层次分析法怎么使用", top_k=5)
for h in hits:
    print(f"[{h.source}] {h.content[:100]}...")
```

### 文献检索 + 知识库工作流

```
1. search_arxiv("traffic flow optimization")
2. fetch_paper_to_kb("https://arxiv.org/pdf/xxx.pdf", "traffic_flow")
3. 重建 RAG 索引
4. 在协作分析中启用 RAG，智能体将自动使用检索到的论文内容
```

## 高级用法

### 自定义 Agent

```python
from agent_app.base import BaseAgent

class CustomAgent(BaseAgent):
    role = "定制智能体"
    system_prompt = "你的自定义系统提示..."

agent = CustomAgent(llm, max_retries=3)
result = agent.invoke("你的问题")
result = agent.stream("你的问题", on_token=lambda t: print(t, end=""))
```

### 长短时记忆系统

```python
from agent_app.memory import MemoryManager, SharedMemory, CompressStrategy

# 完整记忆管理器（含上下文压缩）
mm = MemoryManager(
    llm=llm,
    stm_max_tokens=50000,           # STM token 上限
    recent_window_size=5,           # 保留最近 5 条完整消息
    compress_trigger=30000,         # 超过 30000 token 触发压缩
    compress_rounds=3,              # 每 3 轮触发压缩
    compress_strategy=CompressStrategy.hierarchical,  # 增量合并策略
)

# 记录消息（自动检测压缩）
mm.remember("modeling", "使用 NS 模型进行交通流建模...")

# 获取格式化上下文（含压缩摘要 + 最近消息）
context = mm.get_context(max_tokens=3000)

# 手动触发压缩
mm.force_compress()

# 查看统计
print(mm.stats())
# {'stm_messages': 12, 'stm_tokens': 28450, 'stm_has_compressed_prefix': True,
#  'compressions': 2, 'ltm_total': 45, 'ltm_by_type': {...}}

# 长期记忆召回（SQLite FTS5 全文搜索）
ltm_context = mm.recall("交通流优化", top_k=3)
```

### 上下文压缩机制

当长时间协作中 Agent 消息积累过多时，自动压缩旧消息防止 token 溢出。

**两段式 STM 架构**：
```
[compressed_prefix] ← LLM 增量摘要旧消息（每次压缩与已有摘要合并）
[recent_window]     ← 最近 N 条完整消息（保留完整细节）
```

**三种压缩策略**：

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `sliding_window` | 仅保留最近 N 条，丢弃旧消息 | 快速，无 LLM 成本 |
| `summarize` | LLM 一次性摘要所有旧消息 | 标准压缩 |
| `hierarchical` | 旧摘要 + 新消息 → LLM 合并为新摘要 | 长对话，推荐默认 |

**触发条件**（任一满足即触发）：
- Token 阈值：STM 总 token 超过 `compress_trigger`（默认 30000）
- 轮次阈值：距上次压缩超过 `compress_rounds` 轮（默认 3 轮）

**Orchestrator 集成**：所有协作策略的后阶段（Writer、Synthesizer、评审细化）自动注入压缩后的 STM 上下文，让后期 Agent 了解完整协作历史而不会超出 token 限制。

## 依赖

```
langchain
langchain-core
langchain-deepseek
python-dotenv
scikit-learn
pypdf
jieba
streamlit
fastapi
uvicorn
jinja2
redis[hiredis]  # 可选，Redis Stack 记忆后端需要
pytest
PyMuPDF
numpy
pandas
dashscope       # 可选，百练 Embedding / Qwen-VL 需要
```

## 更新日志

### 2026-05-17：跨项目架构优化（借鉴 AutoGen / CrewAI / MetaGPT）

**Token 追踪与终止条件（AutoGen）**
- `extract_token_usage()` 从 LLM 响应提取真实 prompt/completion tokens
- `AgentMessage` 新增 `prompt_tokens`、`completion_tokens`、`triggered_by` 字段
- 新建 `conditions.py`：6 种可组合终止条件（`MaxRound`、`TokenBudget`、`Timeout`、`QualityThreshold`、`External`、`Compound`）
- `solve_with_review` 每轮检查终止条件，任一触发即优雅退出
- `WorkflowResult.save_state()` / `load_state()` JSON 检查点，支持中断恢复

**LLM 驱动记忆索引（CrewAI）**
- `MemoryManager._analyze_for_archive()` 调用 LLM 自动提取 `scope`、`importance`、`model_types`
- LTM 新增 `importance`/`scope` 字段，层级 scope 组织 + `search_by_scope()` 前缀搜索
- 复合重排序：FTS5 rank + 时间衰减（180 天半衰期）+ 访问热度 + 重要性
- 过采样因子 2x + `adaptive_recall()` 置信度驱动加深搜索

**因果追溯与成本追踪（MetaGPT）**
- `AgentMessage.triggered_by` 记录上游 Agent，`format_for_context()` 展示 ← 追溯链
- `create_llm()` 支持 `max_tokens`，`.env` 支持 `DEEPSEEK_{ROLE}_MAX_TOKENS` 按 Agent 限制
- `WorkflowResult` 统计 `total_prompt_tokens`、`total_completion_tokens`、`estimated_cost_usd`、`elapsed_seconds`
- DeepSeek V4 定价费用估算（$0.27/1M prompt + $1.10/1M completion）

**测试 49 → 65**（新增 16 个：终止条件、Token 提取、AgentMessage 字段）

### 2026-05-17：工程质量全面升级

**Orchestrator 容错恢复**
- `_safe_invoke` / `_safe_stream` 包裹所有 Agent 调用，失败返回降级文本而非崩溃
- `WorkflowResult` 新增 `errors` 字段追踪错误，`format_overview()` 展示错误摘要
- 并行策略中 ThreadPoolExecutor 异常独立捕获，编程/写作不会互相影响

**Web 界面修复**
- 实现 5 个无效按钮：运行代码、导出 .py、编译 LaTeX PDF、导出 .tex、打包下载全部
- 新增 `GET /api/health` 和 `GET /api/status` 端点，含记忆统计
- `_active_tasks` 加 `asyncio.Lock` 解决并发竞态，任务 600s 超时保护

**代码去重**
- `normalize_llm_content()` 提取到 `base.py`，compressor / gepa / cli 统一复用
- `ConstraintCheck` 合并到 `constraints.py`（含 `summary()` 方法），移除 `evaluator.py` 重复定义

**死代码清理**
- 移除 `nature_skills/loader.py` 中未使用的 `load_tool()`、`get_summary_template()`
- 移除 `cli.py` 中未使用的 `build_rag_index()`

**配置增强**
- `Settings` 新增 `retry_delay`、`tool_timeout`、`sandbox_memory_mb`，支持 .env 覆盖
- `requirements.txt` 补全 `dashscope`、`numpy`、`pandas`

**测试**
- 新增 `test_core.py`（26 个测试）：`normalize_llm_content`、重试分类、分段 STM、压缩策略触发
- 全部 49 个测试通过

**CLI 增强**
- 新增 `/compress` 命令手动触发上下文压缩
- `/memory` 显示压缩前缀状态
- 帮助文本补充 `/stream` 命令

### 2026-05-17：上下文压缩机制

**两段式 STM 存储**
- STM 改为 `compressed_prefix` + `recent_window` 两段式结构
- `compress_older()`：将超出窗口的旧消息提取为文本，同时清理 token 计数
- `format_context()`：返回压缩前缀 + 最近消息的整合视图，自动控制 token 预算

**多策略压缩器**
- 三种策略：`sliding_window`（纯截断）、`summarize`（LLM 一次性摘要）、`hierarchical`（增量合并，默认）
- 增量压缩提示词：已有摘要 + 新消息 → 合并为新摘要，保留关键脉络
- 新增轮次触发：每 N 轮自动压缩一次（默认 3 轮），与 token 阈值组合判断
- `force_compress()`：支持手动触发压缩

**Orchestrator 集成**
- 新增 `_build_prompt()` 统一提示词构建方法，自动注入 STM 压缩上下文
- 新增 `_get_stm_context()` 获取带压缩摘要的格式化文本
- 所有四种策略（sequential/review/parallel/stream）的后期阶段均注入压缩上下文
- 前期阶段（Modeler/Programmer）仍获取完整直接依赖输出，不影响方案质量

**Redis 兼容**
- `RedisSharedMemory` 支持 `compressed_prefix` 序列化/反序列化
- `compress_older` / `set_compressed_prefix` 自动持久化到 Redis JSON

### 2026-05-12：工程质量升级

**RAG 检索优化**
- 注入 61 个数模领域专有术语到 jieba 分词词典（如"层次分析法""NSGA-II""Pareto前沿"），避免被错误切分
- 动态相似度阈值：取检索结果平均分的 30% 作为下限，自动过滤噪音
- MMR 去重：相邻 chunk 内容重合度 > 50% 时只保留得分更高的，节省上下文空间
- LaTeX 公式保护：索引时用占位符替换公式，分词后再恢复，避免 `$x_i^k$` 被切成碎片

**重试机制优化**
- 区分可重试错误（429/5xx/网络超时）和不可重试错误（401/403/context length exceeded）
- 不可重试错误立即抛出，不再浪费重试次数和等待时间
- 重试时打印等待时间，方便调试

**评审退出条件改进**
- 原先用脆弱的关键词匹配 `"无问题" in review` 判断是否继续评审
- 改为调用 LLM 做语义判断（`_review_needs_revision`），不依赖特定措辞

**`python_exec` 安全加固**
- 执行前注入安全前导代码：512MB 内存上限（`resource.setrlimit`）
- 拦截 `os.system`、`eval`、`exec`、`subprocess.Popen` 等危险调用
- 文件写操作限制在沙箱目录内

**新增 DataEngineerAgent**
- 第六个专业智能体，负责赛题数据的清洗、探索与特征工程
- 输出结构：数据概况 → 清洗方案 → 特征工程 → 可视化建议 → 格式规范 → 风险提示
- 所有策略方法新增 `enable_data_engineer` 参数，按需启用
- 配置支持 `DEEPSEEK_DATA_ENGINEER_TEMPERATURE` 单独调温

**安全沙箱 (`python_exec`)**
```python
# 自动注入的安全限制
- 内存上限 512MB (resource.RLIMIT_AS)
- 禁用 os.system / eval / exec / __import__
- 文件写入限制在 output/ 目录
```

## License

MIT
