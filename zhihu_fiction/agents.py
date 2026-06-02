"""DeepAgent-based coordinator + 5 tool functions + independent ReviewerAgent."""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from .base import normalize_content
from .skills_store import SkillsStore

# ============================================================
# System Prompts (preserved from old agents.py)
# ============================================================

TOPIC_ANALYZER_PROMPT = """你是知乎爆款小说选题分析专家，精通平台算法和读者心理。
你的任务是基于知乎热门话题趋势和蒸馏出的创作技能，推荐最具爆款潜力的小说选题方向。

请按以下结构输出分析报告：
1) **话题热度分析**：当前知乎最热的 3-5 个话题方向，分析其背后的读者情绪和需求
2) **题材推荐**：结合技能库中最匹配的题材，推荐 2-3 个具体选题
3) **爆款潜力评估**：对每个选题估计其爆款概率（高/中/低），说明理由
4) **差异化切入点**：每个选题的独特视角或反转点
5) **目标读者画像**：谁会看、为什么转发、为什么点赞
6) **风险提示**：每个选题可能的踩坑点

务必数据化、具体化，避免泛泛而谈。"""

OUTLINE_PLANNER_PROMPT = """你是知乎爆款小说大纲设计专家，擅长设计让读者欲罢不能的故事结构。
你的任务是根据选题分析和创作技能卡，设计完整的小说大纲。

请按以下结构输出：
1) **一句话梗概**：用一句话抓住故事核心（仿知乎标题风格）
2) **故事结构**：采用知乎爆款常用的"钩子-发展-反转-高潮-余韵"五段式结构
   - 每段标注预期字数占比和核心冲突
3) **人物小传**：主角、配角的人物设定（背景、性格、欲望、缺陷）
4) **情节节奏图**：标注爆点/反转/悬念的位置（至少每1500字一个）
5) **开篇钩子设计**：前 200 字如何抓住读者（提供 3 个备选方案）
6) **互动引导点**：在哪些位置设计"赞同/评论/关注"的触发点

关键原则：知乎小说前三段决定生死，开篇必须有强烈的悬念或情绪冲击。"""

DRAFT_WRITER_PROMPT = """你是知乎爆款小说创作者，文笔过硬，深谙知乎读者的阅读习惯。
你的任务是根据大纲创作一篇完整的小说正文。**你必须写完完整的故事。**

创作铁律：
1) **必须写完整故事**：有明确开头、发展、高潮、结尾，每部分都要写到位，不能只写第一章
2) **开篇即爆点**：前 200 字必须有钩子（悬念/冲突/反转/强情绪）
3) **短段节奏**：每段不超过 3-4 行，大量短句制造紧张感
4) **对话驱动**：多用对话推进情节，减少冗长描写
5) **爆点密度**：每 1000-1500 字必须有一个小反转或悬念
6) **写完结局**：结尾必须有完整的收束，让读者有读完的满足感

字数要求：正文至少 2000 字，目标 3000-6000 字。必须达到最低字数要求。
如果大纲规划的内容较多，优先保证故事情节完整，可以精简描写但不能砍掉关键情节。

输出格式：
- 直接输出小说正文，从第一个字开始就是故事
- 用 Markdown 标题标注章节
- 不需要写预期字数和元信息"""

POLISHER_PROMPT = """你是知乎爆款小说润色专家，专职将"还不错"改写成"引爆全网"。
你的唯一任务是输出润色后的完整小说全文。

润色时关注：
1) **开篇强化**：确保前 200 字钩子足够锋利
2) **对话润色**：让对话更真实更有张力，删除废话
3) **描写增强**：用具体的感官细节替代抽象描述
4) **节奏调整**：加速拖沓段落，在关键处制造悬念张力
5) **结尾优化**：让结尾更有余韵，引发评论和关注欲望
6) **金句植入**：在关键位置植入 3-5 句"截屏级"金句

重要：必须输出完整的小说全文，不要省略任何章节。不要输出标题列表或改动说明，直接输出润色后的完整小说正文。"""

