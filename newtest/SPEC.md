# PPT/PDF转复习提纲和考试例题智能系统设计文档

## 1. 项目概述

### 1.1 项目目标
构建一个基于DeepAgent的智能系统，能够将PPT/PDF文件转化为复习提纲和考试例题，支持理工科内容，具备Agentic RAG系统、记忆系统和自进化系统。使用MiMo V2.5作为基座大模型，支持多模态解析。

### 1.2 核心特性
- **多智能体协作**：8个专业智能体分工协作（文档解析、内容理解、知识提取、提纲生成、例题生成、质量评估、自进化、人工审核）
- **层级协调器架构**：主协调器管理子协调器
- **Agentic RAG系统**：支持理工科公式和图表的检索增强生成
- **记忆系统**：短期、长期、工作记忆三层架构
- **自进化系统**：Hermes 7步进化管道
- **Human-in-Loop**：混合评估模式
- **结构化输出**：支持Markdown、LaTeX、JSON格式
- **MCP服务集成**：按需集成各种服务

### 1.3 MVP边界与状态定义

当前项目处于 **MVP-0.4：核心骨架阶段**。已有代码主要完成配置、数据结构、基础类和测试骨架；尚未达到“可将真实PPT/PDF稳定转换为复习提纲和考试例题”的功能闭环。

后续实现和验收统一使用以下状态词，避免“接口存在”被误判为“功能完成”：

| 状态 | 含义 | 可进入下一阶段的条件 |
|------|------|----------------------|
| 骨架完成 | 类、接口、数据结构或占位流程存在 | 有单元测试覆盖基本初始化和数据模型 |
| 可用完成 | 能处理真实输入并返回真实业务输出 | 有fixture或mock驱动的行为测试，不返回固定占位文本 |
| 已验收 | 满足本spec的功能、质量、测试和文档标准 | 指定验收命令全部通过，并完成Spec审查和质量审查 |

MVP-1的目标收敛为：输入一个PDF样本文档，完成解析、知识点抽取、复习提纲生成和基础例题生成；PPT解析、Web UI、MCP集成、自进化系统作为后续迭代，不阻塞MVP-1闭环。

## 2. 系统架构

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    用户界面层 (UI Layer)                      │
├─────────────────────────────────────────────────────────────┤
│  CLI界面  │  Web界面  │  API接口  │  MCP客户端               │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    协调器层 (Coordinator Layer)               │
├─────────────────────────────────────────────────────────────┤
│  主协调器 (MainCoordinator)  │  子协调器 (SubCoordinators)   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    智能体层 (Agent Layer)                     │
├─────────────────────────────────────────────────────────────┤
│  文档解析Agent │ 内容理解Agent │ 提纲生成Agent │ 例题生成Agent │
│  知识提取Agent │ 质量评估Agent │ 自进化Agent   │ 人工审核Agent │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    服务层 (Service Layer)                     │
├─────────────────────────────────────────────────────────────┤
│  RAG服务 │ 记忆服务 │ 进化服务 │ 评估服务 │ 工具服务         │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    基础设施层 (Infrastructure Layer)          │
├─────────────────────────────────────────────────────────────┤
│  LLM服务 │ 向量数据库 │ 文件系统 │ 缓存 │ 日志              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 协调器层

**主协调器 (MainCoordinator)**
- **职责**：整体流程控制、子协调器管理、错误恢复
- **接口设计**：
  ```python
  class MainCoordinator:
      def __init__(self, sub_coordinators: dict[str, SubCoordinator], memory_service: MemoryService):
          self.sub_coordinators = sub_coordinators
          self.memory_service = memory_service
          self.state = CoordinatorState()

      async def invoke(self, request: CoordinatorRequest) -> CoordinatorResponse:
          """执行协调流程"""

      async def stream(self, request: CoordinatorRequest, callback: Callable) -> None:
          """流式执行协调流程"""

      async def checkpoint(self) -> None:
          """保存检查点"""

      def get_status(self) -> CoordinatorStatus:
          """获取协调器状态"""
  ```
- **状态管理**：
  ```python
  class CoordinatorState:
      def __init__(self):
          self.current_stage: str = "idle"
          self.completed_stages: list[str] = []
          self.results: dict[str, Any] = {}
          self.errors: list[Error] = []
          self.checkpoints: list[Checkpoint] = []

      def advance_stage(self) -> None:
          """推进到下一阶段"""

      def save_checkpoint(self) -> Checkpoint:
          """保存检查点"""

      def restore_checkpoint(self, checkpoint: Checkpoint) -> None:
          """恢复检查点"""
  ```

**子协调器**：
1. **文档处理协调器**：
   ```python
   class DocumentProcessingCoordinator(SubCoordinator):
       async def process(self, document: Document) -> ProcessedDocument:
           """处理文档：解析、提取、结构化"""

       async def parse_pdf(self, pdf_path: str) -> ParsedContent:
           """解析PDF文件"""

       async def parse_ppt(self, ppt_path: str) -> ParsedContent:
           """解析PPT文件"""
   ```

2. **内容生成协调器**：
   ```python
   class ContentGenerationCoordinator(SubCoordinator):
       async def generate(self, knowledge_graph: KnowledgeGraph, requirements: Requirements) -> GeneratedContent:
           """生成内容：提纲、例题"""

       async def generate_outline(self, knowledge_graph: KnowledgeGraph) -> Outline:
           """生成复习提纲"""

       async def generate_questions(self, knowledge_points: list[KnowledgePoint], difficulty: DifficultyLevel) -> list[Question]:
           """生成考试例题"""
   ```

3. **质量控制协调器**：
   ```python
   class QualityControlCoordinator(SubCoordinator):
       async def evaluate(self, content: GeneratedContent, source: ProcessedDocument) -> QualityReport:
           """评估内容质量"""

       async def review(self, content: GeneratedContent) -> ReviewResult:
           """人工审核"""

       async def approve(self, content: GeneratedContent) -> ApprovalResult:
           """批准内容"""
   ```

4. **自进化协调器**：
   ```python
   class SelfEvolutionCoordinator(SubCoordinator):
       async def optimize(self, target: str, eval_source: str = "synthetic") -> OptimizationResult:
           """优化目标（技能、工具描述、提示词）"""

       async def evaluate_optimization(self, before: BaselineMetrics, after: OptimizedMetrics) -> bool:
           """评估优化效果"""

       async def deploy_optimization(self, optimization: Optimization) -> DeploymentResult:
           """部署优化结果"""
   ```

#### 2.2.2 智能体层

**文档解析Agent**
- **输入**：PPT/PDF文件路径
- **输出**：结构化内容（章节、知识点、公式、图表）
- **工具**：PDF解析器、PPT解析器、OCR工具
- **接口设计**：
  ```python
  class DocumentParsingAgent(BaseAgent):
      role = "文档解析专家"
      system_prompt = """你是一个专业的文档解析专家，能够从PPT和PDF文件中提取结构化内容。
      你需要识别章节结构、知识点、数学公式、图表和表格。"""

      async def invoke(self, file_path: str) -> ParsedDocument:
          """解析文档"""

      async def extract_formulas(self, text: str) -> list[Formula]:
          """提取数学公式"""

      async def extract_tables(self, content: Any) -> list[Table]:
          """提取表格数据"""
  ```

**内容理解Agent**
- **输入**：结构化内容
- **输出**：知识图谱、概念关系、重点难点
- **工具**：NLP工具、概念提取器
- **接口设计**：
  ```python
  class ContentUnderstandingAgent(BaseAgent):
      role = "内容理解专家"
      system_prompt = """你是一个内容理解专家，能够从结构化内容中构建知识图谱。
      你需要识别概念、术语、公式，以及它们之间的关系。"""

      async def invoke(self, content: ParsedDocument) -> KnowledgeGraph:
          """构建知识图谱"""

      async def identify_concepts(self, text: str) -> list[Concept]:
          """识别概念"""

      async def extract_relationships(self, concepts: list[Concept]) -> list[Relationship]:
          """提取关系"""
  ```

**提纲生成Agent**
- **输入**：知识图谱、用户需求
- **输出**：复习提纲（Markdown/LaTeX格式）
- **工具**：模板引擎、格式转换器
- **接口设计**：
  ```python
  class OutlineGenerationAgent(BaseAgent):
      role = "提纲生成专家"
      system_prompt = """你是一个提纲生成专家，能够根据知识图谱生成结构清晰的复习提纲。
      你需要包含核心概念、关键公式、注意事项和复习建议。"""

      async def invoke(self, knowledge_graph: KnowledgeGraph, requirements: Requirements) -> Outline:
          """生成复习提纲"""

      async def format_outline(self, outline: Outline, format: OutputFormat) -> str:
          """格式化提纲"""
  ```

**例题生成Agent**
- **输入**：知识点、难度要求
- **输出**：考试例题（选择题、填空题、解答题）
- **工具**：题目生成器、答案验证器
- **接口设计**：
  ```python
  class QuestionGenerationAgent(BaseAgent):
      role = "例题生成专家"
      system_prompt = """你是一个例题生成专家，能够根据知识点生成高质量的考试例题。
      你需要生成不同类型的题目（选择题、填空题、解答题），并确保答案正确。"""

      async def invoke(self, knowledge_points: list[KnowledgePoint], difficulty: DifficultyLevel, question_type: QuestionType) -> Question:
          """生成考试例题"""

      async def verify_answer(self, question: Question, answer: Answer) -> bool:
          """验证答案正确性"""
  ```

**知识提取Agent**
- **输入**：原始文档内容
- **输出**：结构化知识点
- **工具**：实体识别、关系抽取
- **接口设计**：
  ```python
  class KnowledgeExtractionAgent(BaseAgent):
      role = "知识提取专家"
      system_prompt = """你是一个知识提取专家，能够从原始文档内容中提取结构化知识点。
      你需要识别核心概念、重要公式、关键步骤和注意事项。"""

      async def invoke(self, content: str) -> list[KnowledgePoint]:
          """提取知识点"""

      async def categorize_knowledge(self, points: list[KnowledgePoint]) -> dict[str, list[KnowledgePoint]]:
          """分类知识点"""
  ```

