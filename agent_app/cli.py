
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

from .config import APP_ROOT, load_settings
from .llm import create_llm
from .orchestrator import Orchestrator
from .rag import PaperRAG
from .tools import TOOLS

SINGLE_AGENT_PROMPT = """你是一个基于 DeepSeek 的智能助手，专长数学建模与代码实现。
工作方式：
- 先理解用户目标，再决定是否调用工具
- 需要计算、查看时间、保存笔记时，优先使用工具
- 回答要清晰、实用、简洁
"""

ORCHESTRATOR_HELP = f"""
{'='*60}
  数模多智能体协作系统
{'='*60}

工作流模式：
  1. sequential  - 串行流水线（建模→编程→写作→总控，稳定可靠）
  2. review      - 深度反思（每阶段经评审专家审核后修改，质量优先）
  3. parallel    - 快速并行（建模先行，编程+写作并行执行，速度优先）

命令：
  /mode <模式名>  - 切换工作流模式（默认 sequential）
  /solve <问题>   - 启动多智能体协作分析
  /chat           - 切换到单智能体对话模式
  /help           - 显示此帮助
  /exit           - 退出程序
""".strip()

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
        self.rag = PaperRAG(knowledge_dir=knowledge_dir, index_path=data_dir / "rag_index.pkl")
        if self.rag.load_index():
            print(f"[RAG] 已加载索引（{len(self.rag.chunks)} 个片段）")
        else:
            print("[RAG] 未找到索引文件，运行 build_index() 可构建")

        self.orchestrator = Orchestrator(self.settings, rag=self.rag)
        self.mode: str = "sequential"

    def build_rag_index(self) -> dict:
        return self.rag.build_index()

    def _print_streaming(self, label: str, role: str):
        print(f"\n{'─'*50}")
        print(f"  [{label}] 正在生成...")
        print(f"{'─'*50}")

        first_token = [True]

        def on_token(token: str) -> None:
            if first_token[0]:
                print(f"\n>>> {role} 输出：\n")
                first_token[0] = False
            sys.stdout.write(token)
            sys.stdout.flush()

        return on_token

    def solve(self, question: str) -> None:
        if not question.strip():
            print("请输入有效的问题。")
            return

        print(f"\n工作流模式：{self.mode}")
        print(f"问题：{question}")

        if self.mode == "sequential":
            result = self.orchestrator.solve_sequential(question)
        elif self.mode == "review":
            result = self.orchestrator.solve_with_review(question, max_review_rounds=1)
        elif self.mode == "parallel":
            result = self.orchestrator.solve_parallel(question)
        else:
            print(f"未知模式: {self.mode}")
            return

        self._print_result(result)

    def solve_stream(self, question: str) -> None:
        if not question.strip():
            return

        print(f"\n工作流模式：streaming (sequential)")
        result = self.orchestrator.solve_stream(
            question,
            on_modeling_token=self._print_streaming("建模", "建模智能体"),
            on_programming_token=self._print_streaming("编程", "编程智能体"),
            on_writing_token=self._print_streaming("写作", "写作智能体"),
            on_synthesis_token=self._print_streaming("总控", "总控智能体"),
        )
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
        agent = create_agent(model=llm, tools=TOOLS, system_prompt=SINGLE_AGENT_PROMPT)
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
        if isinstance(content, list):
            return "".join(
                str(item.get("text", item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        return str(content)

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
            if raw.lower() == "/help":
                print(ORCHESTRATOR_HELP)
                continue
            if raw.lower().startswith("/mode"):
                parts = raw.split(maxsplit=1)
                new_mode = parts[1].strip().lower() if len(parts) > 1 else ""
                if new_mode in ("sequential", "review", "parallel"):
                    self.mode = new_mode
                    print(f"已切换到 {new_mode} 模式。")
                else:
                    print(f"无效模式。可选: sequential / review / parallel")
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