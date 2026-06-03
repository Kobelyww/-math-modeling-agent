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

字数要求：正文至少 8000 字，目标 10000-12000 字。必须达到最低字数要求。
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
        大纲会自动经过内容安全筛查。

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
        outline = normalize_content(response.content)
        # 内容安全筛查
        from .pipeline import moderate_content
        return moderate_content(llm, outline)
    return plan_outline


def _make_write_draft(llm: BaseChatModel):
    @tool
    def write_draft(topic: str, outline: str, skills: str, revision_feedback: str = "",
                    chapter_index: int = 1, total_chapters: int = 1) -> str:
        """根据大纲创作小说正文。支持单章和多章模式。

        Args:
            topic: 创作主题
            outline: 故事大纲（多章时包含章节划分）
            skills: 相关创作技能卡内容
            revision_feedback: 上一轮的评审修改意见（首次创作时为空字符串）
            chapter_index: 当前章节序号（1-based，单章模式为1）
            total_chapters: 总章节数（单章模式为1）
        """
        feedback_section = f"\n\n修改意见（必须照此修改）：\n{revision_feedback}" if revision_feedback else ""
        if total_chapters > 1:
            chapter_hint = (
                f"你正在创作第 {chapter_index}/{total_chapters} 章。\n"
                f"本章目标：8000-12000 字，有独立的起承转合，章末留悬念钩子。\n"
                + (f"这是第一章——建立世界观、引入主角和核心冲突。\n" if chapter_index == 1 else "")
                + (f"这是中间章节——推进主线、展开支线、加深人物关系。\n" if 1 < chapter_index < total_chapters else "")
                + (f"这是最终章——收束所有伏笔，给出完整结局。\n" if chapter_index == total_chapters else "")
            )
            prompt = (
                f"创作主题：{topic}\n\n故事大纲：\n{outline}\n\n{skills}\n\n"
                f"{chapter_hint}\n请创作第 {chapter_index} 章完整正文。{feedback_section}"
            )
        else:
            prompt = (
                f"创作主题：{topic}\n\n故事大纲：\n{outline}\n\n{skills}\n\n"
                f"请创作完整小说正文，至少 8000 字，有完整的开头、发展、高潮和结局。{feedback_section}"
            )
        response = llm.invoke([
            SystemMessage(content=DRAFT_WRITER_PROMPT),
            HumanMessage(content=prompt),
        ])
        return normalize_content(response.content)
    return write_draft


