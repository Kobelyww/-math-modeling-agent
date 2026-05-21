"""Subagent spawning system — inspired by Claude Code's Agent tool.

Agents can delegate work to specialized subagents that run in isolated contexts.
Each subagent type has a focused system prompt and limited tool access, preventing
context pollution and enabling parallel work.

Architecture:
  - SubAgentType: defines a subagent's role, system prompt, and allowed tools
  - spawn_subagent(): LangChain tool that agents call to delegate work
  - SubAgentRunner: manages isolated execution and result condensation

Anti-patterns prevented:
  - Infinite recursion: max_depth=1 (subagents cannot spawn further subagents)
  - Context bloat: results are truncated to max_result_chars
  - Tool misuse: each subagent type gets only the tools it needs
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from .base import normalize_llm_content
from .exploration import (
    read_file,
    search_content,
    search_files,
    list_directory,
    web_fetch,
    web_search,
)
from .literature import search_arxiv, search_crossref, search_semantic_scholar

logger = logging.getLogger(__name__)

# ─── Subagent Type Definitions ───────────────────────────────────────────


@dataclass
class SubAgentDef:
    """Definition of a subagent type — role, prompt, and toolset."""

    name: str
    description: str
    system_prompt: str
    tool_names: list[str] = field(default_factory=list)
    max_result_chars: int = 3000


# Subagent types mirror Claude Code's agent types but adapted for MCM/ICM

SUBAGENT_TYPES: dict[str, SubAgentDef] = {
    "explore": SubAgentDef(
        name="explore",
        description="Fast, read-only file/code exploration. Use to find files by pattern, "
        "grep for symbols, or answer 'where is X defined / which files reference Y'. "
        "Best for: locating code, understanding project structure, finding patterns.",
        system_prompt="""你是代码探索助手。专门负责快速、只读地搜索文件系统。

工作方式：
- 使用 search_files 按 glob 模式查找文件
- 使用 search_content 在文件中搜索代码/文本
- 使用 read_file 阅读特定文件的特定行范围
- 使用 list_directory 了解目录结构

输出要求：
- 直接给出发现结果，不要冗长解释
- 包含具体的文件路径和行号
- 如果找不到，明确说明并建议替代搜索策略
- 回答控制在 300 字以内""",
        tool_names=["read_file", "search_files", "search_content", "list_directory"],
        max_result_chars=3000,
    ),
    "research": SubAgentDef(
        name="research",
        description="Web research and literature review. Use to search for academic papers, "
        "find recent documentation, or gather external references for modeling decisions. "
        "Best for: literature review, finding state-of-the-art methods, fact-checking.",
        system_prompt="""你是学术研究助手。专门负责查找和整理外部参考资料。

工作方式：
- 使用 web_search 搜索最新资料和文档
- 使用 web_fetch 阅读网页内容
- 使用 search_arxiv / search_semantic_scholar 搜索学术论文
- 使用 search_crossref 作为文献搜索的补充

输出要求：
- 按相关性排序，列出找到的关键参考资料
- 每条包含：标题、URL、与你任务的关联
- 区分学术论文（peer-reviewed）和网络资源（blog/wiki）
- 如果信息不足，说明搜索盲区
- 回答控制在 500 字以内""",
        tool_names=[
            "web_search", "web_fetch",
            "search_arxiv", "search_semantic_scholar", "search_crossref",
        ],
        max_result_chars=5000,
    ),
    "code": SubAgentDef(
        name="code",
        description="Code generation, execution, and debugging. Use to write algorithms, "
        "test numerical methods, debug Python code, or generate visualizations. "
        "Best for: implementing model solvers, testing code snippets, generating plots.",
        system_prompt="""你是代码专家。专门负责编写、执行和调试 Python 代码。

工作方式：
- 编写完整可运行的 Python 代码
- 使用 python_exec 在沙箱中执行代码
- 使用 read_file 检查已有代码
- 使用 pip_install 安装需要的包

输出要求：
- 给出可直接运行的代码（含 if __name__ == '__main__':）
- 包含必要的 import 和类型标注
- 说明依赖和运行方式
- 如果有执行错误，分析原因并修复
- 回答控制在 500 字以内""",
        tool_names=["python_exec", "pip_install", "read_file",
                   "search_files", "search_content", "read_csv_info"],
        max_result_chars=5000,
    ),
    "general": SubAgentDef(
        name="general",
        description="General-purpose analysis for any task not covered by other types. "
        "Use for: problem analysis, data interpretation, model selection reasoning, "
        "or any complex multi-step reasoning that doesn't fit the other categories.",
        system_prompt="""你是通用分析助手。处理不适合其他专项子智能体的问题。

