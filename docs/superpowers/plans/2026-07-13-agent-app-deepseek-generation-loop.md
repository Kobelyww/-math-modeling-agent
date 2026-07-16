# Agent App DeepSeek Generation Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the template-heavy paper pipeline with a Mimo-vision-only plus DeepSeek V4 Pro text/code/review generation loop, including chapter-level paper writing.

**Architecture:** Keep the existing RunStore, WebSocket streaming, and competition tool API, but add focused services for model routing, structured problem packaging, DeepSeek generation, section writing, and revise control. The first implementation should use injectable fake LLM clients in tests so behavior is deterministic while production calls DeepSeek through the existing LangChain-compatible configuration.

**Tech Stack:** Python 3, FastAPI, LangChain-compatible chat models, DeepAgent tools, PyMuPDF, pytest, markdown/json artifacts.

---

## File Structure

- Modify `agent_app/config.py`: add explicit vision/text provider fields while keeping current `.env` compatibility.
- Modify `agent_app/llm.py`: create role-specific DeepSeek text models and keep Mimo out of text generation.
- Create `agent_app/services/problem_package.py`: build `problem_spec.json`, `tables.json`, `figures.json`, and `source_map.json`.
- Create `agent_app/services/deepseek_generation.py`: typed wrapper for DeepSeek planner/programmer/writer/reviewer calls with fake-client injection.
- Create `agent_app/services/paper_sections.py`: section artifact paths, section context builders, section merge and consistency checks.
- Modify `agent_app/tools/competition.py`: replace B-problem deterministic planner/programmer/writer paths with service-backed DeepSeek generation.
- Modify `agent_app/web/routes.py`: persist structured PDF extraction artifacts and emit visual reconstruction metadata.
- Modify `agent_app/web/paper_stream.py`: stream section-writing and revise-loop events.
- Modify `agent_app/deepagent/runner.py`: mark review failures as partial/needs revision instead of completed.
- Add/modify tests under `agent_app/tests/`.

## Task 1: Model Routing Boundary

**Files:**
- Modify: `agent_app/config.py`
- Modify: `agent_app/llm.py`
- Test: `agent_app/tests/test_model_routing.py`

- [ ] **Step 1: Write failing tests**

```python
from agent_app.config import load_settings


def test_settings_separates_mimo_vision_from_deepseek_text(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "VISION_PROVIDER=mimo\n"
        "MIMO_API_KEY=mimo-key\n"
        "MIMO_API_BASE=https://api.xiaomimimo.com/v1\n"
        "MIMO_VISION_MODEL=mimo-v2.5-pro\n"
        "TEXT_AGENT_PROVIDER=deepseek\n"
        "DEEPSEEK_API_KEY=deepseek-key\n"
        "DEEPSEEK_API_BASE=https://api.deepseek.com\n"
        "DEEPSEEK_MODEL=deepseek-v4-pro\n",
        encoding="utf-8",
    )

    settings = load_settings(env)

    assert settings.vision_provider == "mimo"
    assert settings.vision_model == "mimo-v2.5-pro"
    assert settings.text_agent_provider == "deepseek"
    assert settings.model == "deepseek-v4-pro"
    assert settings.api_key == "deepseek-key"


def test_legacy_mimo_provider_still_loads_for_visual_only_config(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "LLM_PROVIDER=mimo\n"
        "MIMO_API_KEY=mimo-key\n"
        "MIMO_API_BASE=https://api.xiaomimimo.com/v1\n"
        "MIMO_MODEL=mimo-v2.5-pro\n"
        "DEEPSEEK_API_KEY=deepseek-key\n"
        "DEEPSEEK_MODEL=deepseek-v4-pro\n",
        encoding="utf-8",
    )

    settings = load_settings(env)

    assert settings.vision_provider == "mimo"
    assert settings.text_agent_provider == "deepseek"
    assert settings.api_key == "deepseek-key"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest agent_app/tests/test_model_routing.py -q`

Expected: FAIL because `Settings` does not expose `vision_provider`, `vision_model`, or `text_agent_provider`.

- [ ] **Step 3: Implement minimal routing fields**

Add fields to `Settings`:

```python
vision_provider: str = "mimo"
vision_api_key: str | None = None
vision_api_base: str | None = None
vision_model: str = "mimo-v2.5-pro"
text_agent_provider: str = "deepseek"
```

