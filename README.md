# LLM Study — 数模多智能体协作系统

基于 DeepSeek V4 的多 Agent 协作框架，面向数学建模竞赛（MCM/ICM）的全流程自动化方案。
架构深度借鉴 Claude Code：渐进式披露、自主探索、子智能体委托。

---

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                     Orchestrator                        │
│  solve_explore / sequential / review / parallel / stream│
│  渐进式技能注入 + 自主探索决策 + 子智能体委托            │
├─────────────────────────────────────────────────────────┤
│  Phase 0: Meta-decision ─ 编排器分析任务，决定探索策略     │
│  Phase 1: Auto Explore ─ 并行 spawn explore + research  │
│  Phase 2: Synthesize    ─ 整合多源发现                   │
│  Phase 3: Solve ─ Modeling → Programming → Writing → Synth│
├─────────────────────────────────────────────────────────┤
│          Skill Registry (20 skills, 4 domains)          │
│     writing (9) / modeling (7) / coding (3) / data (1)  │
│        按需加载，关键词匹配，渐进式注入到 Agent Prompt     │
├─────────────────────────────────────────────────────────┤
│  7 Specialist Agents + Subagent System (4 types)        │
│  DataEngineer / Modeler / Programmer / CodeDebugger     │
│  Writer / Reviewer / Synthesizer                        │
│  explore / research / code / general (subagents)        │
├─────────────────────────────────────────────────────────┤
│  Memory: STM (两段式压缩) + LTM (SQLite/Redis 回退)     │
│  RAG: TF-IDF + Embedding 混合检索                       │
│  6 Termination Conditions + Checkpoint Recovery         │
└─────────────────────────────────────────────────────────┘
```

---

## 核心特性

### 自主智能体（v2.0 — 借鉴 Claude Code）

| 特性 | 说明 |
|------|------|
| **渐进式披露** | 20 个按需加载技能（Skill Registry），Base Prompt 保持精简，任务相关知识按关键词匹配自动注入 |
| **自主探索** | 6 个探索工具（read_file / search_files / search_content / list_directory / web_search / web_fetch），Agent 自主判断何时使用 |
| **子智能体委托** | 4 种子智能体类型（explore / research / code / general），独立上下文运行，支持并行，自动递归保护 |
| **自主决策四步法** | 每个 Agent 遵循：分析→探索→委托→执行，默认假设信息不完整，主动搜索 |
| **先探索后求解** | solve_explore 策略：Phase 0 元分析 → Phase 1 并行子智能体探索 → Phase 2 整合 → Phase 3 求解 |

### 多智能体系统

| Agent | 角色 | 输出 |
|-------|------|------|
| **DataEngineer** | 数据预处理 | 数据清洗方案、特征工程 |
| **Modeler** | 数学建模 | 问题重述、符号表、模型构建、灵敏度分析 |
| **Programmer** | 代码实现 | 可运行 Python 代码（含 if __name__） |
| **CodeDebugger** | 代码审查 | Bug 检测、依赖检查、性能建议 |
| **Writer** | 论文写作 | 可编译 LaTeX 论文源码 |
| **Reviewer** | 专家评审 | 多维度评审报告、修改建议 |
| **Synthesizer** | 总控整合 | 最终论文包、交付物清单、创新点总结 |

### 5 种求解策略

| 策略 | 特点 | 适用场景 |
|------|------|----------|
| **explore** | 编排器自主分析→并行子智能体探索→基于富上下文求解 | **默认策略**，质量优先 |
| **sequential** | 建模→编程→写作→总控串行流水线 | 稳定可靠，简单任务 |
| **review** | 每阶段经评审专家审核后修改，支持终止条件自动退出 | 深度反思，质量敏感 |
| **parallel** | 建模先行，编程+写作并行执行 | 速度优先 |
| **stream** | 流式输出，token 级实时推送 | 交互体验 |

### 技能系统（渐进式披露）

```
Skills Registry (20 skills)
├── modeling/ (7)          ← 模型选型、算法设计
│   ├── optimization      优化类（LP/ILP/NLP/MO）
│   ├── prediction        预测类（ARIMA/LSTM/XGBoost）
│   ├── evaluation        评价类（AHP/TOPSIS/DEA）
│   ├── dynamics          动力系统（ODE/PDE/CA/ABM）
│   ├── network-graph     图论（Dijkstra/最大流/社区发现）
│   ├── sensitivity       灵敏度分析（参数扫描/蒙特卡洛）
│   └── review-criteria   7维评审量表（ARS）
├── writing/ (9)           ← 学术写作、格式规范
│   ├── academic-structure MCM/ICM 论文结构标准
│   ├── latex-standards    LaTeX 编译规范
│   ├── math-notation      数学符号规范
│   ├── quality-check      去AI化词表+标点控制（ARS）
│   ├── abstract           5组件摘要模型（ARS）
│   ├── paper-structure    6种论文结构+字数分配（ARS）
│   ├── judgment           写作判断启发法（ARS）
│   ├── latex-apa7         APA7 LaTeX模板（ARS）
│   └── raise-framework    RAISE负责任AI框架（ARS）
├── coding/ (3)            ← 算法实现、调试、可视化
│   ├── algorithms         scipy/numpy 最佳实践
│   ├── debugging          Python 常见问题清单
│   └── visualization      Nature 风格绑图规范
└── data/ (1)
    └── exploration        数据预处理标准流程
