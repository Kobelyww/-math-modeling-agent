# LLM Study — 多智能体应用实践

基于 DeepSeek 大模型的多智能体协作系统集合，涵盖数学建模、小说创作等领域的全流程自动化方案。

---

## 项目概览

| 项目 | 说明 | 核心能力 |
|------|------|----------|
| **[agent_app](./agent_app/)** | 数模多智能体协作系统 | 问题分析→模型建立→算法实现→论文写作→评审反思 |
| **[zhihu_fiction](./zhihu_fiction/)** | 知乎爆款小说创作系统 | 数据抓取→技能蒸馏→选题分析→大纲规划→创作润色→多平台发布 |
| **[werewolf](./werewolf/)** | AI 狼人杀多智能体博弈 | 12 人局引擎、信息隔离、评测复盘、自进化、自演化 |

---

## agent_app — 数模竞赛全流程助手

面向数学建模竞赛（国赛/美赛）的 **6 个专业 Agent** 协作框架。

```
DataEngineer → Modeler → Programmer → Writer → Synthesizer
                     ↓          ↓           ↑
                  Reviewer → Reviewer → Reviewer
```

- **6 大智能体**：数据工程师 / 建模 / 编程 / 写作 / 评审 / 总控
- **4 种策略**：串行流水线 / 深度反思 / 快速并行 / 流式输出
- **RAG 知识库**：TF-IDF 论文检索，61 个数学专业术语自定义分词
- **15 个工具**：Python 沙箱执行、LaTeX 编译、文献检索（arXiv/Semantic Scholar/Crossref）
- **双界面**：CLI 命令行 + Streamlit 图形界面
- **安全加固**：代码执行内存限制、危险函数拦截、错误分类重试

```bash
streamlit run agent_app/gui.py
# 或
python -m agent_app.cli
```

详见 [agent_app/README.md](./agent_app/README.md)

---

## zhihu_fiction — 知乎爆款小说工坊

从知乎热榜抓取 → 技能蒸馏 → 多 Agent 创作 → 多平台发布的完整小说生产流水线。

```
抓取热榜 → 蒸馏技能 → 选题分析 → 大纲规划 → 创作润色 → 多平台发布
```

- **6 大智能体**：选题分析 / 大纲规划 / 初稿创作 / 润色优化 / 评审质检 / 总控整合
- **3 种模式**：快速（fast）/ 精打磨（polish）/ 全流程（full）
- **技能蒸馏**：从热门文章中提取创作模式，生成按题材分类的技能卡（自动合并去重）
- **续写能力**：支持逐章续写，上文保持完整
- **自动发布**：Playwright 浏览器自动化，支持知乎盐选 + 起点中文网 + 番茄小说
- **格式导出**：各平台自动生成格式化的发布包（元数据 + 章节 + 发布指引）

```bash
python -m zhihu_fiction.cli
```

---

## 技术栈

| 技术 | 用途 |
|------|------|
| **LangChain** | Agent 框架、工具绑定、消息管理 |
| **DeepSeek V4** | 核心 LLM（通过 langchain-deepseek） |
| **Streamlit** | agent_app 图形界面 |
| **Playwright** | zhihu_fiction 浏览器自动化发布 |
| **scikit-learn + jieba** | agent_app TF-IDF 论文检索 |
| **pypdf** | PDF 论文解析 |

## 快速开始

```bash
# 1. 克隆仓库
git clone git@github.com:Kobelyww/-math-modeling-agent.git
cd -math-modeling-agent

# 2. 安装依赖
pip install -r agent_app/requirements.txt
pip install -r zhihu_fiction/requirements.txt

# 3. 配置 API Key（在项目根目录创建 .env）
echo 'DEEPSEEK_API_KEY=你的key' > .env

# 4. 运行
# 数模助手（图形界面）
streamlit run agent_app/gui.py

# 小说工坊（命令行）
python -m zhihu_fiction.cli
```

## 项目结构

```
├── agent_app/               # 数模多智能体协作系统
│   ├── agents.py            # 6 个专业 Agent 定义
│   ├── orchestrator.py      # 编排器（4 种协作策略 + 数据预处理）
│   ├── rag.py               # TF-IDF 论文知识库
│   ├── tools.py             # 15 个工具（含安全沙箱）
│   ├── literature.py        # 学术文献检索
│   ├── base.py              # Agent 基类（重试 + 错误分类）
│   ├── cli.py / gui.py      # 双界面入口
│   └── README.md            # 详细文档
│
├── zhihu_fiction/           # 知乎爆款小说创作系统
│   ├── agents.py            # 6 个创作 Agent
│   ├── orchestrator.py      # 编排器（3 种模式 + 续写）
│   ├── distiller.py         # 技能蒸馏器（自动合并）
│   ├── automator.py         # Playwright 浏览器自动化
│   ├── scraper.py           # 知乎数据抓取
│   ├── exporter.py          # 多平台发布导出
│   ├── publishers/          # 三平台发布适配器
│   └── cli.py               # 命令行入口
│
├── werewolf/                # AI 狼人杀多智能体博弈
│   ├── agents/              # 6 个角色 Agent（狼人/村民/预言家/女巫/猎人/白痴）
│   ├── orchestrator.py      # 对局协调器（黑夜/白天完整流转）
│   ├── engine.py            # 游戏引擎（行动处理、投票、胜负裁决）
│   ├── state.py             # 游戏状态 + 信息隔离 context 构建
│   ├── evaluation/          # 进阶 ②：多维评测 + 复盘 + Leaderboard
│   ├── evolution/           # 进阶 ③：自进化（分析→优化→锦标赛）
│   ├── self_modify/         # 进阶 ①：自演化（读代码→改代码→沙箱验证）
│   └── README.md
│
└── knowledge_base/          # 共享知识库（论文 PDF）
```

---

*三个项目的核心架构思想一致：Agent 基类 → 专业化 System Prompt → 编排器协调 → 工具增强。agent_app 面向严谨的数学建模，zhihu_fiction 面向创意小说创作，werewolf 面向信息不对称下的多智能体博弈。*