Update `load_settings()` so `DEEPSEEK_*` is the text agent source and `MIMO_*` is the vision source. Preserve existing env compatibility by treating `LLM_PROVIDER=mimo` as `VISION_PROVIDER=mimo` plus `TEXT_AGENT_PROVIDER=deepseek` when `DEEPSEEK_API_KEY` exists.

- [ ] **Step 4: Run routing tests**

Run: `pytest agent_app/tests/test_model_routing.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/config.py agent_app/llm.py agent_app/tests/test_model_routing.py
git commit -m "feat: split vision and text model routing"
```

## Task 2: Structured Problem Package

**Files:**
- Create: `agent_app/services/problem_package.py`
- Modify: `agent_app/tools/competition.py`
- Modify: `agent_app/web/routes.py`
- Test: `agent_app/tests/test_problem_package.py`

- [ ] **Step 1: Write failing tests**

```python
import json

from agent_app.services.artifact_service import ArtifactService
from agent_app.services.problem_package import build_problem_package


def test_build_problem_package_writes_structured_tables(tmp_path):
    artifacts = ArtifactService(tmp_path)
    question = "问题1：抽样检测。表1 企业在生产中遇到的情况 情况 零配件1 次品率 1 10%。"
    tables = [
        {
            "title": "表1 企业在生产中遇到的情况",
            "page": 2,
            "method": "mimo_vision",
            "confidence": 0.82,
            "headers": ["情况", "零配件1次品率"],
            "rows": [["1", "10%"]],
        }
    ]

    package = build_problem_package(artifacts, question=question, tables=tables, figures=[])

    assert package["problem_spec_path"].endswith("problem_spec.json")
    tables_json = json.loads((tmp_path / "tables.json").read_text(encoding="utf-8"))
    assert tables_json["tables"][0]["title"] == "表1 企业在生产中遇到的情况"
    assert tables_json["tables"][0]["source"]["page"] == 2
    assert tables_json["tables"][0]["source"]["method"] == "mimo_vision"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent_app/tests/test_problem_package.py -q`

Expected: FAIL because `problem_package.py` does not exist.

- [ ] **Step 3: Implement `build_problem_package`**

Create a service that writes:

```python
{
  "problem_spec.json": {"background": "问题1：抽样检测", "subproblems": [], "objectives": [], "constraints": []},
  "tables.json": {"tables": [{"title": "表1", "rows": [["1", "10%"]]}]},
  "figures.json": {"figures": [{"title": "图1", "page": 3, "description": "两道工序装配结构"}]},
  "source_map.json": {"sources": [{"artifact": "tables.json", "page": 2, "method": "mimo_vision"}]}
}
```

Keep parsing conservative: this task only persists structured artifacts and source metadata. DeepSeek problem analysis will refine subproblems later.

- [ ] **Step 4: Integrate with tools**

Update `ingest_inputs` or the PDF upload path so uploaded/extracted question text can be persisted as structured artifacts. Do not remove `question.md`.

- [ ] **Step 5: Run tests**

Run: `pytest agent_app/tests/test_problem_package.py agent_app/tests/test_deepagent_tools.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agent_app/services/problem_package.py agent_app/tools/competition.py agent_app/web/routes.py agent_app/tests/test_problem_package.py
git commit -m "feat: persist structured problem packages"
```

## Task 3: DeepSeek Generation Service

**Files:**
- Create: `agent_app/services/deepseek_generation.py`
- Test: `agent_app/tests/test_deepseek_generation_service.py`

- [ ] **Step 1: Write failing tests**

```python
from agent_app.services.deepseek_generation import DeepSeekGenerationService


class FakeChatModel:
    def __init__(self, content):
        self.content = content
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        return type("Msg", (), {"content": self.content})()


def test_generate_json_parses_model_response():
    service = DeepSeekGenerationService(FakeChatModel('{"selected_model":"binomial"}'))

    result = service.generate_json("planner", [{"role": "user", "content": "plan"}])

    assert result == {"selected_model": "binomial"}


def test_generate_markdown_returns_text():
    service = DeepSeekGenerationService(FakeChatModel("# Section\n\nText"))

    result = service.generate_markdown("writer", [{"role": "user", "content": "write"}])

    assert result.startswith("# Section")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest agent_app/tests/test_deepseek_generation_service.py -q`

Expected: FAIL because service does not exist.