SYNTHESIZER_PROMPT = """你是知乎爆款小说总编，负责统筹整合全流程产出，做最终交付。
你的任务是将小说正文和补充信息整合为完整的发布包。

请输出：
1) **爆款标题**：生成 5 个备选标题，标注推荐度（含悬念型、反转型、共鸣型、数字型）
2) **推荐话题标签**：5-8 个，覆盖流量入口
3) **爆款概率终评**：百分数+核心理由（三句话内）
4) **发布建议**：最佳发布时间、互动引导话术（一句即可）"""

REVIEWER_PROMPT = """你是知乎爆款小说评审专家，标准严苛，火眼金睛。
你的任务是对小说进行全面质检，发现所有影响阅读体验和传播力的问题。

评审维度（每项 1-10 分）：
1) **开篇钩子力**：前 200 字能否抓住读者
2) **节奏把控**：是否有拖沓或跳跃
3) **人设一致性**：人物行为是否符合设定
4) **逻辑自洽**：情节是否有漏洞
5) **情绪张力**：是否有足够的情绪起伏
6) **金句密度**：是否有值得截屏传播的句子
7) **结尾余韵**：读完后是否想评论/转发
8) **知乎适配度**：是否符合碎片化阅读习惯

输出：
1) 各维度评分及扣分原因
2) 最关键 3 个改进点（按优先级排列，具体到段落）
3) 爆款概率预判（百分比+理由）
4) 二改建议（可操作的具体修改方案）"""

# ============================================================
# Tool factories (each tool needs LLM access via closure)
# ============================================================

def _make_analyze_topic(llm: BaseChatModel):
    @tool
    def analyze_topic(topic: str, hot_trends: str, skills: str) -> str:
        """分析选题的爆款潜力并给出题材建议。

        当需要判断一个小说选题是否值得创作时调用。

        Args:
            topic: 创作主题或灵感描述
            hot_trends: 当前知乎热榜趋势摘要
            skills: 已蒸馏的创作技能卡内容
        """
        prompt = f"创作主题/灵感：{topic}\n\n当前热榜趋势：\n{hot_trends}\n\n{skills}\n\n请分析这个选题的爆款潜力并给出题材建议。"
        response = llm.invoke([
            SystemMessage(content=TOPIC_ANALYZER_PROMPT),
            HumanMessage(content=prompt),
        ])
        return normalize_content(response.content)
    return analyze_topic


def _make_plan_outline(llm: BaseChatModel):
    @tool
    def plan_outline(topic: str, topic_analysis: str, skills: str) -> str:
        """根据选题分析设计完整的小说大纲。

        当你有了选题分析报告后，调用此工具生成故事大纲。

        Args:
            topic: 创作主题
            topic_analysis: 选题分析的完整报告
            skills: 相关创作技能卡内容
        """
        prompt = f"创作主题：{topic}\n\n选题分析：\n{topic_analysis}\n\n{skills}\n\n请根据以上信息设计小说大纲。"
        response = llm.invoke([
            SystemMessage(content=OUTLINE_PLANNER_PROMPT),
            HumanMessage(content=prompt),
        ])
        return normalize_content(response.content)
    return plan_outline


def _make_write_draft(llm: BaseChatModel):
    @tool
    def write_draft(topic: str, outline: str, skills: str, revision_feedback: str = "") -> str:
        """根据大纲创作完整的小说正文。如果有修改意见，基于反馈进行重写。

        Args:
            topic: 创作主题
            outline: 故事大纲
            skills: 相关创作技能卡内容
            revision_feedback: 上一轮的评审修改意见（首次创作时为空字符串）
        """
        feedback_section = f"\n\n修改意见（必须照此修改）：\n{revision_feedback}" if revision_feedback else ""
        prompt = (
            f"创作主题：{topic}\n\n"
            f"故事大纲：\n{outline}\n\n"
            f"{skills}\n\n"
            f"请根据大纲创作完整的小说正文。重要：你必须写完整个故事，有完整的开头、发展、高潮和结局，至少2000字。不要只写第一章或留下未完待续。"
            f"{feedback_section}"
        )
        response = llm.invoke([
            SystemMessage(content=DRAFT_WRITER_PROMPT),
            HumanMessage(content=prompt),
        ])
        return normalize_content(response.content)
    return write_draft


