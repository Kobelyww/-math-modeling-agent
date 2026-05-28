# DeepSeek Agent Loop Design

## Goal

`agent_app` should move from a fixed workflow runner to a conversation-driven agent loop while continuing to use DeepSeek as the primary model.

The current system has strong building blocks: specialist agents, LangChain tools, RAG, memory, subagents, file output, and CLI/Web/GUI entry points. The new design keeps those assets and changes the orchestration model. Instead of always executing a fixed sequence such as `modeling -> programming -> writing -> synthesis`, a coordinator loop decides the next action from the conversation state.

## Recommended Approach

Add a DeepSeek-backed `solve_agent_loop()` path and make it the default mode. Keep the existing `plan`, `sequential`, `review`, `parallel`, and `explore` strategies as legacy fallback modes.

This is compatible with the DeepAgents style of architecture without forcing a large dependency migration in the first change. The implementation can later wrap the loop with DeepAgents primitives if the project wants deeper framework alignment.

## Architecture

The implementation adds a small agent loop layer around the existing `Orchestrator`.

Core pieces:

- `AgentLoopDecision`: structured coordinator decision with `action`, `reason`, `target_agent`, and optional `instruction`.
- `AgentLoopTrace`: per-step trace entry for UI, tests, and debugging.
- `AgentLoopResult`: internal loop state converted back into the existing `WorkflowResult`.
- `Orchestrator.solve_agent_loop()`: the default solve method for dynamic execution.
- A coordinator prompt that asks the synthesizer/planner model to choose one next action at a time.

The loop should support these actions:

- `explore`: gather local/RAG/research context.
- `model`: call the modeler agent.
- `program`: call the programmer agent.
- `debug`: call the code debugger agent.
- `write`: call the writer agent.
- `review`: call the reviewer agent against a specific output.
- `synthesize`: call the synthesizer.
- `ask_user`: stop with a clarification request when required information is missing.
- `final`: finish and return a `WorkflowResult`.

## Data Flow

1. Receive the user question.
2. Build context from memory and RAG.
3. Ask the coordinator for the next structured action.
4. Execute the chosen specialist agent or tool-backed phase.
5. Store each output in shared memory and the loop trace.
6. Repeat until `final`, `ask_user`, max steps, timeout, or token budget.
7. Normalize outputs into `WorkflowResult`:
   - best modeler output -> `modeling`
   - best programmer/debug output -> `programming`
   - best writer output -> `writing`
   - final synthesis or coordinator summary -> `synthesis`
8. Run existing finalization to save generated files and build logs.

## Compatibility

Existing entry points should continue to work.

- CLI: default mode becomes `agent_loop`; `/mode` still allows legacy strategies.
- GUI: add `agent_loop` as default collaboration strategy.
- Web API: default `strategy` becomes `agent_loop`, while old strategies remain supported.
- Tests: existing fixed-workflow tests remain valid unless they explicitly assert the default mode.

`WorkflowResult` remains the public result type to avoid a broad UI/API rewrite.

## Error Handling

The loop should fail soft where possible.

- Invalid coordinator JSON falls back to a deterministic next action based on missing outputs.
- Unknown action records an error and asks the coordinator again.
- Specialist agent failure records a fallback stage output and continues when useful.
- Max-step termination returns the best available synthesis with a warning.
- Token and timeout conditions stop the loop and return partial results.

## Testing

Implementation should use test-first changes.

Initial tests:

- Coordinator decision parsing accepts valid JSON and rejects invalid actions.
- Fallback policy chooses sensible next actions when coordinator output is invalid.
- `solve_agent_loop()` can run with stubbed agents and produce a compatible `WorkflowResult`.
- CLI default mode is `agent_loop`.
- Web route dispatches `agent_loop` to the new loop method.

No live DeepSeek calls are required for unit tests; use stubs/mocks.

## Out Of Scope

- Full migration to Claude Agent SDK.
- Removing existing workflow strategies.
- Replacing memory/RAG implementations.
- Rebuilding the UI around a new trace model in the first change.
- Introducing mandatory DeepAgents dependency before the local loop is stable.

