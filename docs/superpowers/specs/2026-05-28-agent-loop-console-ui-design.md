# Agent Loop Console UI Design

## Goal

Update `agent_app` UI so the default experience matches the new DeepSeek-backed `agent_loop` orchestration model. The interface should feel like an operator console for a dynamic agent loop, not a fixed `modeling -> programming -> writing -> synthesis` workflow board.

## Recommended Approach

Use the **Agent Loop Console** direction approved in the visual companion. Apply the design to both Web and Streamlit GUI. Do not change CLI visuals and do not change backend agent-loop semantics in this UI pass.

The UI should make three concepts visible:

- Control: task input, strategy selection, RAG/PDF controls, run state.
- Loop: dynamic agent decisions and outputs as a trace/timeline instead of assuming a fixed order.
- Artifacts: generated files and final deliverables in one place.

## Web UI

The FastAPI Web UI should become the primary polished console.

Layout:

- Header: product name, DeepSeek/Agent Loop badge, compact run status.
- Left control rail: strategy select with `agent_loop` first, question/PDF input, RAG controls, and Nature Skills summary.
- Center loop workspace: a horizontal or vertical loop timeline showing steps such as `explore`, `model`, `program`, `debug`, `write`, `review`, and `synthesize`.
- Output panels: reusable agent output cards keyed by role, so dynamic execution can fill whichever roles actually ran.
- Right artifacts rail: buttons or links for code, LaTeX, final report, workflow JSON, and generated output folder status.

Behavior:

- The default selected strategy is `agent_loop`.
- Legacy strategies remain selectable.
- While `agent_loop` is running, the UI should not imply a fixed phase order. Agent cards can still exist, but their labels and empty states should explain that the coordinator decides the next step.
- Existing WebSocket events remain compatible. If only legacy token events are available, the UI renders them into the loop workspace by agent role.

## Streamlit GUI

The Streamlit GUI should mirror the same information architecture with Streamlit-native components.

Layout:

- Sidebar remains the control rail.
- Main collaboration tab starts with a concise console status band and task input.
- Results render in sections for loop trace, agent outputs, final synthesis, and generated files.
- `COLLABORATION_MODES` keeps `agent_loop` first.

Behavior:

- For `agent_loop`, use non-streaming execution for now and display the returned `agent_loop_trace` after completion.
- Existing streaming support remains available for `sequential`.
- Build logs and output directory remain visible when available.

## Styling

The visual direction should be quiet, utilitarian, and work-focused:

- Use a restrained neutral palette with clear accent colors for state.
- Avoid decorative hero sections and marketing-style cards.
- Use compact panels, stable heights, and predictable scan paths.
- Make controls and labels dense enough for repeated operational use.
- Keep cards at `8px` radius or less.

## Data Flow

1. User enters a task or uploads a PDF.
2. UI sends `strategy=agent_loop` by default.
3. Backend runs `Orchestrator.solve_agent_loop()`.
4. UI renders available streaming role events during the run.
5. On completion, UI renders:
   - role outputs,
   - final synthesis,
   - loop trace when present,
   - generated file/build log status when present.

## Error Handling

- Empty question shows an inline validation message.
- WebSocket or solve errors show a clear error banner without clearing existing output.
- PDF/RAG failures stay scoped to their control panels.
- Missing artifacts show disabled or empty states instead of broken buttons.

## Testing

Tests should cover stable behavior rather than visual pixels:

- Web template includes `agent_loop` as the default strategy option.
- Web JavaScript initializes an agent-loop-friendly output model.
- Streamlit constants keep `agent_loop` first.
- Existing agent-loop, route, and orchestrator tests continue to pass.

Manual verification should include launching the relevant local UI or at least validating the static Web files and running the Python test suite.

## Out Of Scope

- Changing agent-loop decision logic.
- Adding a new backend trace streaming protocol.
- Replacing Streamlit with another frontend framework.
- Building a full file browser for `agent_app/output`.
- Pushing to GitHub or opening a PR.