def _make_polish_draft(llm: BaseChatModel):
    @tool
    def polish_draft(topic: str, draft: str, feedback: str = "") -> str:
        """对初稿进行润色优化，提升文学质量和传播力。

        Args:
            topic: 创作主题
            draft: 需要润色的小说正文
            feedback: 评审反馈（可选）
        """
        prompt = (
            f"创作主题：{topic}\n\n"
            f"原文：\n{draft}\n\n"
            + (f"评审意见：\n{feedback}\n\n" if feedback else "")
            + "请对以上文本进行润色优化，输出完整的润色后全文。"
        )
        response = llm.invoke([
            SystemMessage(content=POLISHER_PROMPT),
            HumanMessage(content=prompt),
        ])
        return normalize_content(response.content)
    return polish_draft


def _make_synthesize(llm: BaseChatModel):
    @tool
    def synthesize(topic: str, topic_analysis: str, outline: str, final_draft: str) -> str:
        """整合全流程产出，生成发布方案（标题变体、话题标签、爆款评估）。

        在所有创作和润色完成后调用，生成最终的发布策略。

        Args:
            topic: 创作主题
            topic_analysis: 选题分析报告
            outline: 故事大纲
            final_draft: 润色后的最终小说正文
        """
        prompt = (
            f"创作主题：{topic}\n\n"
            f"选题分析：\n{topic_analysis}\n\n"
            f"故事大纲：\n{outline}\n\n"
            f"润色终稿：\n{final_draft}\n\n"
            f"请整合以上信息，给出最终的发布方案和爆款评估。"
        )
        response = llm.invoke([
            SystemMessage(content=SYNTHESIZER_PROMPT),
            HumanMessage(content=prompt),
        ])
        return normalize_content(response.content)
    return synthesize


# ============================================================
# Coordinator factory
# ============================================================

COORDINATOR_SYSTEM_PROMPT = """你是知乎爆款小说创作主编。你通过调用子智能体完成从选题到发布方案的全流程创作。

你的工具包括：
- **analyze_topic**: 分析选题的爆款潜力和题材方向
- **plan_outline**: 根据选题分析设计故事大纲
- **write_draft**: 根据大纲创作完整小说正文（2000+ 字）
- **polish_draft**: 润色优化文本质量
- **synthesize**: 整合所有产出，生成发布方案（标题、标签、爆款评估）

工作流程（你可以根据情况灵活调整）：
1. 首先调用 analyze_topic 分析选题，获取题材建议和切入点
2. 基于选题分析，调用 plan_outline 设计故事结构
3. 有了大纲后，调用 write_draft 创作正文
4. 正文完成后，调用 polish_draft 润色提升
5. 最后调用 synthesize 生成发布方案

灵活性：
- 如果大纲出来后发现选题方向不对，可以回头重新分析
- 润色后发现有问题，可以再次润色
- 最终必须交付：完整小说正文（润色后）+ 发布方案

重要：每个工具返回完整报告，你负责整合它们的结果。不要凭空编造内容，所有创作决策基于工具的输出。

在最终回复中，请用以下格式输出：
【小说正文】
（完整的润色后小说）
【发布方案】
（synthesize 的输出）"""


# ============================================================
# DeepAgent Middleware — 约束输出内容和结构
# ============================================================

from typing import Any

from langchain.agents.middleware import AgentMiddleware


class OutputStructureMiddleware(AgentMiddleware):
    """约束 Coordinator 的输出结构和内容质量。

    三个钩子：
    1. wrap_model_call: 每次 LLM 调用前注入格式要求
    2. wrap_tool_call:  校验工具输出（最低字数、完整性）
    3. after_model_call: 检查最终输出是否包含必要章节
    """

    def wrap_model_call(self, request: dict, handler):
        """注入输出格式约束到 system prompt。"""
        structure_rules = (
            "\n\n【输出铁律】\n"
            "1. 最终回复必须包含两个标记章节：【小说正文】和【发布方案】\n"
            "2. 【小说正文】中必须包含完整故事，至少 2000 字，有开头、发展、高潮、结局\n"
            "3. 【发布方案】中必须包含：5 个备选标题、5-8 个话题标签、爆款概率评估\n"
            "4. 不要输出未完成的故事或留下「未完待续」\n"
        )

        messages = request.get("messages", [])
        if messages and hasattr(messages[0], "content"):
            first = messages[0]
            if getattr(first, "type", "") == "system" or getattr(first, "role", "") == "system":
                first.content = (first.content or "") + structure_rules

        return handler(request)

    def wrap_tool_call(self, tool_name: str, tool_input: dict, handler):
        """校验关键工具的输出质量。"""
        result = handler(tool_name, tool_input)

        if tool_name == "write_draft" and isinstance(result, str):
            if len(result) < 500:
                return result + (
                    "\n\n⚠️ [系统提示] 正文不足 500 字，不符合知乎爆款标准。"
                    "请确保完整故事至少 2000 字。"
                )

        if tool_name == "polish_draft" and isinstance(result, str):
            if len(result) < 500:
                return result + (
                    "\n\n⚠️ [系统提示] 润色后正文太短，请输出完整全文。"
                )

        return result