```

> 标记 (ARS) 的技能来自 [academic-research-skills](https://github.com/Imbad0202/academic-research-skills) 整合

### 探索工具（6 个）

| 工具 | 功能 | 类比 Claude Code |
|------|------|------------------|
| `read_file` | 读取文件（带行号、offset/limit） | Read |
| `search_files` | 按 glob 模式查找文件 | Bash: find -name |
| `search_content` | 正则搜索文件内容 | Bash: grep -r |
| `list_directory` | 目录列表（树形+文件大小） | Bash: ls -la |
| `web_search` | DuckDuckGo 搜索（无需 API Key） | WebSearch |
| `web_fetch` | 提取网页文本内容 | WebFetch |

### 子智能体系统（4 类型）

| 类型 | 用途 | 工具集 | 输出上限 |
|------|------|--------|----------|
| **explore** | 文件/代码探索 | read_file, search_files, search_content, list_directory | 3,000 字符 |
| **research** | 网络/文献调研 | web_search, web_fetch, search_arxiv, search_semantic_scholar, search_crossref | 5,000 字符 |
| **code** | 代码生成/调试 | python_exec, pip_install, read_file, search_files, search_content, read_csv_info | 5,000 字符 |
| **general** | 通用分析 | 完整工具集（探索+搜索+执行） | 4,000 字符 |

- 上下文隔离（子智能体看不到父智能体对话历史）
- 递归保护（max_depth=1，子智能体不能继续创建子智能体）
- 并行支持（`spawn_parallel` 同时启动多个子智能体）
- LLM 共享（与主智能体使用同一 LLM 实例）

### 更多特性

- **18 个工具**：Python 安全沙箱（512MB + 危险函数拦截）、LaTeX 编译、文献检索（arXiv/Semantic Scholar/Crossref）、Nature 绑图模板
- **混合 RAG**：TF-IDF 关键词匹配 + 阿里云百练 text-embedding-v2（1536 维）语义检索，加权融合
- **长短时记忆**：STM 两段式存储（compressed_prefix + recent_window）+ 多策略上下文压缩（sliding_window / summarize / hierarchical）+ LTM（Redis Stack: RedisJSON + RediSearch，或 SQLite+FTS5 回退）+ 求解自动归档 + LLM 驱动记忆索引
- **6 种终止条件**：Token预算 / 超时 / 轮次 / 质量阈值 / 外部中断 / 组合条件
- **Hermes 自进化**：7 步文本优化管线（SELECT→BUILD→BASELINE→CONSTRAIN→OPTIMIZE→VALIDATE→DEPLOY），自动优化 Agent Prompt
- **三界面**：FastAPI Web（WebSocket 实时流式 + 代码导出/LaTeX 编译）+ Streamlit GUI + CLI
- **容错恢复**：所有 Agent 调用包裹 try/except，失败降级文本 + 部分结果
- **状态检查点**：WorkflowResult JSON 序列化，支持中断恢复
- **Token 追踪**：捕获真实 prompt/completion tokens，费用估算 + 耗时统计
- **安全工程**：AST 白名单计算器、错误分类重试（401/403 不重试）、LaTeX 公式分词保护
- **测试覆盖**：65 个测试（条件系统 + 记忆系统 + 压缩器 + 重试逻辑 + 自进化）

---

## 技术栈

| 技术 | 用途 |
|------|------|
| **LangChain + LangGraph** | Agent 框架、消息管理、工具绑定 |
| **DeepSeek V4 Pro** | 核心 LLM |
| **阿里云百练 text-embedding-v2** | RAG 语义向量检索（1536 维） |
| **FastAPI + WebSocket** | Web 界面 + 实时流式输出 |
| **Redis Stack** | 短期记忆持久化（TTL）+ 长期记忆（RedisJSON + RediSearch） |
| **SQLite + FTS5** | 长期记忆回退方案（Redis 不可用时） |
| **Docker Compose** | Redis Stack 一键部署 |
| **scikit-learn + jieba** | TF-IDF 关键词检索（61 项数学词典） |
| **DashScope** | 百练 Embedding API |

---

## 快速开始

```bash
git clone git@github.com:Kobelyww/-math-modeling-agent.git
cd -math-modeling-agent
cp .env.example .env          # 编辑 .env 填入 DEEPSEEK_API_KEY
pip install -r agent_app/requirements.txt

