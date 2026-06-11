



from __future__ import annotations

# 支持直接执行：python cli.py 或 python -m agent_app.cli
if __name__ == "__main__" and __package__ is None:
    import sys as _sys
    from pathlib import Path as _Path

    _parent = _Path(__file__).resolve().parent.parent
    if str(_parent) not in _sys.path:
        _sys.path.insert(0, str(_parent))
    __package__ = "agent_app"

import sys
from pathlib import Path
from typing import Callable

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage

from .base import normalize_llm_content
from .config import APP_ROOT, load_settings
from .llm import create_llm
from .memory import MemoryManager
from .orchestrator import Orchestrator
from .rag import PaperRAG
from .tools import TOOLS_FULL

SINGLE_AGENT_PROMPT = """你是一个基于 DeepSeek 的智能助手，专长数学建模与代码实现。

## 核心行为准则：自主判断，主动行动

你不是被动的问答机器。每个请求你都要自主判断最好的处理方式：

### 第一步：分析（每次必做）
收到任务后先在心里问自己：
1. 我需要更多信息吗？→ 是就去探索，不要猜
2. 任务可以拆分成独立子任务吗？→ 是就用 spawn_subagent 并行处理
3. 需要写代码验证吗？→ 是就用 python_exec
4. 有现成的领域知识可以加载吗？→ 参考技能系统

### 第二步：探索（信息不足时必须做）
默认假设你掌握的信息不完整。以下情况**必须**先探索再回答：
- 需要知道项目中有哪些相关文件 → read_file / search_files / search_content / list_directory
- 需要最新方法或论文 → web_search + spawn_subagent('research', ...)
- 需要找到特定代码模式 → search_content
- 需要了解代码库结构 → list_directory / search_files

### 第三步：委托（能并行就并行）
以下情况**主动使用 spawn_subagent**，不要自己逐个做：
- 需要同时搜代码 + 查文献 → 并行 spawn explore + research
- 文献调研量大 → spawn_subagent('research', ...)
- 需要生成并测试代码 → spawn_subagent('code', ...)
- 复杂逻辑需要独立分析 → spawn_subagent('general', ...)

### 第四步：执行
工具可执行的绝不猜测。原则：
- 能用 search_content 找到的，不靠记忆
- 能用 python_exec 验证的，不靠推理
- 能并行完成的子任务，不串行
- RAG/技能系统给了答案的，直接引用

## 可用能力
- **文件探索**: read_file, search_files, search_content, list_directory
- **网络**: web_search, web_fetch
- **代码执行**: python_exec, pip_install, read_csv_info
- **子智能体**: spawn_subagent('explore'|'research'|'code'|'general', task)
- **学术文献**: search_arxiv, search_semantic_scholar, search_crossref
- **LaTeX**: latex_template, latex_compile, latex_render_math
- **笔记**: save_note, read_note, list_notes
- **可视化**: nature_viz_template, model_reference, writing_rules

## 输出风格
- 先给出结论或答案，再给出过程和依据
- 引用找到的文件、URL 或搜索结果作为支撑
- 不确定的地方明确标注，说明如何进一步验证
"""

ORCHESTRATOR_HELP = f"""
{'='*60}
  数模多智能体协作系统  v2.1 (Plan-and-Execute 架构)
{'='*60}

工作流模式：
  1. agent_loop   - 对话驱动 Agent Loop（默认，动态选择下一步）
  2. plan         - 规划先行（legacy）
  3. explore      - 先探索后求解（legacy）
  4. sequential   - 串行流水线（legacy）
  5. review       - 深度反思（legacy）
  6. parallel     - 快速并行（legacy）

命令：
  /mode <模式名>  - 切换工作流模式（默认 agent_loop）
  /plan <问题>    - 仅生成求解计划，不执行
  /solve <问题>   - 启动多智能体协作分析
  /stream         - 流式输出模式（实时 token 级输出）
  /chat           - 切换到单智能体对话模式
  /memory         - 查看记忆系统统计（STM/LTM/压缩）
  /compress       - 强制触发上下文压缩
  /skills         - 列出可用技能（渐进式披露）
  /subagent       - 列出可用子智能体类型
  /help           - 显示此帮助
  /exit           - 退出程序
""".strip()

