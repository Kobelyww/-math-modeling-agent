# LLM Study — 数模多智能体协作系统

基于 DeepSeek V4 的多 Agent 协作框架，面向数学建模竞赛（MCM/ICM）的全流程自动化方案。
架构深度借鉴 Claude Code：渐进式披露、自主探索、子智能体委托、Plan-and-Execute。

---

## 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                      Orchestrator                            │
│  solve_with_plan / explore / sequential / review / parallel  │
│  渐进式技能注入 + Agent 工具调用 + 子智能体委托 + 文件生成     │
├──────────────────────────────────────────────────────────────┤
│  Phase 0: PLAN  ─ PlannerAgent 分析问题，制定结构化执行计划     │
│  Phase 1: EXECUTE ─ 各 Agent 自主调用工具，按计划执行           │
│  Phase 2: SYNTHESIZE ─ 整合 + 自动保存文件到 output/          │
├──────────────────────────────────────────────────────────────┤
│           Skill Registry (20 skills, 4 domains)              │
│      writing (9) / modeling (7) / coding (3) / data (1)     │
│         按需加载，关键词匹配，渐进式注入到 Agent Prompt         │
├──────────────────────────────────────────────────────────────┤
│  8 Specialist Agents + Tool Calling + Subagent System        │
│  Planner / DataEngineer / Modeler / Programmer / CodeDebugger│
│  Writer / Reviewer / Synthesizer                             │
│  每个 Agent 拥有定制工具集，自主调用 web_search/read_file/...  │
│  4 种子智能体（explore/research/code/general）并行委托        │
├──────────────────────────────────────────────────────────────┤
│  Memory: STM (两段式压缩) + LTM (Redis Stack / SQLite 回退)  │
│  RAG: TF-IDF + Embedding 混合检索                            │
│  文件生成: 自动提取代码/LaTeX 保存到 output/                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 核心特性

### Plan-and-Execute 架构（v2.2 默认策略）

| 阶段 | 负责 | 说明 |
|------|------|------|
| **Plan** | PlannerAgent | 分析问题 → 子问题分解 → 模型选型 → 技能识别 → 执行步骤设计 → 风险评估 |
| **Execute** | 各专业 Agent | 按计划执行，每个 Agent 自主调用工具（web_search/read_file/spawn_subagent 等） |
| **Synthesize** | SynthesizerAgent | 整合所有产出 + 自动保存文件到 `output/` 目录 |

### Agent 工具调用（v2.2）

每个 Agent 拥有定制工具集，基于 ReAct 循环自主调用，最多 3 轮工具交互：

| Agent | 可用工具 |
|-------|---------|
| **Planner** | web_search, spawn_subagent, model_reference, writing_rules, search_files, search_content, read_file |
| **Modeler** | web_search, search_arxiv, model_reference, writing_rules, read_file, search_content |
| **Programmer** | python_exec, read_file, search_files, search_content, read_csv_info, pip_install |
| **CodeDebugger** | python_exec, read_file, search_content |
| **Writer** | latex_template, latex_compile, web_search, save_note, writing_rules, read_file, list_directory |
| **Synthesizer** | spawn_subagent, web_search, search_files, search_content, read_file, list_directory, web_fetch |
| **Reviewer** | read_file, search_content, web_search |
| **DataEngineer** | read_csv_info, search_files, read_file, python_exec |

工具调用使用 `deepseek-chat`（V3）确保多轮工具调用可靠（V4 的 thinking mode 与多轮 tool calling 不兼容）。

### 渐进式技能系统（20 skills）