- [ ] **Step 3: Implement service**

Implement:

- `generate_json(role: str, messages: list[dict[str, str]]) -> dict`
- `generate_markdown(role: str, messages: list[dict[str, str]]) -> str`
- JSON parsing that strips fenced code blocks.
- Clear `ValueError` when JSON is invalid.

- [ ] **Step 4: Run tests**

Run: `pytest agent_app/tests/test_deepseek_generation_service.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/services/deepseek_generation.py agent_app/tests/test_deepseek_generation_service.py
git commit -m "feat: add deepseek generation service"
```

## Task 4: DeepSeek Planner Replaces B-Problem Template

**Files:**
- Modify: `agent_app/tools/competition.py`
- Test: `agent_app/tests/test_deepseek_planner_tool.py`

- [ ] **Step 1: Write failing test**

```python
from agent_app.domain.models import RunSpec
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


class FakeGenerationService:
    def generate_json(self, role, messages):
        assert role == "modeling_planner"
        return {
            "selected_model": "DeepSeek generated plan",
            "subproblem_plans": [{"id": "q1", "title": "抽样检测", "result_file": "results/q1.csv"}],
            "experiment_conclusion_links": ["q1 -> 论文结论：抽样检测方案；关系：支撑"],
        }

    def generate_markdown(self, role, messages):
        assert role == "modeling_planner"
        return "# Modeling Plan\n\nDeepSeek generated modeling report."


def test_plan_model_uses_deepseek_generation_for_b_problem(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="生产过程中的决策问题 零配件 拆解"))
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store, generation_service=FakeGenerationService())}

    result = tools["plan_model"].invoke(
        {"run_id": state.run_id, "problem_brief": {"background": "生产过程中的决策问题 零配件 拆解"}, "data_audit": {}, "evidence_notes": []}
    )

    assert result["modeling_plan"]["selected_model"] == "DeepSeek generated plan"
    assert "DeepSeek generated modeling report" in (store.run_dir(state.run_id) / "modeling_report.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent_app/tests/test_deepseek_planner_tool.py -q`

Expected: FAIL because `plan_model` still uses deterministic B-problem text.

- [ ] **Step 3: Modify `plan_model`**

When `generation_service` is provided, build a planner prompt from `problem_spec.json`, `tables.json`, `data_audit`, and `evidence_notes`. Save returned JSON as `model_plan.json` and Markdown as `modeling_report.md`.

Keep deterministic fallback only for tests or when no generation service exists.

- [ ] **Step 4: Run tests**

Run: `pytest agent_app/tests/test_deepseek_planner_tool.py agent_app/tests/test_deepagent_tools.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/tools/competition.py agent_app/tests/test_deepseek_planner_tool.py
git commit -m "feat: use deepseek planner for modeling plans"
```

## Task 5: DeepSeek Programmer and Debug Loop

**Files:**
- Modify: `agent_app/tools/competition.py`
- Test: `agent_app/tests/test_deepseek_programmer_tool.py`

- [ ] **Step 1: Write failing test**

```python
from agent_app.domain.models import RunSpec
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


class FakeGenerationService:
    def generate_markdown(self, role, messages):
        assert role in {"programmer", "code_debugger"}
        return (
            "```python\n"
            "from pathlib import Path\n"
            "def main():\n"
            "    out = Path('results'); out.mkdir(exist_ok=True)\n"
            "    (out / 'q1.csv').write_text('metric,value\\nanswer,1\\n', encoding='utf-8')\n"
            "    (out / 'model_equations.md').write_text('# Equations\\n', encoding='utf-8')\n"
            "if __name__ == '__main__': main()\n"
            "```"
        )


