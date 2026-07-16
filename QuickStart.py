"""Quickstart demo for the LangChain-compatible agent stub."""

from __future__ import annotations

from dataclasses import dataclass

import workspace_shims  # noqa: F401
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt

from env_utils import DEEPSEEK_API_BASE, DEEPSEEK_API_KEY
from langchain_deepseek import ChatDeepSeek


@dataclass
class Content:
    user_adr: str = "nanjing"
    user_name: str = "haobowang"


def build_agent():
    llm = ChatDeepSeek(
        model="deepseek-reasoner",
        temperature=0.7,
        api_key=DEEPSEEK_API_KEY,
        api_base=DEEPSEEK_API_BASE,
    )

    @dynamic_prompt
    def prompt(request: ModelRequest) -> str:
        user_adr = request.runtime.context.user_adr
        user_name = request.runtime.context.user_name
        prompt_text = "你是一个opus4.7，根据指令进行回答"

        if user_adr:
            prompt_text += f"，当前用于地址为{user_adr}"

        if user_name:
            prompt_text += f"，当前用于用户为{user_name}"

        return prompt_text

    return create_agent(
        model=llm,
        middleware=[prompt],
        context_schema=Content,
    )


def main() -> None:
    agent = build_agent()
    resp = agent.invoke(
        {"message": [{"role": "user", "content": "你是谁"}]},
        context=Content(user_adr="beijing", user_name="haobowang"),
    )
    print(resp)


if __name__ == "__main__":
    main()