```
Skills Registry (20 skills, 4 domains)
├── modeling/ (7)          ← 模型选型、算法设计
│   ├── optimization      线性/整数/非线性/多目标规划
│   ├── prediction        ARIMA/LSTM/XGBoost 预测模型
│   ├── evaluation        AHP/TOPSIS/熵权法/模糊评价
│   ├── dynamics          ODE/PDE/元胞自动机/ABM
│   ├── network-graph     Dijkstra/最大流/社区发现
│   ├── sensitivity       参数扫描/蒙特卡洛/Sobol
│   └── review-criteria   7维评审量表（ARS 整合）
├── writing/ (9)           ← 学术写作、格式规范
│   ├── academic-structure MCM/ICM 论文结构标准
│   ├── latex-standards    LaTeX 编译规范
│   ├── math-notation      数学符号规范
│   ├── quality-check      去AI化词表+标点控制（ARS）
│   ├── abstract           5组件摘要模型（ARS）
│   ├── paper-structure    6种论文结构+字数分配（ARS）
│   ├── judgment           Clarity Test/So-What层级（ARS）
│   ├── latex-apa7         APA7 LaTeX模板（ARS）
│   └── raise-framework    RAISE负责任AI框架（ARS）
├── coding/ (3)            ← 算法实现、调试、可视化
└── data/ (1)              ← 数据预处理标准流程
```

### 探索工具（6 个）

| 工具 | 功能 | 类比 |
|------|------|------|
| `read_file` | 读取文件（带行号、offset/limit） | Claude Code Read |
| `search_files` | 按 glob 模式查找文件 | find -name |
| `search_content` | 正则搜索文件内容 | grep -r |
| `list_directory` | 目录列表（树形+文件大小） | ls -la |
| `web_search` | DuckDuckGo 搜索（无需 API Key） | WebSearch |
| `web_fetch` | 提取网页文本内容 | WebFetch |

### 子智能体系统（4 类型）

| 类型 | 用途 | 工具集 | 输出上限 |
|------|------|--------|----------|
| **explore** | 文件/代码探索 | read_file, search_files, search_content, list_directory | 3,000 |
| **research** | 网络/文献调研 | web_search, web_fetch, search_arxiv 等 | 5,000 |
| **code** | 代码生成/调试 | python_exec, pip_install, read_file 等 | 5,000 |
| **general** | 通用分析 | 完整工具集 | 4,000 |

- 上下文隔离，递归保护（max_depth=1）
- 并行支持（spawn_parallel）
- 使用 `deepseek-chat`（V3）确保工具调用可靠

### 自动文件生成

每次 solve 完成后自动保存到 `output/`：
```
output/
├── modeling_report.md      # 建模方案
├── solve.py                 # 提取的 Python 代码（可运行）
├── paper.tex                # 提取的 LaTeX 论文（可编译）
├── final_synthesis.md       # 最终整合报告
└── workflow_result.json     # 完整结果 JSON
```

### 更多特性

- **流式输出 + 思考过程**：所有模式自动流式输出，DeepSeek V4 的 reasoning_content 灰色显示
- **6 种求解策略**：plan / explore / sequential / review / parallel / stream
- **18 个工具**：Python 安全沙箱（512MB + 危险函数拦截）、LaTeX 编译、文献检索（arXiv/Semantic Scholar/Crossref）
- **混合 RAG**：TF-IDF 关键词匹配 + 阿里云百练 text-embedding-v2（1536 维）语义检索，加权融合
- **长短时记忆**：STM 两段式存储（compressed_prefix + recent_window）+ 多策略上下文压缩 + LTM（Redis Stack 或 SQLite+FTS5 回退）+ LLM 驱动记忆索引
- Unified IP memory and Agent DAG traces connect novel generation, short-drama adaptation, and video prompt production.
- **6 种终止条件**：Token预算 / 超时 / 轮次 / 质量阈值 / 外部中断 / 组合条件
- **容错恢复**：所有 Agent 调用包裹 try/except，失败降级 + 部分结果
- **测试覆盖**：65 个测试

---

## 快速开始

```bash
git clone git@github.com:Kobelyww/-math-modeling-agent.git
cd -math-modeling-agent
cp .env.example .env          # 编辑 .env 填入 DEEPSEEK_API_KEY
pip install -r agent_app/requirements.txt

# 启动 Redis Stack（记忆系统后端，可选）
docker compose up -d

# CLI（推荐，功能最完整）
python -m agent_app.cli
```

