
# LLM Study — 数模多智能体协作系统

基于 DeepSeek 大模型的 7 Agent 协作框架，面向数学建模竞赛（MCM/ICM）的全流程自动化方案。

---

## agent_app — 数模竞赛全流程助手

**7 个专业 Agent** 协作，从数据处理到最终论文交付：

```
DataEngineer → Modeler → Programmer → CodeDebugger → Writer → (Reviewer) → Synthesizer
                                      ↓ 代码审查      ↑ 评审反思环       ↓ 最终交付
                                  可运行 .py      可编译 .tex      完整论文包
```

### 核心特性

- **8 大模块**：7 个专业 Agent + Hermes 自进化引擎
- **4 种协作策略**：串行流水线 / 深度反思（LLM 语义判断退出）/ 快速并行 / 流式输出
- **产出即交付**：Programmer 输出可运行 Python 代码，Writer 输出可编译 LaTeX 论文，Synthesizer 打包最终交付
- **混合 RAG 检索**：TF-IDF 关键词匹配 + 阿里云百练 text-embedding-v2（1536 维）语义检索，加权融合
- **长短时记忆**：STM 两段式存储（compressed_prefix + recent_window）+ 多策略上下文压缩（sliding_window / summarize / hierarchical 增量合并）+ LTM（Redis Stack: RedisJSON + RediSearch，或 SQLite+FTS5 回退）+ 求解自动归档（problem/pattern/mistake 三类知识）
- **Nature Skills**：学术写作铁律、Nature 期刊绑图模板（9 个）、模型选型速查
- **18 个工具**：Python 安全沙箱（512MB 限制 + 危险函数拦截）、LaTeX 编译、文献检索（arXiv/Semantic Scholar/Crossref）
- **Hermes 自进化**：7 步文本优化管线（SELECT→BUILD→BASELINE→CONSTRAIN→OPTIMIZE→VALIDATE→DEPLOY），自动优化 Agent Prompt
- **三界面**：FastAPI Web（WebSocket 实时流式 + 代码导出/LaTeX 编译）+ Streamlit GUI + CLI
- **容错机制**：所有 Agent 调用包裹 try/except，失败时返回降级文本 + 部分结果，不会丢失已完成工作
- **终止条件系统**：6 种可组合条件（Token预算/超时/轮次/质量阈值/外部中断），评审循环自动检测
- **Token 追踪**：捕获真实 LLM prompt/completion tokens，WorkflowResult 展示费用估算和耗时
- **LLM 驱动记忆索引**：归档时自动分析 scope、importance、model_types，层级 scope 组织 + 复合重排序召回
- **状态检查点**：WorkflowResult JSON 序列化，支持中断恢复
- **安全工程**：AST 白名单计算器、错误分类重试（401/403 不重试）、LaTeX 公式分词保护
- **测试覆盖**：65 个测试（条件系统 + 记忆系统 + 压缩器 + 重试逻辑 + 自进化）

### 启动方式

```bash
# Web 界面（推荐）
uvicorn agent_app.web.main:app --reload --port 8000

# Hermes 自进化（7 步文本优化管线，自动优化 Agent Prompt）
python -m agent_app.evolution.evolve --generations 3 --tasks 5
```

详见 [agent_app/README.md](./agent_app/README.md)

---

## 最近更新 (2026-05)

