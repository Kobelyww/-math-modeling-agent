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


class TestUsageTracking:
    def test_tool_loop_accumulates_usage_across_rounds(self, monkeypatch):
        from agent_app.base import BaseAgent

        class FakeToolLLM:
            def __init__(self):
                self.calls = 0

            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                self.calls += 1
                response = MagicMock()
                if self.calls == 1:
                    response.content = ""
                    response.tool_calls = [{
                        "name": "echo",
                        "args": {"value": "hello"},
                        "id": "call-1",
                    }]
                    response.usage_metadata = {"input_tokens": 5, "output_tokens": 2}
                else:
                    response.content = "final answer"
                    response.tool_calls = []
                    response.usage_metadata = {"input_tokens": 7, "output_tokens": 3}
                response.response_metadata = {}
                return response

        class FakeChatDeepSeek:
            def __init__(self, **kwargs):
                self.llm = FakeToolLLM()

            def bind_tools(self, tools):
                return self.llm

        class FakeParentLLM:
            api_key = "test-key"
            api_base = ""

        monkeypatch.setattr("langchain_deepseek.ChatDeepSeek", FakeChatDeepSeek)

        def echo(value):
            return value

        monkeypatch.setitem(__import__("agent_app.base").base._TOOL_EXECUTORS, "echo", echo)

        agent = BaseAgent(FakeParentLLM())
        agent.role = "test-agent"
        result = agent.invoke_with_tools("prompt", tools=[MagicMock(name="echo")], max_tool_rounds=2)

        assert result == "\n[工具调用: echo(value='hello')]\nfinal answer"
        assert agent.last_usage == {"prompt_tokens": 12, "completion_tokens": 5}


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


class TestToolPathSecurity:
    def test_read_file_rejects_outside_workspace(self, tmp_path, monkeypatch):
        from agent_app import config
        from agent_app.exploration import read_file

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        secret = tmp_path / "secret.txt"
        secret.write_text("secret", encoding="utf-8")
        monkeypatch.setattr(config, "APP_ROOT", workspace / "agent_app")

        msg = read_file.invoke({"filepath": str(secret)})

        assert "outside workspace" in msg

    def test_search_files_rejects_outside_workspace(self, tmp_path, monkeypatch):
        from agent_app import config
        from agent_app.exploration import search_files

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        monkeypatch.setattr(config, "APP_ROOT", workspace / "agent_app")

        msg = search_files.invoke({"pattern": "*.py", "directory": str(outside)})

        assert "outside workspace" in msg

    def test_read_csv_info_rejects_outside_workspace(self, tmp_path, monkeypatch):
        from agent_app import config
        from agent_app.tools import read_csv_info

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        outside_csv = tmp_path / "data.csv"
        outside_csv.write_text("x\n1\n", encoding="utf-8")
        monkeypatch.setattr(config, "APP_ROOT", workspace / "agent_app")

        msg = read_csv_info.invoke({"filepath": str(outside_csv)})

        assert "outside workspace" in msg


class TestWebToolApi:
    def test_web_tool_api_executes_python_tool(self, monkeypatch):
        import asyncio

        from agent_app.web import routes

        class FakeTool:
            @staticmethod
            def invoke(args):
                return f"ran {args['code']}"

        monkeypatch.setitem(routes.WEB_TOOL_REGISTRY, "python_exec", FakeTool())

        result = asyncio.run(routes.run_tool("python_exec", {"code": "print(1)"}))

        assert result == {"result": "ran print(1)"}

    def test_web_tool_api_normalizes_latex_content_key(self, monkeypatch):
        import asyncio

        from agent_app.web import routes

        seen = {}

        class FakeLatexTool:
            @staticmethod
            def invoke(args):
                seen.update(args)
                return "Compilation successful. PDF at: /tmp/paper.pdf"

        monkeypatch.setitem(routes.WEB_TOOL_REGISTRY, "latex_compile", FakeLatexTool())

        result = asyncio.run(routes.run_tool("latex_compile", {"tex_content": "\\documentclass{article}"}))

        assert seen == {"content": "\\documentclass{article}"}
        assert result["result"].startswith("Compilation successful")

    def test_frontend_uses_latex_compile_content_parameter(self):
        from pathlib import Path

        js = Path("agent_app/web/static/app.js").read_text(encoding="utf-8")

        assert "body: JSON.stringify({ content: latex })" in js
        assert "tex_content" not in js


class TestDockerSandbox:
    def test_build_image_skips_build_when_image_already_exists(self, monkeypatch, tmp_path):
        from agent_app.sandbox.docker_sandbox import DockerSandbox, SandboxConfig

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        monkeypatch.setattr("agent_app.sandbox.docker_sandbox.SANDBOX_DIR", tmp_path)
        monkeypatch.setattr("agent_app.sandbox.docker_sandbox.shutil.which", lambda name: "/usr/bin/docker")
        monkeypatch.setattr("agent_app.sandbox.docker_sandbox.subprocess.run", fake_run)

        sandbox = DockerSandbox(SandboxConfig(image="agent-app-sandbox:test"))

        assert sandbox.build_image() is True

        assert calls == [["docker", "image", "inspect", "agent-app-sandbox:test"]]
