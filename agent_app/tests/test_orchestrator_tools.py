"""Tests for orchestrator tool resolution and output finalization."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent_app.agents import ModelerAgent, ProgrammerAgent, WriterAgent
from agent_app.config import Settings
from agent_app.memory import SharedMemory
from agent_app.orchestrator import Orchestrator, StageResult, WorkflowResult


@pytest.fixture
def orchestrator() -> Orchestrator:
    settings = Settings(
        api_key="test-key",
        api_base=None,
        model="deepseek-chat",
        temperature=0.3,
    )
    orch = Orchestrator(settings, rag=None, memory_manager=None)
    return orch


class TestToolRoleResolution:
    def test_stage_label_maps_to_tools(self, orchestrator: Orchestrator):
        tools = orchestrator._resolve_agent_tools(orchestrator.modeler, "modeling")
        names = {t.name for t in tools}
        assert "write_file" in names
        assert "web_search" in names

    def test_programming_label_gets_python_exec(self, orchestrator: Orchestrator):
        tools = orchestrator._resolve_agent_tools(orchestrator.programmer, "programming")
        names = {t.name for t in tools}
        assert "python_exec" in names
        assert "write_file" in names

    def test_writer_label_gets_latex_compile(self, orchestrator: Orchestrator):
        tools = orchestrator._resolve_agent_tools(orchestrator.writer, "writing")
        names = {t.name for t in tools}
        assert "latex_compile" in names

    def test_agent_instance_fallback(self, orchestrator: Orchestrator):
        tools = orchestrator._resolve_agent_tools(orchestrator.writer, "unknown_label")
        assert any(t.name == "latex_compile" for t in tools)

    def test_max_tool_rounds_for_programmer(self, orchestrator: Orchestrator):
        assert orchestrator._max_tool_rounds(orchestrator.programmer, "programming") >= 5

    def test_safe_invoke_uses_invoke_with_tools_when_role_has_tools(
        self,
        orchestrator: Orchestrator,
        monkeypatch: pytest.MonkeyPatch,
    ):
        class ToolAwareStubAgent:
            def __init__(self):
                self.invoked_with_tools = False
                self.stream_called = False
                self.last_usage = {"prompt_tokens": 2, "completion_tokens": 3}
                self.seen_tools = None
                self.seen_max_tool_rounds = None

            def invoke_with_tools(self, prompt, tools, max_tool_rounds):
                self.invoked_with_tools = True
                self.seen_tools = tools
                self.seen_max_tool_rounds = max_tool_rounds
                return "tool output"

            def stream(self, prompt, on_token=None, on_thinking=None):
                self.stream_called = True
                return "stream output"

        agent = ToolAwareStubAgent()
        tools = [MagicMock(name="fake_tool")]
        stm = SharedMemory()
        errors: list[str] = []
        tokens: list[str] = []

        monkeypatch.setattr(orchestrator, "_resolve_agent_tools", lambda agent, role_label: tools)
        monkeypatch.setattr(orchestrator, "_max_tool_rounds", lambda agent, role_label: 7)

        result = orchestrator._safe_invoke(
            agent,
            "prompt",
            "programming",
            stm,
            errors,
            on_token=tokens.append,
        )

        assert agent.invoked_with_tools is True
        assert agent.stream_called is False
        assert agent.seen_tools == tools
        assert agent.seen_max_tool_rounds == 7
        assert result == "tool output"
        assert tokens == ["tool output"]
        msg = stm.latest_by_role("programming")
        assert msg is not None
        assert msg.prompt_tokens == 2
        assert msg.completion_tokens == 3
        assert errors == []


class TestFinalizeWorkflow:
    def test_finalize_calls_save_outputs(self, orchestrator: Orchestrator):
        result = WorkflowResult(
            question="test",
            modeling=StageResult("建模", "```python\nprint(1)\n```"),
            programming=StageResult("编程", "```python\nprint('hi')\n```"),
            writing=StageResult("写作", "no latex here"),
            synthesis="done",
        )
        with patch.object(orchestrator, "_save_outputs", return_value="✅ solve.py") as mock_save:
            out = orchestrator._finalize_workflow(result)
        mock_save.assert_called_once_with(result)
        assert out.build_log == "✅ solve.py"


class TestSafeStreamLegacyBehavior:
    def test_safe_stream_does_not_inject_orchestrator_callbacks(self, orchestrator: Orchestrator):
        class StubStreamAgent:
            def __init__(self):
                self.last_usage = {"prompt_tokens": 7, "completion_tokens": 3}
                self.received_callbacks = None

            def stream(self, prompt, on_token=None, on_thinking=None):
                self.received_callbacks = (on_token, on_thinking)
                return "stream output"

        stub = StubStreamAgent()
        orchestrator.on_agent_token = lambda token, role: (_ for _ in ()).throw(
            AssertionError("unexpected orchestrator token callback")
        )
        orchestrator.on_agent_thinking = lambda token, role: (_ for _ in ()).throw(
            AssertionError("unexpected orchestrator thinking callback")
        )

        stm = SharedMemory()
        errors: list[str] = []

        result = orchestrator._safe_stream(stub, "prompt", "modeling", stm, errors)

        assert result == "stream output"
        assert stub.received_callbacks == (None, None)
        assert errors == []


class TestWriteFileTool:
    def test_write_file_allows_subdir(self, tmp_path, monkeypatch):
        from agent_app.exploration import write_file
        from agent_app import config

        out = tmp_path / "output"
        monkeypatch.setattr(config, "APP_ROOT", tmp_path)
        msg = write_file.invoke({"filepath": "figures/plot.py", "content": "x = 1"})
        assert "figures/plot.py" in msg
        assert (out / "figures" / "plot.py").exists()

    def test_write_file_rejects_traversal(self, tmp_path, monkeypatch):
        from agent_app.exploration import write_file
        from agent_app import config

        monkeypatch.setattr(config, "APP_ROOT", tmp_path)
        msg = write_file.invoke({"filepath": "../escape.py", "content": "bad"})
        assert "Invalid" in msg