# 启动 Redis Stack（记忆系统后端，可选）
docker compose up -d

# 方式 1: CLI（推荐，功能最完整）
python -m agent_app.cli

# 方式 2: Web 界面
uvicorn agent_app.web.main:app --reload --port 8000

# 方式 3: Hermes 自进化（自动优化 Agent Prompt）
python -m agent_app.evolution.evolve --generations 3 --tasks 5
```

### CLI 命令

```
/mode explore|sequential|review|parallel  切换求解策略（默认 explore）
/solve <问题>                             启动多智能体协作求解
/stream                                   流式输出模式
/chat                                     单智能体对话模式（含所有探索工具+子智能体）
/skills                                   列出可用技能（渐进式披露）
/subagent                                 列出可用子智能体类型
/memory                                   查看记忆系统统计（STM/LTM/压缩）
/compress                                 强制触发上下文压缩
/help                                     帮助
/exit                                     退出
```

---

## 项目结构

```
agent_app/
├── agents.py                 # 7 个专业 Agent + 渐进式 Prompt 构建 + 技能注入
├── orchestrator.py           # 编排器（5 策略 + 技能注入 + 自主探索 + 容错 + 终止条件 + 检查点）
├── conditions.py             # 6 种可组合终止条件（Token/超时/轮次/质量/外部/组合）
├── base.py                   # Agent 基类（invoke/stream + 自动重试 + Token 提取 + 错误分类）
├── cli.py                    # CLI 入口（支持 5 种求解模式 + 技能/子智能体查询）
├── gui.py                    # Streamlit 入口
├── config.py                 # 配置管理（.env + 按 Agent 个性化设置）
├── llm.py                    # LLM 工厂（DeepSeek Chat）
├── tools.py                  # 18 个工具 + TOOLS_FULL（含探索+子智能体）
├── exploration.py            # 6 个探索工具（文件/目录/代码/网络）
├── subagent.py               # 子智能体系统（4 类型 + 并行 + 递归保护）
├── rag.py                    # 混合 RAG（TF-IDF + Embedding 加权融合）
├── literature.py             # 文献检索工具（arXiv / Semantic Scholar / Crossref）
├── skills/
│   ├── __init__.py           # 技能系统入口
│   ├── registry.py           # 技能注册表（20 个技能） + 解析器 + 关键词匹配
│   └── academic_ars.py       # ARS 学术研究技能（7 个，整合自 academic-research-skills）
├── memory/
│   ├── __init__.py           # 记忆系统入口
│   ├── short_term.py         # 短期记忆（两段式：compressed_prefix + recent_window）
│   ├── long_term.py          # 长期记忆（SQLite + FTS5）
│   ├── compressor.py         # 上下文压缩器（3 种策略：sliding / summarize / hierarchical）
│   ├── manager.py            # 记忆管理器（协调 STM/LTM/压缩 + LLM 驱动归档分析）
│   └── redis_backends.py     # Redis Stack 后端（RedisJSON + RediSearch）
├── evolution/
│   ├── __init__.py           # 自进化引擎入口
│   ├── evolve.py             # 7 步进化管线（SELECT→BUILD→...→DEPLOY）
│   ├── gepa_optimizer.py     # GEPA 优化器（生成→评估→提升→应用）
│   ├── evaluator.py          # 多维适应度评估
│   ├── constraints.py        # 约束验证器（长度/关键词/结构）
│   └── tracker.py            # 进化过程追踪
├── nature_skills/
│   ├── Rules/                # MCM 学术写作规范（5 篇 md）
│   ├── Viz_Templates/        # Nature 期刊绑图模板（9 个 py）
│   ├── Tools/                # PDF 提取工具
│   └── loader.py             # 技能加载器（前端matter 剥离 + 缓存）
├── sandbox/
│   ├── __init__.py           # 沙箱入口
│   ├── docker_sandbox.py     # Docker 容器隔离 + 宿主机降级方案
│   └── Dockerfile            # 沙箱容器定义
├── web/
│   ├── __init__.py           # Web 入口
│   ├── main.py               # FastAPI 应用 + WebSocket 端点
│   └── routes.py             # API 路由
├── tests/
│   ├── test_core.py          # 65 测试（条件 / 记忆 / 压缩 / 重试 / Token）
│   ├── test_memory.py        # 记忆系统测试（STM / LTM / Manager）
│   └── test_evolution.py     # 自进化引擎测试
├── data/                     # RAG 索引 + 记忆数据库
├── output/                   # 求解输出（.tex / .pdf / .py / 日志）
└── README.md

