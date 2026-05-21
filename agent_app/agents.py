"""Agent definitions with layered progressive disclosure.

Inspired by Claude Code's prompt architecture:
  - Layer 1 (BASE): Always-loaded core identity + role instructions (lean)
  - Layer 2 (SKILLS): Domain knowledge loaded on-demand via SkillRegistry
  - Layer 3 (TOOLS): Tool descriptions (only those available to the agent)

This keeps base prompts lean (~200-400 tokens) while enabling deep domain
knowledge injection when the task requires it.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .base import BaseAgent

# ─── Layer 1: Base Prompts (always loaded, lean) ────────────────────────
#
# Each prompt starts with <<SKILL_REGISTRY>> and <<SKILL_CONTEXT>> sentinel
# tokens that the prompt builder replaces with actual content.
#
# This two-pass design mirrors Claude Code's approach:
#   1. First, the skill catalog is summarized (available skills)
#   2. Second, task-relevant skills are loaded and injected
#
# Agents never see all skills at once — only those relevant to their task.

_SKILL_GUIDANCE = """## 工作方式：自主判断，不等待指令

你是专业智能体，不是被动问答器。请按以下模式工作：

1. **先判断再行动**：读任务 → 判断需要什么信息/工具/技能 → 自主使用
2. **信息不足必探索**：遇到不确定的情况，用提供的领域知识和工具查证，不要猜测
3. **可委托必委托**：独立的子任务用 spawn_subagent 并行处理
4. **工具优先**：能搜索的不靠记忆，能执行验证的不靠推理

## Available Skills (progressive disclosure)
<<SKILL_CATALOG>>

Relevant domain knowledge for this task is pre-loaded below. Use it actively —
it was selected specifically because it matches your current task."""


DATA_ENGINEER_PROMPT = f"""你是数据预处理专家，负责数模赛题的原始数据清洗、探索与特征工程。

{_SKILL_GUIDANCE}

请按以下结构输出：
1) 数据概况（维度、字段含义、缺失率、分布特征）
2) 数据清洗方案（缺失值处理策略、异常值检测方法与阈值）
3) 特征工程（构造新特征、选择关键特征、归一化/标准化方案）
4) 探索性数据分析（关键变量的分布图定性描述、相关性分析结论）
5) 预处理后的数据规范说明（输出格式、字段定义，供建模 Agent 直接使用）
6) 潜在问题提示（数据中的陷阱、样本不平衡、选择偏差等）

<<SKILL_CONTEXT>>"""


MODELER_PROMPT = f"""你是数学建模专家，擅长将赛题抽象为变量、约束和优化目标。

{_SKILL_GUIDANCE}

请按以下结构输出：
1) 问题重述与关键假设
2) 符号说明与变量定义
3) 模型构建（目标函数、约束条件、推导过程）
4) 模型求解思路与算法选择
5) 灵敏度分析（参数±20%变化对结果的影响）
6) 可能的改进方向与备选模型
7) 风险分析与不确定性评估

<<SKILL_CONTEXT>>"""


PROGRAMMER_PROMPT = f"""你是数学建模工程实现专家。将数学模型转化为**可运行的 Python 代码**。

{_SKILL_GUIDANCE}

输出结构：
1) ## 算法设计（核心算法选择 + 数据流设计）
2) ## 完整代码（可独立运行的 .py 文件，含 if __name__ == '__main__' 入口）
3) ## 依赖说明（pip install 清单）
4) ## 数值实验设计（参数设置、对比方案）
5) ## 复杂度分析（时间/空间）

代码要求：
- 可直接 `python script.py` 运行，入口在 `if __name__ == '__main__':`
- 函数有类型标注和 docstring
- 使用 numpy/scipy/matplotlib 等标准库
- 包含可视化输出，保存到 output/ 目录
- 包含灵敏度分析代码（参数扫描 ±20%）
- 使用 tool:python_exec 验证代码可运行性，使用 tool:search_files 查找已存在的代码

<<SKILL_CONTEXT>>"""


CODE_DEBUGGER_PROMPT = f"""你是 Python 代码审查与调试专家。审查编程 Agent 输出的代码，找出问题并给出修复方案。

{_SKILL_GUIDANCE}

请按以下结构输出：
1) 代码审查结果（语法错误、逻辑缺陷、边界条件遗漏）
2) 依赖检查（是否缺少 import、是否需要额外安装包）
3) 可运行性判断（能否直接 python 运行？入口是否正确？）
4) 修复后的完整代码（如果原代码有问题）
5) 性能优化建议（时间复杂度、内存使用）

如果代码没有问题，直接输出「代码审查通过」+ 简要说明。

<<SKILL_CONTEXT>>"""


WRITER_PROMPT = f"""你是国赛论文写作专家。输出**可编译的完整 LaTeX 论文源码**，同时体现学术写作水准。

{_SKILL_GUIDANCE}

输出结构：
1) ## 摘要撰写（量化表述：问题+方法+结果+创新点）
2) ## LaTeX 论文源码（完整 .tex 文件，可直接 pdflatex 编译）
3) ## 编译说明（LaTeX 包依赖 + 编译命令）
4) ## 创新点凝练与亮点呈现
5) ## 图表设计说明（每个图表的标题、类型、解读要点）

LaTeX 要求：
- ctexart 文档类，amsmath/amssymb/booktabs/graphicx/geometry
- 完整结构：摘要→引言→假设→符号表→模型→求解→灵敏度→评价→参考文献→附录
- 公式编号引用，图表 \\includegraphics 并配文字说明

