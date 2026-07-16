# PPT/PDF转复习提纲和考试例题智能系统

基于DeepAgent的智能系统，能够将PPT/PDF文件转化为复习提纲和考试例题。

## 功能特性

- **多智能体协作**：8个专业智能体分工协作
- **Agentic RAG**：混合检索方案，支持知识点问答解释
- **记忆系统**：短期、长期、工作记忆三层架构
- **自进化系统**：基于DSPy + GEPA的反射式进化优化
- **多模态支持**：图表理解、公式识别、表格提取

## 当前状态

项目当前处于 **MVP-0.4 核心骨架阶段**。配置、基础Agent、模型路由、解析器数据结构、知识图谱、RAG服务、记忆服务、主协调器和CLI入口已有骨架代码，但真实PDF/PPT到复习提纲和考试例题的端到端闭环尚未完成。

优先级最高的后续工作：

1. 修复测试环境，确保异步测试通过。
2. 按当前 `marker-pdf` API 适配PDF解析器。
3. 实现PDF解析、知识点抽取、提纲生成、例题生成的MVP闭环。

## 快速开始

### 安装依赖

```bash
python -m pip install -e ".[dev]"
```

### 配置环境变量

```bash
# 如需调用真实模型，创建 .env 并配置API密钥。
# 当前仓库尚未提供 .env.example，变量名以 src/config.py 为准。
touch .env
```

### 运行系统

```bash
python -m src.main
```

## 项目结构

```
newtest/
├── src/                    # 源代码
│   ├── agents/            # 智能体层
│   ├── coordinator/       # 协调器层
│   ├── knowledge/         # 知识处理
│   ├── parsers/           # 文档解析
│   ├── services/          # 服务层
│   └── utils/             # 工具函数
├── tests/                 # 测试
├── docs/                  # 文档
├── requirements.txt       # 依赖
└── README.md              # 项目说明
```

## 技术栈

- **LLM**：MiMo V2.5
- **PDF解析**：Marker
- **RAG**：LangChain + ChromaDB
- **知识图谱**：NetworkX
- **自进化**：DSPy + GEPA
- **Web框架**：FastAPI
- **正式前端**：React + TypeScript + Vite
- **内部调试台**：Streamlit

## 开发指南

### 运行测试

```bash
pytest -q
```

如果看到 `async def functions are not natively supported` 或 `Unknown pytest.mark.asyncio`，说明当前环境没有安装/加载 `pytest-asyncio`，请先确认已使用 `python -m pip install -e ".[dev]"` 安装开发依赖。

### 代码格式化

```bash
black src/ tests/
isort src/ tests/
```

### 类型检查

```bash
mypy src/
```

## 许可证

MIT License