docker-compose.yml            # Redis Stack 一键部署
.env.example                  # 环境变量模板
```

---

## 架构演进

| 版本 | 核心变化 |
|------|----------|
| **v2.0** | 渐进式披露技能系统（20 skills）+ 自主探索工具 + 子智能体委托 + 自主决策四步法 + solve_explore 策略 + ARS 学术技能整合 |
| v1.5 | Token 追踪 + 6 终止条件 + 检查点 + LLM 记忆索引 + 因果追溯 + 费用估算 |
| v1.4 | 两段式 STM + 多策略压缩器 + Redis Stack 记忆后端 + solve_stream 接入记忆 |
| v1.3 | Hermes 自进化引擎（7 步管线 + GEPA）+ FastAPI Web + WebSocket 流式 |
| v1.2 | Nature Skills 学术写作规范 + 18 工具 + 混合 RAG（TF-IDF + Embedding）|
| v1.1 | CodeDebugger Agent + Code Reviewer + 代码审查流程 |
| v1.0 | 7 Agent 协作框架 + 3 种协作策略 + 基础工具 |

---

## 参考与致谢

- [academic-research-skills](https://github.com/Imbad0202/academic-research-skills) — Claude Code 学术研究插件（ARS），提供了写作质量检查、摘要模型、论文结构、评审框架、RAISE 框架等 7 个整合技能
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — 渐进式披露 + 自主探索 + 子智能体架构的灵感来源
- Nature Skills 中的绑图模板和学术写作规范来自 MCM/ICM 竞赛经验积累