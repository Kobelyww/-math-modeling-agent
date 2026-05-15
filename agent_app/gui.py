"""Streamlit GUI for the multi-agent math modeling collaboration system.

Launch: streamlit run agent_app/gui.py
or:      python -m agent_app.gui
"""

from __future__ import annotations

# Allow direct execution: python gui.py  or  python -m agent_app.gui
if __name__ == "__main__" and __package__ is None:
    import sys as _sys
    from pathlib import Path as _Path

    _parent = _Path(__file__).resolve().parent.parent
    if str(_parent) not in _sys.path:
        _sys.path.insert(0, str(_parent))
    __package__ = "agent_app"

import subprocess
import sys
from pathlib import Path

import streamlit as st

from .config import APP_ROOT, load_settings
from .llm import create_llm
from .memory import MemoryManager
from .orchestrator import Orchestrator, StageResult, WorkflowResult
from .rag import PaperRAG
from .tools import TOOLS

# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------

KNOWLEDGE_DIR = APP_ROOT.parent / "knowledge_base"
DATA_DIR = APP_ROOT / "data"
INDEX_PATH = DATA_DIR / "rag_index.pkl"

# ---------------------------------------------------------------------------
# launch helpers
# ---------------------------------------------------------------------------


def _running_in_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


def _launch_streamlit() -> int:
    print("Starting Streamlit server...")
    return subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve())],
        check=False,
    ).returncode


# ---------------------------------------------------------------------------
# session init
# ---------------------------------------------------------------------------


def _init_session():
    if "settings" not in st.session_state:
        st.session_state.settings = load_settings()
    if "rag" not in st.session_state:
        rag = PaperRAG(knowledge_dir=KNOWLEDGE_DIR, index_path=INDEX_PATH)
        rag.load_index()
        st.session_state.rag = rag
    if "orchestrator" not in st.session_state:
        try:
            memory_manager = MemoryManager(use_redis=True)
            from .memory.redis_backends import _redis_client
            _redis_client().ping()
        except Exception:
            memory_manager = MemoryManager(use_redis=False)
        st.session_state.orchestrator = Orchestrator(
            st.session_state.settings,
            rag=st.session_state.rag,
            memory_manager=memory_manager,
        )
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "single_agent" not in st.session_state:
        from langchain.agents import create_agent

        llm = create_llm(st.session_state.settings)
        st.session_state.single_agent = create_agent(
            model=llm,
            tools=TOOLS,
            system_prompt="你是一个基于 DeepSeek 的智能助手，专长数学建模与代码实现。",
        )


# ---------------------------------------------------------------------------
# streaming callback
# ---------------------------------------------------------------------------


def _stream_to_placeholder(placeholder, label: str):
    parts: list[str] = []

    def on_token(token: str) -> None:
        parts.append(token)
        placeholder.markdown(f"### {label}\n\n{''.join(parts)}")

    return on_token


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _display_result(result: WorkflowResult):
    st.success("协作完成")
    with st.expander("建模智能体输出", expanded=False):
        st.write(result.modeling.content)
    with st.expander("编程智能体输出", expanded=False):
        st.write(result.programming.content)
    with st.expander("写作智能体输出", expanded=False):
        st.write(result.writing.content)
    st.markdown("### 总控整合方案")
    st.write(result.synthesis)


# ---------------------------------------------------------------------------
# page components
# ---------------------------------------------------------------------------


def _sidebar():
    st.sidebar.title("配置")

    mode = st.sidebar.selectbox(
        "协作策略",
        options=["sequential", "review", "parallel"],
        format_func=lambda m: {
            "sequential": "串行流水线",
            "review": "深度反思",
            "parallel": "快速并行",
        }.get(m, m),
        help="sequential=建模→编程→写作→总控 | review=每阶段评审后修改 | parallel=建模先行，编程+写作并行",
    )

    review_rounds = 1
    if mode == "review":
        review_rounds = st.sidebar.slider("评审轮数", 1, 3, 1)

    st.sidebar.markdown("---")
    st.sidebar.subheader("RAG 知识库")

    top_k = st.sidebar.slider("召回片段数", 3, 12, 6)

    st.sidebar.write(f"目录：`{KNOWLEDGE_DIR}`")
    uploaded = st.sidebar.file_uploader(
        "上传论文（pdf/txt/md）",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
        key="rag_upload",
    )
    if uploaded:
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        count = 0
        for f in uploaded:
            (KNOWLEDGE_DIR / f.name).write_bytes(f.getbuffer())
            count += 1
        st.sidebar.success(f"已保存 {count} 个文件")

    if st.sidebar.button("重建 RAG 索引", use_container_width=True):
        with st.spinner("正在构建索引..."):
            stats = st.session_state.rag.build_index()
        st.sidebar.success(f"索引完成：{stats['files']} 文件，{stats['chunks']} 片段")

    rag_ready = st.session_state.rag.is_ready
    st.sidebar.caption(
        f"索引状态：{'已就绪' if rag_ready else '未构建'}（{len(st.session_state.rag.chunks)} 片段）"
    )

    return mode, review_rounds, top_k