def test_run_experiment_uses_deepseek_programmer_output(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="建立模型"))
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store, generation_service=FakeGenerationService())}

    result = tools["run_experiment"].invoke(
        {"run_id": state.run_id, "modeling_plan": {"subproblem_plans": [{"id": "q1", "result_file": "results/q1.csv"}]}, "data_files": []}
    )

    assert result["experiment_result"]["execution_status"] == "success"
    assert (store.run_dir(state.run_id) / "results" / "q1.csv").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent_app/tests/test_deepseek_programmer_tool.py -q`

Expected: FAIL because `run_experiment` ignores the generation service.

- [ ] **Step 3: Implement programmer path**

Extract fenced Python code, write `solve.py`, execute it in the run directory, collect `results/`, and write `experiment_manifest.json`. On failure, call role `code_debugger` once with traceback and previous code, then retry.

- [ ] **Step 4: Run tests**

Run: `pytest agent_app/tests/test_deepseek_programmer_tool.py agent_app/tests/test_deepagent_tools.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/tools/competition.py agent_app/tests/test_deepseek_programmer_tool.py
git commit -m "feat: generate experiments with deepseek programmer"
```

## Task 6: Chapter-Level Paper Writing

**Files:**
- Create: `agent_app/services/paper_sections.py`
- Modify: `agent_app/tools/competition.py`
- Test: `agent_app/tests/test_section_paper_writer.py`

- [ ] **Step 1: Write failing test**

```python
from agent_app.services.paper_sections import REQUIRED_SECTION_FILES, section_path


def test_required_section_files_are_chapter_level():
    assert "00_abstract.md" in REQUIRED_SECTION_FILES
    assert "04_model_building.md" in REQUIRED_SECTION_FILES
    assert "09_appendix.md" in REQUIRED_SECTION_FILES


def test_section_path_uses_paper_sections_directory(tmp_path):
    assert section_path(tmp_path, "04_model_building.md") == tmp_path / "paper" / "sections" / "04_model_building.md"
```

- [ ] **Step 2: Add tool-level failing test**

```python
from agent_app.domain.models import RunSpec
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


class FakeWriterService:
    def generate_markdown(self, role, messages):
        if role == "paper_synthesizer":
            return "# Final Paper\n\nMerged section text."
        if role == "latex_synthesizer":
            return "\\documentclass{article}\n\\begin{document}\nMerged section text.\n\\end{document}\n"
        return "# Section\n\nUses cited artifacts."


def test_draft_competition_paper_writes_section_artifacts(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="建立模型"))
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store, generation_service=FakeWriterService())}

    result = tools["draft_competition_paper"].invoke(
        {
            "run_id": state.run_id,
            "problem_brief": {"subproblems": [{"id": "q1", "title": "抽样检测"}]},
            "data_audit": {},
            "modeling_plan": {"subproblem_plans": [{"id": "q1", "title": "抽样检测", "result_file": "results/q1.csv"}]},
            "experiment_result": {"result_paths": ["results/q1.csv"]},
            "evidence_notes": [],
        }
    )

    run_dir = store.run_dir(state.run_id)
    assert (run_dir / "paper" / "sections" / "00_abstract.md").exists()
    assert (run_dir / "paper" / "sections" / "04_model_building.md").exists()
    assert "Merged section text" in (run_dir / "paper.md").read_text(encoding="utf-8")
    assert result["paper_markdown_path"].endswith("paper.md")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest agent_app/tests/test_section_paper_writer.py -q`

Expected: FAIL because section service does not exist.

- [ ] **Step 4: Implement section service**

Create constants for required section files, section prompts, and merge helpers. Abstract must be generated last. Each section context must include only relevant artifacts and the shared symbol table.

- [ ] **Step 5: Modify `draft_competition_paper`**

When generation service exists:

1. Generate section files one by one.
2. Generate `paper_consistency_report.md`.
3. Generate `paper.md`.
4. Generate `paper.tex`.

Keep deterministic fallback only when no generation service exists.

- [ ] **Step 6: Run tests**

Run: `pytest agent_app/tests/test_section_paper_writer.py agent_app/tests/test_deepagent_tools.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add agent_app/services/paper_sections.py agent_app/tools/competition.py agent_app/tests/test_section_paper_writer.py
git commit -m "feat: write papers by section with deepseek"
```

## Task 7: Review Failure Stops Packaging and Triggers Revise State

**Files:**
- Modify: `agent_app/web/paper_stream.py`
- Modify: `agent_app/deepagent/runner.py`
- Modify: `agent_app/tools/competition.py`
- Test: `agent_app/tests/test_review_revise_loop.py`

- [ ] **Step 1: Write failing test**

```python
from agent_app.domain.models import RunSpec
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