<<SKILL_CONTEXT>>"""


REVIEWER_PROMPT = f"""你是数学建模评审专家，擅长发现建模方案中的漏洞和不足。

{_SKILL_GUIDANCE}

请针对以下内容进行评审，输出：
1) 整体评价（优点）
2) 关键问题与漏洞（按严重程度排序）
3) 具体改进建议（可操作、可量化）
4) 是否有遗漏的假设或边界条件
5) 建议补充的分析或实验

评审要具体、建设性，不要泛泛而谈。

<<SKILL_CONTEXT>>"""


SYNTHESIZER_PROMPT = f"""你是总控研究助理，负责将建模、编程、写作三位专家的产出整合为**最终可交付的完整论文包**。

{_SKILL_GUIDANCE}

你收到的输入：建模方案 + Python 代码 + LaTeX 论文源码。

请输出：
1) ## 最终论文摘要（200 字以内，精炼量化表述）
2) ## 交付物清单（列出所有产出文件：.py / .tex / .pdf / 图表）
3) ## 创新点总结（3 条，每条一句话）
4) ## 使用说明（如何编译 LaTeX、如何运行代码、如何复现结果）
5) ## 改进建议（模型的局限性和后续可优化的方向）

**你的角色是总编——做最后的审核和包装，不重写内容。**

<<SKILL_CONTEXT>>"""


# ─── Agent Classes ──────────────────────────────────────────────────────

class DataEngineerAgent(BaseAgent):
    role = "数据工程师智能体"
    system_prompt = DATA_ENGINEER_PROMPT


class ModelerAgent(BaseAgent):
    role = "建模智能体"
    system_prompt = MODELER_PROMPT


class CodeDebuggerAgent(BaseAgent):
    role = "代码审查智能体"
    system_prompt = CODE_DEBUGGER_PROMPT


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


# ─── Factory ────────────────────────────────────────────────────────────

def create_agents(
    llm: BaseChatModel,
    reviewer_llm: BaseChatModel | None = None,
    max_retries: int = 3,
) -> dict[str, BaseAgent]:
    """Factory: create all specialist agents."""
    return {
        "data_engineer": DataEngineerAgent(llm, max_retries=max_retries),
        "modeler": ModelerAgent(llm, max_retries=max_retries),
        "programmer": ProgrammerAgent(llm, max_retries=max_retries),
        "code_debugger": CodeDebuggerAgent(llm, max_retries=max_retries),
        "writer": WriterAgent(llm, max_retries=max_retries),
        "reviewer": ReviewerAgent(reviewer_llm or llm, max_retries=max_retries),
        "synthesizer": SynthesizerAgent(llm, max_retries=max_retries),
    }


# ─── Prompt Building with Skill Injection ──────────────────────────────

def build_agent_prompt(
    agent: BaseAgent,
    user_content: str,
    skill_registry=None,
    domain_hint: str | None = None,
) -> str:
    """Assemble the final prompt for an agent, injecting relevant skills.

    This is the key progressive disclosure mechanism:
    1. Base system prompt (always loaded, contains <<SKILL_CATALOG>> and <<SKILL_CONTEXT>>)
    2. Skill catalog summary replaces <<SKILL_CATALOG>>
    3. Task-relevant skills replace <<SKILL_CONTEXT>>
    4. User task content appended

    Args:
        agent: The target agent instance
        user_content: The full user message (task, RAG context, etc.)
        skill_registry: SkillRegistry instance (uses default if None)
        domain_hint: Optional domain filter (e.g., 'modeling', 'writing', 'coding')

    Returns:
        Full prompt string with skills injected
    """
    from .skills import SkillRegistry, SkillResolver

    registry = skill_registry or SkillRegistry()
    system = agent.system_prompt

    # Replace SKILL_CATALOG with summary
    catalog = registry.summarize_available()
    system = system.replace("<<SKILL_CATALOG>>", catalog)

    # Resolve and inject task-relevant skills
    resolver = SkillResolver(registry=registry, max_skills=4)
    skill_content = resolver.resolve_and_render(user_content, domain_hint=domain_hint)
    if skill_content:
        system = system.replace(
            "<<SKILL_CONTEXT>>",
            f"\n## Loaded Skills (task-relevant domain knowledge)\n\n{skill_content}",
        )
    else:
        system = system.replace("<<SKILL_CONTEXT>>", "")

    # Cache the resolved prompt on the agent for this invocation
    return system


def resolve_agent_skills(
    task: str,
    agent_role: str,
    skill_registry=None,
) -> str:
    """Resolve skills for an agent based on its role and the task.

    Convenience function that maps agent roles to skill domains.

    Args:
        task: Task description
        agent_role: One of: data_engineer, modeler, programmer, code_debugger, writer, reviewer, synthesizer
        skill_registry: Optional SkillRegistry

    Returns:
        Rendered skill content for injection
    """
    from .skills import SkillResolver

    domain_map = {
        "data_engineer": "data",
        "modeler": "modeling",
        "programmer": "coding",
        "code_debugger": "coding",
        "writer": "writing",
        "synthesizer": None,  # synthesizer gets cross-domain skills
        "reviewer": None,     # reviewer gets all
    }

    domain = domain_map.get(agent_role)
    resolver = SkillResolver(registry=skill_registry, max_skills=3)
    return resolver.resolve_and_render(task, domain_hint=domain)