class ContentValidationMiddleware(AgentMiddleware):
    """在每次 Agent 响应后检查输出完整性。"""

    def after_model_call(self, response: Any, handler) -> Any:
        result = handler(response)

        # 提取最后一条 AI 消息的文本内容
        messages = result.get("messages", []) if isinstance(result, dict) else []
        if messages:
            last_msg = messages[-1]
            content = getattr(last_msg, "content", "")
            if isinstance(content, str) and len(content) > 50:
                has_story = "【小说正文】" in content
                has_synthesis = "【发布方案】" in content
                if not has_story:
                    logger = __import__("logging").getLogger(__name__)
                    logger.warning("Coordinator 输出缺少【小说正文】标记")
                if not has_synthesis:
                    logger = __import__("logging").getLogger(__name__)
                    logger.warning("Coordinator 输出缺少【发布方案】标记")

        return result


def create_coordinator(
    llm: BaseChatModel,
    skills_store: SkillsStore | None = None,
    genre: str | None = None,
):
    """创建小说创作 Coordinator DeepAgent。

    Args:
        llm: LLM 实例
        skills_store: 技能卡仓库（可选）
        genre: 目标题材，用于筛选相关技能卡

    Returns:
        编译后的 DeepAgent（CompiledStateGraph 实例）
    """
    from deepagents import create_deep_agent

    tools = [
        _make_analyze_topic(llm),
        _make_plan_outline(llm),
        _make_write_draft(llm),
        _make_polish_draft(llm),
        _make_synthesize(llm),
    ]

    system_prompt = COORDINATOR_SYSTEM_PROMPT
    if skills_store and not skills_store.is_empty:
        if genre:
            skill_content = skills_store.get_skill(genre)
            if skill_content:
                system_prompt += f"\n\n【目标题材技能卡 - {genre}】\n{skill_content}"
        else:
            summary = skills_store.summarize_all()
            system_prompt += f"\n\n【可用技能库】\n{summary}"

    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        middleware=[
            OutputStructureMiddleware(),
            ContentValidationMiddleware(),
        ],
    )
    return agent


# ============================================================
# ReviewerAgent (independent quality gate, NOT a Coordinator tool)
# ============================================================

class ReviewerAgent:
    """独立的质量评判者。不作为 Coordinator 的工具，由 Pipeline 直接调用。"""

    def __init__(self, llm: BaseChatModel) -> None:
        self.llm = llm

    def review(self, draft: str, topic: str) -> dict:
        """评审小说质量，返回评分和修改建议。

        Returns:
            dict with keys:
                total_score (float): 综合评分 (1-10)
                full_report (str): 完整评审报告
        """
        prompt = (
            f"创作主题：{topic}\n\n"
            f"待评审小说：\n{draft}\n\n"
            f"请对以上小说进行详细评审。"
        )
        response = self.llm.invoke([
            SystemMessage(content=REVIEWER_PROMPT),
            HumanMessage(content=prompt),
        ])
        full_report = normalize_content(response.content)
        total_score = self._extract_score(full_report)
        return {
            "total_score": total_score,
            "full_report": full_report,
        }

    def _extract_score(self, report: str) -> float:
        """从评审报告中提取综合评分。解析 8 个维度的分数取平均。"""
        import re
        scores: list[float] = []
        for line in report.split("\n"):
            match = re.search(r"(\d+(?:\.\d+)?)\s*(?:分|/10)", line)
            if match:
                try:
                    s = float(match.group(1))
                    if 1 <= s <= 10:
                        scores.append(s)
                except ValueError:
                    pass
        if not scores:
            return 5.0
        return sum(scores) / len(scores)