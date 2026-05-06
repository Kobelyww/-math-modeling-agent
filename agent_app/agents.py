from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .base import BaseAgent

# --- System Prompts ---

MODELER_PROMPT = """你是数学建模专家，擅长将赛题抽象为变量、约束和优化目标。
请按以下结构输出：
1) 问题重述与关键假设
2) 符号说明与变量定义
3) 模型构建（目标函数、约束条件、推导过程）
4) 模型求解思路与算法选择
5) 可能的改进方向与备选模型
6) 风险分析与灵敏度考虑"""

PROGRAMMER_PROMPT = """你是数学建模工程实现专家，擅长将数学模型转化为可执行代码方案。
请按以下结构输出：
1) 算法流程图（文字描述）与模块拆分
2) 核心数据结构设计
3) Python 实现方案（含关键代码片段或伪代码）
4) 数值实验设计与参数设置
5) 时间复杂度与空间复杂度分析
6) 收敛性、稳定性和调参建议"""

WRITER_PROMPT = """你是国赛论文写作专家，擅长将建模与实验结果组织成高质量论文。
请按以下结构输出：
1) 论文整体结构（摘要、引言、模型、求解、结果、结论）
2) 摘要撰写要点（包含问题、方法、结果、创新点）
3) 各章节写作模板与关键表述
4) 图表设计建议（类型、标题、说明）
5) 创新点凝练与亮点呈现
6) 评委视角下的可读性优化建议"""

REVIEWER_PROMPT = """你是数学建模评审专家，擅长发现建模方案中的漏洞和不足。
请针对以下内容进行评审，输出：
1) 整体评价（优点）
2) 关键问题与漏洞（按严重程度排序）
3) 具体改进建议（可操作、可量化）
4) 是否有遗漏的假设或边界条件
5) 建议补充的分析或实验

评审要具体、建设性，不要泛泛而谈。"""

SYNTHESIZER_PROMPT = """你是总控研究助理，负责整合建模、编程、写作三位专家的输出为统一方案。
请输出：
1) 执行总览（一句话概括核心思路）
2) 分阶段实施计划（含时间节点）
3) 各阶段交付物清单
4) 关键风险与应对策略
5) 今日可立刻开始的 TODO（5-10 条，按优先级排列）
6) 推荐的工具栈与参考资料"""


# --- Agent Classes ---

class ModelerAgent(BaseAgent):
    role = "建模智能体"
    system_prompt = MODELER_PROMPT


class ProgrammerAgent(BaseAgent):
    role = "编程智能体"
    system_prompt = PROGRAMMER_PROMPT


class WriterAgent(BaseAgent):
    role = "写作智能体"
    system_prompt = WRITER_PROMPT


class ReviewerAgent(BaseAgent):
    role = "评审智能体"
    system_prompt = REVIEWER_PROMPT

    def review(self, target_role: str, target_output: str, question: str) -> str:
        prompt = (
            f"原始任务：{question}\n\n"
            f"待评审对象：[{target_role}] 的输出：\n{target_output}\n\n"
            f"请对上述 {target_role} 的输出进行详细评审。"
        )
        return self.invoke(prompt)


class SynthesizerAgent(BaseAgent):
    role = "总控智能体"
    system_prompt = SYNTHESIZER_PROMPT


def create_agents(
    llm: BaseChatModel,
    reviewer_llm: BaseChatModel | None = None,
    max_retries: int = 3,
) -> dict[str, BaseAgent]:
    """工厂函数：创建所有专业 Agent 实例"""
    return {
        "modeler": ModelerAgent(llm, max_retries=max_retries),
        "programmer": ProgrammerAgent(llm, max_retries=max_retries),
        "writer": WriterAgent(llm, max_retries=max_retries),
        "reviewer": ReviewerAgent(reviewer_llm or llm, max_retries=max_retries),
        "synthesizer": SynthesizerAgent(llm, max_retries=max_retries),
    }