工作方式：
- 分析问题，明确关键点
- 使用可用工具获取需要的信息
- 给出结构化的分析和建议

输出要求：
- 先给出核心结论
- 再展开分析过程
- 区分事实和推断
- 回答控制在 400 字以内""",
        tool_names=["read_file", "search_files", "search_content",
                   "web_search", "web_fetch", "python_exec",
                   "search_arxiv", "search_semantic_scholar"],
        max_result_chars=4000,
    ),
}

# Map tool names to actual tool functions
_TOOL_REGISTRY = {
    "read_file": read_file,
    "search_files": search_files,
    "search_content": search_content,
    "list_directory": list_directory,
    "web_search": web_search,
    "web_fetch": web_fetch,
    "search_arxiv": search_arxiv,
    "search_crossref": search_crossref,
    "search_semantic_scholar": search_semantic_scholar,
    # These are added at spawn time since they need imports from tools.py
}


# ─── Subagent Runner ───────────────────────────────────────────────────

# Guard against infinite recursion: subagents cannot spawn subagents.
_MAX_RECURSION_DEPTH = 1


def _run_subagent(
    agent_type: str,
    task: str,
    llm: BaseChatModel,
    recursion_depth: int = 0,
    extra_tools: list | None = None,
    extra_tool_names: dict[str, callable] | None = None,
) -> str:
    """Execute a subagent in an isolated context and return condensed results.

    Args:
        agent_type: One of 'explore', 'research', 'code', 'general'
        task: The task description for the subagent
        llm: LLM instance to use
        recursion_depth: Current recursion level (prevents infinite loops)
        extra_tools: Additional LangChain tool functions to register
        extra_tool_names: Mapping of tool name -> tool function

    Returns:
        Condensed subagent result as a string
    """
    if recursion_depth >= _MAX_RECURSION_DEPTH:
        return (
            f"[Subagent '{agent_type}' blocked: max recursion depth "
            f"({_MAX_RECURSION_DEPTH}) reached. Subagents cannot spawn further subagents.]"
        )

    agent_def = SUBAGENT_TYPES.get(agent_type)
    if not agent_def:
        available = ", ".join(SUBAGENT_TYPES.keys())
        return f"Unknown subagent type: '{agent_type}'. Available: {available}"

    # Assemble the subagent's toolset
    tools: list = []
    for name in agent_def.tool_names:
        tool_obj = _TOOL_REGISTRY.get(name)
        if tool_obj:
            tools.append(tool_obj)

    # Add any extra tools passed from the parent
    if extra_tools:
        tools.extend(extra_tools)

    # Add extra tool name mappings
    if extra_tool_names:
        for name, tool_obj in extra_tool_names.items():
            _TOOL_REGISTRY[name] = tool_obj
            if name in agent_def.tool_names:
                tools.append(tool_obj)

    # Build the subagent prompt — include recursion guard
    system_prompt = agent_def.system_prompt
    if recursion_depth > 0:
        system_prompt += "\n\n⚠ 你不能再次创建子智能体。你必须自己完成这个任务。"

    full_task = f"""{system_prompt}

## 任务
{task}

