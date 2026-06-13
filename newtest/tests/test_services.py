import pytest
from src.services.rag_service import RAGService, QueryType, RetrievalStrategy


def test_rag_service_initialization():
    """测试RAG服务初始化"""
    rag = RAGService()
    assert rag.vector_store is None
    assert rag.knowledge_graph is None


def test_query_type_detection():
    """测试查询类型检测"""
    rag = RAGService()
    assert rag.detect_query_type("什么是机器学习？") == QueryType.DEFINITION
    assert rag.detect_query_type("举个例子") == QueryType.EXAMPLE


def test_retrieval_strategy_selection():
    """测试检索策略选择"""
    rag = RAGService()
    strategy = rag.select_strategy("简单事实查询", QueryType.DEFINITION)
    assert strategy == RetrievalStrategy.SIMPLE_RAG