**质量评估Agent**
- **输入**：生成的内容
- **输出**：质量评分、改进建议
- **工具**：评估指标、对比分析
- **接口设计**：
  ```python
  class QualityEvaluationAgent(BaseAgent):
      role = "质量评估专家"
      system_prompt = """你是一个质量评估专家，能够评估生成内容的质量。
      你需要评估准确性、完整性、可读性，并提供改进建议。"""

      async def invoke(self, content: GeneratedContent, source: ProcessedDocument) -> EvaluationResult:
          """评估内容质量"""

      async def suggest_improvements(self, evaluation: EvaluationResult) -> list[Improvement]:
          """提供改进建议"""
  ```

**自进化Agent**
- **输入**：用户反馈、质量评估
- **输出**：优化的提示词、改进的策略
- **工具**：DSPy + GEPA优化器
- **接口设计**：
  ```python
  class SelfEvolutionAgent(BaseAgent):
      role = "自进化专家"
      system_prompt = """你是一个自进化专家，能够使用DSPy + GEPA优化系统性能。
      你需要分析当前问题，生成改进候选，评估效果，并部署最佳方案。"""

      async def invoke(self, target: str, eval_source: str = "synthetic") -> EvolutionResult:
          """执行自进化"""

      async def analyze_current_issues(self, target: str) -> list[Issue]:
          """分析当前问题"""

      async def generate_candidates(self, issues: list[Issue]) -> list[Candidate]:
          """生成改进候选"""
  ```

**人工审核Agent**
- **输入**：待审核内容
- **输出**：审核结果、修改建议
- **工具**：审核界面、反馈收集
- **接口设计**：
  ```python
  class HumanReviewAgent(BaseAgent):
      role = "人工审核协调员"
      system_prompt = """你是一个人工审核协调员，能够协调人工审核流程。
      你需要收集审核意见，整合反馈，并提供修改建议。"""

      async def invoke(self, content: GeneratedContent) -> ReviewResult:
          """协调人工审核"""

      async def collect_feedback(self, content: GeneratedContent) -> list[Feedback]:
          """收集审核反馈"""

      async def integrate_feedback(self, feedback: list[Feedback]) -> IntegratedFeedback:
          """整合反馈"""
  ```

#### 2.2.3 服务层

**RAG服务（分阶段混合方案：普通RAG + Graph RAG-lite + Agentic RAG + 自动路由）**

本项目需要实验多种RAG策略，但必须分阶段推进。MVP-1建立普通RAG baseline与评测雏形，MVP-2只在Web产品雏形中接入普通RAG，MVP-3引入Graph RAG-lite，MVP-4再引入Agentic RAG和自动路由。所有策略必须共享同一套评测集，不能仅凭主观效果决定上线。

**架构设计**：
```
┌─────────────────────────────────────────────────────────────┐
│                    查询处理层 (Query Processing)             │
├─────────────────────────────────────────────────────────────┤
│  查询分析  │  查询重写  │  查询澄清  │  对话历史摘要          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    检索策略层 (Retrieval Strategy)            │
├─────────────────────────────────────────────────────────────┤
│  普通RAG检索  │  Graph RAG-lite  │ Agentic RAG │ 自动路由    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    知识处理层 (Knowledge Processing)          │
├─────────────────────────────────────────────────────────────┤
│  知识图谱  │  知识点提取  │  知识点问答解释  │  上下文压缩      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    生成层 (Generation Layer)                  │
├─────────────────────────────────────────────────────────────┤
│  回答生成  │  引用生成  │  质量评估  │  自我纠正              │
└─────────────────────────────────────────────────────────────┘
```

**核心组件**：

0. **统一RAG策略接口**：
   ```python
   class RetrievalMode(Enum):
       SIMPLE = "simple_rag"
       GRAPH = "graph_rag_lite"
       AGENTIC = "agentic_rag"
       HYBRID = "hybrid"

   @dataclass
   class RetrievalDecision:
       mode: RetrievalMode
       reason: str
       confidence: float
       estimated_cost: str  # "low" | "medium" | "high"

   class BaseRetriever(ABC):
       @abstractmethod
       async def retrieve(self, query: str, context: RetrievalContext) -> RetrievalResult:
           """返回带来源引用的检索结果"""
   ```

1. **查询处理模块**：
   ```python
   class QueryProcessor:
       def __init__(self, llm, conversation_memory):
           self.llm = llm
           self.conversation_memory = conversation_memory

       async def analyze_query(self, query: str) -> QueryAnalysis:
           """分析查询：判断是否清晰、是否需要澄清"""

       async def rewrite_query(self, query: str, context: str) -> list[str]:
           """重写查询：将模糊查询转换为清晰的检索查询"""

       async def clarify_query(self, query: str) -> str:
           """澄清查询：当查询不明确时请求用户澄清"""
   ```

2. **检索策略模块**：
   ```python
   class RetrievalStrategy:
       def __init__(self, vector_store, knowledge_graph):
           self.vector_store = vector_store
           self.knowledge_graph = knowledge_graph

       async def simple_rag_retrieval(self, query: str, top_k: int = 5) -> list[Chunk]:
           """普通RAG检索：基于关键词/向量相似度，适合定义、原文定位、公式查询"""

       async def graph_rag_lite_retrieval(self, query: str, max_hops: int = 2) -> GraphRetrievalResult:
           """Graph RAG-lite：基于知识点图谱扩展前置知识、相关概念、章节依赖"""

       async def agentic_rag_retrieval(self, query: str, max_iterations: int = 3) -> AgenticResult:
           """Agentic RAG：用于跨章节综合、出题、比较、推理等复杂任务"""

       async def hybrid_retrieval(self, query: str, strategy: str = "auto") -> HybridResult:
           """混合检索：根据查询类型、成本、置信度自动选择策略"""
   ```

3. **Graph RAG-lite模块**：
   ```python
   class GraphRAGLiteRetriever(BaseRetriever):
       def __init__(self, knowledge_graph: KnowledgeGraph, chunk_store: ChunkStore):
           self.knowledge_graph = knowledge_graph
           self.chunk_store = chunk_store

       async def retrieve(self, query: str, context: RetrievalContext) -> RetrievalResult:
           """围绕命中的知识点进行图谱扩展并回收源文档chunk"""

       def find_seed_points(self, query: str) -> list[KnowledgePoint]:
           """从查询中匹配概念、公式、章节标题作为图检索种子"""

       def expand_neighbors(self, seed_ids: list[str], max_hops: int = 2) -> list[KnowledgePoint]:
           """扩展前置、依赖、包含、相似、应用关系"""
   ```

   Graph RAG-lite的目标不是一开始替代完整GraphRAG框架，而是复用项目已有 `KnowledgeGraph`，为学习任务提供可解释的概念依赖和复习路径。

4. **知识点问答解释模块**：
   ```python
   class KnowledgeQAExplainer:
       def __init__(self, llm, knowledge_graph):
           self.llm = llm
           self.knowledge_graph = knowledge_graph

       async def explain_knowledge_point(self, point: KnowledgePoint, context: str) -> Explanation:
           """解释单个知识点"""

       async def explain_with_examples(self, point: KnowledgePoint, examples: list[Example]) -> Explanation:
           """通过示例解释知识点"""

       async def explain_prerequisites(self, point: KnowledgePoint) -> PrerequisiteExplanation:
           """解释前置知识"""

       async def explain_connections(self, point: KnowledgePoint) -> ConnectionExplanation:
           """解释知识点之间的联系"""
   ```

**检索策略选择逻辑**：
```python
class RetrievalStrategySelector:
    def __init__(self, llm=None):
        self.llm = llm

    async def select_strategy(self, query: str, query_type: str, user_preference: str = "balanced") -> RetrievalDecision:
        """根据查询类型选择检索策略"""
        if query_type in ["definition", "formula_lookup", "page_lookup", "simple_fact"]:
            return RetrievalDecision(RetrievalMode.SIMPLE, "简单定位或定义查询", 0.90, "low")
        elif query_type in ["prerequisite", "concept_relation", "review_path"]:
            return RetrievalDecision(RetrievalMode.GRAPH, "需要知识点关系或前置路径", 0.85, "medium")
        elif query_type in ["cross_chapter_reasoning", "question_generation", "comparison", "diagnosis"]:
            return RetrievalDecision(RetrievalMode.AGENTIC, "需要多步检索、推理或生成计划", 0.80, "high")
        else:
            return RetrievalDecision(RetrievalMode.HYBRID, "查询类型不确定，先低成本检索再升级", 0.60, "medium")
```

**自动路由规则**：
| 查询意图 | 示例 | 默认策略 | 升级条件 |
|----------|------|----------|----------|
| 定义/原文定位 | “什么是特征值？” | 普通RAG | 无结果或引用置信度低 |
| 公式/页码查询 | “链式法则公式在哪？” | 普通RAG | 公式被拆分或多处冲突 |
| 前置知识 | “学矩阵特征值前要会什么？” | Graph RAG-lite | 图谱节点不足 |
| 概念联系 | “导数和梯度有什么关系？” | Graph RAG-lite | 需要跨章节推理 |
| 综合出题 | “基于第2章和第4章出一道综合题” | Agentic RAG | 默认就是高成本路径 |
| 对比/诊断 | “这两个方法为什么结果不同？” | Agentic RAG | 默认就是高成本路径 |

**混合RAG工作流程**：
```
用户查询 → 查询分析 → 查询重写 → 检索策略选择
    ↓
[普通RAG路径] → 向量检索 → 相关性过滤 → 上下文构建 → 回答生成
    ↓
[Graph RAG-lite路径] → 知识点命中 → 图谱邻居扩展 → 源chunk回收 → 关系解释
    ↓
[Agentic RAG路径] → 任务分解 → 多轮检索 → 自我纠正 → 上下文压缩 → 回答生成
    ↓
[自动路由路径] → 低成本尝试 → 置信度评估 → 必要时升级到Graph/Agentic
    ↓
回答质量评估 → 引用验证 → 最终回答
```

**RAG评测要求**：
所有RAG策略必须在同一评测集上比较，至少记录以下指标：
- 答案准确率
- 引用准确率
- 召回率/命中率
- 平均延迟
- token/模型调用成本
- 用户评分
- 失败率和升级率

评测集最少包含：
- 20个定义/事实问题
- 20个公式/页码定位问题
- 20个前置知识/概念关系问题
- 20个跨章节综合问题
- 20个出题/解释类问题