## 输出格式要求
请用中文输出你的发现。直接给出结果，不要啰嗦。控制在你角色的字数限制内。"""

    try:
        if tools:
            # Use LangChain agent with tools
            agent = create_agent(
                model=llm,
                tools=tools,
                system_prompt=system_prompt,
            )
            response = agent.invoke({
                "messages": [HumanMessage(content=full_task)],
            })
            # Extract content from agent response
            messages = response.get("messages", [])
            result = ""
            if messages:
                last = messages[-1]
                result = getattr(last, "content", str(last))
                result = normalize_llm_content(result) if not isinstance(result, str) else result
        else:
            # Direct LLM call — no tools
            from langchain_core.messages import SystemMessage as SysMsg
            response = llm.invoke([
                SysMsg(content=system_prompt),
                HumanMessage(content=task),
            ])
            result = normalize_llm_content(response.content)
    except Exception as exc:
        return f"[Subagent '{agent_type}' execution failed: {exc}]"

    # Condense result to prevent context bloat
    if len(result) > agent_def.max_result_chars:
        truncation_note = (
            f"\n\n... [结果被截断到 {agent_def.max_result_chars} 字符，"
            f"原始输出为 {len(result)} 字符]"
        )
        result = result[:agent_def.max_result_chars - len(truncation_note)] + truncation_note

    return result


# ─── LangChain Tool: spawn_subagent ────────────────────────────────────

# The LLM reference is set at module load time by the orchestrator.
# This follows the same pattern as other tools in this project.
_subagent_llm: BaseChatModel | None = None
python_exec_tool = None
pip_install_tool = None
read_csv_info_tool = None


def configure_subagent_llm(llm: BaseChatModel) -> None:
    """Set the LLM to use for subagent execution. Called by the orchestrator."""
    global _subagent_llm
    _subagent_llm = llm


def _set_code_tools(python_exec_fn, pip_install_fn, read_csv_fn) -> None:
    """Register code execution tools for the 'code' subagent type."""
    global python_exec_tool, pip_install_tool, read_csv_info_tool
    python_exec_tool = python_exec_fn
    pip_install_tool = pip_install_fn
    read_csv_info_tool = read_csv_fn

    _TOOL_REGISTRY["python_exec"] = python_exec_fn
    _TOOL_REGISTRY["pip_install"] = pip_install_fn
    _TOOL_REGISTRY["read_csv_info"] = read_csv_fn


@tool
def spawn_subagent(agent_type: str, task: str) -> str:
    """Spawn a specialized subagent to handle a task independently.

    Like Claude Code's Agent tool — the subagent runs in its own context and
    returns a condensed result. Use this to delegate work and avoid polluting
    your main context.

    Available subagent types:
      - explore:    Fast file/code exploration. Use to find files, grep code,
                    or understand project structure.
      - research:   Web research & literature review. Use to find papers,
                    documentation, or external references.
      - code:       Code generation & debugging. Use to write algorithms,
                    test snippets, or fix Python code.
      - general:    General-purpose analysis. Use for anything else.

    Args:
        agent_type: The type of subagent to spawn ('explore','research','code','general')
        task: A clear, self-contained task description. Include all context the
              subagent needs — it won't see your conversation history.

    Returns:
        The subagent's condensed result.

    Examples:
        spawn_subagent('explore', 'Find all Python files related to optimization in agent_app/')
        spawn_subagent('research', 'Search for recent papers on NSGA-II traffic optimization')
        spawn_subagent('code', 'Write and test a function to solve TSP with genetic algorithm')
    """
    if not _subagent_llm:
        return (
            "[Subagent not available: LLM not configured. "
            "This tool requires the orchestrator to be initialized first.]"
        )

    agent_type = agent_type.strip().lower()
    if agent_type not in SUBAGENT_TYPES:
        available = ", ".join(SUBAGENT_TYPES.keys())
        return f"Unknown subagent type: '{agent_type}'. Available: {available}"

    logger.info("[SubAgent] Spawning '%s' for task: %.100s...", agent_type, task)

    result = _run_subagent(
        agent_type=agent_type,
        task=task,
        llm=_subagent_llm,
        recursion_depth=0,
    )

    header = (
        f"── Subagent Result [{agent_type}] ──\n"
        f"{result}\n"
        f"── End Subagent [{agent_type}] ──"
    )
    return header


# ─── Convenience: spawn multiple subagents in parallel ─────────────────

def spawn_parallel(
    tasks: list[tuple[str, str]],
    llm: BaseChatModel,
) -> list[str]:
    """Spawn multiple subagents in parallel using ThreadPoolExecutor.

    Args:
        tasks: List of (agent_type, task_description) tuples
        llm: LLM instance

    Returns:
        List of results in the same order as tasks
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=min(len(tasks), 4)) as executor:
        future_to_idx = {
            executor.submit(
                _run_subagent, agent_type=at, task=t, llm=llm
            ): i
            for i, (at, t) in enumerate(tasks)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                results[idx] = f"[Subagent failed: {exc}]"

    return [results[i] for i in range(len(tasks))]


def list_subagent_types() -> str:
    """Return a human-readable summary of available subagent types."""
    lines = ["## 可用子智能体类型\n"]
    for name, defn in SUBAGENT_TYPES.items():
        lines.append(f"### {name}")
        lines.append(f"  {defn.description}")
        lines.append(f"  可用工具: {', '.join(defn.tool_names) if defn.tool_names else '无'}")
        lines.append(f"  输出上限: {defn.max_result_chars} 字符\n")
    return "\n".join(lines)