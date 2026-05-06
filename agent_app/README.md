# 数模多智能体协作系统

基于 DeepSeek 大模型的数学建模竞赛多 Agent 协作框架，提供从**问题分析 → 模型建立 → 算法实现 → 论文写作 → 评审反思**的全流程自动化支持。

## 功能概览

- **5 个专业智能体**：建模 / 编程 / 写作 / 评审 / 总控，分工协作
- **4 种协作策略**：串行流水线、评审反思迭代、快速并行、流式输出
- **RAG 知识库**：基于 TF-IDF 的论文检索增强生成，支持 PDF/MD/TXT
- **15 个工具**：Python 执行、LaTeX 编译、文献检索、数据分析、笔记管理
- **双界面**：CLI 命令行 + Streamlit 图形界面
- **文献检索**：接入 arXiv、Semantic Scholar、Crossref 三大免费学术 API
- **流式输出**：所有 Agent 支持 token 级实时流式生成
- **自动重试**：LLM 调用失败自动指数退避重试

## 项目结构

```
agent_app/
├── __init__.py          # 包入口
├── config.py            # 配置管理（.env / Agent 个性化设置）
├── llm.py               # LLM 工厂（ChatDeepSeek）
├── base.py              # Agent 基类（invoke / stream / 重试）
├── agents.py            # 五大专业 Agent + 工厂函数
├── orchestrator.py      # 编排器（4 种协作策略）
├── memory.py            # 跨 Agent 共享上下文总线
├── rag.py               # 论文知识库（TF-IDF 检索）
├── literature.py        # 学术文献检索（arXiv / Semantic Scholar / Crossref）
├── tools.py             # 工具集（15 个工具）
├── cli.py               # 命令行入口
├── gui.py               # Streamlit 图形界面入口
├── requirements.txt     # 依赖
├── output/              # 输出目录（代码执行、LaTeX 编译结果）
├── notes/               # 笔记存储
└── data/                # RAG 索引存储
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

## 五大智能体

| 智能体 | 角色 | 职责 |
|--------|------|------|
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

### 共享内存

```python
from agent_app.memory import SharedMemory

memory = SharedMemory()
result = orch.solve_sequential("问题", memory=memory)

# 查看协作历史
for entry in memory.get_round(0):
    print(entry.role, entry.content[:100])
```

## 依赖

```
langchain >= 0.3
langchain-core
langchain-deepseek
python-dotenv
scikit-learn
pypdf
jieba
streamlit
pandas          # 可选，read_csv_info 需要
```

## License

MIT
