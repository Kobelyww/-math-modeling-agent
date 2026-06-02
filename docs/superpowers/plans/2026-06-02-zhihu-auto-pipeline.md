# Zhihu Auto Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-to-end autonomous fiction pipeline (scrape → select topic → DeepAgent create → review with retry → full auto publish) for Zhihu.

**Architecture:** Rewrite the agent layer with DeepAgents — a Coordinator DeepAgent orchestrates 5 tool functions (topic analysis, outline, draft, polish, synthesize) via tool-calling. ReviewerAgent stays independent as Pipeline's quality gate. A new `pipeline.py` ties scraping, selection, creation, review, and publishing into a schedulable workflow. `automator_zhihu.py` achieves true full-auto publishing by clicking buttons and handling confirmation dialogs.

**Tech Stack:** DeepAgents (`create_deep_agent` with LangChain tools), Playwright (browser automation), existing DeepSeek LLM via `langchain-deepseek`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `base.py` (rewrite) | Content normalization utility, no more BaseAgent class |
| `agents.py` (rewrite) | 5 `@tool` functions + `create_coordinator()` factory + `ReviewerAgent` |
| `orchestrator.py` (rewrite) | Thin `create_orchestrator()` — wraps Coordinator.invoke() + parses output |
| `pipeline.py` (new) | `Pipeline` class: scrape → select → create → review → publish, supports scheduling |
| `automator_zhihu.py` (new) | `ZhihuPublisher` class: login, fill title/content/tags, click publish, confirm, verify |
| `cli.py` (modify) | Add `/auto`, `/schedule start/stop/status` commands |
| `__init__.py` (modify) | Remove `workspace_shims`, update exports |

---

### Task 1: Rewrite `base.py` — remove BaseAgent, keep utilities

**Files:**
- Rewrite: `zhihu_fiction/base.py`

`base.py` currently holds `BaseAgent` (invoke + stream + retry) and `SharedMemory`. With DeepAgents, the Coordinator handles retry and context. SharedMemory becomes unnecessary since DeepAgent manages its own message history. Keep only the content normalization utility.

- [ ] **Step 1: Write the new base.py**

```python
"""Shared utilities — content normalization."""
from __future__ import annotations


def normalize_content(content) -> str:
    """Normalize LangChain message content to a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)
```

- [ ] **Step 2: Verify nothing else imports from base.py that will break**

Run: `grep -rn "from .base import\|from zhihu_fiction.base import" zhihu_fiction/`

If any file imports `BaseAgent` or `SharedMemory`, those files will be rewritten in later tasks (agents.py, orchestrator.py). Note them for reference.

- [ ] **Step 3: Commit**

```bash
git add zhihu_fiction/base.py
git commit -m "refactor: simplify base.py to normalize_content utility"
```

---

### Task 2: Rewrite `agents.py` — 5 tool functions + Coordinator factory + ReviewerAgent

**Files:**
- Rewrite: `zhihu_fiction/agents.py`

The old 6 Agent subclasses become 5 `@tool` functions (each internally calls LLM) + 1 `create_coordinator()` factory + `ReviewerAgent` class. System prompts from old `agents.py` are preserved as constants.

- [ ] **Step 1: Write the new agents.py**

```python
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


def create_coordinator(
    llm: BaseChatModel,
    skills_store: SkillsStore | None = None,
    genre: str | None = None,
) -> "CompiledStateGraph":
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
                scores (dict[str, int]): 8 维度评分
                total_score (float): 综合评分 (1-10)
                top_issues (list[str]): 最关键的改进点
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
            match = re.search(r"(\d+)\s*(?:分|/10)", line)
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
```

- [ ] **Step 2: Verify the file has no syntax errors**

Run: `python -c "import ast; ast.parse(open('zhihu_fiction/agents.py').read()); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add zhihu_fiction/agents.py
git commit -m "refactor: rewrite agents with DeepAgents coordinator + 5 tool functions"
```

---

### Task 3: Rewrite `orchestrator.py` — thin wrapper around Coordinator

**Files:**
- Rewrite: `zhihu_fiction/orchestrator.py`

The old `Orchestrator` class had 5 methods (solve_fast/polish/full/stream/continue) each with ~50 lines of manual prompt concatenation. The new version is a thin function that invokes the DeepAgent Coordinator and parses the result.

- [ ] **Step 1: Write the new orchestrator.py**