| 日期 | 更新 | 说明 |
|------|------|------|
| 05-17 | 跨项目架构优化 | 借鉴 AutoGen/CrewAI/MetaGPT：Token 追踪 + 6 终止条件 + 检查点 + LLM 记忆索引 + 复合重排序 + 因果追溯 + 费用估算 |
| 05-17 | 工程质量全面升级 | 容错恢复（4 策略全包裹）、Web 死按钮修复、健康检查端点、65 测试、去重死代码清理、可配置化 |
| 05-17 | 上下文压缩机制 | 两段式 STM + 多策略压缩器（层次增量合并）+ Orchestrator 全部策略注入压缩上下文 |
| 05-16 | Hermes 自进化引擎 | 7 步管线（SELECT→DEPLOY），GEPA 优化器，多维适应度评估，Prompt 自动变异择优 |
| 05-16 | 记忆系统完善 | solve_stream 接入记忆、mistake 自动归档、print→logging、.env.example、死代码清理 |
| 05-15 | Redis Stack 记忆升级 | RedisJSON + RediSearch 全文搜索，STM TTL 持久化，Docker 一键部署，自动回退 SQLite |
| 05-14 | 长短时记忆系统 | STM 消息总线 + LTM SQLite/FTS5 持久化 + 上下文自动压缩 |
| 05-14 | 百练 Embedding RAG | text-embedding-v2 混合检索，TF-IDF + 语义加权融合 |
| 05-14 | CodeDebugger Agent | 第 7 个 Agent，代码审查 + bug 检测 + 性能建议 |
| 05-14 | 产出升级 | Programmer → 可运行 .py，Writer → 可编译 .tex |
| 05-13 | Web 界面 | FastAPI + WebSocket 流式四栏布局 + 代码导出/LaTeX 编译按钮 |
| 05-12 | Nature Skills | 学术写作规范注入 + 18 个工具（含 Nature 绑图模板） |
| 05-11 | RAG + 安全加固 | 动态阈值、MMR 去重、公式保护、沙箱内存限制、错误分类 |

---

## 技术栈

| 技术 | 用途 |
|------|------|
| **LangChain + LangGraph** | Agent 框架、消息管理 |
| **DeepSeek V4** | 核心 LLM |
| **阿里云百练 text-embedding-v2** | RAG 语义向量检索（1536 维） |
| **FastAPI + WebSocket** | Web 界面 + 实时流式输出 |
| **Redis Stack** | 短期记忆持久化（TTL）+ 长期记忆（RedisJSON + RediSearch） |
| **SQLite + FTS5** | 长期记忆回退方案（Redis 不可用时） |
| **Docker Compose** | Redis Stack 一键部署 |
| **scikit-learn + jieba** | TF-IDF 关键词检索（61 项数学词典） |
| **DashScope** | 百练 Embedding API |

## 快速开始

```bash
git clone git@github.com:Kobelyww/-math-modeling-agent.git
cd -math-modeling-agent
cp .env.example .env   # 编辑 .env 填入你的 API Key
pip install -r agent_app/requirements.txt

# 启动 Redis Stack（记忆系统后端）
docker compose up -d

uvicorn agent_app.web.main:app --port 8000
```

## 项目结构

```
agent_app/
├── web/                  # FastAPI Web 界面 + WebSocket 流式
├── nature_skills/        # MCM 学术写作 + 可视化 + 模型选型技能包
├── memory/               # 长短时记忆（两段式 STM + 多策略压缩 + Redis/SQLite）
├── evolution/            # Hermes 自进化（7 步管线 + GEPA + 适应度评估）
├── agents.py             # 7 个专业 Agent（含 CodeDebugger）
├── orchestrator.py       # 编排器（4 策略 + 容错恢复 + 6 终止条件 + 检查点 + 费用估算）
├── conditions.py          # 6 种可组合终止条件（Token/超时/轮次/质量/外部/组合）
├── rag.py                # 混合 RAG（TF-IDF + Embedding 加权融合）
├── tools.py              # 18 个工具（安全沙箱 + Nature Skills）
├── base.py               # Agent 基类（重试 + Token 提取 + normalize_llm_content）
├── cli.py / gui.py       # CLI + Streamlit 入口
├── tests/                # 65 个测试（条件 / 记忆 / 压缩器 / 重试 / 自进化）
└── README.md

docker-compose.yml        # Redis Stack 一键部署
.env.example              # 环境变量模板（复制为 .env 后填入密钥）
redis_utils.py            # 通用 Redis 工具（连接/JSON/搜索）
env_utils.py              # 环境变量加载（API Key + Redis 配置）
```