def _make_polish_draft(llm: BaseChatModel):
    @tool
    def polish_draft(topic: str, draft: str, feedback: str = "",
                     chapter_index: int = 1, total_chapters: int = 1) -> str:
        """润色优化小说正文，提升文学质量和传播力。

        Args:
            topic: 创作主题
            draft: 需要润色的小说正文
            feedback: 评审反馈（可选）
            chapter_index: 当前章节序号
            total_chapters: 总章节数
        """
        ch_hint = f"（第 {chapter_index}/{total_chapters} 章）" if total_chapters > 1 else ""
        prompt = (
            f"创作主题：{topic}\n\n原文{ch_hint}：\n{draft}\n\n"
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
- **plan_outline**: 设计故事大纲（多章时需划分每章要点）
- **write_draft**: 创作小说正文，参数 chapter_index/total_chapters 控制章节
- **polish_draft**: 润色优化文本质量
- **synthesize**: 整合所有产出，生成发布方案

工作流程：

[单章模式] total_chapters=1：
1. analyze_topic → 2. plan_outline → 3. write_draft(chapter_index=1) → 审查 → polish_draft → synthesize

[多章模式] total_chapters>1：
1. analyze_topic
2. plan_outline（标注每章核心情节、人物弧光、悬念点）
3. 对每一章依次：write_draft(chapter_index=N) → 审查 → polish_draft(chapter_index=N)
4. 全部章节完成后：synthesize（生成完整发布方案）

[续写模式] 已有前文，需要续写下一章：
- 根据已有章节内容和大纲，调用 write_draft 创作下一章，保持连贯

每章目标 8000-12000 字。章末留悬念钩子。
最终输出格式：【小说正文】（含所有章节）和【发布方案】"""


# ============================================================
# DeepAgent Middleware — 状态机 + 双权限审查
# ============================================================

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware

logger = logging.getLogger(__name__)


def _get_request_messages(request) -> list:
    """Normalize request.messages — request can be dict or ModelRequest object."""
    if isinstance(request, dict):
        return request.get("messages", [])
    return getattr(request, "messages", [])


# 审查提示词
REVIEW_SPEC_PROMPT = """请对以上创作结果进行**计划审查 (Spec Review)**：
对照原始大纲和创作要求，逐项检查：
1. 是否覆盖了大纲中的所有情节要点？
2. 人物设定是否与规划一致？
3. 开篇钩子是否按要求实现？
4. 字数是否达标（≥2000字）？
5. 故事是否有完整的开头、发展、高潮、结局？
审查通过时请在输出末尾加上：[SPEC_APPROVED]"""

REVIEW_QUALITY_PROMPT = """请对以上创作结果进行**质量审查 (Quality Review)**：
1. 开篇钩子力：前200字能否抓住读者？
2. 对话和描写的张力是否足够？
3. 节奏是否有拖沓或跳跃？
4. 结尾余韵：读完后是否想评论/转发？
5. 是否有值得截屏传播的金句？
审查通过时请在输出末尾加上：[QUALITY_APPROVED]"""

# 流水线阶段定义
# permission_review_spec:     True=该阶段要求 spec 审查通过才能离开
# permission_review_quality:  True=该阶段要求 quality 审查通过才能离开
# approval_marker:           Coordinator 审批时在输出中标注的关键词
STAGES = {
    "init": {
        "label": "🎯 选题分析",
        "tools": ["analyze_topic"],
        "requires": [],
        "permission_review_spec": False,
        "permission_review_quality": False,
    },
    "topic_analyzed": {
        "label": "📋 大纲规划",
        "tools": ["analyze_topic", "plan_outline"],
        "requires": ["analyze_topic"],
        "permission_review_spec": False,
        "permission_review_quality": False,
    },
    "outline_planned": {
        "label": "✍️ 初稿创作",
        "tools": ["analyze_topic", "plan_outline", "write_draft"],
        "requires": ["analyze_topic", "plan_outline"],
        "permission_review_spec": False,
        "permission_review_quality": False,
    },
    "draft_written": {
        "label": "🔍 计划审查",
        "tools": [],
        "requires": ["analyze_topic", "plan_outline", "write_draft"],
        "permission_review_spec": True,
        "permission_review_quality": False,
        "review_prompt": REVIEW_SPEC_PROMPT,
        "approval_marker": "[SPEC_APPROVED]",
    },
    "draft_reviewed_spec": {
        "label": "🔎 质量审查",
        "tools": [],
        "requires": ["analyze_topic", "plan_outline", "write_draft"],
        "permission_review_spec": False,
        "permission_review_quality": True,
        "review_prompt": REVIEW_QUALITY_PROMPT,
        "approval_marker": "[QUALITY_APPROVED]",
    },
    "draft_reviewed_quality": {
        "label": "✨ 润色优化",
        "tools": ["write_draft", "polish_draft"],
        "requires": ["analyze_topic", "plan_outline", "write_draft"],
        "permission_review_spec": False,
        "permission_review_quality": False,
    },
    "polished": {
        "label": "📦 发布整合",
        "tools": ["polish_draft", "synthesize"],
        "requires": ["analyze_topic", "plan_outline", "write_draft", "polish_draft"],
        "permission_review_spec": False,
        "permission_review_quality": False,
    },
    "done": {
        "label": "✅ 全部完成",
        "tools": [],
        "requires": ["analyze_topic", "plan_outline", "write_draft", "polish_draft", "synthesize"],
        "permission_review_spec": False,
        "permission_review_quality": False,
    },
}


class StageGateMiddleware(AgentMiddleware):
    """状态机 + 双权限审查中间件。

    审查流程：
    1. write_draft 完成 → 进入 🔍 计划审查（无工具可用）
    2. Coordinator 输出审查意见 + [SPEC_APPROVED] → 中间件捕获
    3. 进入 🔎 质量审查
    4. Coordinator 输出审查意见 + [QUALITY_APPROVED] → 中间件捕获
    5. 两项都 allow → 进入 ✨ 润色优化
    """

    def __init__(self) -> None:
        super().__init__()
        self._stage: str = "init"
        self._tool_history: list[str] = []
        self._spec_approved: bool = False
        self._quality_approved: bool = False

    @property
    def current_stage(self) -> str:
        return self._stage

    # ---- helpers ----

    def _stage_info(self) -> dict:
        return STAGES.get(self._stage, STAGES["init"])

    def _missing_requires(self, target_stage: str) -> list[str]:
        return [r for r in STAGES.get(target_stage, {}).get("requires", []) if r not in self._tool_history]

    def _check_permissions(self, target_stage: str) -> bool:
        info = STAGES.get(target_stage, {})
        if info.get("permission_review_spec") and not self._spec_approved:
            return False
        if info.get("permission_review_quality") and not self._quality_approved:
            return False
        return True

    def _can_enter(self, target_stage: str) -> bool:
        return not self._missing_requires(target_stage) and self._check_permissions(target_stage)

    # ---- wrap_model_call ----

    def wrap_model_call(self, request, handler):
        self._inject_context(request)
        result = handler(request)
        self._detect_approval(result)
        self._try_advance()
        return result

    def _detect_approval(self, result) -> None:
        # result can be ModelResponse, AIMessage, or dict
        content = ""
        if isinstance(result, dict):
            messages = result.get("messages", [])
            if messages:
                last = messages[-1]
                content = last.get("content", "") if isinstance(last, dict) else getattr(last, "content", "")
        else:
            content = getattr(result, "content", "")
        if not isinstance(content, str) or not content:
            return
        info = self._stage_info()
        marker = info.get("approval_marker", "")
        if marker and marker in content:
            if marker == "[SPEC_APPROVED]" and not self._spec_approved:
                self._spec_approved = True
                logger.info("✅ Spec 审查通过")
            elif marker == "[QUALITY_APPROVED]" and not self._quality_approved:
                self._quality_approved = True
                logger.info("✅ Quality 审查通过")

    def _inject_context(self, request) -> None:
        info = self._stage_info()
        available = info.get("tools", [])
        label = info.get("label", self._stage)
        review_prompt = info.get("review_prompt", "")
        marker = info.get("approval_marker", "")

        # 权限状态
        perm_parts: list[str] = []
        if info.get("permission_review_spec"):
            perm_parts.append(f"  permission_review_spec: {'✅ allow' if self._spec_approved else '⏳ pending（需输出 {marker}）'}")
        if info.get("permission_review_quality"):
            perm_parts.append(f"  permission_review_quality: {'✅ allow' if self._quality_approved else '⏳ pending（需输出 {marker}）'}")

        stage_hint = f"\n\n【{label}】\n"
        if perm_parts:
            stage_hint += "审查权限：\n" + "\n".join(perm_parts) + "\n"

        if review_prompt:
            stage_hint += (
                f"\n⚠️ 审查阶段 — 不可调用工具。请针对上一轮输出进行审查：\n\n"
                f"{review_prompt}\n"
            )
        elif available:
            stage_hint += f"工具：{', '.join(available)}\n"
        else:
            stage_hint += "工具：无（请输出最终结果）\n"

        stage_hint += f"历史：{' → '.join(self._tool_history) if self._tool_history else '无'}\n"

        messages = _get_request_messages(request)
        if messages:
            first = messages[0]
            role = getattr(first, "type", "") or getattr(first, "role", "")
            if role in ("system",):
                first.content = (first.content or "") + stage_hint

    # ---- wrap_tool_call ----

    def wrap_tool_call(self, request, handler):
        # ToolCallRequest has: tool_call (dict with name/args), tool, state, runtime
        tc = request.tool_call if hasattr(request, "tool_call") else request
        tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")

        result = handler(request)
        self._tool_history.append(tool_name)
        self._try_advance()
        return self._validate(tool_name, result)

    def _try_advance(self) -> None:
        best = self._stage
        for name in STAGES:
            if self._can_enter(name):
                best = name
        if best != self._stage:
            logger.info("推进: %s → %s", STAGES[self._stage]["label"], STAGES[best]["label"])
            self._stage = best

    def _validate(self, tool_name: str, result) -> Any:
        text = result
        if not isinstance(result, str):
            text = getattr(result, "content", "") or str(result)
        if tool_name == "write_draft" and isinstance(text, str) and len(text) < 1000:
            return text + "\n\n⚠️ 正文不足 1000 字，请确保完整章节至少 8000 字。"
        if tool_name == "polish_draft" and isinstance(text, str) and len(text) < 1000:
            return text + "\n\n⚠️ 润色后正文太短，请输出完整全文。"
        return result


class FinalOutputMiddleware(AgentMiddleware):
    """确保最终输出包含【小说正文】和【发布方案】两个章节。"""

    def wrap_model_call(self, request, handler):
        output_rules = (
            "\n\n【输出铁律】\n"
            "1. 最终回复必须包含两个标记章节：【小说正文】和【发布方案】\n"
            "2. 【小说正文】：完整故事 ≥2000 字，有开头、发展、高潮、结局\n"
            "3. 【发布方案】：5 个备选标题 + 5-8 个标签 + 爆款概率评估\n"
            "4. 禁止输出不完整的故事或「未完待续」\n"
        )
        messages = _get_request_messages(request)
        if messages:
            first = messages[0]
            role = getattr(first, "type", "") or getattr(first, "role", "")
            if role in ("system",):
                first.content = (first.content or "") + output_rules
        return handler(request)


def create_coordinator(
    llm: BaseChatModel,
    skills_store: SkillsStore | None = None,
    genre: str | None = None,
):
    """创建小说创作 Coordinator DeepAgent。"""
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
            StageGateMiddleware(),
            FinalOutputMiddleware(),
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
        return {"total_score": total_score, "full_report": full_report}

    def _extract_score(self, report: str) -> float:
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
        return sum(scores) / len(scores) if scores else 5.0
