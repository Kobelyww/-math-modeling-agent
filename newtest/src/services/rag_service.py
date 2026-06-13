from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class QueryType(Enum):
    """查询类型"""
    DEFINITION = "definition"
    EXAMPLE = "example"
    CONNECTION = "connection"
    PREREQUISITE = "prerequisite"
    SIMPLE_FACT = "simple_fact"
    COMPLEX_REASONING = "complex_reasoning"


class RetrievalStrategy(Enum):
    """检索策略"""
    SIMPLE_RAG = "simple_rag"
    AGENTIC_RAG = "agentic_rag"
    HYBRID = "hybrid"


@dataclass
class Chunk:
    """文档块"""
    content: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


@dataclass
class RAGResponse:
    """RAG响应"""
    answer: str
    sources: List[str] = field(default_factory=list)
    chunks: List[Chunk] = field(default_factory=list)
    confidence: float = 0.0


class RAGService:
    """RAG服务（混合方案）"""

    def __init__(self):
        self.vector_store = None
        self.knowledge_graph = None

    def detect_query_type(self, query: str) -> QueryType:
        """检测查询类型"""
        if "什么是" in query or "定义" in query:
            return QueryType.DEFINITION
        elif "例子" in query or "举例" in query:
            return QueryType.EXAMPLE
        elif "关系" in query or "联系" in query:
            return QueryType.CONNECTION
        elif "前置" in query or "基础" in query:
            return QueryType.PREREQUISITE
        else:
            return QueryType.SIMPLE_FACT

    def select_strategy(self, query: str, query_type: QueryType) -> RetrievalStrategy:
        """选择检索策略"""
        if query_type in [QueryType.SIMPLE_FACT, QueryType.DEFINITION, QueryType.EXAMPLE]:
            return RetrievalStrategy.SIMPLE_RAG
        elif query_type in [QueryType.COMPLEX_REASONING]:
            return RetrievalStrategy.AGENTIC_RAG
        else:
            return RetrievalStrategy.HYBRID

    async def query(self, query: str) -> RAGResponse:
        """执行查询"""
        query_type = self.detect_query_type(query)
        strategy = self.select_strategy(query, query_type)

        if strategy == RetrievalStrategy.SIMPLE_RAG:
            return await self._simple_rag_query(query)
        elif strategy == RetrievalStrategy.AGENTIC_RAG:
            return await self._agentic_rag_query(query)
        else:
            return await self._hybrid_query(query)

    async def _simple_rag_query(self, query: str) -> RAGResponse:
        """简单RAG查询"""
        return RAGResponse(
            answer="简单RAG查询结果",
            sources=[],
            chunks=[],
            confidence=0.8
        )

    async def _agentic_rag_query(self, query: str) -> RAGResponse:
        """Agentic RAG查询"""
        return RAGResponse(
            answer="Agentic RAG查询结果",
            sources=[],
            chunks=[],
            confidence=0.9
        )

    async def _hybrid_query(self, query: str) -> RAGResponse:
        """混合查询"""
        return RAGResponse(
            answer="混合查询结果",
            sources=[],
            chunks=[],
            confidence=0.85
        )
