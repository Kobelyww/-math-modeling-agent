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

- **7 大智能体**：数据工程师 / 建模 / 编程 / 代码审查 / 写作 / 评审 / 总控
- **4 种协作策略**：串行流水线 / 深度反思（LLM 语义判断退出）/ 快速并行 / 流式输出
- **产出即交付**：Programmer 输出可运行 Python 代码，Writer 输出可编译 LaTeX 论文，Synthesizer 打包最终交付
- **混合 RAG 检索**：TF-IDF 关键词匹配 + 阿里云百练 text-embedding-v2（1536 维）语义检索，加权融合
- **长短时记忆**：短期（进程内消息总线，token 超限自动压缩）+ 长期（SQLite + FTS5 全文搜索，三类知识持久化）
- **Nature Skills**：学术写作铁律、Nature 期刊绑图模板（9 个）、模型选型速查
- **18 个工具**：Python 安全沙箱（512MB 限制 + 危险函数拦截）、LaTeX 编译、文献检索（arXiv/Semantic Scholar/Crossref）
- **三界面**：FastAPI Web（WebSocket 实时流式 + 代码导出/LaTeX 编译）+ Streamlit GUI + CLI
- **安全工程**：AST 白名单计算器、错误分类重试（401/403 不重试）、LaTeX 公式分词保护

### 启动方式

```bash
# Web 界面（推荐）
uvicorn agent_app.web.main:app --reload --port 8000

# 一键进化（Hermes 风格 7 步文本优化管线）
python -m agent_app.evolution.evolve --generations 3 --games 20
```

详见 [agent_app/README.md](./agent_app/README.md)

---

## 最近更新 (2026-05)

| 日期 | 更新 | 说明 |
|------|------|------|
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
| **SQLite + FTS5** | 长期记忆持久化 + 全文搜索 |
| **scikit-learn + jieba** | TF-IDF 关键词检索（61 项数学词典） |
| **DashScope** | 百练 Embedding API |

## 快速开始

```bash
git clone git@github.com:Kobelyww/-math-modeling-agent.git
cd -math-modeling-agent
echo 'DEEPSEEK_API_KEY=你的key' >> .env
echo 'EMBEDDING_API_KEY=你的百练key' >> .env
pip install -r agent_app/requirements.txt
uvicorn agent_app.web.main:app --port 8000
```

## 项目结构

```
agent_app/
├── web/                  # FastAPI Web 界面 + WebSocket 流式
├── nature_skills/        # MCM 学术写作 + 可视化 + 模型选型技能包
├── memory/               # 长短时记忆系统（STM + LTM + 压缩）
├── evolution/            # Hermes 风格自进化管线（7 步文本优化）
├── agents.py             # 7 个专业 Agent（含 CodeDebugger）
├── orchestrator.py       # 编排器（4 种策略 + LTM 召回 + 数据预处理）
├── rag.py                # 混合 RAG（TF-IDF + Embedding 加权融合）
├── tools.py              # 18 个工具（安全沙箱 + Nature Skills）
├── base.py               # Agent 基类（重试 + 错误分类）
├── cli.py / gui.py       # CLI + Streamlit 入口
└── README.md
```
