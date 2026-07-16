"""Compatibility shims for optional third-party packages.

The workspace contains many LangChain/DeepSeek/OpenAI example scripts, but
those packages are not always installed in the local execution environment.
This module installs lightweight fallbacks only when the real packages are
missing, so imports keep working without affecting environments that already
have the dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
import inspect
import sys
import types
from typing import Any


def _missing(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is None
    except Exception:
        return True


def _package(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__package__ = name
    module.__path__ = []  # mark as package
    sys.modules[name] = module
    return module


def _submodule(parent: types.ModuleType, name: str) -> types.ModuleType:
    full_name = f"{parent.__name__}.{name}"
    module = types.ModuleType(full_name)
    module.__package__ = parent.__name__
    sys.modules[full_name] = module
    setattr(parent, name, module)
    return module


def _extract_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, _BaseMessage):
        return str(payload.content)
    if isinstance(payload, dict):
        for key in ("content", "text", "message"):
            value = payload.get(key)
            if value is not None:
                return _extract_text(value)
        return " ".join(f"{k}={v}" for k, v in payload.items())
    if isinstance(payload, (list, tuple)):
        return "".join(_extract_text(item) for item in payload)
    return str(payload)


@dataclass
class _BaseMessage:
    content: Any = ""
    additional_kwargs: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    response_metadata: dict[str, Any] = field(default_factory=dict)
    usage_metadata: dict[str, Any] = field(default_factory=dict)
    name: str | None = None
    tool_call_id: str | None = None


class AIMessage(_BaseMessage):
    pass


class HumanMessage(_BaseMessage):
    pass


class SystemMessage(_BaseMessage):
    pass


class ToolMessage(_BaseMessage):
    pass


class BaseChatModel:
    """Tiny stand-in for LangChain chat models.

    It produces deterministic echo-style responses and exposes the small API
    surface that this workspace uses (`invoke`, `stream`, `bind_tools`,
    `ainvoke`, `astream`, `batch`, `abatch`).
    """

    def __init__(
        self,
        model: str = "",
        temperature: float = 0.0,
        api_key: str | None = None,
        api_base: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self.api_base = api_base
        self.openai_api_key = api_key
        self.openai_api_base = api_base
        self.max_tokens = max_tokens
        self._bound_tools: list[Any] = []
        self._extra_kwargs = kwargs

    def bind_tools(self, tools: list[Any] | tuple[Any, ...] | None = None):
        self._bound_tools = list(tools or [])
        return self

    def _render(self, messages: Any) -> str:
        text = _extract_text(messages).strip()
        if not text:
            text = "Hello"
        if len(text) > 500:
            text = text[:500] + "..."
        prefix = self.model or self.__class__.__name__
        return f"[{prefix} stub] {text}"

    def _usage(self, content: str) -> dict[str, int]:
        prompt_tokens = max(len(content) // 4, 1)
        completion_tokens = max(len(content) // 6, 1)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }

    def invoke(self, messages: Any, **kwargs: Any) -> AIMessage:
        content = self._render(messages)
        usage = self._usage(content)
        return AIMessage(
            content=content,
            usage_metadata={
                "input_tokens": usage["prompt_tokens"],
                "output_tokens": usage["completion_tokens"],
            },
            response_metadata={
                "token_usage": usage,
            },
        )

    def stream(self, messages: Any, **kwargs: Any):
        yield self.invoke(messages, **kwargs)

    async def ainvoke(self, messages: Any, **kwargs: Any) -> AIMessage:
        return self.invoke(messages, **kwargs)

    async def astream(self, messages: Any, **kwargs: Any):
        yield self.invoke(messages, **kwargs)

    def batch(self, messages: Any, **kwargs: Any) -> list[AIMessage]:
        if isinstance(messages, (list, tuple)) and messages:
            first = messages[0]
            if isinstance(first, (list, tuple, dict, _BaseMessage, str)):
                if all(isinstance(item, str) for item in messages):
                    return [self.invoke(item, **kwargs) for item in messages]
                if isinstance(first, (list, tuple, dict, _BaseMessage)):
                    return [self.invoke(messages, **kwargs)]
        return [self.invoke(messages, **kwargs)]

    async def abatch(self, messages: Any, **kwargs: Any) -> list[AIMessage]:
        return self.batch(messages, **kwargs)

    def __call__(self, messages: Any, **kwargs: Any) -> AIMessage:
        return self.invoke(messages, **kwargs)


class ChatDeepSeek(BaseChatModel):
    pass


class ChatOpenAI(BaseChatModel):
    pass


class PromptTemplate:
    def __init__(self, template: str, input_variables: list[str] | None = None) -> None:
        self.template = template
        self.input_variables = input_variables or []

    @classmethod
    def from_template(cls, template: str) -> "PromptTemplate":
        return cls(template=template)

    def format(self, **kwargs: Any) -> str:
        return self.template.format(**kwargs)


class LangChainException(Exception):
    pass


class SimpleTool:
    def __init__(self, func):
        inspect.signature(func)
        self.func = func
        self.name = getattr(func, "__name__", "tool")
        self.description = inspect.getdoc(func) or ""
        self.args_schema = None
        self.__doc__ = func.__doc__
        self.__name__ = self.name
        self.__wrapped__ = func

    def invoke(self, args: Any | None = None):
        if args is None:
            return self.func()
        if isinstance(args, dict):
            return self.func(**args)
        if isinstance(args, (list, tuple)):
            return self.func(*args)
        return self.func(args)

    def __call__(self, *args: Any, **kwargs: Any):
        return self.func(*args, **kwargs)


def tool(func=None, **kwargs):
    if func is None:
        def decorator(inner):
            return SimpleTool(inner)

        return decorator
    return SimpleTool(func)


class _Runtime:
    def __init__(self, context: Any = None) -> None:
        self.context = context


class ModelRequest:
    def __init__(self, runtime: _Runtime | None = None) -> None:
        self.runtime = runtime or _Runtime()


class SimpleAgent:
    def __init__(
        self,
        model: BaseChatModel,
        tools: list[Any] | None = None,
        middleware: list[Any] | None = None,
        system_prompt: str = "",
        context_schema: Any = None,
    ) -> None:
        self.model = model
        self.tools = tools or []
        self.middleware = middleware or []
        self.system_prompt = system_prompt
        self.context_schema = context_schema

    def _resolve_system_prompt(self, context: Any = None) -> str:
        for middleware in self.middleware:
            if callable(middleware):
                try:
                    value = middleware(ModelRequest(runtime=_Runtime(context=context)))
                except TypeError:
                    try:
                        value = middleware()
                    except Exception:
                        continue
                except Exception:
                    continue
                if value is not None:
                    return str(value)
        return self.system_prompt

    def invoke(self, payload: Any, context: Any = None, **kwargs: Any) -> AIMessage:
        prompt = self._resolve_system_prompt(context=context)
        messages: list[_BaseMessage] = []
        if prompt:
            messages.append(SystemMessage(content=prompt))

        if isinstance(payload, dict):
            raw_messages = payload.get("messages") or payload.get("message") or payload.get("input")
            if raw_messages is None:
                raw_messages = payload
        else:
            raw_messages = payload

        if isinstance(raw_messages, (list, tuple)):
            for item in raw_messages:
                if isinstance(item, dict):
                    role = item.get("role", "user")
                    content = item.get("content", "")
                    if role == "system":
                        messages.append(SystemMessage(content=content))
                    elif role == "assistant":
                        messages.append(AIMessage(content=content))
                    else:
                        messages.append(HumanMessage(content=content))
                elif isinstance(item, _BaseMessage):
                    messages.append(item)
                else:
                    messages.append(HumanMessage(content=str(item)))
        elif isinstance(raw_messages, _BaseMessage):
            messages.append(raw_messages)
        elif raw_messages is not None:
            messages.append(HumanMessage(content=str(raw_messages)))

        return self.model.invoke(messages)


def create_agent(*, model: BaseChatModel, tools=None, middleware=None, system_prompt="", context_schema=None, **kwargs):
    return SimpleAgent(
        model=model,
        tools=list(tools or []),
        middleware=list(middleware or []),
        system_prompt=system_prompt,
        context_schema=context_schema,
    )


def dynamic_prompt(func):
    func.__dynamic_prompt__ = True
    return func


def _install_langchain_core() -> None:
    pkg = _package("langchain_core")
    pkg.__version__ = "0.0.0-stub"
    pkg.__all__ = [
        "BaseChatModel",
        "AIMessage",
        "HumanMessage",
        "SystemMessage",
        "ToolMessage",
        "PromptTemplate",
        "LangChainException",
        "tool",
    ]

    language_models = _submodule(pkg, "language_models")
    language_models.BaseChatModel = BaseChatModel

    messages = _submodule(pkg, "messages")
    messages.AIMessage = AIMessage
    messages.HumanMessage = HumanMessage
    messages.SystemMessage = SystemMessage
    messages.ToolMessage = ToolMessage
    messages.BaseMessage = _BaseMessage

    tools_mod = _submodule(pkg, "tools")
    tools_mod.tool = tool
    tools_mod.SimpleTool = SimpleTool

    exceptions = _submodule(pkg, "exceptions")
    exceptions.LangChainException = LangChainException

    prompts = _submodule(pkg, "prompts")
    prompts.PromptTemplate = PromptTemplate

    pkg.BaseChatModel = BaseChatModel
    pkg.AIMessage = AIMessage
    pkg.HumanMessage = HumanMessage
    pkg.SystemMessage = SystemMessage
    pkg.ToolMessage = ToolMessage
    pkg.PromptTemplate = PromptTemplate
    pkg.LangChainException = LangChainException
    pkg.tool = tool


def _install_langchain_deepseek() -> None:
    pkg = _package("langchain_deepseek")
    pkg.__version__ = "0.0.0-stub"
    pkg.ChatDeepSeek = ChatDeepSeek


def _install_langchain_openai() -> None:
    pkg = _package("langchain_openai")
    pkg.__version__ = "0.0.0-stub"
    pkg.ChatOpenAI = ChatOpenAI


def _install_langchain() -> None:
    pkg = _package("langchain")
    pkg.__version__ = "0.0.0-stub"

    messages = _submodule(pkg, "messages")
    messages.AIMessage = AIMessage
    messages.HumanMessage = HumanMessage
    messages.SystemMessage = SystemMessage
    messages.ToolMessage = ToolMessage
    messages.BaseMessage = _BaseMessage

    agents = _submodule(pkg, "agents")
    agents.create_agent = create_agent

    middleware = _submodule(agents, "middleware")
    middleware.dynamic_prompt = dynamic_prompt
    middleware.ModelRequest = ModelRequest

    chat_models = _submodule(pkg, "chat_models")
    chat_models.init_chat_model = lambda **kwargs: ChatOpenAI(**kwargs)
    chat_models.ChatOpenAI = ChatOpenAI

    chat_models_base = _submodule(chat_models, "base")
    chat_models_base._ConfigurableModel = BaseChatModel

    pkg.messages = messages
    pkg.agents = agents
    pkg.chat_models = chat_models


def _install_langchain_community() -> None:
    pkg = _package("langchain_community")
    pkg.__version__ = "0.0.0-stub"


def _install_openai() -> None:
    pkg = _package("openai")
    pkg.__version__ = "0.0.0-stub"
    pkg.api_key = None


if _missing("langchain_core"):
    _install_langchain_core()

if _missing("langchain_deepseek"):
    _install_langchain_deepseek()

if _missing("langchain_openai"):
    _install_langchain_openai()

if _missing("langchain"):
    _install_langchain()

if _missing("langchain_community"):
    _install_langchain_community()

if _missing("openai"):
    _install_openai()