def test_failed_review_prevents_completed_package(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="生产过程中的决策问题 零配件 拆解"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "modeling_report.md").write_text("生产过程中的决策问题\n", encoding="utf-8")
    (run_dir / "solve.py").write_text("def main():\n    print('shallow')\n", encoding="utf-8")
    (run_dir / "paper.tex").write_text("\\documentclass{article}\\begin{document}shallow\\end{document}", encoding="utf-8")
    (run_dir / "paper.md").write_text("# 生产过程中的决策问题\n\n浅层论文。", encoding="utf-8")

    tools = {tool.name: tool for tool in make_competition_tools(run_store=store)}
    review = tools["review_submission"].invoke(
        {"run_id": state.run_id, "paper_draft": {}, "experiment_result": {}, "artifacts": []}
    )

    assert review["quality_report"]["passed"] is False
    assert review["quality_report"]["required_fixes"]
    # The coordinator/runner integration added in this task must consume this failed report
    # and skip package_submission, leaving the run partial instead of completed.
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent_app/tests/test_review_revise_loop.py -q`

Expected: FAIL because current pipeline can continue to package after review failure.

- [ ] **Step 3: Implement revise control**

Add review result handling:

- `passed=True`: continue packaging.
- `passed=False`: emit `quality_gate`, emit `revise_required`, skip package, mark run partial.
- If `max_repair_attempts` remains, route back to the failed stage in a later task.

- [ ] **Step 4: Run tests**

Run: `pytest agent_app/tests/test_review_revise_loop.py agent_app/tests/test_paper_chat_stream.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/web/paper_stream.py agent_app/deepagent/runner.py agent_app/tools/competition.py agent_app/tests/test_review_revise_loop.py
git commit -m "feat: stop packaging on failed review"
```

## Task 8: Web Streaming for Section Writing

**Files:**
- Modify: `agent_app/web/paper_stream.py`
- Modify: `agent_app/web/static/app.js`
- Test: `agent_app/tests/test_paper_chat_stream.py`

- [ ] **Step 1: Write failing test**

```python
from agent_app.domain.models import RunSpec
from agent_app.web.paper_stream import PaperChatStreamer