```python
"""Thin wrapper around DeepAgent Coordinator invocation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agents import create_coordinator, create_reviewer, ReviewerAgent
from .base import normalize_content
from .config import Settings
from .llm import create_llm
from .skills_store import SkillsStore


@dataclass
class StageResult:
    role: str
    content: str


@dataclass
class WorkflowResult:
    topic: str
    genre: str
    topic_analysis: str
    outline: str
    draft: str
    polished: str
    review: str
    synthesis: str  # The combined final story + publish plan

    def format_overview(self) -> str:
        lines = [
            "=" * 60,
            f"  选题：{self.topic}",
            f"  题材：{self.genre}",
            "=" * 60,
            "",
            self.polished,
            "",
            "=" * 60,
            self.synthesis,
        ]
        return "\n".join(lines)

    @property
    def final_story(self) -> str:
        return self.polished


def _parse_coordinator_output(output: str) -> dict[str, str]:
    """Parse Coordinator's final output into structured sections.

    Coordinator outputs:
    【小说正文】
    <story>
    【发布方案】
    <publish plan>
    """
    result = {"story": "", "synthesis": ""}

    story_start = output.find("【小说正文】")
    synth_start = output.find("【发布方案】")

    if story_start >= 0 and synth_start >= 0:
        result["story"] = output[story_start + 7:synth_start].strip()
        result["synthesis"] = output[synth_start + 7:].strip()
    elif story_start >= 0:
        result["story"] = output[story_start + 7:].strip()
    else:
        result["story"] = output

    return result


def run_coordinator(
    llm,
    coordinator,
    topic: str,
    hot_trends: str = "",
    genre: str | None = None,
    revision_feedback: str = "",
) -> WorkflowResult:
    """Run the Coordinator DeepAgent to create a fiction from topic.

    Args:
        llm: LLM instance
        coordinator: Compiled DeepAgent from create_coordinator()
        topic: The fiction topic/theme
        hot_trends: Current Zhihu hot trends summary (for context)
        genre: Target genre (optional)

    Returns:
        WorkflowResult with the complete fiction and metadata
    """
    feedback_section = ""
    if revision_feedback:
        feedback_section = f"\n\n【修改要求】上一轮评审未达标，请根据以下反馈重新创作：\n{revision_feedback}"

    prompt = f"""请创作一篇关于以下主题的知乎爆款小说：{topic}

当前知乎热榜趋势参考：
{hot_trends or '暂无热榜数据，请根据你的知识判断选题方向'}

请按照标准工作流程完成创作：选题分析 → 大纲规划 → 初稿创作 → 润色优化 → 发布方案整合。
最终用【小说正文】和【发布方案】两个标记分别输出。{feedback_section}"""

    result = coordinator.invoke({
        "messages": [{"role": "user", "content": prompt}],
    })

    final_message = result["messages"][-1]
    output = normalize_content(final_message.content)

    parsed = _parse_coordinator_output(output)

    resolved_genre = genre or "未指定"
    return WorkflowResult(
        topic=topic,
        genre=resolved_genre,
        topic_analysis="",  # intermediate steps are inside Coordinator trace
        outline="",
        draft="",
        polished=parsed["story"],
        review="",
        synthesis=parsed["synthesis"],
    )


def create_orchestrator(
    settings: Settings,
    skills_store: SkillsStore | None = None,
    genre: str | None = None,
):
    """Create the Coordinator and ReviewerAgent for the given settings.

    Returns a tuple of (coordinator, reviewer, llm).
    """
    llm = create_llm(settings)
    coordinator = create_coordinator(llm, skills_store=skills_store, genre=genre)
    reviewer = ReviewerAgent(llm)
    return coordinator, reviewer, llm


class OrchestratorCompat:
    """Backward-compatible wrapper so old CLI commands (/create, /fast, etc) keep working.

    Delegates to run_coordinator under the hood.
    """

    def __init__(self, coordinator, reviewer, llm, settings, skills_store=None):
        self._coordinator = coordinator
        self._reviewer = reviewer
        self._llm = llm
        self.settings = settings
        self.skills = skills_store

    def solve_fast(self, topic: str, genre: str | None = None, memory=None) -> WorkflowResult:
        return run_coordinator(self._llm, self._coordinator, topic=topic, genre=genre)

    def solve_full(self, topic: str, genre: str | None = None, max_review_rounds=2, memory=None) -> WorkflowResult:
        return run_coordinator(self._llm, self._coordinator, topic=topic, genre=genre)

    def solve_polish(self, topic: str, genre: str | None = None, max_review_rounds=2, memory=None) -> WorkflowResult:
        return run_coordinator(self._llm, self._coordinator, topic=topic, genre=genre)

    def solve_stream(
        self,
        topic: str,
        genre: str | None = None,
        on_topic_token=None,
        on_outline_token=None,
        on_draft_token=None,
        on_polish_token=None,
        on_synthesis_token=None,
    ) -> WorkflowResult:
        return run_coordinator(self._llm, self._coordinator, topic=topic, genre=genre)

    def continue_story(
        self,
        existing_story: str,
        topic: str,
        genre: str | None = None,
        chapter_count: int = 1,
    ) -> str:
        prompt = (
            f"创作主题：{topic}\n\n"
            f"已有故事：\n{existing_story}\n\n"
            f"请续写第 {chapter_count + 1} 章，保持文风一致，2000-4000 字，章末留悬念。"
        )
        result = self._coordinator.invoke({
            "messages": [{"role": "user", "content": prompt}],
        })
        from .base import normalize_content
        return normalize_content(result["messages"][-1].content)
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('zhihu_fiction/orchestrator.py').read()); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add zhihu_fiction/orchestrator.py
git commit -m "refactor: rewrite orchestrator as thin DeepAgent wrapper"
```

---

### Task 4: Create `pipeline.py` — end-to-end Pipeline with scheduling

**Files:**
- Create: `zhihu_fiction/pipeline.py`

Pipeline ties together: scrape → select topic → run Coordinator → review with retry → publish. Supports both one-shot `run()` and scheduled `run_scheduled()`.

- [ ] **Step 1: Write pipeline.py**