def _tab_collaboration(mode: str, review_rounds: int, top_k: int):
    st.subheader("多智能体协作分析")

    question = st.text_area(
        "输入赛题或研究任务",
        placeholder="例如：建立新能源车充电站布局优化模型，并给出可实现方案与论文写作框架",
        height=120,
    )

    use_streaming = st.checkbox("流式输出（实时显示生成过程）", value=True)

    if st.button("开始协作分析", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("请先输入任务问题。")
            return

        orch: Orchestrator = st.session_state.orchestrator

        # ---- RAG preview ----
        with st.expander("RAG 参考片段", expanded=False):
            chunks = st.session_state.rag.query(question, top_k=top_k) if st.session_state.rag.is_ready else []
            if chunks:
                for i, c in enumerate(chunks, 1):
                    st.markdown(f"**{i}. {c.source}（片段 {c.chunk_id}）**\n\n{c.content}")
            else:
                st.info("未命中索引片段。请上传论文并重建索引。")

        # ---- streaming mode ----
        if use_streaming and mode == "sequential":
            col1, col2, col3 = st.columns(3)
            with col1:
                m_box = st.empty()
                m_box.markdown("### 建模智能体\n\n_等待生成中..._")
            with col2:
                p_box = st.empty()
                p_box.markdown("### 编程智能体\n\n_等待生成中..._")
            with col3:
                w_box = st.empty()
                w_box.markdown("### 写作智能体\n\n_等待生成中..._")

            st.markdown("---")
            s_box = st.empty()
            s_box.markdown("### 总控整合方案\n\n_等待生成中..._")

            with st.spinner("智能体流式协作中..."):
                result = orch.solve_stream(
                    question,
                    top_k=top_k,
                    on_modeling_token=_stream_to_placeholder(m_box, "建模智能体"),
                    on_programming_token=_stream_to_placeholder(p_box, "编程智能体"),
                    on_writing_token=_stream_to_placeholder(w_box, "写作智能体"),
                    on_synthesis_token=_stream_to_placeholder(s_box, "总控整合方案"),
                )
            _display_result(result)
            return

        # ---- non-streaming modes ----
        with st.spinner(f"智能体协作中（模式：{mode}）..."):
            if mode == "sequential":
                result = orch.solve_sequential(question, top_k=top_k)
            elif mode == "review":
                result = orch.solve_with_review(question, top_k=top_k, max_review_rounds=review_rounds)
            else:
                result = orch.solve_parallel(question, top_k=top_k)

        _display_result(result)


def _tab_single_agent():
    st.subheader("单智能体对话")

    # show history
    for msg in st.session_state.chat_history:
        role = "user" if msg["role"] == "user" else "assistant"
        with st.chat_message(role):
            st.write(msg["content"])

    if prompt := st.chat_input("输入消息..."):
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            with st.spinner("思考中..."):
                from langchain_core.messages import AIMessage, HumanMessage

                history_msgs = []
                for m in st.session_state.chat_history:
                    if m["role"] == "user":
                        history_msgs.append(HumanMessage(content=m["content"]))
                    else:
                        history_msgs.append(AIMessage(content=m["content"]))

                response = st.session_state.single_agent.invoke({
                    "messages": [*history_msgs, HumanMessage(content=prompt)]
                })
                messages = response.get("messages", [])
                answer = ""
                if messages:
                    last = messages[-1]
                    content = getattr(last, "content", last)
                    if isinstance(content, list):
                        answer = "".join(
                            str(item.get("text", item)) if isinstance(item, dict) else str(item)
                            for item in content
                        )
                    else:
                        answer = str(content)

                placeholder.write(answer)

        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun()

    if st.button("清空对话", use_container_width=True):
        st.session_state.chat_history.clear()
        st.rerun()


def _tab_rag_explorer(top_k: int):
    st.subheader("知识库检索测试")

    query = st.text_input("检索问题", placeholder="例如：国奖论文中灵敏度分析的常见写法")
    if st.button("检索", use_container_width=True):
        if not st.session_state.rag.is_ready:
            st.warning("索引未就绪，请先在侧边栏构建索引。")
        else:
            hits = st.session_state.rag.query(query, top_k=top_k)
            if not hits:
                st.info("无匹配结果。")
            for i, hit in enumerate(hits, 1):
                st.markdown(f"**{i}. {hit.source} / chunk-{hit.chunk_id}**")
                st.write(hit.content)


def _tab_agent_info():
    st.subheader("智能体说明")

    agents = [
        ("建模智能体", "将赛题抽象为变量、约束和优化目标，构建数学模型"),
        ("编程智能体", "将数学模型转化为可执行代码方案，设计算法与实验"),
        ("写作智能体", "将建模与实验结果组织为高质量竞赛论文"),
        ("评审智能体", "审查各阶段输出，发现漏洞并提供具体改进建议"),
        ("总控智能体", "整合各专家输出为统一方案，制定实施计划"),
    ]
    for name, desc in agents:
        with st.expander(name):
            st.write(desc)


# ---------------------------------------------------------------------------
# main ui
# ---------------------------------------------------------------------------


def run_ui():
    st.set_page_config(
        page_title="数模多智能体协作系统",
        page_icon="🧠",
        layout="wide",
    )
    st.title("数模多智能体协作系统（DeepSeek + RAG）")
    st.caption("五大专业智能体分工协作：建模 / 编程 / 写作 / 评审 / 总控")

    _init_session()
    mode, review_rounds, top_k = _sidebar()

    tabs = st.tabs(["多智能体协作", "单智能体对话", "RAG 检索", "智能体说明"])

    with tabs[0]:
        _tab_collaboration(mode, review_rounds, top_k)
    with tabs[1]:
        _tab_single_agent()
    with tabs[2]:
        _tab_rag_explorer(top_k)
    with tabs[3]:
        _tab_agent_info()


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _running_in_streamlit():
        run_ui()
    else:
        raise SystemExit(_launch_streamlit())