**上下文压缩机制**：
```python
class ContextCompressor:
    def __init__(self, llm, max_tokens: int = 4000):
        self.llm = llm
        self.max_tokens = max_tokens

    async def compress_context(self, context: str, query: str) -> str:
        """压缩上下文：保留与查询相关的关键信息"""

    async def summarize_findings(self, findings: list[Finding]) -> str:
        """总结发现：将多个检索结果压缩为摘要"""
```

**知识点问答解释功能**：
```python
class KnowledgeQAService:
    def __init__(self, knowledge_graph, llm, rag_service):
        self.knowledge_graph = knowledge_graph
        self.llm = llm
        self.rag_service = rag_service

    async def answer_knowledge_question(self, question: str) -> KnowledgeAnswer:
        """回答知识点问题"""
        # 1. 分析问题类型
        question_type = await self.analyze_question_type(question)

        # 2. 选择回答策略
        if question_type == "definition":
            return await self.explain_definition(question)
        elif question_type == "example":
            return await self.provide_examples(question)
        elif question_type == "connection":
            return await self.explain_connections(question)
        elif question_type == "prerequisite":
            return await self.explain_prerequisites(question)
        else:
            return await self.general_knowledge_qa(question)

    async def explain_definition(self, question: str) -> KnowledgeAnswer:
        """解释定义"""

    async def provide_examples(self, question: str) -> KnowledgeAnswer:
        """提供示例"""

    async def explain_connections(self, question: str) -> KnowledgeAnswer:
        """解释知识点联系"""

    async def explain_prerequisites(self, question: str) -> KnowledgeAnswer:
        """解释前置知识"""
```

**质量评估与自我纠正**：
```python
class QualityEvaluator:
    def __init__(self, llm):
        self.llm = llm

    async def evaluate_answer(self, answer: str, context: str, query: str) -> EvaluationResult:
        """评估回答质量"""

    async def self_correct(self, answer: str, evaluation: EvaluationResult) -> str:
        """自我纠正：根据评估结果改进回答"""

    async def verify_citations(self, answer: str, sources: list[Source]) -> bool:
        """验证引用准确性"""
```

**记忆服务（三层架构）**
- **短期记忆 (STM)**：
  ```python
  class ShortTermMemory:
      def __init__(self, max_tokens: int = 50000):
          self.compressed_prefix: str = ""  # LLM压缩的旧消息摘要
          self.recent_window: list[Message] = []  # 最近N条完整消息
          self.max_tokens = max_tokens

      def add_message(self, message: Message) -> None:
          """添加消息，自动检测压缩触发"""

      def get_context(self, max_tokens: int = 3000) -> str:
          """获取格式化上下文（压缩前缀 + 最近消息）"""

      def force_compress(self) -> None:
          """手动触发压缩"""
  ```
- **长期记忆 (LTM)**：
  ```python
  class LongTermMemory:
      def __init__(self, db_path: str):
          self.db = sqlite3.connect(db_path)
          self._init_fts5()  # 全文搜索索引

      def store(self, memory: MemoryEntry) -> None:
          """存储记忆条目（含scope、importance、model_types）"""

      def recall(self, query: str, top_k: int = 3) -> list[MemoryEntry]:
          """复合重排序召回：FTS5 rank + 时间衰减 + 访问热度 + 重要性"""

      def search_by_scope(self, scope: str, query: str) -> list[MemoryEntry]:
          """按scope前缀搜索"""
  ```
- **工作记忆 (WM)**：
  ```python
  class WorkingMemory:
      def __init__(self):
          self.document_content: dict[str, Any] = {}  # 当前文档结构化内容
          self.knowledge_graph_state: Graph = None  # 知识图谱临时状态
          self.intermediate_results: dict[str, Any] = {}  # 生成过程中间数据

      def update_document_content(self, doc_id: str, content: Any) -> None:
          """更新当前文档内容"""

      def get_intermediate_result(self, key: str) -> Any:
          """获取中间结果"""
  ```

**进化服务（基于Hermes架构）**
- **核心功能**：基于DSPy + GEPA的反射式进化优化
- **接口设计**：
  ```python
  class EvolutionService:
      def __init__(self, dspy_config, gepa_optimizer):
          self.dspy_config = dspy_config
          self.gepa_optimizer = gepa_optimizer

      async def evolve_skill(self, skill_name: str, eval_source: str = "synthetic") -> EvolutionResult:
          """进化技能文件"""

      async def evolve_tool_descriptions(self, iterations: int = 5) -> EvolutionResult:
          """进化工具描述"""

      async def evolve_prompt_section(self, section: str, iterations: int = 5) -> EvolutionResult:
          """进化系统提示词部分"""
  ```
- **评估数据集构建**：
  ```python
  class EvalDatasetBuilder:
      def __init__(self, session_db, llm_judge):
          self.session_db = session_db
          self.llm_judge = llm_judge

      def build_from_synthetic(self, skill_name: str, num_examples: int = 20) -> EvalDataset:
          """合成生成评估数据集"""

      def build_from_session_history(self, skill_name: str) -> EvalDataset:
          """从会话历史挖掘评估数据集"""

      def split_dataset(self, dataset: EvalDataset) -> tuple[EvalDataset, EvalDataset, EvalDataset]:
          """分割为训练/验证/测试集"""
  ```
- **约束验证**：
  ```python
  class ConstraintValidator:
      def validate_test_suite(self, variant: Variant) -> bool:
          """验证是否通过完整测试套件"""

      def validate_size_limits(self, variant: Variant) -> bool:
          """验证字符/令牌限制"""

      def validate_semantic_preservation(self, original: str, evolved: str) -> bool:
          """验证语义保留"""
  ```

**评估服务（多维度评估）**
- **核心功能**：内容质量评估、用户满意度评估、学习效果评估
- **接口设计**：
  ```python
  class EvaluationService:
      def __init__(self, llm_judge, metrics_calculator):
          self.llm_judge = llm_judge
          self.metrics_calculator = metrics_calculator

      async def evaluate_outline(self, outline: Outline, source_content: str) -> EvaluationResult:
          """评估提纲质量"""

      async def evaluate_questions(self, questions: list[Question], source_content: str) -> EvaluationResult:
          """评估例题质量"""

      async def evaluate_user_satisfaction(self, feedback: UserFeedback) -> SatisfactionScore:
          """评估用户满意度"""
  ```
- **评估指标**：
  ```python
  class EvaluationMetrics:
      def accuracy_score(self, generated: str, reference: str) -> float:
          """准确性评分"""

      def completeness_score(self, outline: Outline, knowledge_points: list[str]) -> float:
          """完整性评分"""

      def readability_score(self, text: str) -> float:
          """可读性评分"""

      def difficulty_level(self, question: Question) -> DifficultyLevel:
          """难度级别评估"""
  ```

**工具服务（MCP集成）**
- **核心功能**：提供各种工具供智能体调用
- **工具列表**：
  ```python
  class ToolService:
      def __init__(self):
          self.tools = {
              "pdf_parser": PDFParserTool(),
              "ppt_parser": PPTParserTool(),
              "ocr_tool": OCRTool(),
              "knowledge_graph": KnowledgeGraphTool(),
              "template_engine": TemplateEngineTool(),
              "format_converter": FormatConverterTool(),
          }

      def get_tool(self, tool_name: str) -> Tool:
          """获取工具实例"""

      def list_tools(self) -> list[ToolInfo]:
          """列出所有可用工具"""
  ```
- **工具接口**：
  ```python
  class Tool(ABC):
      @abstractmethod
      def name(self) -> str:
          """工具名称"""

      @abstractmethod
      def description(self) -> str:
          """工具描述"""

      @abstractmethod
      async def execute(self, **kwargs) -> ToolResult:
          """执行工具"""
  ```

### 2.3 数据流

```
用户上传PPT/PDF
    ↓
文档解析Agent提取内容
    ↓
内容理解Agent构建知识图谱
    ↓
知识提取Agent生成结构化知识点
    ↓
提纲生成Agent生成复习提纲
    ↓
例题生成Agent生成考试例题
    ↓
质量评估Agent评估质量
    ↓
人工审核Agent审核（可选）
    ↓
输出最终结果

查询流程：
用户查询 → 查询分析 → 查询重写 → 检索策略选择
    ↓
[普通RAG路径] → 向量检索 → 相关性过滤 → 上下文构建 → 回答生成
    ↓
[Graph RAG-lite路径] → 知识点命中 → 图谱关系扩展 → 源chunk回收 → 关系解释
    ↓
[Agentic RAG路径] → 任务分解 → 多轮检索 → 自我纠正 → 上下文压缩 → 回答生成
    ↓
[自动路由路径] → 低成本普通RAG → 置信度评估 → 必要时升级Graph/Agentic
    ↓
回答质量评估 → 引用验证 → 最终回答
```

## 3. 详细设计

### 3.1 文档解析模块（改进方案）

**问题分析**：
传统PDF/PPT解析工具（如PyMuPDF、python-pptx）在处理带图表的文档时，会得到混乱的结构，因为：
1. 无法正确识别文档的逻辑结构（标题、段落、列表）
2. 图表和文本混合在一起，难以分离
3. 表格结构被破坏，无法保持原有的行列关系
4. 数学公式被拆分成碎片，无法正确识别

**改进方案：基于Marker和Docling的智能解析**

**PDF解析（使用Marker）**：
- **核心优势**：基于深度学习的PDF解析，能够准确识别文档结构
- **功能特点**：
  - 自动识别标题、段落、列表、表格、图表
  - 保持文档的逻辑结构
  - 准确提取数学公式（LaTeX格式）
  - 识别并分离图表和文本
  - 支持OCR识别扫描版PDF
- **接口设计**：
  ```python
  class MarkerPDFParser:
      def __init__(self, model_name: str = "marker"):
          self.model_name = model_name

      async def parse(self, pdf_path: str) -> StructuredDocument:
          """使用Marker解析PDF，返回结构化文档"""

      async def extract_with_structure(self, pdf_path: str) -> DocumentWithStructure:
          """提取文档结构：标题层级、段落、表格、图表"""

      async def extract_formulas(self, pdf_path: str) -> list[Formula]:
          """提取数学公式（LaTeX格式）"""

      async def extract_tables(self, pdf_path: str) -> list[Table]:
          """提取表格数据（保持结构）"""

      async def extract_figures(self, pdf_path: str) -> list[Figure]:
          """提取图表和图像"""
  ```