### CLI 命令

```
/mode plan|explore|sequential|review|parallel  切换求解策略（默认 plan）
/plan <问题>                                  仅生成求解计划，不执行
/solve <问题>                                 启动多智能体协作求解
/execute                                      基于 /plan 生成的计划执行求解
/stream                                       流式输出模式
/chat                                         单智能体对话模式（含所有工具+子智能体）
/skills                                       列出可用技能（渐进式披露）
/subagent                                     列出可用子智能体类型
/memory                                       查看记忆系统统计
/help                                         帮助
/exit                                         退出
```

---

## 项目结构

```
agent_app/
├── agents.py                 # 8 Agent（含 Planner）+ 渐进式 Prompt + 技能注入
├── orchestrator.py           # 编排器（6 策略 + 工具调用 + 文件生成 + 容错 + 终止条件）
├── base.py                   # Agent 基类（invoke/stream/invoke_with_tools + 重试 + sanitize）
├── cli.py                    # CLI（plan/explore 等 6 模式 + 流式思考展示 + 自动文件保存）
├── config.py                 # 配置管理（.env + 按 Agent 个性化）
├── llm.py                    # LLM 工厂（DeepSeek V4/V3）
├── tools.py                  # 18 个工具 + TOOLS_FULL
├── exploration.py            # 6 个探索工具
├── subagent.py               # 4 种子智能体（explore/research/code/general）+ 并行
├── conditions.py             # 6 种可组合终止条件
├── rag.py                    # 混合 RAG（TF-IDF + Embedding）
├── literature.py             # 文献检索（arXiv / Semantic Scholar / Crossref）
├── skills/
│   ├── registry.py           # 技能注册表（20 个技能）+ 解析器
│   └── academic_ars.py       # ARS 学术技能（7 个）
├── memory/
│   ├── short_term.py         # 两段式 STM
│   ├── long_term.py          # LTM（SQLite + FTS5）
│   ├── compressor.py         # 3 种压缩策略
│   ├── manager.py            # Memory 中枢 + LLM 归档分析
│   └── redis_backends.py     # Redis Stack 后端
├── evolution/                # Hermes 自进化引擎（7 步管线 + GEPA）
├── nature_skills/            # MCM 写作规范 + Nature 绑图模板
├── sandbox/                  # Docker 安全沙箱
├── web/                      # FastAPI + WebSocket Web 界面
├── tests/                    # 65 个测试
├── data/                     # RAG 索引 + 记忆 DB
└── output/                   # 求解输出（自动生成 .py/.tex/.json）
```

---

## 架构演进

| 版本 | 核心变化 |
|------|----------|
| **v2.2** | Plan-and-Execute 架构（PlannerAgent 先规划后执行）+ Agent 工具调用（ReAct 循环）+ 自动文件生成 |
| **v2.1** | 子智能体 V3 修复 + 流式思考过程展示 + surrogate 字符清洗 |
| **v2.0** | 渐进式披露技能系统（20 skills）+ 自主探索工具（6 个）+ 子智能体委托（4 类）+ solve_explore 策略 + ARS 学术技能整合 |
| v1.5 | Token 追踪 + 6 终止条件 + 检查点 + LLM 记忆索引 + 因果关系追溯 + 费用估算 |
| v1.4 | 两段式 STM + 多策略压缩器 + Redis Stack 记忆后端 |
| v1.3 | Hermes 自进化引擎 + FastAPI Web + WebSocket 流式 |
| v1.2 | Nature Skills + 18 工具 + 混合 RAG |
| v1.0 | 7 Agent 框架 + 3 种策略 + 基础工具 |

---

## 参考与致谢

- [academic-research-skills](https://github.com/Imbad0202/academic-research-skills) — ARS 插件，提供了写作质量检查、摘要模型、论文结构、评审框架、RAISE 框架等 7 个整合技能
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — 渐进式披露 + 自主探索 + 子智能体架构的灵感来源