```python
"""End-to-end autonomous fiction pipeline with scheduling."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Protocol

from .config import APP_ROOT
from .scraper import scrape_zhihu_hot

RUN_DIR = APP_ROOT / "output" / ".pipeline"
SCHEDULE_FILE = RUN_DIR / "schedule.json"


# ============================================================
# Protocols
# ============================================================

class ScraperProtocol(Protocol):
    def __call__(self, limit: int = 50) -> list[dict]: ...


class TopicSelectorProtocol(Protocol):
    def __call__(self, hot_items: list[dict], llm) -> dict: ...


class PublisherProtocol(Protocol):
    def publish(self, title: str, content: str, tags: list[str], genre: str) -> dict: ...


# ============================================================
# Default topic selector
# ============================================================

TOPIC_SELECTOR_PROMPT = """你是知乎小说选题决策专家。从以下热榜话题中选出最适合创作爆款小说的1个话题。

热榜列表：
{hot_list}

请选出最具爆款潜力的1个话题，按以下格式输出：
选题：<话题标题>
题材：<题材类型，如悬疑/言情/职场/科幻等>
理由：<一句话说明为什么选这个（30字内）>"""


def select_topic(hot_items: list[dict], llm) -> dict:
    """Analyze hot list and select the best topic for fiction creation."""
    hot_list_text = "\n".join(
        f"{i + 1}. [{item.get('hot_score', 0):.0f}] {item['title']}"
        for i, item in enumerate(hot_items[:20])
    )
    prompt = TOPIC_SELECTOR_PROMPT.format(hot_list=hot_list_text)
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item)
            for item in content
        )

    import re
    topic_match = re.search(r"选题[：:]\s*(.+?)(?:\n|$)", content)
    genre_match = re.search(r"题材[：:]\s*(.+?)(?:\n|$)", content)

    topic = topic_match.group(1).strip() if topic_match else hot_items[0]["title"]
    genre = genre_match.group(1).strip() if genre_match else "未指定"

    return {"topic": topic, "genre": genre, "raw_analysis": content}


# ============================================================
# Stage result and run result
# ============================================================

@dataclass
class StageRecord:
    status: str  # ok | skipped | failed | fallback
    duration_s: float
    extra: dict = field(default_factory=dict)


@dataclass
class RunResult:
    run_id: str
    trigger: str  # scheduled | manual
    topic: str
    genre: str
    stages: dict[str, StageRecord] = field(default_factory=dict)
    total_duration_s: float = 0.0
    published_url: str = ""
    error: str = ""
    timestamp: str = ""

    def to_json(self) -> dict:
        return {
            "run_id": self.run_id,
            "trigger": self.trigger,
            "topic": self.topic,
            "genre": self.genre,
            "stages": {
                name: {"status": s.status, "duration_s": s.duration_s, **s.extra}
                for name, s in self.stages.items()
            },
            "total_duration_s": self.total_duration_s,
            "published_url": self.published_url,
            "error": self.error,
            "timestamp": self.timestamp,
        }


# ============================================================
# Pipeline
# ============================================================

class Pipeline:
    """Content-type agnostic autonomous fiction pipeline."""

    def __init__(
        self,
        coordinator,
        reviewer,
        llm,
        publisher,
        scraper=scrape_zhihu_hot,
        topic_selector=select_topic,
        quality_threshold: float = 6.0,
        max_rewrites: int = 2,
    ) -> None:
        self.coordinator = coordinator
        self.reviewer = reviewer
        self.llm = llm
        self.publisher = publisher
        self._scraper = scraper
        self._selector = topic_selector
        self.quality_threshold = quality_threshold
        self.max_rewrites = max_rewrites

        self._schedule_thread: threading.Thread | None = None
        self._schedule_stop = threading.Event()

        RUN_DIR.mkdir(parents=True, exist_ok=True)

    def run(self, topic: str | None = None, genre: str | None = None) -> RunResult:
        """Execute one full pipeline run.

        Args:
            topic: Fiction topic. If None, auto-select from hot list.
            genre: Target genre. If None, auto-detect.

        Returns:
            RunResult with all stage outcomes.
        """
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        result = RunResult(
            run_id=run_id,
            trigger="manual" if topic else "scheduled",
            topic=topic or "",
            genre=genre or "",
            timestamp=datetime.now().isoformat(),
        )
        start_time = time.time()

        # Stage 1: Scrape
        t0 = time.time()
        try:
            hot_items = self._scraper()
            result.stages["scrape"] = StageRecord(
                status="ok",
                duration_s=round(time.time() - t0, 1),
                extra={"items": len(hot_items)},
            )
        except Exception as exc:
            result.stages["scrape"] = StageRecord(
                status="failed",
                duration_s=round(time.time() - t0, 1),
                extra={"error": str(exc)},
            )
            result.total_duration_s = round(time.time() - start_time, 1)
            result.error = f"scrape failed: {exc}"
            self._append_run(result)
            return result

        # Stage 2: Select topic (only if not provided)
        if not topic:
            t0 = time.time()
            try:
                selection = self._selector(hot_items, self.llm)
                topic = selection["topic"]
                genre = selection.get("genre", genre)
                result.topic = topic
                result.genre = genre or "未指定"
                result.stages["select_topic"] = StageRecord(
                    status="ok",
                    duration_s=round(time.time() - t0, 1),
                    extra={"selected": topic, "genre": genre or ""},
                )
            except Exception as exc:
                topic = hot_items[0]["title"]
                result.topic = topic
                result.stages["select_topic"] = StageRecord(
                    status="fallback",
                    duration_s=round(time.time() - t0, 1),
                    extra={"selected": topic, "error": str(exc)},
                )
        else:
            result.stages["select_topic"] = StageRecord(
                status="ok", duration_s=0, extra={"selected": topic}
            )

        # Stage 3: Create (Coordinator + Review loop)
        t0 = time.time()
        hot_summary = self._format_hot_summary(hot_items)

        try:
            from .orchestrator import run_coordinator

            wf_result = run_coordinator(
                self.llm,
                self.coordinator,
                topic=topic,
                hot_trends=hot_summary,
                genre=genre,
            )

            # Quality gate: review + retry loop
            review_rounds = 0
            for round_num in range(self.max_rewrites + 1):
                review = self.reviewer.review(wf_result.final_story, topic)
                score = review["total_score"]
                review_rounds += 1

                if score >= self.quality_threshold:
                    break

                if round_num < self.max_rewrites:
                    feedback = f"评分 {score:.1f}/10 (门槛 {self.quality_threshold})。\n{review['full_report']}"
                    wf_result = run_coordinator(
                        self.llm,
                        self.coordinator,
                        topic=topic,
                        hot_trends=hot_summary,
                        genre=genre,
                        revision_feedback=feedback,
                    )

            result.stages["create"] = StageRecord(
                status="ok",
                duration_s=round(time.time() - t0, 1),
                extra={"words": len(wf_result.final_story)},
            )
            result.stages["review"] = StageRecord(
                status="ok",
                duration_s=0,  # included in create time
                extra={"score": review["total_score"], "rounds": review_rounds},
            )

            # Skip publish if quality too low after all retries
            if review["total_score"] < self.quality_threshold:
                result.stages["publish"] = StageRecord(
                    status="skipped",
                    duration_s=0,
                    extra={"reason": f"score {review['total_score']:.1f} < threshold {self.quality_threshold}"},
                )
                result.total_duration_s = round(time.time() - start_time, 1)
                self._append_run(result)
                return result

        except Exception as exc:
            result.stages["create"] = StageRecord(
                status="failed",
                duration_s=round(time.time() - t0, 1),
                extra={"error": str(exc)},
            )
            result.total_duration_s = round(time.time() - start_time, 1)
            result.error = f"create failed: {exc}"
            self._append_run(result)
            return result

        # Stage 4: Publish
        t0 = time.time()
        try:
            pub_result = self.publisher.publish(
                title=wf_result.topic,
                content=wf_result.final_story,
                tags=[],
                genre=wf_result.genre,
            )
            result.stages["publish"] = StageRecord(
                status="ok" if pub_result.get("success") else "failed",
                duration_s=round(time.time() - t0, 1),
                extra={"url": pub_result.get("url", ""), "message": pub_result.get("message", "")},
            )
            result.published_url = pub_result.get("url", "")
        except Exception as exc:
            result.stages["publish"] = StageRecord(
                status="failed",
                duration_s=round(time.time() - t0, 1),
                extra={"error": str(exc)},
            )

        result.total_duration_s = round(time.time() - start_time, 1)
        self._append_run(result)
        return result

    def run_scheduled(self, interval_minutes: int = 360) -> threading.Event:
        """Start background scheduled runs.

        Args:
            interval_minutes: Minutes between runs (default 6 hours).

        Returns:
            threading.Event to signal stop.
        """
        self._schedule_stop.clear()

        def _loop():
            while not self._schedule_stop.is_set():
                try:
                    self.run(topic=None)
                except Exception as exc:
                    # Log and continue — a single run failure does not stop the schedule
                    print(f"[pipeline] scheduled run failed: {exc}")

                # Wait with periodic check for stop signal
                deadline = time.time() + interval_minutes * 60
                while time.time() < deadline and not self._schedule_stop.is_set():
                    time.sleep(10)

        self._schedule_thread = threading.Thread(target=_loop, daemon=True)
        self._schedule_thread.start()

        # Persist schedule state
        SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
        SCHEDULE_FILE.write_text(json.dumps({
            "active": True,
            "interval_minutes": interval_minutes,
            "started_at": datetime.now().isoformat(),
        }, ensure_ascii=False, indent=2))

        return self._schedule_stop

    def stop_scheduled(self) -> None:
        """Stop the background schedule."""
        self._schedule_stop.set()
        if SCHEDULE_FILE.exists():
            data = json.loads(SCHEDULE_FILE.read_text())
            data["active"] = False
            data["stopped_at"] = datetime.now().isoformat()
            SCHEDULE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def schedule_status(self) -> dict | None:
        """Get current schedule status."""
        if not SCHEDULE_FILE.exists():
            return None
        return json.loads(SCHEDULE_FILE.read_text())

    def _format_hot_summary(self, hot_items: list[dict]) -> str:
        lines: list[str] = []
        for i, item in enumerate(hot_items[:15]):
            score = item.get("hot_score", 0)
            title = item.get("title", "")
            excerpt = item.get("excerpt", "")[:80]
            lines.append(f"{i + 1}. [{score:.0f}] {title}")
            if excerpt:
                lines.append(f"   摘要: {excerpt}")
        return "\n".join(lines)

    def _append_run(self, result: RunResult) -> None:
        runs_file = RUN_DIR / "runs.jsonl"
        try:
            with open(runs_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result.to_json(), ensure_ascii=False) + "\n")
        except Exception:
            pass
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('zhihu_fiction/pipeline.py').read()); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add zhihu_fiction/pipeline.py
git commit -m "feat: add Pipeline for end-to-end autonomous fiction workflow"
```

