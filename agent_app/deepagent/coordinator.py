from __future__ import annotations

from typing import Any

from agent_app.deepagent.middleware import CompetitionStageMiddleware
from agent_app.deepagent.prompts import COMPETITION_COORDINATOR_PROMPT
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


def create_competition_paper_agent(
    llm: Any,
    run_store: RunStore,
    middleware: CompetitionStageMiddleware | None = None,
    event_handler: Any | None = None,
    **services: Any,
):
    from deepagents import create_deep_agent

    tools = make_competition_tools(run_store=run_store, **services)
    active_middleware = [middleware or CompetitionStageMiddleware(event_handler=event_handler)]
    return create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=COMPETITION_COORDINATOR_PROMPT,
        middleware=active_middleware,
    )