**PPT解析（使用python-pptx + 增强处理）**：
- **核心改进**：增强python-pptx，添加结构识别和图表分离
- **功能特点**：
  - 识别幻灯片的逻辑结构（标题、内容、图表）
  - 分离文本和图表
  - 保持幻灯片的顺序和层级关系
  - 提取图表中的数据和描述
- **接口设计**：
  ```python
  class EnhancedPPTParser:
      def __init__(self):
          self.base_parser = python_pptx  # 使用python-pptx作为基础

      async def parse(self, ppt_path: str) -> StructuredPresentation:
          """解析PPT，返回结构化演示文稿"""

      async def extract_slides_with_structure(self, ppt_path: str) -> list[SlideWithStructure]:
          """提取幻灯片结构：标题、内容、图表"""

      async def extract_charts_from_slides(self, ppt_path: str) -> list[Chart]:
          """从幻灯片中提取图表"""

      async def extract_images_from_slides(self, ppt_path: str) -> list[Image]:
          """从幻灯片中提取图像"""
  ```

**文档结构化输出**：
```python
class StructuredDocument:
    def __init__(self):
        self.title: str = ""
        self.sections: list[Section] = []
        self.tables: list[Table] = []
        self.figures: list[Figure] = []
        self.formulas: list[Formula] = []
        self.metadata: dict[str, Any] = {}

class Section:
    def __init__(self):
        self.level: int = 1  # 标题层级
        self.title: str = ""
        self.content: str = ""
        self.subsections: list[Section] = []
        self.tables: list[Table] = []
        self.figures: list[Figure] = []
        self.formulas: list[Formula] = []

class Table:
    def __init__(self):
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        self.caption: str = ""
        self.page_number: int = 0

class Figure:
    def __init__(self):
        self.image_path: str = ""
        self.caption: str = ""
        self.description: str = ""  # 使用多模态LLM生成的描述
        self.page_number: int = 0

class Formula:
    def __init__(self):
        self.latex: str = ""
        self.description: str = ""
        self.page_number: int = 0
  ```

**多模态内容处理**：
```python
class MultimodalContentProcessor:
    def __init__(self, llm_config: LLMConfig):
        self.llm_config = llm_config

    async def process_figure(self, figure: Figure) -> ProcessedFigure:
        """处理图表：使用多模态LLM生成描述"""
        model = self.llm_config.get_model_for_task("image_understanding")
        # 使用MiMo V2.5的多模态能力生成图表描述

    async def process_table_image(self, image_path: str) -> TableData:
        """处理表格图像，提取结构化数据"""

    async def process_formula_image(self, image_path: str) -> LaTeXFormula:
        """处理公式图像，识别LaTeX公式"""
  ```

**解析策略选择**：
```python
class ParserSelector:
    def __init__(self):
        self.parsers = {
            "pdf_marker": MarkerPDFParser(),
            "pdf_pymupdf": PyMuPDFParser(),  # 备用方案
            "ppt_enhanced": EnhancedPPTParser(),
            "ppt_base": python_pptx,  # 备用方案
        }

    def select_parser(self, file_path: str, has_figures: bool = True) -> str:
        """根据文件类型和内容选择解析器"""
        if file_path.endswith(".pdf"):
            if has_figures:
                return "pdf_marker"  # 带图表的PDF使用Marker
            else:
                return "pdf_pymupdf"  # 纯文本PDF使用PyMuPDF
        elif file_path.endswith(".pptx"):
            return "ppt_enhanced"  # PPT使用增强解析器
        else:
            raise ValueError(f"Unsupported file type: {file_path}")
  ```

**深度学习模型调用方案**：

**Marker开源确认**：
- **项目地址**：https://github.com/datalab-to/marker
- **包名**：`marker-pdf`
- **当前核验日期**：2026-06-15
- **许可证**：GNU General Public License v3 or later (GPLv3+)
- **模型权重许可**：Marker项目说明中提到模型权重使用 modified AI Pubs Open Rail-M license；商业场景需要单独评估
- **Python要求**：Python >=3.10, <4.0
- **本地部署**：✅ 支持本地部署
- **主要功能**：将PDF、图片、PPTX、DOCX、XLSX、HTML、EPUB等转换为Markdown、JSON、chunks和HTML，支持表格、公式、图片抽取和可选LLM增强
- **实现约束**：代码不得继续假设旧API `marker.load_model` / `marker.convert.convert_single_pdf` 一定存在；解析器实现前必须以当前安装版本的官方API做适配测试。

**方案一：本地部署（推荐用于生产环境）**
```python
class LocalMarkerModel:
    def __init__(self, config: dict | None = None):
        self.config = config or {"output_format": "json"}
        self.converter = None

    def load_converter(self):
        """按当前marker-pdf API加载转换器"""
        from marker.config.parser import ConfigParser
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict

        config_parser = ConfigParser(self.config)
        self.converter = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=create_model_dict(),
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
            llm_service=config_parser.get_llm_service(),
        )

    async def parse_pdf(self, pdf_path: str) -> StructuredDocument:
        """使用本地Marker模型解析PDF"""
        if self.converter is None:
            self.load_converter()

        rendered = self.converter(pdf_path)

        return self._map_marker_json_to_structured_document(rendered)
```

**方案二：API调用（推荐用于开发测试）**
```python
class MarkerAPIClient:
    def __init__(self, api_key: str, api_url: str):
        self.api_key = api_key
        self.api_url = api_url

    async def parse_pdf(self, pdf_path: str) -> StructuredDocument:
        """通过Datalab托管API或本地marker_server解析PDF"""
        import aiohttp

        with open(pdf_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("file", f, filename="document.pdf", content_type="application/pdf")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    data=data,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

        return StructuredDocument(
            title=result.get("title", ""),
            sections=self._parse_sections(result.get("sections", [])),
            tables=result.get("tables", []),
            figures=result.get("figures", []),
            formulas=result.get("formulas", [])
        )
```

**方案三：Docker容器化部署**
```python
class MarkerDockerClient:
    def __init__(self, container_name: str = "marker-service"):
        self.container_name = container_name

    async def parse_pdf(self, pdf_path: str) -> StructuredDocument:
        """通过Docker容器调用Marker"""
        import docker

        client = docker.from_env()

        # 挂载PDF文件到容器
        volumes = {pdf_path: {"bind": "/input/document.pdf", "mode": "ro"}}

        # 运行容器
        container = client.containers.run(
            "marker:latest",
            command="/input/document.pdf",
            volumes=volumes,
            detach=True,
            remove=True
        )

        # 等待完成并获取结果
        result = container.wait()
        logs = container.logs().decode()

        return self._parse_result(logs)
```

**方案四：混合调用策略**
```python
class HybridMarkerClient:
    def __init__(self, local_model_path: str, api_key: str, api_url: str):
        self.local_client = LocalMarkerModel(local_model_path)
        self.api_client = MarkerAPIClient(api_key, api_url)
        self.docker_client = MarkerDockerClient()

    async def parse_pdf(self, pdf_path: str, strategy: str = "auto") -> StructuredDocument:
        """混合调用策略：根据情况选择最佳方案"""
        if strategy == "auto":
            # 自动选择：优先本地，失败则API，最后Docker
            try:
                return await self.local_client.parse_pdf(pdf_path)
            except Exception:
                try:
                    return await self.api_client.parse_pdf(pdf_path)
                except Exception:
                    return await self.docker_client.parse_pdf(pdf_path)
        elif strategy == "local":
            return await self.local_client.parse_pdf(pdf_path)
        elif strategy == "api":
            return await self.api_client.parse_pdf(pdf_path)
        elif strategy == "docker":
            return await self.docker_client.parse_pdf(pdf_path)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
```

**模型加载和管理**：
```python
class ModelManager:
    def __init__(self):
        self.models = {}
        self.model_configs = {
            "marker": {"type": "converter", "output_format": "json"},
            "ocr": {"type": "api", "url": "https://api.ocr.com", "key": ""},
            "multimodal": {"type": "local", "path": "mimo-v2.5", "gpu": True}
        }

    def load_model(self, model_name: str):
        """加载模型"""
        config = self.model_configs.get(model_name)
        if config["type"] == "converter":
            self._load_marker_converter(model_name, config)
        elif config["type"] == "local":
            self._load_local_model(model_name, config)
        elif config["type"] == "api":
            self._init_api_client(model_name, config)

    def _load_marker_converter(self, model_name: str, config: dict):
        """加载Marker转换器，API需以当前安装版本为准"""
        from marker.config.parser import ConfigParser
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict

        config_parser = ConfigParser({"output_format": config.get("output_format", "json")})
        self.models[model_name] = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=create_model_dict(),
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
            llm_service=config_parser.get_llm_service(),
        )

    def _load_local_model(self, model_name: str, config: dict):
        """加载本地模型"""
        if model_name == "multimodal":
            # 加载MiMo V2.5多模态模型
            self.models[model_name] = self._load_mimo_model(config["path"])

    def _load_mimo_model(self, model_path: str):
        """加载MiMo V2.5模型"""
        # 根据模型格式加载（PyTorch、ONNX、TensorRT等）
        pass
```

**性能优化**：
```python
class PerformanceOptimizer:
    def __init__(self):
        self.cache = {}
        self.batch_size = 8

    async def parse_with_cache(self, pdf_path: str) -> StructuredDocument:
        """带缓存的解析"""
        cache_key = self._get_cache_key(pdf_path)
        if cache_key in self.cache:
            return self.cache[cache_key]

        result = await self.parse_pdf(pdf_path)
        self.cache[cache_key] = result
        return result

    async def batch_parse(self, pdf_paths: list[str]) -> list[StructuredDocument]:
        """批量解析多个PDF"""
        results = []
        for i in range(0, len(pdf_paths), self.batch_size):
            batch = pdf_paths[i:i + self.batch_size]
            batch_results = await asyncio.gather(*[self.parse_pdf(p) for p in batch])
            results.extend(batch_results)
        return results
```

**与传统方案的对比**：
| 特性 | 传统方案（PyMuPDF/python-pptx） | 改进方案（Marker+增强PPT） |
|------|--------------------------------|---------------------------|
| 文档结构识别 | ❌ 混乱 | ✅ 准确识别 |
| 图表处理 | ❌ 混合在文本中 | ✅ 分离并描述 |
| 表格提取 | ❌ 结构破坏 | ✅ 保持结构 |
| 公式识别 | ❌ 碎片化 | ✅ LaTeX格式 |
| 多模态支持 | ❌ 无 | ✅ 图表描述 |