---

### Task 5: Create `automator_zhihu.py` — full auto Zhihu publisher

**Files:**
- Create: `zhihu_fiction/automator_zhihu.py`

Achieves true full-auto publishing: fill title, content, tags, click publish button, handle confirmation dialog, verify result.

- [ ] **Step 1: Write automator_zhihu.py**

```python
"""Zhihu fully-automated publisher via Playwright.

Fills title/content/tags, clicks publish, handles confirmation dialogs,
and verifies the published article URL.
"""
from __future__ import annotations

import time
from pathlib import Path

from .config import APP_ROOT

AUTH_DIR = APP_ROOT / "data" / "auth"
DEBUG_DIR = APP_ROOT / "data" / "debug"
SESSION_PATH = AUTH_DIR / "zhihu_session.json"

WRITE_URL = "https://zhuanlan.zhihu.com/write"


class PublishError(Exception):
    """Publishing failed for a recoverable reason (selector missing, timeout, etc.)."""
    def __init__(self, message: str, screenshot_path: str | None = None):
        super().__init__(message)
        self.screenshot_path = screenshot_path


class LoginRequired(Exception):
    """Session expired or not logged in."""


class ZhihuPublisher:
    """Fully automated Zhihu article publisher."""

    def __init__(self, headless: bool = False, slow_mo: int = 200) -> None:
        self._headless = headless
        self._slow_mo = slow_mo
        self._playwright = None
        self._browser = None
        AUTH_DIR.mkdir(parents=True, exist_ok=True)
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    def _ensure_browser(self):
        if self._playwright is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=self._headless,
                slow_mo=self._slow_mo,
                channel="chrome",
            )

    # ---- Login ----

    def login_interactive(self, timeout_seconds: int = 180) -> bool:
        """Open browser for manual login, save session on success."""
        self._ensure_browser()
        context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()
        page.goto("https://www.zhihu.com/signin", wait_until="domcontentloaded")

        print(f"\n  [知乎] 请在浏览器中扫码登录（{timeout_seconds}秒超时）")
        start = time.time()

        while time.time() - start < timeout_seconds:
            current_url = page.url
            if "/signin" not in current_url and "zhihu.com" in current_url:
                page.wait_for_timeout(3000)
                context.storage_state(path=str(SESSION_PATH))
                print(f"  [知乎] 登录成功，session 已保存")
                page.close()
                context.close()
                return True
            time.sleep(1)

        page.close()
        context.close()
        print(f"  [知乎] 登录超时")
        return False

    def is_logged_in(self) -> bool:
        """Check if saved session is still valid."""
        if not SESSION_PATH.exists():
            return False
        try:
            self._ensure_browser()
            context = self._browser.new_context(storage_state=str(SESSION_PATH))
            page = context.new_page()
            page.goto(WRITE_URL, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)

            has_editor = page.query_selector(
                ".public-DraftEditor-content, [contenteditable='true'], [role='textbox']"
            )
            context.close()
            return has_editor is not None
        except Exception:
            return False

    def ensure_login(self) -> bool:
        """Ensure logged in. If saved session is valid, use it. Otherwise, interactive login."""
        if self.is_logged_in():
            print("  [知乎] session 有效，已登录")
            return True
        print("  [知乎] 需要登录")
        return self.login_interactive()

    # ---- Publish ----

    def publish(
        self,
        title: str,
        content: str,
        tags: list[str] | None = None,
        genre: str = "",
    ) -> dict:
        """Publish an article to Zhihu.

        Args:
            title: Article title
            content: Article body (plain text or Markdown)
            tags: List of tags
            genre: Genre (not used for Zhihu, kept for interface compatibility)

        Returns:
            dict with keys: success (bool), url (str), message (str)
        """
        if not self.is_logged_in():
            raise LoginRequired("知乎未登录")

        self._ensure_browser()
        context = self._browser.new_context(
            storage_state=str(SESSION_PATH),
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.new_page()

        try:
            # Navigate to editor
            print("  [知乎] 打开发布页面...")
            page.goto(WRITE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Fill title
            self._fill_title(page, title)
            print(f"  [知乎] 标题已填入")

            # Fill content
            self._fill_content(page, content)
            print(f"  [知乎] 正文已填入 ({len(content)} 字)")

            # Add tags
            if tags:
                self._add_tags(page, tags)
                print(f"  [知乎] 标签已填入: {', '.join(tags)}")

            # Click publish button
            self._click_publish(page)
            print("  [知乎] 已点击发布按钮")

            # Handle confirmation dialog
            self._confirm_publish(page)

            # Verify: wait for redirect to published article
            article_url = self._wait_for_article(page)
            if article_url:
                print(f"  [知乎] 发布成功: {article_url}")
                return {"success": True, "url": article_url, "message": "发布成功"}
            else:
                # Take screenshot for debugging
                ts = time.strftime("%Y%m%d_%H%M%S")
                ss_path = str(DEBUG_DIR / f"zhihu_publish_{ts}.png")
                page.screenshot(path=ss_path)
                return {
                    "success": True,
                    "url": "",
                    "message": f"已发布但未能获取 URL，截图: {ss_path}",
                }

        except Exception as exc:
            ts = time.strftime("%Y%m%d_%H%M%S")
            ss_path = str(DEBUG_DIR / f"zhihu_error_{ts}.png")
            try:
                page.screenshot(path=ss_path)
            except Exception:
                ss_path = ""
            raise PublishError(str(exc), screenshot_path=ss_path)

        finally:
            page.close()
            context.close()

    def _fill_title(self, page, title: str) -> None:
        for selector in [
            "textarea[placeholder*='标题']",
            "input[placeholder*='标题']",
            "h1[contenteditable='true']",
            ".WriteIndex-titleInput textarea",
        ]:
            el = page.query_selector(selector)
            if el:
                el.click()
                el.fill("")
                el.fill(title)
                return
        page.keyboard.type(title, delay=10)

    def _fill_content(self, page, content: str) -> None:
        for selector in [
            ".public-DraftEditor-content",
            "div[contenteditable='true']",
            "[role='textbox']",
        ]:
            editor = page.query_selector(selector)
            if editor:
                editor.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Delete")
                page.keyboard.type(content, delay=5)
                return
        # JS fallback
        page.evaluate(
            """(text) => {
                const el = document.querySelector('[contenteditable="true"], .public-DraftEditor-content, [role="textbox"]');
                if (el) { el.focus(); el.innerText = text; }
            }""",
            content,
        )

    def _add_tags(self, page, tags: list[str]) -> None:
        for selector in [
            ".TagInput input",
            "[data-testid='article-tags'] input",
            "input[placeholder*='标签']",
        ]:
            tag_input = page.query_selector(selector)
            if tag_input:
                tag_input.click()
                for tag in tags:
                    tag_input.type(tag, delay=10)
                    page.wait_for_timeout(500)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(300)
                return

    def _click_publish(self, page) -> None:
        # Find exact "发布" button (not "发布设置")
        btn = None
        for selector in [
            'button:text-is("发布")',
            'button:text-is("发表")',
        ]:
            btn = page.query_selector(selector)
            if btn and btn.is_visible():
                break
            btn = None

        if not btn:
            all_btns = page.query_selector_all("button")
            for b in reversed(all_btns):
                try:
                    if b.inner_text().strip() == "发布":
                        btn = b
                        break
                except Exception:
                    continue

        if not btn:
            raise PublishError("未找到发布按钮")

        btn.scroll_into_view_if_needed()
        time.sleep(0.5)
        try:
            btn.evaluate("el => el.click()")
        except Exception:
            btn.click(force=True)
        time.sleep(3)

    def _confirm_publish(self, page) -> None:
        for selector in [
            '.Modal button:has-text("确认发布")',
            'button:has-text("确认发布")',
            '[role="dialog"] button:has-text("确认")',
            '.Modal button:has-text("发布")',
            'button:has-text("确定发布")',
        ]:
            confirm = page.query_selector(selector)
            if confirm:
                try:
                    confirm.evaluate("el => el.click()")
                except Exception:
                    confirm.click()
                time.sleep(3)
                return

    def _wait_for_article(self, page, timeout: int = 30) -> str:
        """Wait for redirect to published article page. Returns the article URL."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            url = page.url
            # Published article URLs: zhuanlan.zhihu.com/p/<id>
            if "/p/" in url and "zhuanlan.zhihu.com" in url:
                return url
            # Or redirected to articles list
            if "/articles" in url:
                return url
            time.sleep(1)
        return ""

    def cleanup(self) -> None:
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('zhihu_fiction/automator_zhihu.py').read()); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add zhihu_fiction/automator_zhihu.py
git commit -m "feat: add ZhihuPublisher for full-auto article publishing"
```

