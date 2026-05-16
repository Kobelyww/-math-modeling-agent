"""数模多智能体协作系统 - agent_app

提供可扩展的多 Agent 协作框架，用于数学建模竞赛问题的分析求解。

核心模块：
- config: 配置管理，支持 .env 与按 Agent 的个性化设置
- llm: LLM 工厂
- base: Agent 基类（invoke / stream / 自动重试）
- agents: 五大专业 Agent（建模/编程/写作/评审/总控）
- orchestrator: 编排器，支持 3 种协作策略
- memory: 共享上下文总线
- rag: 论文知识库检索增强
- tools: 通用工具（计算器、笔记）
- cli: 命令行交互入口
- gui: Streamlit 图形界面入口
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from .config import Settings, load_settings
from .orchestrator import Orchestrator, WorkflowResult

__all__ = ["Settings", "load_settings", "Orchestrator", "WorkflowResult"]