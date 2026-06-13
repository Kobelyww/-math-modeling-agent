import pytest
from src.agents.base_agent import BaseAgent, AgentResult, AgentStatus


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


class FailingAgent(BaseAgent):
    """测试用失败智能体"""
    role = "失败专家"
    system_prompt = "总是失败"
    
    def __init__(self, fail_count: int = 3):
        super().__init__()
        self.fail_count = fail_count
        self.call_count = 0
    
    async def process(self, input_data: str) -> AgentResult:
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise ValueError(f"模拟失败第{self.call_count}次")
        return AgentResult(
            success=True,
            data={"processed": input_data},
            message="终于成功"
        )


class AlwaysFailAgent(BaseAgent):
    """总是失败的智能体"""
    role = "永久失败者"
    system_prompt = "永远失败"
    
    async def process(self, input_data: str) -> AgentResult:
        raise RuntimeError("永久失败")

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


@pytest.mark.asyncio
async def test_invoke_success():
    """测试invoke成功调用"""
    agent = MockAgent()
    assert agent.status == AgentStatus.IDLE
    
    result = await agent.invoke("测试输入")
    
    assert result.success is True
    assert result.data == {"processed": "测试输入"}
    assert result.message == "处理完成"
    assert result.status == AgentStatus.COMPLETED
    assert agent.status == AgentStatus.COMPLETED


@pytest.mark.asyncio
async def test_invoke_status_transitions():
    """测试invoke状态转换"""
    agent = MockAgent()
    assert agent.status == AgentStatus.IDLE
    
    await agent.invoke("test")
    
    assert agent.status == AgentStatus.COMPLETED


@pytest.mark.asyncio
async def test_invoke_error_handling():
    """测试invoke错误处理"""
    agent = AlwaysFailAgent()
    assert agent.status == AgentStatus.IDLE
    
    result = await agent.invoke("test")
    
    assert result.success is False
    assert result.status == AgentStatus.FAILED
    assert "处理失败" in result.message
    assert agent.status == AgentStatus.FAILED
    assert agent.retry_count > 0


@pytest.mark.asyncio
async def test_invoke_retry_logic():
    """测试重试逻辑 - 失败后重试最终成功"""
    agent = FailingAgent(fail_count=2)
    agent.max_retries = 3
    
    result = await agent.invoke("test")
    
    assert result.success is True
    assert result.data == {"processed": "test"}
    assert agent.call_count == 3


@pytest.mark.asyncio
async def test_invoke_exhausted_retries():
    """测试重试耗尽"""
    agent = FailingAgent(fail_count=5)
    agent.max_retries = 3
    
    result = await agent.invoke("test")
    
    assert result.success is False
    assert result.status == AgentStatus.FAILED
    assert "重试3次后" in result.message
    assert agent.retry_count == 4


def test_reset():
    """测试reset方法"""
    agent = MockAgent()
    agent.status = AgentStatus.COMPLETED
    agent.retry_count = 5
    
    agent.reset()
    
    assert agent.status == AgentStatus.IDLE
    assert agent.retry_count == 0