---

### Task 6: Update `cli.py` — add `/auto` and `/schedule` commands

**Files:**
- Modify: `zhihu_fiction/cli.py`

Changes:
1. Import `Pipeline` and `ZhihuPublisher`
2. Add `cmd_auto()` method
3. Add `cmd_schedule()` method (start/stop/status)
4. Register new commands in the REPL loop
5. Initialize Pipeline in `__init__`

- [ ] **Step 1: Add imports to cli.py**

Read `zhihu_fiction/cli.py` lines 1-30, then add Pipeline and ZhihuPublisher to the imports:

At line 30 (after the existing imports), add:
```python
from .pipeline import Pipeline
from .automator_zhihu import ZhihuPublisher, LoginRequired
from .orchestrator import OrchestratorCompat, create_orchestrator
```

- [ ] **Step 2: Add Pipeline init to CLI.__init__**

After `self.exporter = Exporter(create_llm(self.settings, temperature=0.3))` (line 82), add:
```python
coordinator, reviewer, pipeline_llm = create_orchestrator(
    self.settings, skills_store=self.skills_store
)
self.orchestrator = OrchestratorCompat(
    coordinator=coordinator,
    reviewer=reviewer,
    llm=pipeline_llm,
    settings=self.settings,
    skills_store=self.skills_store,
)
self.pipeline = Pipeline(
    coordinator=coordinator,
    reviewer=reviewer,
    llm=pipeline_llm,
    publisher=ZhihuPublisher(headless=False, slow_mo=200),
)
self._schedule_active = False
```

