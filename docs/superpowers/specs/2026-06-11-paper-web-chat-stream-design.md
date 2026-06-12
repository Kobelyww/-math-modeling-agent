# Paper Web Chat Stream Design

## Goal

Make the Web UI use the DeepAgent paper workflow as a conversational, streaming experience. Users can submit a competition/research question, watch stage-by-stage progress in a chat panel, inspect artifacts as they appear, and send follow-up instructions that start another paper run with the conversation context.

## Architecture

The existing legacy `/api/solve` WebSocket flow remains available, but the main page shifts to a paper-focused chat console. A new paper task API creates a task id, and `/ws/paper/{task_id}` streams structured events: `start`, `stage`, `tool`, `artifact`, `quality_gate`, `message`, `done`, and `error`.

The first implementation streams deterministic stage/tool progress from the existing competition tool pipeline. This gives a real observable process without pretending DeepAgent token streaming exists where it does not. The event protocol includes `token`/`message` fields so a later DeepAgent `stream`/`astream` integration can plug into the same UI.

## Web UX

The page is a production work surface, not a marketing page:

- Left rail: strategy selector, attachments, run button, RAG, skills.
- Center: chat transcript with user turns, stage updates, quality reports, and final summary.
- Right rail: live stage checklist and artifact list.
- Bottom input: follow-up instruction box that appends prior transcript context to the next run.

## Boundaries

- Keep old `/api/solve` and `/ws/solve/{task_id}`.
- Keep `/api/paper/run` for non-stream API clients.
- Web-provided file paths still resolve only under `agent_app/data/paper_inputs`.
- No fake token-by-token LLM output. Stage events are real; token events are reserved for future direct model streaming.

## Verification

- Unit tests cover paper event streaming and follow-up prompt construction.
- Existing competition runner and smoke tests keep passing.
- Browser check confirms the main page loads and exposes the paper chat controls.