### 3.2 内容理解模块

**知识图谱构建**：
- 实体识别：概念、术语、公式
- 关系抽取：包含、依赖、相似
- 图谱存储：Neo4j或内存图结构

**重点难点分析**：
- 基于文档结构识别重点内容
- 基于知识点依赖关系识别难点
- 基于考试频率识别高频考点

### 3.3 提纲生成模块

**提纲结构**：
```
章节标题
├── 知识点1
│   ├── 核心概念
│   ├── 关键公式
│   └── 注意事项
├── 知识点2
│   ├── 核心概念
│   ├── 关键公式
│   └── 注意事项
└── 复习建议
    ├── 重点内容
    ├── 难点解析
    └── 学习方法
```

**格式支持**：
- Markdown格式：通用性强，易于编辑
- LaTeX格式：支持复杂公式，适合理工科
- JSON格式：程序化处理，支持API调用

### 3.4 例题生成模块

**题目类型**：
1. **选择题**：单选、多选
2. **填空题**：单空、多空
3. **解答题**：计算题、证明题、应用题

**题目生成策略**：
- 基于知识点生成基础题目
- 基于公式生成计算题目
- 基于概念生成理解题目
- 基于应用场景生成综合题目

**质量控制**：
- 答案正确性验证
- 难度级别控制
- 题目多样性保证
- 避免重复题目

### 3.5 记忆系统设计

**短期记忆 (STM)**：
- 存储当前会话上下文
- 保存处理中间结果
- 支持上下文压缩

**长期记忆 (LTM)**：
- 用户偏好和学习历史
- 成功的处理策略
- 高质量的生成模板

**工作记忆 (WM)**：
- 当前文档的结构化内容
- 知识图谱的临时状态
- 生成过程中的中间数据

### 3.6 自进化系统设计（基于Hermes Agent Self-Evolution架构）

**核心架构**：基于DSPy + GEPA（Genetic-Pareto Prompt Evolution）的反射式进化优化

**优化循环**：
```
选择优化目标 → 构建评估数据集 → 包装为DSPy模块 → 运行优化器 → 评估比较 → 部署（需人工批准）
```

**三层优化目标**：

#### 第一层：技能文件优化（最高价值，最低风险）
- **目标**：优化SKILL.md文件（程序化指令）
- **方法**：将技能文本包装为DSPy模块，通过batch_runner在测试任务上评估，使用GEPA进化
- **评估数据来源**：
  - 合成生成：使用强模型（如Claude Opus）生成测试用例
  - 会话挖掘：从历史会话中提取真实使用案例
  - 人工策划：高质量技能的手工测试用例
- **约束条件**：
  - 技能文件大小≤15KB
  - 必须通过完整测试套件
  - 保持语义一致性

#### 第二层：工具描述优化（中等价值，低风险）
- **目标**：优化工具schema中的description字段
- **方法**：GEPA进化描述文本，评估工具选择准确性
- **评估数据来源**：
  - 合成工具选择数据集：（任务描述，正确工具，正确参数）三元组
  - 会话挖掘：识别工具误选模式
  - 基准测试：从TBLite等基准测试中提取工具选择失败案例
- **约束条件**：
  - 工具描述≤500字符
  - 参数描述≤200字符
  - 必须保持事实准确性
  - 模式结构（参数名、类型）冻结，只进化文本

#### 第三层：系统提示词优化（高价值，较高风险）
- **目标**：优化系统提示词的各个部分（人格、策略、格式指令）
- **方法**：将提示词部分参数化为DSPy Signature，使用GEPA独立优化
- **可优化部分**：
  - 默认代理身份（人格、行为特征）
  - 记忆指导（何时保存、保存什么）
  - 会话搜索指导（触发条件）
  - 技能指导（触发条件）
- **约束条件**：
  - 每个部分大小增加不超过20%
  - 总系统提示词必须在模型提示词缓存边界内
  - 必须保持核心特征（有帮助、直接、承认不确定性）

**进化引擎**：
| 引擎 | 优化目标 | 许可证 | 集成方式 |
|------|----------|--------|----------|
| DSPy + GEPA | 技能、提示词、工具描述 | MIT | 原生Python，主要引擎 |
| Darwinian Evolver | 代码文件、工具实现 | AGPL v3 | 仅外部CLI |
| DSPy MIPROv2 | 少样本示例、指令文本 | MIT | 原生Python，备用优化器 |

**约束条件和防护栏**：
1. **完整测试套件**：pytest tests/ -q 必须100%通过
2. **字符/令牌限制**：技能≤15KB，工具描述≤500字符
3. **提示词缓存兼容性**：永不热交换到活跃对话中
4. **语义保留**：进化内容不得偏离原始目的
5. **通过PR部署**：永不直接提交，所有变更需人工审查

**评估数据集构建**：
```
会话数据库（真实对话）→ 评估数据集构建器 → DSPy模块包装 → GEPA优化器
```

**基准测试作为适应度信号**：
| 基准测试 | 测试内容 | 速度 | 在自进化中的角色 |
|----------|----------|------|------------------|
| TBLite | 编码/系统管理（100个任务） | ~1-2小时 | 主要回归门控 |
| YC-Bench | 长期战略一致性（100-500轮） | ~3-6小时 | 一致性检查 |

**部署流程**：
```bash
git checkout -b evolve/<target>-<timestamp>
# 应用进化变更
git add <files>
git commit -m "evolve: <target> — score improved X% → Y%"
git push -u origin evolve/<target>-<timestamp>
gh pr create --title "evolve: <target>" --body "<metrics, diff, comparison>"
```

**成本估算**：
- GEPA优化：每次运行~$2-10
- Darwinian Evolver：每次任务~$2-9
- 建议从小规模评估数据集开始（10-20个示例）

### 3.7 Human-in-Loop设计

**混合评估模式**：
1. **自动评估**：系统自动评估内容质量
2. **人工审核**：关键节点插入人工审核
3. **用户反馈**：收集用户使用反馈
4. **专家评审**：邀请领域专家评审

**审核节点**：
- 文档解析后：确认内容提取准确性
- 提纲生成后：确认结构合理性
- 例题生成后：确认题目质量
- 最终输出前：确认整体质量

### 3.8 MCP服务集成

**基础MCP服务**：
- 文件系统服务：读写文件
- 向量数据库服务：存储和检索向量
- 缓存服务：提高性能

**文档处理MCP**：
- PDF解析服务：提取PDF内容
- PPT解析服务：提取PPT内容
- OCR服务：识别扫描文档

**知识图谱MCP**：
- 实体识别服务：识别概念和术语
- 关系抽取服务：提取概念关系
- 图谱查询服务：查询知识图谱

**学术搜索MCP**：
- 论文检索服务：搜索相关论文
- 公式识别服务：识别数学公式
- 参考文献服务：管理参考文献

**评估MCP**：
- 质量评估服务：评估内容质量
- 用户反馈服务：收集用户反馈
- 学习分析服务：分析学习效果

## 4. 实现计划

### 4.1 第一阶段：核心框架（2周）
- 搭建项目结构（已骨架完成）
- 实现主协调器和基础接口（已骨架完成，未完成真实编排）
- 实现文档解析Agent（已骨架完成，Marker API需更新）
- 实现基础RAG服务（已骨架完成，未接入向量库和真实检索）
- 配置模型路由器（已骨架完成，真实模型名和SDK需核验）
- 修复测试环境，保证异步测试可执行

### 4.1.1 当前优先修复任务
1. **测试环境闭环**：统一Python版本、安装dev依赖，确保 `pytest -q` 能加载 `pytest-asyncio`。
2. **Marker适配**：将 `MarkerPDFParser` 从旧API改为当前 `PdfConverter/create_model_dict` 方案，新增真实或最小PDF fixture测试。
3. **主流程真实编排**：让 `MainCoordinator.invoke()` 至少串起文档解析、知识点抽取、提纲生成的MVP路径，不再返回固定success占位。
4. **CLI EOF处理**：修复非交互运行 `python -m src.main` 时遇到stdin EOF后无限循环打印错误的问题。
5. **RAG最小可用**：实现文档chunk、内存检索或轻量BM25检索，再扩展到ChromaDB/Agentic RAG。
6. **输出生成闭环**：优先实现 `OutlineGenerationAgent` 和 `QuestionGenerationAgent` 的可测试mock/模板版本，再接入真实LLM。

### 4.2 第二阶段：内容生成（3周）
- 实现内容理解Agent
- 实现提纲生成Agent
- 实现例题生成Agent
- 实现记忆系统

### 4.3 第三阶段：质量控制（2周）
- 实现质量评估Agent
- 实现人工审核Agent
- 实现评估服务
- 集成Human-in-Loop

### 4.4 第四阶段：自进化系统（3周）
**第一周：基础架构**
- 安装DSPy + GEPA，验证环境
- 实现技能-as-DSPy模块包装器
- 实现评估数据集生成器（合成生成为主）
- 实现GEPA优化运行器

**第二周：技能进化**
- 选择2-3个目标技能进行进化（如文档解析、提纲生成、例题生成）
- 为每个技能生成评估数据集（15-30个示例）
- 运行GEPA优化（每个技能5-10次迭代）
- 比较基线与进化版本在保留测试集上的表现

**第三周：验证与部署**
- 运行基准测试（TBLite快速子集）验证无回归
- 人工审查进化后的技能差异
- 创建改进PR，包含完整指标和对比
- 文档化优化流程，使其可重用于其他技能

### 4.5 第五阶段：测试和部署（1周）
- 单元测试
- 集成测试
- 性能测试
- 部署和文档

## 5. 技术选型

### 5.1 核心依赖
- **基座大模型**：MiMo V2.5（多模态能力：图像、表格、公式识别）
- **对话模型**：DeepSeek V4（推理能力：逻辑推理、数学推理、代码生成）
- **Embedding模型**：阿里云百练 text-embedding-v2（向量化，Dim=1536）
- **智能模型路由器**：根据任务特点自动选择最优模型