- [ ] **Step 3: Add cmd_auto and cmd_schedule methods**

Add these methods to the `CLI` class (before `run()`):

```python
def cmd_auto(self, topic: str | None = None) -> None:
    """Run the full autonomous pipeline once."""
    print("\n" + "=" * 60)
    print("  全自动创作发布模式")
    print("=" * 60)

    if topic:
        print(f"\n指定主题: {topic}")
    else:
        print("\nAI 将从热榜中自动选择最具爆款潜力的选题")

    print(f"质量门槛: {self.pipeline.quality_threshold}/10 | 最多重写: {self.pipeline.max_rewrites} 轮")
    print(f"发布平台: 知乎盐选")
    print()

    try:
        result = self.pipeline.run(topic=topic, genre=self.genre)
        self._print_run_result(result)
    except LoginRequired:
        print("\n[知乎] 需要登录。正在打开发布器登录窗口...")
        publisher = self.pipeline.publisher
        if publisher.login_interactive():
            print("登录成功，请再次运行 /auto")
        else:
            print("登录失败或超时。")
    except Exception as exc:
        print(f"\n[错误] 全自动流程失败: {exc}")

def cmd_schedule(self, action: str = "status", interval: str = "") -> None:
    """Manage the background scheduler.

    Actions: start, stop, status
    """
    if action == "start":
        minutes = 360  # default 6 hours
        if interval:
            num = "".join(c for c in interval if c.isdigit())
            if num:
                val = int(num)
                if interval.endswith("m"):
                    minutes = val
                elif interval.endswith("h"):
                    minutes = val * 60
                else:
                    minutes = val * 60  # bare number = hours

        self.pipeline.run_scheduled(interval_minutes=minutes)
        self._schedule_active = True
        print(f"\n[调度] 已启动 — 每 {minutes} 分钟运行一次")
        print(f"[调度] 使用 /schedule status 查看状态")
        print(f"[调度] 使用 /schedule stop 停止")

    elif action == "stop":
        self.pipeline.stop_scheduled()
        self._schedule_active = False
        print("\n[调度] 已停止")

    elif action == "status":
        status = self.pipeline.schedule_status()
        if status is None:
            active = self._schedule_active
            print(f"\n[调度] {'运行中' if active else '未启动'}")
        else:
            print(f"\n[调度] {'运行中' if status.get('active') else '已停止'}")
            if status.get("interval_minutes"):
                print(f"       间隔: {status['interval_minutes']} 分钟")
            if status.get("started_at"):
                print(f"       启动时间: {status['started_at']}")
            if status.get("stopped_at"):
                print(f"       停止时间: {status['stopped_at']}")

def _print_run_result(self, result) -> None:
    """Pretty-print a pipeline RunResult."""
    print("\n" + "=" * 60)
    print(f"  运行结果: {result.run_id}")
    print("=" * 60)
    for stage_name, stage in result.stages.items():
        icon = {"ok": "✓", "skipped": "⊘", "failed": "✗", "fallback": "⚠"}.get(stage.status, "?")
        print(f"  {icon} {stage_name}: {stage.status} ({stage.duration_s}s)")
        for k, v in stage.extra.items():
            if k != "error":
                print(f"      {k}: {v}")
    if result.published_url:
        print(f"\n  发布地址: {result.published_url}")
    if result.error:
        print(f"\n  错误: {result.error}")
    total_min = result.total_duration_s / 60
    print(f"\n  总耗时: {result.total_duration_s:.0f}s ({total_min:.1f}min)")
```

- [ ] **Step 4: Register new commands in REPL loop**

In the `run()` method, add handling for `/auto` and `/schedule`:

After the existing command handlers (line ~587), add:
```python
elif cmd == "/auto":
    self.cmd_auto(arg if arg else None)
elif cmd == "/schedule":
    sched_parts = raw.split(maxsplit=2)
    sched_action = sched_parts[1] if len(sched_parts) > 1 else "status"
    sched_arg = sched_parts[2] if len(sched_parts) > 2 else ""
    self.cmd_schedule(sched_action, sched_arg)
```

- [ ] **Step 5: Add import for create_orchestrator**

The `cmd_auto` method references `create_orchestrator` in the __init__ changes. Update the orchestrator import:

Change line 28 from:
```python
from .orchestrator import Orchestrator, WorkflowResult
```
to:
```python
from .orchestrator import OrchestratorCompat, WorkflowResult, create_orchestrator
```

The old code uses `self.orchestrator = Orchestrator(...)` (line 77-78). Replace with the Pipeline + OrchestratorCompat init from Step 2 above.

- [ ] **Step 6: Verify syntax**

Run: `python -c "import ast; ast.parse(open('zhihu_fiction/cli.py').read()); print('OK')"`

- [ ] **Step 7: Commit**

```bash
git add zhihu_fiction/cli.py
git commit -m "feat: add /auto and /schedule commands to CLI"
```

---

### Task 7: Fix `__init__.py` — remove workspace_shims, update exports

**Files:**
- Modify: `zhihu_fiction/__init__.py`

- [ ] **Step 1: Rewrite __init__.py**

```python
from .config import Settings, load_settings
from .exporter import Exporter
from .pipeline import Pipeline
from .publishers import ZhihuSaltPublisher, QidianPublisher, FanqiePublisher
from .skills_store import SkillsStore

__all__ = [
    "Settings",
    "load_settings",
    "Pipeline",
    "SkillsStore",
    "Exporter",
    "ZhihuSaltPublisher",
    "QidianPublisher",
    "FanqiePublisher",
]
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('zhihu_fiction/__init__.py').read()); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add zhihu_fiction/__init__.py
git commit -m "fix: remove workspace_shims import, update exports for Pipeline"
```

---

### Task 8: Create tests

