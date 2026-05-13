# LLM Study — 多智能体应用实践

基于 DeepSeek 大模型的多智能体协作系统，面向数学建模竞赛（MCM/ICM）的全流程自动化方案。

---

## agent_app — 数模竞赛全流程助手

**6 个专业 Agent** 协作框架，覆盖从问题分析到论文写作的完整工作流。

```
DataEngineer → Modeler → Programmer → Writer → Synthesizer
                     ↓          ↓           ↑
                  Reviewer → Reviewer → Reviewer
```

### 核心特性

- **6 大智能体**：数据工程师 / 建模 / 编程 / 写作 / 评审 / 总控
- **4 种策略**：串行流水线 / 深度反思 / 快速并行 / 流式输出
- **RAG 知识库**：TF-IDF 论文检索，61 个数学专业术语自定义分词，动态阈值 + MMR 去重
- **18 个工具**：Python 沙箱执行（512MB 内存限制）、LaTeX 编译、文献检索（arXiv/Semantic Scholar/Crossref）
- **Nature Skills**：MCM/ICM 学术写作规范（去 AI 化）、Nature 期刊风格绑图模板（9 个）、模型选型速查
- **三界面**：CLI 命令行 + Streamlit GUI + FastAPI Web 界面（WebSocket 实时流式）
- **安全加固**：代码执行内存限制、危险函数拦截（os.system/eval）、错误分类重试（401/403 不重试）
- **评审改进**：LLM 语义判断替代关键词匹配，区分可重试/不可重试错误

### 启动方式

```bash
# Web 界面（推荐）
uvicorn agent_app.web.main:app --reload --port 8000

# Streamlit GUI
streamlit run agent_app/gui.py

# CLI
python -m agent_app.cli
```

详见 [agent_app/README.md](./agent_app/README.md)

---

## 最近更新 (2026-05)

### FastAPI Web 界面 + WebSocket 流式输出
`agent_app/web/` — 深色主题四栏布局，WebSocket 实时推送每个 Agent 的 token 级输出。

### Nature Skills 集成
`agent_app/nature_skills/` — 来自 [MCM-AI-Starter-Kit](https://github.com/Gunp-666/MCM-AI-Starter-Kit)。
- 写作 Agent 注入学术写作铁律（去 AI 化、摘要为王、零容忍虚构）
- 建模 Agent 注入模型选型速查（优化/预测/评价/动力系统/图网络）
- 3 个新增工具：`nature_viz_template` / `model_reference` / `writing_rules`

### RAG 检索优化
动态阈值（均值×30%）、MMR 去重、LaTeX 公式保护、61 个数学专业术语词典。

---

## 技术栈

| 技术 | 用途 |
|------|------|
| **LangChain** | Agent 框架、工具绑定、消息管理 |
| **DeepSeek V4** | 核心 LLM |
| **FastAPI + WebSocket** | Web 界面 + 实时流式输出 |
| **Streamlit** | 备选 GUI |
| **scikit-learn + jieba** | TF-IDF 论文检索 |
| **pypdf** | PDF 论文解析 |

## 快速开始

```bash
git clone git@github.com:Kobelyww/-math-modeling-agent.git
cd -math-modeling-agent
echo 'DEEPSEEK_API_KEY=你的key' > .env
pip install -r agent_app/requirements.txt
uvicorn agent_app.web.main:app --port 8000
```

## 项目结构

```
├── agent_app/
│   ├── web/                  # FastAPI Web 界面 + WebSocket 流式
│   ├── nature_skills/        # MCM 学术写作 + 可视化 + 模型选型技能包
│   ├── agents.py             # 6 个专业 Agent（已注入 Nature Skills）
│   ├── orchestrator.py       # 编排器（4 种策略 + 数据预处理）
│   ├── rag.py                # TF-IDF 知识库（动态阈值 + MMR 去重）
│   ├── tools.py              # 18 个工具（含安全沙箱 + Nature Skills 工具）
│   ├── base.py               # Agent 基类（重试 + 错误分类）
│   ├── cli.py / gui.py       # CLI + Streamlit 入口
│   └── README.md
│
├── werewolf/                 # AI 狼人杀（独立仓库）
│   └── https://github.com/Kobelyww/ai-werewolf
│
└── knowledge_base/           # 共享知识库（论文 PDF）
```