def test_paper_stream_emits_section_writing_events(tmp_path):
    events = []

    class FakeCoordinator:
        def __init__(self, run_store, settings=None, event_handler=None):
            self.run_store = run_store
            self.event_handler = event_handler

        def invoke(self, payload):
            run_dir = self.run_store.run_dir(payload["run_id"])
            section = run_dir / "paper" / "sections" / "04_model_building.md"
            section.parent.mkdir(parents=True, exist_ok=True)
            section.write_text("# 模型建立\n", encoding="utf-8")
            self.event_handler({"type": "section", "stage": "draft_paper", "name": "04_model_building.md", "status": "completed", "path": str(section)})
            return {"messages": [{"content": str(section)}]}

    streamer = PaperChatStreamer(output_root=tmp_path, coordinator_factory=FakeCoordinator)
    streamer.run(RunSpec(question="建立模型"), events.append)

    assert any(event.get("type") == "section" and event.get("name") == "04_model_building.md" for event in events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent_app/tests/test_paper_chat_stream.py::test_paper_stream_emits_section_writing_events -q`

Expected: FAIL because no section event exists.

- [ ] **Step 3: Implement events**

Emit:

```json
{"type": "section", "stage": "draft_paper", "name": "04_model_building.md", "status": "completed", "path": "/tmp/run/paper/sections/04_model_building.md"}
```

Update `app.js` to render section events as progress entries and artifacts.

- [ ] **Step 4: Run tests and JS check**

Run:

```bash
pytest agent_app/tests/test_paper_chat_stream.py -q
node --check agent_app/web/static/app.js
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/web/paper_stream.py agent_app/web/static/app.js agent_app/tests/test_paper_chat_stream.py
git commit -m "feat: stream chapter writing progress"
```

## Task 9: B Problem Acceptance Test

**Files:**
- Create or modify: `agent_app/tests/test_b_problem_acceptance.py`

- [ ] **Step 1: Write acceptance test with fake DeepSeek**

```python
from agent_app.domain.models import RunSpec
from agent_app.services.run_store import RunStore
from agent_app.tools.competition import make_competition_tools


class FakeFullChainGenerationService:
    def generate_json(self, role, messages):
        if role == "modeling_planner":
            return {
                "selected_model": "DeepSeek generated B problem model",
                "subproblem_plans": [
                    {"id": "q1", "title": "抽样检测", "result_file": "results/q1.csv"},
                    {"id": "q2", "title": "表1决策", "result_file": "results/q2.csv"},
                    {"id": "q3", "title": "表2决策", "result_file": "results/q3.csv"},
                    {"id": "q4", "title": "抽样不确定性", "result_file": "results/q4.csv"},
                ],
                "experiment_conclusion_links": ["q1-q4 -> 论文结论：四个子问题均有结果支撑；关系：支撑"],
            }
        return {"passed": True, "required_fixes": []}

    def generate_markdown(self, role, messages):
        if role == "programmer":
            return (
                "```python\n"
                "import json\n"
                "from pathlib import Path\n"
                "def main():\n"
                "    tables = json.loads(Path('tables.json').read_text(encoding='utf-8'))\n"
                "    out = Path('results'); out.mkdir(exist_ok=True)\n"
                "    (out / 'q1.csv').write_text('metric,value\\nrows,' + str(len(tables.get('tables', []))) + '\\n', encoding='utf-8')\n"
                "    (out / 'model_equations.md').write_text('# Equations\\n', encoding='utf-8')\n"
                "if __name__ == '__main__': main()\n"
                "```"
            )
        if role == "paper_synthesizer":
            return "# Final Paper\n\n四个子问题均已回答。"
        if role == "latex_synthesizer":
            return "\\documentclass{article}\\begin{document}四个子问题均已回答。\\end{document}"
        return "# Section\n\n章节内容引用了 results/q1.csv。"


def test_b_problem_full_chain_uses_structured_tables_and_sections(tmp_path):
    store = RunStore(output_root=tmp_path)
    state = store.create_run(RunSpec(question="生产过程中的决策问题 零配件 拆解"))
    run_dir = store.run_dir(state.run_id)
    (run_dir / "tables.json").write_text('{"tables":[{"title":"表1","rows":[["1","10%"]]}]}', encoding="utf-8")
    tools = {tool.name: tool for tool in make_competition_tools(run_store=store, generation_service=FakeFullChainGenerationService())}

    plan = tools["plan_model"].invoke({"run_id": state.run_id, "problem_brief": {"background": state.spec.question}, "data_audit": {}, "evidence_notes": []})
    experiment = tools["run_experiment"].invoke({"run_id": state.run_id, "modeling_plan": plan["modeling_plan"], "data_files": []})
    paper = tools["draft_competition_paper"].invoke({"run_id": state.run_id, "problem_brief": {}, "data_audit": {}, "modeling_plan": plan["modeling_plan"], "experiment_result": experiment["experiment_result"], "evidence_notes": []})
    review = tools["review_submission"].invoke({"run_id": state.run_id, "paper_draft": paper["paper_draft"], "experiment_result": experiment["experiment_result"], "artifacts": []})

    assert (run_dir / "tables.json").exists()
    assert "tables.json" in (run_dir / "solve.py").read_text(encoding="utf-8")
    assert (run_dir / "paper" / "sections" / "00_abstract.md").exists()
    assert review["quality_report"]["passed"] is True
```

- [ ] **Step 2: Run test to verify it fails until previous tasks are integrated**

Run: `pytest agent_app/tests/test_b_problem_acceptance.py -q`

Expected: FAIL before integration, PASS after tasks 1-8.

- [ ] **Step 3: Run relevant suite**

Run:

```bash
python -m py_compile agent_app/config.py agent_app/llm.py agent_app/tools/competition.py agent_app/web/paper_stream.py
pytest agent_app/tests/test_model_routing.py agent_app/tests/test_problem_package.py agent_app/tests/test_deepseek_generation_service.py agent_app/tests/test_deepseek_planner_tool.py agent_app/tests/test_deepseek_programmer_tool.py agent_app/tests/test_section_paper_writer.py agent_app/tests/test_review_revise_loop.py agent_app/tests/test_b_problem_acceptance.py -q
```

Expected: PASS.

- [ ] **Step 4: Manual smoke**

Run service:

```bash
uvicorn agent_app.web.main:app --host 127.0.0.1 --port 8000
```

Upload `/Users/haobowang/Desktop/B题.pdf` through `/paper`.

Expected:

- Mimo visual reconstruction is shown only for PDF/table extraction.
- DeepSeek stages run for planning, code, writing, review.
- Paper sections appear one by one.
- Failed review does not show completed package.

- [ ] **Step 5: Commit**

```bash
git add agent_app/tests/test_b_problem_acceptance.py
git commit -m "test: add b problem generation loop acceptance"
```