**模型路由策略**：
| 任务类型 | 推荐模型 | 原因 |
|----------|----------|------|
| 图像/图表理解 | MiMo V2.5 | 多模态能力强 |
| 表格解析 | MiMo V2.5 | 视觉理解能力 |
| 公式识别 | MiMo V2.5 | 数学符号识别 |
| OCR文字识别 | MiMo V2.5 | 图像识别能力 |
| 逻辑推理 | DeepSeek V4 | 推理能力强 |
| 数学计算 | DeepSeek V4 | 数学推理能力 |
| 代码生成 | DeepSeek V4 | 代码能力强 |
| 长文本处理 | DeepSeek V4 | 长上下文支持 |
| 文本摘要 | DeepSeek V4 | 成本低、效果好 |
- **向量数据库**：ChromaDB或FAISS
- **文档处理**：
  - Marker（PDF解析，基于深度学习）
  - python-pptx + 增强处理（PPT解析）
  - PyMuPDF（备用PDF解析）
  - PDFPlumber（表格提取）
- **NLP**：jieba、spaCy
- **知识图谱**：NetworkX或Neo4j
- **自进化框架**：DSPy、GEPA、Darwinian Evolver（可选）
- **基准测试**：TBLite、YC-Bench

**LLM配置设计**：
```python
class LLMConfig:
    def __init__(self):
        self.primary_model = "mimo-v2.5"  # 主要LLM（多模态）
        self.deepseek_model = "deepseek-v4"  # 对话模型（推理）
        self.multimodal_model = "mimo-v2.5"  # 多模态模型（图表、OCR）
        self.api_base = "https://api.mimo.example.com"  # MiMo API地址
        self.deepseek_api_base = "https://api.deepseek.com"  # DeepSeek API地址
        self.api_key = ""  # MiMo API密钥
        self.deepseek_api_key = ""  # DeepSeek API密钥
        self.temperature = 0.3  # 默认温度
        self.max_retries = 3  # 重试次数

    def get_model_for_task(self, task_type: str) -> str:
        """根据任务类型获取合适的模型"""
        # MiMo V2.5 擅长：多模态、图像、表格、公式、OCR
        # DeepSeek V4 擅长：推理、代码、数学、长文本、摘要
        ...
```

**多模态任务处理**：
```python
class MultimodalHandler:
    def __init__(self, llm_config: LLMConfig):
        self.llm_config = llm_config

    async def process_image(self, image_path: str) -> ImageDescription:
        """处理图像，使用多模态模型"""
        model = self.llm_config.get_model_for_task("image_understanding")
        # 使用MiMo V2.5的多模态能力

    async def process_table_image(self, image_path: str) -> TableData:
        """处理表格图像，提取结构化数据"""
        model = self.llm_config.get_model_for_task("multimodal")

    async def process_formula_image(self, image_path: str) -> LaTeXFormula:
        """处理公式图像，识别LaTeX公式"""
        model = self.llm_config.get_model_for_task("multimodal")
```

**智能模型路由器（ModelRouter）**：
```python
class ModelRouter:
    """根据任务特点智能选择模型"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._task_keywords = self._build_task_keywords()

    def analyze_task(self, task_description: str) -> TaskAnalysis:
        """分析任务并推荐模型"""
        # 1. 检测任务类别（多模态/推理/代码等）
        # 2. 评估复杂度（简单/中等/复杂）
        # 3. 检测是否需要多模态
        # 4. 检测是否需要强推理
        # 5. 选择模型

    def get_model_for_task(self, task_description: str) -> str:
        """获取任务对应的模型"""
        # MiMo V2.5: 图像、表格、公式、OCR
        # DeepSeek V4: 推理、代码、数学、长文本、摘要

# 任务类别
class TaskCategory(Enum):
    # MiMo V2.5 擅长
    MULTIMODAL = "multimodal"  # 图像理解
    OCR = "ocr"  # 文字识别
    TABLE_UNDERSTANDING = "table_understanding"  # 表格理解
    FORMULA_RECOGNITION = "formula_recognition"  # 公式识别

    # DeepSeek V4 擅长
    REASONING = "reasoning"  # 逻辑推理
    MATH_REASONING = "math_reasoning"  # 数学推理
    CODE_GENERATION = "code_generation"  # 代码生成
    LONG_TEXT = "long_text"  # 长文本处理
    SUMMARIZATION = "summarization"  # 文本摘要
```

### 5.2 开发工具
- **测试**：pytest
- **代码质量**：black、isort、mypy
- **文档**：Sphinx
- **CI/CD**：GitHub Actions

### 5.3 部署环境
- **容器化**：Docker
- **编排**：Docker Compose
- **监控**：Prometheus + Grafana

## 6. 风险评估

### 6.1 技术风险
- **LLM生成质量不稳定**：通过多轮评估和人工审核缓解
- **文档解析准确性**：使用多种解析工具和OCR技术
- **知识图谱构建复杂度**：从简单关系开始，逐步完善

### 6.2 性能风险
- **处理大文档的性能**：分块处理和并行化
- **LLM调用成本**：优化提示词，减少不必要的调用
- **内存使用**：及时释放中间结果

### 6.3 用户体验风险
- **生成内容不符合预期**：提供自定义选项和反馈机制
- **处理时间过长**：提供进度反馈和异步处理
- **格式兼容性问题**：支持多种输出格式

## 7. 成功标准

### 7.1 MVP-1功能标准
- 能够解析至少1个PDF fixture，并输出非空的 `StructuredDocument`，包含标题/章节或正文内容。
- 能够从结构化文档中抽取至少3个知识点，并保存到 `KnowledgeGraph`。
- 能够基于知识点生成Markdown复习提纲，包含章节、核心概念、关键公式/术语、复习建议。
- 能够基于知识点生成至少5道例题，包含题干、答案、解析和难度字段。
- CLI的 `/parse`、`/outline`、`/questions` 不再只打印“正在开发中”，而是调用真实流程或给出明确错误。

### 7.2 测试和验收标准
- 使用Python 3.11或3.12创建虚拟环境。
- 安装命令：`python -m pip install -e ".[dev]"`。
- 单元/集成测试命令：`pytest -q`。
- CLI冒烟测试命令：`printf "/quit\n" | python -m src.main`。
- 每次任务结束必须完成两轮审查：Spec审查和质量审查。
- 如果测试因为缺少外部模型、GPU、API key或网络而跳过，必须在测试输出和文档中标记为 `xfail` 或 `skip`，不能把未执行测试算作通过。

### 7.3 RAG实验验收标准
- 普通RAG必须先作为baseline实现，支持chunk索引、来源引用和低成本问答。
- Graph RAG-lite必须证明在前置知识、概念关系、复习路径类问题上优于普通RAG，才能进入默认路由。
- Agentic RAG必须证明在跨章节综合、复杂出题、比较诊断类问题上优于普通RAG和Graph RAG-lite，才能进入高成本路由。
- 自动路由必须有离线评测集，且输出每次路由的 `mode`、`reason`、`confidence` 和成本等级。
- 任一RAG策略不能返回无来源答案；无法定位来源时必须明确标记为推断或低置信度。

### 7.4 后续性能标准
- 文档解析时间：小于30秒/100页（需要真实Marker环境和样本文档基准）
- 提纲生成时间：小于60秒
- 例题生成时间：小于30秒/10题
- 系统响应时间：小于5秒

### 7.5 质量标准
- 内容准确性：大于90%
- 用户满意度：大于85%
- 系统稳定性：大于99%
- 错误恢复率：大于95%
- 以上质量指标必须绑定可重复评测集；在评测集建立前，只能作为目标，不作为已验收事实。

### 7.6 正式产品补充验收标准
- 任一展示给用户的提纲、例题、问答答案和导出内容，必须能追踪到源文档页码、章节或chunk；无法追踪时必须标记为低置信度或人工生成内容。
- 用户编辑后的提纲和例题必须创建新版本，不允许覆盖历史版本；导出内容必须绑定明确版本号。
- 后台任务必须支持 `queued`、`running`、`completed`、`failed`、`cancelled` 状态，并记录阶段、进度、错误码、错误摘要和可重试标记。
- 上传、查看、编辑、导出、删除文档都必须校验用户或组织归属权。
- 反馈和人工审核结果必须保存为结构化数据，能够反向关联到文档、提纲、例题、QA消息或导出版本。
- 正式产品验收时必须有至少一条端到端用例覆盖：上传文件、生成结果、编辑版本、提交反馈、导出文件、查看任务日志。

## 8. 扩展性考虑

### 8.1 学科扩展
- 支持更多理工科领域
- 支持文科和社会科学
- 支持艺术和设计类学科

### 8.2 功能扩展
- 支持视频和音频文件
- 支持交互式学习
- 支持个性化学习路径

### 8.3 集成扩展
- 支持更多MCP服务
- 支持第三方题库
- 支持学习管理系统（LMS）

## 9. 实现状态

### 9.1 骨架完成

| 模块 | 当前状态 | 文件位置 | 下一步 |
|------|----------|----------|--------|
| 配置管理 | 骨架完成 | `src/config.py` | 核验真实模型名、SDK包名、环境变量样例 |
| 智能模型路由器 | 骨架完成 | `src/services/model_router.py` | 增加真实模型profile和回退策略 |
| 基础智能体 | 骨架完成 | `src/agents/base_agent.py` | 明确重试策略、错误分类、日志 |
| 文档解析Agent | 骨架完成 | `src/agents/document_parsing.py` | 接入更新后的Marker解析器和文件校验 |
| Marker PDF解析 | 骨架完成但API待更新 | `src/parsers/marker_pdf.py` | 改为当前Marker API，并解析真实输出 |
| 知识图谱 | 骨架完成 | `src/knowledge/knowledge_graph.py` | 接入内容理解/知识抽取流程，并作为Graph RAG-lite基础补前置/依赖/相似关系 |
| RAG服务 | 骨架完成但返回占位文本 | `src/services/rag_service.py` | 实现chunk、索引、检索、引用 |
| 记忆服务 | 骨架完成 | `src/services/memory_service.py` | 补充工作记忆、压缩策略和FTS5召回 |
| 主协调器 | 骨架完成但未真实编排 | `src/coordinator/main_coordinator.py` | 串起MVP端到端流程 |
| 应用入口 | 骨架完成但命令未执行真实功能 | `src/main.py` | `/parse`、`/outline`、`/questions` 调用真实流程 |

### 9.2 尚未完成

