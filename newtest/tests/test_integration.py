import pytest
from src.config import load_config
from src.agents.base_agent import BaseAgent, AgentResult
from src.parsers.marker_pdf import MarkerPDFParser, StructuredDocument
from src.knowledge.knowledge_graph import KnowledgeGraph, KnowledgePoint
from src.services.rag_service import RAGService
from src.services.memory_service import MemoryService
from src.coordinator.main_coordinator import MainCoordinator

@pytest.mark.asyncio
async def test_full_pipeline():
    """测试完整流程"""
    # 1. 加载配置
    config = load_config()
    assert config.llm.primary_model == "mimo-v2.5"

    # 2. 初始化组件
    parser = MarkerPDFParser()
    knowledge_graph = KnowledgeGraph()
    rag_service = RAGService()
    memory_service = MemoryService()
    coordinator = MainCoordinator()

    # 3. 测试组件集成
    assert parser is not None
    assert knowledge_graph is not None
    assert rag_service is not None
    assert memory_service is not None
    assert coordinator is not None

    # 4. 测试知识图谱添加
    kp = KnowledgePoint(
        id="kp1",
        name="测试概念",
        description="这是一个测试概念",
        category="概念",
        importance=0.8
    )
    knowledge_graph.add_point(kp)
    assert len(knowledge_graph.nodes) == 1

    # 5. 测试记忆服务
    memory_service.add_message("user", "测试消息")
    context = memory_service.get_context()
    assert "测试消息" in context

    # 6. 测试协调器状态
    status = coordinator.get_status()
    assert status["current_stage"] == "idle"