DEFAULT_ORCHESTRATOR_MODE = "agent_loop"
LEGACY_ORCHESTRATOR_MODES = ("plan", "explore", "sequential", "review", "parallel")
ORCHESTRATOR_MODES = (DEFAULT_ORCHESTRATOR_MODE, *LEGACY_ORCHESTRATOR_MODES)

SINGLE_AGENT_HELP = """
单智能体模式。可直接聊天或使用工具：
- 现在几点？
- 帮我计算 (18 + 24) * 3
- 保存笔记...

输入 /orchestrate 切换到多智能体模式，输入 /exit 退出。
""".strip()


class CLI:
    def __init__(self) -> None:
        self.settings = load_settings()
        data_dir = APP_ROOT / "data"
        knowledge_dir = APP_ROOT.parent / "knowledge_base"
        self.rag = PaperRAG(knowledge_dir=knowledge_dir, index_path=data_dir / "rag_index.pkl", embedding_api_key=self.settings.embedding_api_key)
        if self.rag.load_index():
            print(f"[RAG] 已加载索引（{len(self.rag.chunks)} 个片段）")
        else:
            print("[RAG] 未找到索引文件，运行 build_index() 可构建")

        # 初始化记忆系统（Redis Stack）
        try:
            self.memory_manager = MemoryManager(use_redis=True)
            from .memory.redis_backends import _redis_client
            _redis_client().ping()
            print("[Memory] Redis Stack 已连接，记忆系统就绪")
        except Exception:
            self.memory_manager = MemoryManager(use_redis=False)
            print("[Memory] Redis 不可用，使用 SQLite 回退方案")

        self.orchestrator = Orchestrator(self.settings, rag=self.rag, memory_manager=self.memory_manager)
        self.mode: str = DEFAULT_ORCHESTRATOR_MODE

        # 设置默认流式回调 — 所有模式自动流式输出 + 思考内容
        self._current_role: str = ""
        self._thinking_active: bool = False
        self._output_active: bool = False
        self.orchestrator.on_agent_thinking = self._on_agent_thinking
        self.orchestrator.on_agent_token = self._on_agent_token

    def _on_agent_thinking(self, token: str, role_label: str) -> None:
        """默认思考回调：首次思考时打印标签，灰显内容。"""
        if role_label != self._current_role:
            if self._output_active:
                print()
            print(f"\n{'─'*50}")
            print(f"  [{role_label}] 生成中...")
            print(f"{'─'*50}")
            self._current_role = role_label
            self._thinking_active = False
            self._output_active = False
        if not self._thinking_active:
            print(f"\n>>> 思考过程：")
            self._thinking_active = True
        sys.stdout.write(f"\033[90m{token}\033[0m")
        sys.stdout.flush()

    def _on_agent_token(self, token: str, role_label: str) -> None:
        """默认输出回调：思考结束后打印输出标签。"""
        if role_label != self._current_role:
            if self._output_active:
                print()
            print(f"\n{'─'*50}")
            print(f"  [{role_label}] 生成中...")
            print(f"{'─'*50}")
            self._current_role = role_label
            self._thinking_active = False
            self._output_active = False
        if not self._output_active:
            if self._thinking_active:
                print(f"\n\n>>> 输出：\n")
            else:
                print(f"\n>>> 输出：\n")
            self._output_active = True
        sys.stdout.write(token)
        sys.stdout.flush()

    def _print_streaming(self, label: str, role: str):
        """Return (on_token, on_thinking) callbacks for streaming display."""
        print(f"\n{'─'*50}")
        print(f"  [{label}] 正在生成...")
        print(f"{'─'*50}")

        thinking_started = [False]
        output_started = [False]

        def on_thinking(token: str) -> None:
            if not thinking_started[0]:
                print(f"\n>>> {role} 思考过程：")
                thinking_started[0] = True
            # Dimmed gray for thinking content
            sys.stdout.write(f"\033[90m{token}\033[0m")
            sys.stdout.flush()

        def on_token(token: str) -> None:
            if not output_started[0]:
                if thinking_started[0]:
                    print(f"\n\n>>> {role} 输出：\n")
                else:
                    print(f"\n>>> {role} 输出：\n")
                output_started[0] = True
            sys.stdout.write(token)
            sys.stdout.flush()

        return on_token, on_thinking

    def solve(self, question: str) -> None:
        if not question.strip():
            print("请输入有效的问题。")
            return

        print(f"\n工作流模式：{self.mode}")
        print(f"问题：{question}")

        if self.mode == "agent_loop":
            result = self.orchestrator.solve_agent_loop(question)
        elif self.mode == "plan":
            result = self.orchestrator.solve_with_plan(question)
        elif self.mode == "explore":
            result = self.orchestrator.solve_explore(question)
        elif self.mode == "sequential":
            result = self.orchestrator.solve_sequential(question)
        elif self.mode == "review":
            result = self.orchestrator.solve_with_review(question, max_review_rounds=1)
        elif self.mode == "parallel":
            result = self.orchestrator.solve_parallel(question)
        else:
            print(f"未知模式: {self.mode}")
            return

        # Persist outputs when running with the real orchestrator. Some tests
        # provide a small fake that only implements the selected solve method.
        save_outputs = getattr(self.orchestrator, "_save_outputs", None)
        if save_outputs is not None:
            save_outputs(result)
        self._print_result(result)

    def solve_stream(self, question: str) -> None:
        if not question.strip():
            return

        print(f"\n工作流模式：streaming (sequential)")
        m_tok, m_think = self._print_streaming("建模", "建模智能体")
        p_tok, p_think = self._print_streaming("编程", "编程智能体")
        w_tok, w_think = self._print_streaming("写作", "写作智能体")
        s_tok, s_think = self._print_streaming("总控", "总控智能体")
        result = self.orchestrator.solve_stream(
            question,
            on_modeling_token=m_tok, on_modeling_thinking=m_think,
            on_programming_token=p_tok, on_programming_thinking=p_think,
            on_writing_token=w_tok, on_writing_thinking=w_think,
            on_synthesis_token=s_tok, on_synthesis_thinking=s_think,
        )
        self.orchestrator._save_outputs(result)
        self._print_result(result)

    @staticmethod
    def _print_result(result) -> None:
        print("\n" + "=" * 60)
        print("  协作完成")
        print("=" * 60)
        print(result.format_overview())

    def run_single_agent(self) -> None:
        print(SINGLE_AGENT_HELP)
        llm = create_llm(self.settings)
        agent = create_agent(model=llm, tools=TOOLS_FULL, system_prompt=SINGLE_AGENT_PROMPT)
        history: list = []

        while True:
            try:
                user_input = input("\n你：").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break

            if not user_input:
                continue
            if user_input.lower() in {"/exit", "exit", "quit"}:
                print("再见！")
                break
            if user_input.lower() == "/orchestrate":
                print("已切换到多智能体模式。")
                return self.run()
            if user_input.lower() == "/reset":
                history.clear()
                print("Agent：已清空对话记忆。")
                continue

            response = agent.invoke({"messages": [*history, HumanMessage(content=user_input)]})
            answer = self._extract_content(response)
            print(f"Agent：{answer}")
            history.append(HumanMessage(content=user_input))
            history.append(AIMessage(content=answer))

    @staticmethod
    def _extract_content(response: dict) -> str:
        messages = response.get("messages", [])
        if not messages:
            return ""
        last = messages[-1]
        content = getattr(last, "content", last)
        return normalize_llm_content(content)

    def run(self) -> None:
        print(ORCHESTRATOR_HELP)
        while True:
            try:
                raw = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break

            if not raw:
                continue

            if raw.lower() in {"/exit", "exit", "quit"}:
                print("再见！")
                break
            if raw.lower() == "/chat":
                print("已切换到单智能体模式。")
                return self.run_single_agent()
            if raw.lower() == "/memory":
                stats = self.memory_manager.stats()
                print(f"\n短期记忆：{stats['stm_messages']} 条消息，{stats['stm_tokens']} tokens")
                print(f"压缩前缀：{'有' if stats.get('stm_has_compressed_prefix') else '无'}，压缩次数：{stats['compressions']}")
                print(f"长期记忆：{stats['ltm_total']} 条知识，{stats['ltm_by_type']}")
                continue
            if raw.lower() == "/compress":
                result = self.memory_manager.force_compress()
                if result:
                    print(f"压缩完成：{result[:200]}...")
                else:
                    print("压缩器未启用或无需压缩（未配置 LLM 或消息不足）")
                continue
            if raw.lower() == "/skills":
                from .skills import SkillRegistry
                registry = SkillRegistry()
                print(registry.summarize_available())
                continue
            if raw.lower() == "/subagent":
                from .subagent import list_subagent_types
                print(list_subagent_types())
                continue
            if raw.lower() == "/help":
                print(ORCHESTRATOR_HELP)
                continue
            if raw.lower().startswith("/mode"):
                parts = raw.split(maxsplit=1)
                new_mode = parts[1].strip().lower() if len(parts) > 1 else ""
                if new_mode in ORCHESTRATOR_MODES:
                    self.mode = new_mode
                    print(f"已切换到 {new_mode} 模式。")
                else:
                    print(f"无效模式。可选: {' / '.join(ORCHESTRATOR_MODES)}")
                continue
            if raw.lower().startswith("/plan"):
                question = raw.split(maxsplit=1)[1].strip() if len(raw) > 5 else ""
                if question:
                    print(f"\n生成求解计划：{question}\n")
                    import time as _time
                    started = _time.monotonic()
                    plan = self.orchestrator.plan_only(question)
                    elapsed = _time.monotonic() - started
                    print(plan)
                    print(f"\n── 计划生成耗时 {elapsed:.1f}s ──")
                    print("输入 /execute 基于此计划执行求解，或 /solve 重新求解")
                    self._last_plan = plan  # save for /execute
                else:
                    print("请提供问题，例如：/plan 建立交通流优化模型")
                continue
            if raw.lower() == "/execute":
                if hasattr(self, '_last_plan') and self._last_plan:
                    question = self._last_plan.split("问题分析")[0]
                    question = question.replace("#", "").strip()[:200]
                    if not question:
                        question = "执行已规划的任务"
                    result = self.orchestrator.solve_with_plan(
                        question, pre_generated_plan=self._last_plan,
                    )
                    self.orchestrator._save_outputs(result)
                    self._print_result(result)
                    del self._last_plan
                else:
                    print("没有可执行的计划。请先用 /plan <问题> 生成计划。")
                continue
            if raw.lower().startswith("/solve"):
                question = raw.split(maxsplit=1)[1].strip() if len(raw) > 6 else ""
                if question:
                    self.solve(question)
                else:
                    print("请提供问题，例如：/solve 建立交通流优化模型")
                continue
            if raw.lower() == "/stream":
                print("请输入问题（流式模式）：")
                q = input("问题：").strip()
                if q:
                    self.solve_stream(q)
                continue

            # 默认按多智能体协作处理
            self.solve(raw)


def main() -> None:
    app = CLI()
    app.run()


if __name__ == "__main__":
    main()