| 模块 | 功能 | 优先级 | 阻塞关系 |
|------|------|--------|----------|
| 测试环境 | `pytest-asyncio`可用、异步测试可执行 | 最高 | 阻塞所有“已验收”声明 |
| CLI EOF处理 | 非交互stdin关闭时正常退出 | 最高 | 阻塞CLI冒烟测试 |
| Marker API适配 | 使用当前 `marker-pdf` API解析PDF | 最高 | 阻塞真实文档解析 |
| 提纲生成Agent | OutlineGenerationAgent | 高 | 依赖知识点抽取 |
| 例题生成Agent | QuestionGenerationAgent | 高 | 依赖知识点抽取 |
| 内容理解Agent | ContentUnderstandingAgent | 高 | 依赖解析输出 |
| 质量评估Agent | QualityEvaluationAgent | 中 | 依赖提纲/例题输出 |
| 增强PPT解析 | EnhancedPPTParser | 中 | 不阻塞MVP-1 PDF闭环 |
| 工作记忆 | WorkingMemory | 中 | 影响长流程可靠性 |
| 评估服务 | EvaluationService | 中 | 影响自动质量评估 |
| 普通RAG baseline | chunk索引、检索、引用、低成本问答 | 高 | MVP-1/MVP-2 RAG基础 |
| Graph RAG-lite | 基于知识图谱的概念关系和复习路径检索 | 中 | MVP-3实验和产品化 |
| Agentic RAG | 多步检索、任务分解、自我纠正 | 中 | MVP-4复杂问答与出题 |
| RAG自动路由 | simple/graph/agentic/hybrid 策略选择 | 中 | MVP-4，依赖RAG评测集 |
| RAG评测集 | 定义、公式、关系、综合、出题类问题 | 中 | 决定是否启用高级RAG |
| FastAPI后端 | HTTP API、上传、任务状态、结果接口 | 中 | MVP-2正式产品雏形 |
| React前端 | 文档列表、上传、任务详情、提纲/例题页面 | 中 | MVP-2正式产品雏形 |
| 数据库持久化 | PostgreSQL/pgvector schema与迁移 | 中 | MVP-3产品化RAG |
| 异步任务队列 | Redis + worker任务执行 | 中 | 正式产品长任务可靠性 |
| 对象存储 | 原始文件、解析图片、导出结果 | 中 | 正式部署文件生命周期 |
| 文档标准化层 | StructuredDocument到Section/Chunk/Asset/SourceSpan的规范转换 | 高 | 阻塞引用追踪、RAG和导出质量 |
| 版本与导出服务 | 编辑版本、导出任务、导出文件记录 | 中 | 正式产品结果交付 |
| 反馈与审核服务 | 用户反馈、人工审核任务、质量闭环 | 中 | 自进化和质量评估的数据来源 |
| 权限与审计 | 用户隔离、资源归属校验、关键操作审计日志 | 中 | 正式产品安全边界 |
| 可观测性 | 结构化日志、指标、错误ID、任务追踪 | 中 | 长任务排障和上线运维 |
| 自进化服务 | EvolutionService (DSPy+GEPA) | 低 | 应在MVP-1稳定后实施 |

### 9.3 当前测试状态

最近一次本地执行 `pytest -q` 的结果为：30 passed, 14 failed。失败原因集中在异步测试插件未加载，表现为 `async def functions are not natively supported` 和 `Unknown pytest.mark.asyncio` 警告。该结果说明当前环境不能作为“测试通过”的验收依据，下一步必须先修复dev环境安装/执行方式。

## 10. 正式产品工业化架构

本项目目标调整为正式产品后，需要在Agent核心能力之外补齐Web产品、API后端、数据库、文件存储、异步任务和部署运维设计。工业化能力按阶段交付，不能阻塞MVP-1的PDF端到端闭环。

### 10.1 产品形态

正式产品面向学生、教师和教研人员，核心价值是把课程资料转化为可复习、可编辑、可导出、可追问的学习资产。

**核心用户流程**：
1. 用户上传PDF/PPT资料。
2. 系统创建处理任务，展示解析、知识点抽取、提纲生成、例题生成进度。
3. 用户查看结构化文档、知识点图谱、复习提纲和例题。
4. 用户编辑提纲、调整题目难度、重新生成部分内容。
5. 用户导出Markdown、LaTeX、PDF或JSON。
6. 用户基于资料进行知识点问答，并可提交反馈用于质量评估。

**首版正式产品范围**：
- 支持单用户或轻量多用户登录。
- 支持文档上传、任务状态、结果查看、结果编辑、结果导出。
- 支持PDF优先，PPT作为第二阶段增强。
- 支持可恢复任务，失败后能看到错误原因并重试。

### 10.2 前端架构

正式产品前端推荐使用 **React + TypeScript + Vite**。Streamlit只适合作为内部调试台，不作为正式产品主界面。

**页面结构**：
| 页面 | 主要职责 |
|------|----------|
| 登录/用户入口 | 用户登录、API key或组织身份接入 |
| 文档列表页 | 查看上传资料、处理状态、最近生成结果 |
| 上传页 | 拖拽上传、文件校验、解析参数选择 |
| 任务详情页 | 展示解析进度、阶段日志、错误和重试入口 |
| 文档解析结果页 | 展示章节、公式、表格、图片描述和原文引用 |
| 知识点图谱页 | 查看知识点、依赖关系、重点难点 |
| 提纲编辑页 | 查看和编辑Markdown/LaTeX提纲，支持重新生成局部内容 |
| 例题页 | 按知识点、题型、难度查看例题和答案解析 |
| 问答页 | 基于当前文档集合进行RAG问答 |
| 导出页 | 导出Markdown、LaTeX、PDF、JSON |

**前端状态模型**：
```ts
type JobStatus =
  | "queued"
  | "parsing"
  | "extracting_knowledge"
  | "generating_outline"
  | "generating_questions"
  | "evaluating"
  | "completed"
  | "failed"
  | "cancelled";
```

**交互原则**：
- 长任务不阻塞页面，通过轮询或SSE获取任务进度。
- 所有AI生成内容都可编辑，系统保留版本。
- 每个结果块必须能追溯到源文档页码、章节或chunk。
- 失败状态必须显示可理解错误、技术错误ID和重试按钮。

### 10.3 后端架构

正式产品后端推荐使用 **FastAPI + Pydantic + SQLAlchemy/Alembic**。Agent核心能力保留在 `src/agents/`、`src/services/`、`src/coordinator/`，Web API放在独立应用层，避免把HTTP细节混进Agent逻辑。

**建议目录结构**：
```text
src/
  api/
    app.py
    deps.py
    routes/
      auth.py
      documents.py
      jobs.py
      outlines.py
      questions.py
      qa.py
      exports.py
      feedback.py
      review.py
  db/
    session.py
    models.py
    migrations/
  storage/
    file_store.py
    object_store.py
  workers/
    tasks.py
    queue.py
```

**API边界**：
| API | 方法 | 职责 |
|-----|------|------|
| `/api/documents` | POST | 上传文档并创建解析任务 |
| `/api/documents` | GET | 列出文档 |
| `/api/documents/{id}` | GET | 获取文档元数据和处理摘要 |
| `/api/jobs/{id}` | GET | 查询任务状态、进度、错误 |
| `/api/jobs/{id}/retry` | POST | 重试失败任务 |
| `/api/outlines/{document_id}` | GET | 获取提纲 |
| `/api/outlines/{document_id}` | PUT | 保存用户编辑后的提纲 |
| `/api/questions/{document_id}` | GET | 获取例题 |
| `/api/questions/generate` | POST | 按题型/难度重新生成例题 |
| `/api/qa` | POST | 基于文档集合问答 |
| `/api/exports/{document_id}` | POST | 创建导出任务 |
| `/api/exports/jobs/{id}` | GET | 查询导出状态和下载地址 |
| `/api/versions/{target_type}/{target_id}` | GET | 查看提纲/例题/QA摘要的版本列表 |
| `/api/feedback` | POST | 提交用户反馈 |
| `/api/review-tasks` | GET | 审核员查看待审核任务 |
| `/api/review-tasks/{id}/decision` | POST | 提交人工审核决定 |

**异步任务模型**：
- 文档解析、知识点抽取、提纲生成、例题生成和导出都作为后台job执行。
- MVP可用进程内队列或SQLite job表轮询；正式部署推荐 Celery/RQ/Dramatiq + Redis。
- Job必须持久化状态、进度、当前阶段、错误类型和重试次数。

**后端错误分类**：
| 错误类型 | 示例 | 处理方式 |
|----------|------|----------|
| `validation_error` | 文件类型不支持、文件过大 | 直接返回4xx和用户可读提示 |
| `parser_error` | Marker解析失败 | 记录日志，允许重试或切换备用解析器 |
| `model_error` | LLM超时、限流、返回格式错误 | 指数退避重试，最终进入failed |
| `storage_error` | 文件保存失败 | 告警并阻止任务继续 |
| `internal_error` | 未捕获异常 | 返回错误ID，记录结构化日志 |

### 10.4 数据库设计

正式产品推荐 **PostgreSQL + pgvector**。开发期可以用SQLite，但schema应按PostgreSQL设计，避免后续迁移痛苦。