**Files:**
- Create: `zhihu_fiction/tests/__init__.py` (empty)
- Create: `zhihu_fiction/tests/test_agents.py`
- Create: `zhihu_fiction/tests/test_pipeline.py`

- [ ] **Step 1: Create tests/__init__.py**

```bash
mkdir -p zhihu_fiction/tests
touch zhihu_fiction/tests/__init__.py
```

- [ ] **Step 2: Write test_agents.py**

```python
"""Tests for agent tools and ReviewerAgent."""
import pytest
from unittest.mock import MagicMock, patch

from zhihu_fiction.agents import (
    _make_analyze_topic,
    _make_plan_outline,
    _make_write_draft,
    _make_polish_draft,
    _make_synthesize,
    ReviewerAgent,
)


class TestAgentTools:
    """Verify tool factories return callable tools with correct schemas."""

    def test_analyze_topic_is_tool(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="选题分析报告内容")
        tool = _make_analyze_topic(llm)
        assert callable(tool)
        result = tool.invoke({"topic": "穿越古代", "hot_trends": "热榜...", "skills": "技能卡..."})
        assert "选题分析报告内容" in result

    def test_plan_outline_is_tool(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="故事大纲内容")
        tool = _make_plan_outline(llm)
        assert callable(tool)
        result = tool.invoke({
            "topic": "穿越古代",
            "topic_analysis": "分析报告",
            "skills": "技能卡",
        })
        assert "故事大纲内容" in result

    def test_write_draft_is_tool(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="完整小说正文3000字")
        tool = _make_write_draft(llm)
        assert callable(tool)
        result = tool.invoke({
            "topic": "穿越古代",
            "outline": "大纲",
            "skills": "技能卡",
            "revision_feedback": "",
        })
        assert "完整小说正文3000字" in result

    def test_write_draft_with_feedback(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="根据反馈重写的小说")
        tool = _make_write_draft(llm)
        result = tool.invoke({
            "topic": "穿越古代",
            "outline": "大纲",
            "skills": "技能卡",
            "revision_feedback": "开篇不够吸引人",
        })
        assert "根据反馈重写的小说" in result

    def test_polish_draft_is_tool(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="润色后的小说全文")
        tool = _make_polish_draft(llm)
        result = tool.invoke({
            "topic": "穿越古代",
            "draft": "初稿",
            "feedback": "改进开篇",
        })
        assert "润色后的小说全文" in result

    def test_synthesize_is_tool(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="发布方案")
        tool = _make_synthesize(llm)
        result = tool.invoke({
            "topic": "穿越古代",
            "topic_analysis": "分析",
            "outline": "大纲",
            "final_draft": "终稿",
        })
        assert "发布方案" in result


class TestReviewerAgent:
    """Tests for the independent ReviewerAgent."""

    def test_review_returns_score(self):
        llm = MagicMock()
        review_output = (
            "1) 开篇钩子力：8 分\n"
            "2) 节奏把控：7 分\n"
            "3) 人设一致性：6 分\n"
            "4) 逻辑自洽：7 分\n"
            "5) 情绪张力：8 分\n"
            "6) 金句密度：5 分\n"
            "7) 结尾余韵：7 分\n"
            "8) 知乎适配度：8 分\n"
        )
        llm.invoke.return_value = MagicMock(content=review_output)
        reviewer = ReviewerAgent(llm)
        result = reviewer.review("小说正文", "测试选题")

        assert "total_score" in result
        assert result["total_score"] == pytest.approx(7.0, 0.5)


    def test_review_extract_score_fallback(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="写得很好，没有具体分数")
        reviewer = ReviewerAgent(llm)
        result = reviewer.review("小说正文", "测试选题")
        assert result["total_score"] == 5.0  # fallback
```

- [ ] **Step 3: Run the agent tests**

```bash
cd zhihu_fiction && python -m pytest tests/test_agents.py -v
```
Expected: 8 tests pass

- [ ] **Step 4: Write test_pipeline.py**

