import pytest
from src.agents.base_agent import BaseAgent, AgentResult

class MockAgent(BaseAgent):
    """测试用模拟智能体"""
    role = "测试专家"
    system_prompt = "你是一个测试专家"
    
    async def process(self, input_data: str) -> AgentResult:
        return AgentResult(
            success=True,
            data={"processed": input_data},
            message="处理完成"
        )

def test_base_agent_initialization():
    """测试基础智能体初始化"""
    agent = MockAgent()
    assert agent.role == "测试专家"
    assert agent.system_prompt == "你是一个测试专家"

def test_agent_result_creation():
    """测试智能体结果创建"""
    result = AgentResult(
        success=True,
        data={"key": "value"},
        message="成功"
    )
    assert result.success is True
    assert result.data == {"key": "value"}
    assert result.message == "成功"