**核心表**：
| 表 | 主要字段 | 说明 |
|----|----------|------|
| `users` | `id`, `email`, `name`, `created_at` | 用户身份 |
| `documents` | `id`, `user_id`, `filename`, `mime_type`, `size_bytes`, `storage_uri`, `status`, `created_at` | 上传文档 |
| `processing_jobs` | `id`, `document_id`, `job_type`, `status`, `stage`, `progress`, `error_code`, `error_message`, `retry_count` | 后台任务 |
| `parsed_sections` | `id`, `document_id`, `parent_id`, `title`, `content`, `page_start`, `page_end`, `order_index` | 结构化章节 |
| `document_chunks` | `id`, `document_id`, `section_id`, `content`, `page_number`, `chunk_index`, `embedding` | RAG检索单元 |
| `document_assets` | `id`, `document_id`, `asset_type`, `storage_uri`, `caption`, `description`, `page_number`, `metadata` | 图片、表格、公式等资源 |
| `source_spans` | `id`, `document_id`, `section_id`, `chunk_id`, `page_number`, `bbox`, `char_start`, `char_end` | 引用来源定位 |
| `knowledge_points` | `id`, `document_id`, `name`, `description`, `category`, `importance`, `metadata` | 知识点 |
| `knowledge_relations` | `id`, `source_id`, `target_id`, `relation_type`, `weight` | 知识点关系 |
| `outlines` | `id`, `document_id`, `content_markdown`, `content_latex`, `version`, `created_by` | 复习提纲 |
| `questions` | `id`, `document_id`, `knowledge_point_id`, `question_type`, `difficulty`, `stem`, `answer`, `explanation` | 例题 |
| `qa_sessions` | `id`, `user_id`, `document_id`, `title`, `created_at` | 问答会话 |
| `qa_messages` | `id`, `session_id`, `role`, `content`, `sources`, `created_at` | 问答消息 |
| `feedback` | `id`, `user_id`, `target_type`, `target_id`, `rating`, `comment` | 用户反馈 |
| `content_versions` | `id`, `target_type`, `target_id`, `version`, `content`, `created_by`, `change_summary` | 编辑和生成版本 |
| `export_jobs` | `id`, `document_id`, `version_id`, `format`, `status`, `storage_uri`, `error_message` | 导出任务 |
| `export_files` | `id`, `export_job_id`, `storage_uri`, `size_bytes`, `content_hash`, `created_at` | 导出产物 |
| `quality_scores` | `id`, `target_type`, `target_id`, `metric`, `score`, `evidence`, `created_at` | 自动评估结果 |
| `review_tasks` | `id`, `target_type`, `target_id`, `status`, `assignee`, `decision`, `comment` | 人工审核任务 |
| `audit_logs` | `id`, `actor_id`, `action`, `resource_type`, `resource_id`, `request_id`, `created_at` | 权限和关键操作审计 |

**向量检索策略**：
- MVP：ChromaDB本地持久化或FAISS。
- 正式产品：优先pgvector，保持关系数据和向量索引一致；大规模部署可切换Qdrant/Milvus。
- 每个chunk必须保存源文档、页码、章节和版本，问答引用不可只返回裸文本。

### 10.5 文档标准化与引用追踪

Marker、PPT解析器和后续多模态解析器的输出必须先进入统一标准化层，再进入知识抽取、RAG、提纲、例题和导出模块。禁止各模块直接依赖某个解析器的原始输出结构。

**标准化数据对象**：
| 对象 | 关键字段 | 说明 |
|------|----------|------|
| `NormalizedDocument` | `document_id`, `title`, `sections`, `assets`, `metadata` | 解析后的统一文档视图 |
| `NormalizedSection` | `id`, `parent_id`, `title`, `content`, `level`, `order_index`, `source_spans` | 章节/段落结构 |
| `DocumentChunk` | `id`, `section_id`, `content`, `chunk_index`, `source_spans`, `metadata` | RAG和引用检索单元 |
| `DocumentAsset` | `id`, `type`, `storage_uri`, `caption`, `description`, `source_span` | 图片、表格、公式等资源 |
| `SourceSpan` | `page_number`, `bbox`, `section_id`, `char_start`, `char_end` | 引用来源定位 |

**标准化规则**：
- 每个section和chunk必须保留 `SourceSpan`，至少包含页码或章节定位。
- 表格、公式、图片必须以asset形式保存，不得只混入纯文本。
- chunk切分应优先按章节、标题、公式块和表格边界切分，避免切断公式或表格。
- 标准化层必须输出可序列化JSON，作为后续调试、回放和评测的稳定输入。
- 如果解析器无法提供页码或bbox，必须在metadata中记录缺失原因，并将引用置信度降级。

### 10.6 版本、编辑与导出

正式产品必须把“AI生成结果”和“用户编辑结果”作为版本化资产管理。提纲、例题、QA摘要和导出文件都不能只保留最后一次生成结果。

**版本对象**：
| 对象 | 字段 | 说明 |
|------|------|------|
| `content_versions` | `id`, `target_type`, `target_id`, `version`, `content`, `created_by`, `created_at`, `change_summary` | 提纲、例题、QA摘要等内容版本 |
| `export_jobs` | `id`, `document_id`, `version_id`, `format`, `status`, `storage_uri`, `error_message` | 导出任务 |
| `export_files` | `id`, `export_job_id`, `storage_uri`, `size_bytes`, `content_hash`, `created_at` | 导出产物 |

**导出要求**：
- Markdown导出保留标题层级、公式LaTeX、题目答案和来源引用。
- LaTeX/PDF导出必须校验公式转义，导出失败时返回可读错误和错误ID。
- JSON导出必须包含结构化字段、版本号、来源引用和生成/编辑元数据。
- 导出任务必须异步执行，不能阻塞API请求；导出结果必须受权限校验保护。

### 10.7 质量评估、反馈与人工审核

质量闭环分为自动评估、用户反馈、人工审核和后续自进化数据沉淀。MVP-1只需要基础自动校验；正式产品必须把反馈和审核沉淀为结构化数据。

**自动评估维度**：
| 目标 | 指标 | 失败处理 |
|------|------|----------|
| 提纲 | 覆盖率、层级完整性、引用覆盖率、重复率 | 标记低置信度并建议重新生成 |
| 例题 | 答案一致性、难度匹配、题型多样性、知识点覆盖 | 阻止进入“推荐”状态 |
| QA回答 | 来源召回率、引用准确率、未支持断言比例 | 降级置信度或要求补检索 |
| 导出 | 格式有效性、引用完整性、文件可打开 | 导出任务失败并保留错误 |

**反馈对象**：
| 对象 | 字段 | 说明 |
|------|------|------|
| `feedback` | `target_type`, `target_id`, `rating`, `reason`, `comment`, `created_by` | 用户反馈 |
| `review_tasks` | `target_type`, `target_id`, `status`, `assignee`, `decision`, `comment` | 人工审核任务 |
| `quality_scores` | `target_type`, `target_id`, `metric`, `score`, `evidence` | 自动评估结果 |

**进入自进化的门槛**：
- 只有通过人工审核或高置信度自动评估的数据，才能进入自进化候选数据集。
- 用户负反馈必须先聚类和脱敏，不能直接作为提示词优化输入。
- 自进化变更必须走PR式人工批准流程，不允许运行时自动替换生产提示词或策略。

### 10.8 文件存储

**开发期**：
- 本地 `data/uploads/` 保存原始文件。
- 本地 `data/outputs/` 保存导出产物。
- 本地 `data/vector_db/` 保存向量索引。

**正式部署**：
- 原始文件、解析图片、导出PDF等二进制文件进入对象存储，如S3、MinIO或云厂商OSS。
- 数据库只保存 `storage_uri`、hash、大小、mime type和生命周期状态。
- 上传必须限制文件类型、文件大小、路径穿越和重复文件hash。
- 需要定义数据保留策略：默认保留原始文件和结果，用户可删除文档并级联删除派生数据。

### 10.9 安全、权限与审计

- 所有上传文件必须按用户或组织隔离。
- 禁止将API key、原始文件路径、模型响应中的敏感信息写入普通日志。
- 文件名只作为展示字段，实际存储使用UUID或hash路径。
- 导出接口必须校验文档归属权。
- RAG查询必须限定在用户可访问的文档集合内。
- 后台任务读取文件时只能使用受控storage接口，不能拼接任意用户输入路径。

**权限模型**：
| 资源 | 权限动作 | 要求 |
|------|----------|------|
| 文档 | `read`, `update`, `delete`, `export` | 必须校验用户或组织归属 |
| 任务 | `read`, `retry`, `cancel` | 只能操作自己可见文档的任务 |
| 反馈 | `create`, `read` | 普通用户只能读取自己的反馈 |
| 审核任务 | `read`, `decide` | 仅审核员或管理员可操作 |

**审计日志**：
- 记录上传、删除、导出、重试、权限拒绝、审核决定等关键事件。
- 审计日志必须包含 `actor_id`、`action`、`resource_type`、`resource_id`、`request_id`、`created_at`。
- 审计日志不得记录原始文件内容、完整模型输出、API key或用户隐私文本。

### 10.10 部署与运维

**正式产品组件**：
```text
Web Frontend
  -> FastAPI API Server
  -> PostgreSQL + pgvector
  -> Redis Queue
  -> Worker Process
  -> Object Storage
  -> LLM/Marker Providers
```

**最小部署**：
- Docker Compose启动 API、worker、PostgreSQL、Redis、MinIO。
- 前端可由Vite构建静态文件，通过Nginx或API服务托管。

**可观测性**：
- 结构化日志包含 `request_id`、`user_id`、`document_id`、`job_id`、`stage`。
- 指标至少包括任务成功率、平均处理时间、模型调用失败率、解析失败率、队列长度。
- 每个失败job保留错误类型、错误摘要和可重试标记。

**运维门槛**：
- 每个API请求必须生成或传播 `request_id`。
- 每个后台job必须能从API日志追踪到worker日志。
- 模型调用、解析调用、导出任务必须记录耗时和失败类型。
- 生产环境必须提供健康检查接口，至少区分API、数据库、队列、对象存储和模型供应商可用性。

### 10.11 分阶段路线

| 阶段 | 目标 | 范围 |
|------|------|------|
| MVP-1 | PDF端到端核心闭环 | CLI/内部接口，PDF解析、知识点、提纲、例题、测试修复 |
| MVP-2 | Web正式产品雏形 + 普通RAG baseline | React前端、FastAPI、文档上传、任务状态、结果展示、chunk检索、文档标准化 |
| MVP-3 | 数据持久化与Graph RAG-lite | PostgreSQL/pgvector、文档库、问答会话、引用追踪、知识图谱检索、版本化存储 |
| MVP-4 | Agentic RAG与自动路由 | 多步检索、复杂出题、RAG评测集、路由策略 |
| MVP-5 | 协作与质量闭环 | 用户反馈、版本管理、人工审核、质量评估 |
| MVP-6 | 规模化与运维 | 队列worker、对象存储、监控告警、权限隔离、审计日志 |
| MVP-7 | 自进化系统 | DSPy/GEPA评估集、人工批准、PR式部署 |

## 11. 总结

本设计文档描述了PPT/PDF转复习提纲和考试例题智能系统的目标架构、组件、数据流和实现计划。系统最终将采用模块化分层架构，通过多智能体协作、Agentic RAG、记忆系统和智能模型路由，提供高质量的复习提纲和考试例题生成服务。

**当前进度**：核心骨架约40%完成，但真实业务闭环尚未完成。下一步应优先修复测试环境、适配当前Marker API、实现MVP-1端到端PDF流程，再扩展PPT、Web/API、MCP和自进化能力。