```python
"""Tests for Pipeline orchestration logic."""
import json
import pytest
from unittest.mock import MagicMock, patch, call

from zhihu_fiction.pipeline import (
    Pipeline,
    RunResult,
    StageRecord,
    select_topic,
    RUN_DIR,
)


class TestSelectTopic:
    def test_parses_topic_and_genre(self):
        llm = MagicMock()
        response = MagicMock()
        response.content = "选题：密室逃脱\n题材：悬疑\n理由：热度高"
        llm.invoke.return_value = response

        hot_items = [
            {"title": "密室逃脱", "hot_score": 5000, "excerpt": ""},
            {"title": "宫斗", "hot_score": 3000, "excerpt": ""},
        ]
        result = select_topic(hot_items, llm)
        assert result["topic"] == "密室逃脱"
        assert result["genre"] == "悬疑"

    def test_fallback_to_first_hot(self):
        llm = MagicMock()
        response = MagicMock()
        response.content = "乱七八糟没有匹配格式"
        llm.invoke.return_value = response

        hot_items = [{"title": "热门第一", "hot_score": 9999}]
        result = select_topic(hot_items, llm)
        assert result["topic"] == "热门第一"


class TestPipeline:
    def test_run_with_provided_topic(self):
        coordinator = MagicMock()
        reviewer = MagicMock()
        llm = MagicMock()
        publisher = MagicMock()

        # Mock coordinator output
        from langchain_core.messages import HumanMessage
        coordinator.invoke.return_value = {
            "messages": [HumanMessage(content="【小说正文】\n完整小说内容\n【发布方案】\n发布方案内容")]
        }

        # Mock reviewer passes
        reviewer.review.return_value = {"total_score": 7.5, "full_report": "评审报告"}
        reviewer.quality_threshold = 6.0  # not actually used this way

        # Mock scraper
        scraper = MagicMock(return_value=[
            {"title": "热榜1", "hot_score": 5000, "excerpt": "摘要1"},
        ])

        # Mock publisher
        publisher.publish.return_value = {"success": True, "url": "https://zhuanlan.zhihu.com/p/123"}

        pipeline = Pipeline(
            coordinator=coordinator,
            reviewer=reviewer,
            llm=llm,
            publisher=publisher,
            scraper=scraper,
            quality_threshold=6.0,
            max_rewrites=2,
        )

        result = pipeline.run(topic="测试主题", genre="悬疑")

        assert result.topic == "测试主题"
        assert result.trigger == "manual"
        assert result.stages["scrape"].status == "ok"
        assert result.stages["select_topic"].status == "ok"
        assert result.stages["create"].status == "ok"
        assert result.stages["review"].status == "ok"
        assert result.stages["review"].extra["score"] == 7.5
        assert result.stages["publish"].status == "ok"
        assert result.published_url == "https://zhuanlan.zhihu.com/p/123"

    def test_skip_publish_when_quality_low(self):
        coordinator = MagicMock()
        reviewer = MagicMock()
        llm = MagicMock()
        publisher = MagicMock()

        from langchain_core.messages import HumanMessage
        coordinator.invoke.return_value = {
            "messages": [HumanMessage(content="【小说正文】\n不太好的小说\n【发布方案】\n方案")]
        }

        # Reviewer gives low score
        reviewer.review.return_value = {"total_score": 4.5, "full_report": "质量问题"}

        scraper = MagicMock(return_value=[{"title": "热榜1", "hot_score": 5000, "excerpt": ""}])

        pipeline = Pipeline(
            coordinator=coordinator,
            reviewer=reviewer,
            llm=llm,
            publisher=publisher,
            scraper=scraper,
            quality_threshold=6.0,
            max_rewrites=2,
        )

        result = pipeline.run(topic="测试主题")

        assert result.stages["publish"].status == "skipped"
        publisher.publish.assert_not_called()

    def test_retry_when_quality_low_then_pass(self):
        coordinator = MagicMock()
        reviewer = MagicMock()
        llm = MagicMock()
        publisher = MagicMock()

        from langchain_core.messages import HumanMessage

        # First run gives a draft that will be reviewed poorly
        coordinator.invoke.side_effect = [
            {"messages": [HumanMessage(content="【小说正文】\n第一版\n【发布方案】\n方案1")]},
            {"messages": [HumanMessage(content="【小说正文】\n改进版\n【发布方案】\n方案2")]},
        ]

        # First review fails, second passes
        reviewer.review.side_effect = [
            {"total_score": 4.5, "full_report": "不够好"},
            {"total_score": 7.0, "full_report": "改进后通过了"},
        ]

        scraper = MagicMock(return_value=[{"title": "热榜1", "hot_score": 5000, "excerpt": ""}])
        publisher.publish.return_value = {"success": True, "url": "https://zhuanlan.zhihu.com/p/456"}

        pipeline = Pipeline(
            coordinator=coordinator,
            reviewer=reviewer,
            llm=llm,
            publisher=publisher,
            scraper=scraper,
            quality_threshold=6.0,
            max_rewrites=2,
        )

        result = pipeline.run(topic="测试主题")

        assert result.stages["review"].extra["score"] == 7.0
        assert result.stages["review"].extra["rounds"] == 2
        assert result.stages["publish"].status == "ok"
        assert coordinator.invoke.call_count == 2  # first run + one retry
        publisher.publish.assert_called_once()

    def test_run_writes_to_runs_jsonl(self, tmp_path):
        import os
        coordinator = MagicMock()
        reviewer = MagicMock()
        llm = MagicMock()
        publisher = MagicMock()

        from langchain_core.messages import HumanMessage
        coordinator.invoke.return_value = {
            "messages": [HumanMessage(content="【小说正文】\n小说\n【发布方案】\n方案")]
        }
        reviewer.review.return_value = {"total_score": 7.0, "full_report": "ok"}
        scraper = MagicMock(return_value=[{"title": "热榜1", "hot_score": 5000, "excerpt": ""}])
        publisher.publish.return_value = {"success": True, "url": "https://zhuanlan.zhihu.com/p/789"}

        # Use tmp_path for run_dir
        pipeline = Pipeline(
            coordinator=coordinator,
            reviewer=reviewer,
            llm=llm,
            publisher=publisher,
            scraper=scraper,
        )
        # Override RUN_DIR for test
        import zhihu_fiction.pipeline as pmod
        old_run_dir = pmod.RUN_DIR
        pmod.RUN_DIR = tmp_path / ".pipeline"
        pmod.RUN_DIR.mkdir(parents=True, exist_ok=True)

        try:
            result = pipeline.run(topic="测试主题")

            runs_file = pmod.RUN_DIR / "runs.jsonl"
            assert runs_file.exists()

            lines = runs_file.read_text().strip().split("\n")
            assert len(lines) == 1

            data = json.loads(lines[0])
            assert data["topic"] == "测试主题"
            assert data["trigger"] == "manual"
            assert data["stages"]["publish"]["status"] == "ok"
        finally:
            pmod.RUN_DIR = old_run_dir
```

- [ ] **Step 5: Run the pipeline tests**

```bash
cd zhihu_fiction && python -m pytest tests/test_pipeline.py -v
```
Expected: 6 tests pass

- [ ] **Step 6: Commit**

```bash
git add zhihu_fiction/tests/
git commit -m "test: add agent and pipeline unit tests"
```

---

### Task 9: Requirements update

**Files:**
- Modify: `zhihu_fiction/requirements.txt`

Add `deepagents` to the requirements.

- [ ] **Step 1: Add deepagents to requirements.txt**

Read `zhihu_fiction/requirements.txt`, append:
```
deepagents>=0.5.0
```

- [ ] **Step 2: Commit**

```bash
git add zhihu_fiction/requirements.txt
git commit -m "chore: add deepagents dependency"
```

---

### Task 10: Integration verification

- [ ] **Step 1: Verify no import errors**

Run: `cd zhihu_fiction && python -c "from agents import create_coordinator, ReviewerAgent; print('agents OK')"`

- [ ] **Step 2: Verify pipeline import works**

Run: `cd zhihu_fiction && python -c "from pipeline import Pipeline; print('pipeline OK')"`

- [ ] **Step 3: Run all tests**

```bash
cd zhihu_fiction && python -m pytest tests/ -v
```
Expected: All 14 tests pass.

- [ ] **Step 4: Verify CLI help text**

Run: `cd zhihu_fiction && python -c "
from cli import CLI, HELP_TEXT
# Verify /auto and /schedule are in help text
"`

- [ ] **Step 5: Commit any final fixes**

```bash
git add -A
git commit -m "chore: integration verification and final fixes"
```