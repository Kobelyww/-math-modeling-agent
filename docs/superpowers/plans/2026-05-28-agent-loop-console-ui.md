# Agent Loop Console UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update Web and Streamlit UI so the default experience is an Agent Loop Console for DeepSeek `agent_loop`, not a fixed workflow board.

**Architecture:** Keep backend orchestration unchanged. Refactor the FastAPI static UI into a three-zone console: control rail, loop workspace, and artifact rail. Add small Streamlit helper functions so the GUI can render loop trace and artifacts consistently while keeping legacy streaming sequential mode.

**Tech Stack:** FastAPI/Jinja2 static template, vanilla JavaScript, CSS, Streamlit, pytest.

---

## File Structure

- Modify `agent_app/web/templates/index.html`: Web console layout and default strategy option.
- Modify `agent_app/web/static/style.css`: dense console styling, responsive grid, loop timeline, artifact rail.
- Modify `agent_app/web/static/app.js`: agent-loop-friendly role metadata, timeline updates, artifact button state, compatible WebSocket handling.
- Modify `agent_app/gui.py`: Streamlit console status band, loop trace rendering, artifact/build log display.
- Modify `agent_app/tests/test_agent_loop.py`: Web static UI assertions and Streamlit helper tests.

Do not change `agent_app/orchestrator.py`, `agent_app/web/routes.py`, or backend agent-loop decision behavior in this UI pass.

## Task 1: Add Failing UI Contract Tests

**Files:**
- Modify: `agent_app/tests/test_agent_loop.py`

- [ ] **Step 1: Append Web static UI tests**

Append these tests to `agent_app/tests/test_agent_loop.py`:

```python
def test_web_template_defaults_to_agent_loop_console():
    from pathlib import Path

    html = Path("agent_app/web/templates/index.html").read_text(encoding="utf-8")

    assert '<option value="agent_loop" selected>' in html
    assert 'class="console-shell"' in html
    assert 'id="loop-timeline"' in html
    assert 'id="artifact-rail"' in html


def test_web_assets_define_console_regions():
    from pathlib import Path

    css = Path("agent_app/web/static/style.css").read_text(encoding="utf-8")
    js = Path("agent_app/web/static/app.js").read_text(encoding="utf-8")

    assert ".console-shell" in css
    assert ".control-rail" in css
    assert ".loop-workspace" in css
    assert ".artifact-rail" in css
    assert "const ROLE_META" in js
    assert "function appendTimelineEvent" in js
    assert "function updateArtifactState" in js
```

- [ ] **Step 2: Run Web UI tests and verify they fail**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py::test_web_template_defaults_to_agent_loop_console agent_app/tests/test_agent_loop.py::test_web_assets_define_console_regions -v
```

Expected: FAIL because the current template has no `agent_loop` option and the CSS/JS console markers are missing.

- [ ] **Step 3: Append Streamlit helper tests**

Append these tests to `agent_app/tests/test_agent_loop.py`:

```python
def test_streamlit_agent_loop_trace_rows_are_stable():
    from agent_app.agent_loop import AgentLoopTrace
    from agent_app.gui import _agent_loop_trace_rows

    rows = _agent_loop_trace_rows([
        AgentLoopTrace(
            step=1,
            action="model",
            role="modeling",
            reason="Need formulation",
            instruction="Build variables",
            output="Long output " * 40,
        )
    ])

    assert rows == [{
        "step": 1,
        "action": "model",
        "role": "modeling",
        "reason": "Need formulation",
        "instruction": "Build variables",
        "output_preview": ("Long output " * 40)[:220] + "...",
    }]


def test_streamlit_artifact_summary_uses_build_log():
    from agent_app.gui import _artifact_summary_lines

    lines = _artifact_summary_lines("Written: solve.py\n✅ workflow_result.json")

    assert lines == ["Written: solve.py", "✅ workflow_result.json"]
    assert _artifact_summary_lines("") == []
```

- [ ] **Step 4: Run Streamlit helper tests and verify they fail**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py::test_streamlit_agent_loop_trace_rows_are_stable agent_app/tests/test_agent_loop.py::test_streamlit_artifact_summary_uses_build_log -v
```

Expected: FAIL with import errors for `_agent_loop_trace_rows` and `_artifact_summary_lines`.

- [ ] **Step 5: Commit failing tests**

Do not commit failing tests separately. Keep them unstaged until Task 2 and Task 4 make them pass.

## Task 2: Refactor Web Template and CSS Into Console Layout

**Files:**
- Modify: `agent_app/web/templates/index.html`
- Modify: `agent_app/web/static/style.css`

- [ ] **Step 1: Replace strategy selector in `index.html`**

Change the strategy selector to:

```html
<select id="strategy">
  <option value="agent_loop" selected>Agent Loop（动态对话驱动）</option>
  <option value="sequential">串行流水线</option>
  <option value="review">深度反思</option>
  <option value="parallel">快速并行</option>
</select>
```

- [ ] **Step 2: Replace main grid wrapper with console shell**

In `agent_app/web/templates/index.html`, replace the current `<div class="main-grid">...</div>` body content with this structure, preserving existing IDs used by JavaScript:

```html
<div class="console-shell">
  <aside class="control-rail">
    <div class="panel">
      <div class="panel-label">Control</div>
      <label for="strategy">协作策略</label>
      <select id="strategy">
        <option value="agent_loop" selected>Agent Loop（动态对话驱动）</option>
        <option value="sequential">串行流水线</option>
        <option value="review">深度反思</option>
        <option value="parallel">快速并行</option>
      </select>
      <label for="question">任务输入</label>
      <textarea id="question" rows="7" placeholder="例如：建立新能源车充电站布局优化模型，并给出可实现方案与论文写作框架"></textarea>
      <div class="upload-row">
        <label for="pdf-file" class="btn-secondary">上传 PDF 题目</label>
        <input type="file" id="pdf-file" accept=".pdf" onchange="onPDFSelected()" class="sr-only">
        <span id="pdf-name" class="upload-hint"></span>
      </div>
      <div id="upload-status" class="status-text"></div>
      <button id="btn-solve" onclick="startSolve()">开始协作分析</button>
      <div id="status" class="status-text">等待任务输入</div>
    </div>

    <div class="panel">
      <div class="panel-label">RAG</div>
      <div id="rag-status">{{ '已就绪' if rag_ready else '未构建' }}</div>
      <input id="rag-query" placeholder="检索论文或方法...">
      <div class="button-row">
        <button onclick="searchRAG()">检索</button>
        <button class="btn-secondary" onclick="rebuildRAG()">重建索引</button>
      </div>
      <div id="rag-results"></div>
    </div>

    <div class="panel">
      <div class="panel-label">Nature Skills</div>
      <div id="skills-list">加载中...</div>
    </div>
  </aside>

  <main class="loop-workspace">
    <section class="loop-overview">
      <div>
        <div class="panel-label">Loop Timeline</div>
        <h2>动态执行轨迹</h2>
      </div>
      <div id="run-state" class="run-state">Idle</div>
    </section>
    <div id="loop-timeline" class="loop-timeline">
      <div class="timeline-empty">协调者会根据上下文动态选择探索、建模、编程、调试、写作、评审或总结。</div>
    </div>

    <section class="agent-grid">
      <div class="agent-panel" id="panel-modeling" data-role="modeling">
        <div class="agent-header"><span>建模智能体</span><span class="spinner hidden" id="spin-modeling"></span></div>
        <div class="agent-output" id="out-modeling">等待协调者调用。</div>
        <div class="progress"><div class="progress-bar" id="bar-modeling"></div></div>
      </div>
      <div class="agent-panel" id="panel-programming" data-role="programming">
        <div class="agent-header">
          <span>编程智能体</span><span class="spinner hidden" id="spin-programming"></span>
          <span class="btn-group"><button class="btn-sm" onclick="runCode()">运行</button><button class="btn-sm" onclick="exportCode()">导出.py</button></span>
        </div>
        <div class="agent-output code-output" id="out-programming">等待协调者调用。</div>
        <div id="code-result" class="code-result hidden"></div>
        <div class="progress"><div class="progress-bar" id="bar-programming"></div></div>
      </div>
      <div class="agent-panel" id="panel-writing" data-role="writing">
        <div class="agent-header">
          <span>写作智能体</span><span class="spinner hidden" id="spin-writing"></span>
          <span class="btn-group"><button class="btn-sm" onclick="compileLatex()">编译PDF</button><button class="btn-sm" onclick="exportLatex()">导出.tex</button></span>
        </div>
        <div class="agent-output latex-output" id="out-writing">等待协调者调用。</div>
        <div id="latex-result" class="code-result hidden"></div>
        <div class="progress"><div class="progress-bar" id="bar-writing"></div></div>
      </div>
      <div class="agent-panel wide" id="panel-synthesis" data-role="synthesis">
        <div class="agent-header"><span>总控整合</span><span class="spinner hidden" id="spin-synthesis"></span></div>
        <div class="agent-output" id="out-synthesis">最终整合会在这里显示。</div>
        <div class="progress"><div class="progress-bar" id="bar-synthesis"></div></div>
      </div>
    </section>
  </main>

  <aside class="artifact-rail" id="artifact-rail">
    <div class="panel">
      <div class="panel-label">Artifacts</div>
      <button class="btn-secondary" id="btn-export-code" onclick="exportCode()" disabled>导出代码</button>
      <button class="btn-secondary" id="btn-export-latex" onclick="exportLatex()" disabled>导出 LaTeX</button>
      <button class="btn-secondary" id="btn-download-all" onclick="downloadAll()" disabled>打包下载</button>
      <div class="artifact-note">完成后可导出代码、论文和整合报告。</div>
    </div>
  </aside>
</div>
```

- [ ] **Step 3: Replace `style.css` layout styles**

In `agent_app/web/static/style.css`, replace old layout rules with console-specific rules. Keep existing code/latex output selectors but add these required class definitions:

```css
:root {
  --bg: #f6f8fa;
  --surface: #ffffff;
  --surface-muted: #f0f3f6;
  --border: #d0d7de;
  --text: #24292f;
  --text-dim: #57606a;
  --accent: #0969da;
  --green: #1a7f37;
  --orange: #9a6700;
  --red: #cf222e;
  --radius: 8px;
  --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font: 14px/1.5 var(--font); }

header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
header h1 { font-size: 18px; font-weight: 650; }
.badge { font-size: 11px; padding: 3px 8px; border-radius: 999px; background: var(--surface-muted); color: var(--accent); border: 1px solid var(--border); }

.console-shell {
  display: grid;
  grid-template-columns: minmax(250px, 280px) minmax(0, 1fr) minmax(210px, 240px);
  gap: 12px;
  padding: 12px;
  min-height: calc(100vh - 61px);
}
.control-rail,
.artifact-rail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.loop-workspace {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.panel,
.agent-panel,
.loop-overview,
.loop-timeline {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.panel { padding: 12px; }
.panel-label {
  color: var(--text-dim);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
label { display: block; color: var(--text-dim); font-size: 12px; margin: 10px 0 4px; }
select, textarea, input, button {
  width: 100%;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: 13px var(--font);
  margin-bottom: 8px;
}
textarea { resize: vertical; min-height: 120px; }
button { background: var(--accent); color: #fff; border-color: var(--accent); cursor: pointer; font-weight: 600; }
button:disabled { cursor: not-allowed; opacity: 0.45; }
.btn-secondary { background: var(--surface); color: var(--text); border: 1px solid var(--border); }
.button-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.sr-only { position: absolute; width: 1px; height: 1px; opacity: 0; overflow: hidden; }

.loop-overview {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
}
.loop-overview h2 { font-size: 17px; }
.run-state {
  color: var(--text-dim);
  border: 1px solid var(--border);
  background: var(--surface-muted);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
}
.loop-timeline {
  min-height: 76px;
  padding: 10px;
  display: flex;
  gap: 8px;
  overflow-x: auto;
}
.timeline-empty { color: var(--text-dim); padding: 14px; }
.timeline-item {
  min-width: 128px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px;
  background: var(--surface-muted);
}
.timeline-item.active { border-color: var(--accent); background: #ddf4ff; }
.timeline-role { font-weight: 700; font-size: 12px; }
.timeline-status { color: var(--text-dim); font-size: 11px; margin-top: 4px; }

.agent-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.agent-panel {
  min-height: 290px;
  display: flex;
  flex-direction: column;
}
.agent-panel.wide { grid-column: 1 / -1; min-height: 220px; }
.agent-header {
  min-height: 40px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 650;
}
.agent-output {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 420px;
}
.progress { height: 3px; background: var(--surface-muted); }
.progress-bar { height: 100%; background: var(--green); width: 0%; transition: width 0.2s; }

.artifact-note,
.status-text,
.upload-hint,
#rag-results,
#skills-list { color: var(--text-dim); font-size: 12px; }

@media (max-width: 1100px) {
  .console-shell { grid-template-columns: 1fr; }
  .agent-grid { grid-template-columns: 1fr; }
  .agent-panel.wide { grid-column: auto; }
}
```

- [ ] **Step 4: Run Web static tests**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py::test_web_template_defaults_to_agent_loop_console agent_app/tests/test_agent_loop.py::test_web_assets_define_console_regions -v
```

Expected: The template assertion should pass after `index.html`; the CSS/JS assertion may still fail until Task 3 adds JS functions.

## Task 3: Update Web JavaScript for Agent Loop Console

**Files:**
- Modify: `agent_app/web/static/app.js`

- [ ] **Step 1: Add role metadata and reset helper**

At the top of `agent_app/web/static/app.js`, replace the first three lines with:

```javascript
let ws = null, taskId = null;

const ROLE_META = {
  modeling: { label: '建模智能体', progressStart: 0.05, progressEnd: 0.3 },
  programming: { label: '编程智能体', progressStart: 0.3, progressEnd: 0.55 },
  writing: { label: '写作智能体', progressStart: 0.55, progressEnd: 0.8 },
  synthesis: { label: '总控整合', progressStart: 0.8, progressEnd: 1.0 },
};
const agents = Object.keys(ROLE_META);
const buffers = {};
agents.forEach(a => { buffers[a] = ''; });
```

Add this helper after `setProgress`:

```javascript
function resetOutputState() {
  const timeline = document.getElementById('loop-timeline');
  if (timeline) timeline.innerHTML = '';
  agents.forEach(a => {
    buffers[a] = '';
    const out = document.getElementById('out-' + a);
    if (out) out.innerHTML = '等待协调者调用。';
    setProgress(a, 0);
    showSpinner(a);
  });
  updateArtifactState();
}
```

- [ ] **Step 2: Add timeline and artifact helpers**

Add these functions after `resetOutputState`:

```javascript
function appendTimelineEvent(agent, status) {
  const timeline = document.getElementById('loop-timeline');
  if (!timeline) return;
  const empty = timeline.querySelector('.timeline-empty');
  if (empty) empty.remove();
  const item = document.createElement('div');
  item.className = 'timeline-item' + (status === 'running' ? ' active' : '');
  item.innerHTML =
    '<div class="timeline-role">' + (ROLE_META[agent]?.label || agent) + '</div>' +
    '<div class="timeline-status">' + status + '</div>';
  timeline.appendChild(item);
  timeline.scrollLeft = timeline.scrollWidth;
}

function setRunState(text, color) {
  const el = document.getElementById('run-state');
  if (!el) return;
  el.textContent = text;
  el.style.color = color || '';
}

function updateArtifactState() {
  const hasCode = Boolean(extractCodeFromOutput(buffers.programming));
  const hasLatex = Boolean(extractLatexFromOutput(buffers.writing));
  const hasAny = agents.some(a => buffers[a] && buffers[a].trim());
  const codeButton = document.getElementById('btn-export-code');
  const latexButton = document.getElementById('btn-export-latex');
  const allButton = document.getElementById('btn-download-all');
  if (codeButton) codeButton.disabled = !hasCode;
  if (latexButton) latexButton.disabled = !hasLatex;
  if (allButton) allButton.disabled = !hasAny;
}
```

- [ ] **Step 3: Use reset helper in `startSolve`**

In `startSolve`, replace the existing `agents.forEach(...)` reset block with:

```javascript
  resetOutputState();
  setRunState('Running');
```

Keep the existing `setStatus('启动中...');` call immediately after this block.

- [ ] **Step 4: Update WebSocket event handling**

In the `token` case, add timeline and artifact updates:

```javascript
        appendTimelineEvent(msg.agent, 'running');
        buffers[msg.agent] += msg.content;
        const out = document.getElementById('out-' + msg.agent);
        out.innerHTML = '<p>' + simpleMarkdown(buffers[msg.agent]) + '</p>';
        out.scrollTop = out.scrollHeight;
        const mid = (msg.progress_start + msg.progress_end) / 2 * 100;
        setProgress(msg.agent, Math.min(mid, 95));
        updateArtifactState();
```

In the `phase` completed block, add:

```javascript
          appendTimelineEvent(msg.agent, 'completed');
          updateArtifactState();
```

In the `done` case, add:

```javascript
        setRunState('Complete', 'var(--green)');
        updateArtifactState();
```

In the `error` case, add:

```javascript
        setRunState('Error', 'var(--red)');
```

- [ ] **Step 5: Run Web static tests**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py::test_web_template_defaults_to_agent_loop_console agent_app/tests/test_agent_loop.py::test_web_assets_define_console_regions -v
```

Expected: PASS.

- [ ] **Step 6: Commit Web UI changes**

Run:

```bash
git add agent_app/web/templates/index.html agent_app/web/static/style.css agent_app/web/static/app.js agent_app/tests/test_agent_loop.py
git commit -m "feat: add agent loop web console UI"
```

## Task 4: Update Streamlit GUI Console Rendering

**Files:**
- Modify: `agent_app/gui.py`
- Modify: `agent_app/tests/test_agent_loop.py`

- [ ] **Step 1: Add pure helper functions**

In `agent_app/gui.py`, add these helpers above `_display_result`:

```python
def _agent_loop_trace_rows(trace) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in trace or []:
        preview = item.output[:220] + "..." if len(item.output) > 220 else item.output
        rows.append({
            "step": item.step,
            "action": item.action,
            "role": item.role,
            "reason": item.reason,
            "instruction": item.instruction,
            "output_preview": preview,
        })
    return rows


def _artifact_summary_lines(build_log: str) -> list[str]:
    return [line.strip() for line in build_log.splitlines() if line.strip()]
```

- [ ] **Step 2: Update result display to show trace and artifacts**

In `_display_result`, after `st.success("协作完成")`, add:

```python
    trace_rows = _agent_loop_trace_rows(result.agent_loop_trace)
    if trace_rows:
        with st.expander("Agent Loop 执行轨迹", expanded=True):
            st.dataframe(trace_rows, use_container_width=True, hide_index=True)

    artifact_lines = _artifact_summary_lines(result.build_log)
    if artifact_lines:
        with st.expander("文件生成与验证", expanded=True):
            st.code("\n".join(artifact_lines))
        st.caption(f"产出目录：`{APP_ROOT / 'output'}`")
```

If an earlier uncommitted `build_log` display block already exists, merge it into this implementation and avoid duplicate expanders.

- [ ] **Step 3: Update collaboration tab status band**

In `_tab_collaboration`, replace:

```python
    st.subheader("多智能体协作分析")
```

with:

```python
    st.subheader("Agent Loop Console")
    st.caption("默认由 DeepSeek 协调者动态选择探索、建模、编程、调试、写作、评审或总结。")
```

After `use_streaming = ...`, add:

```python
    if mode == "agent_loop":
        st.info("当前为 Agent Loop：运行完成后展示动态轨迹和产物。legacy 流式输出仍保留在串行模式。")
```

- [ ] **Step 4: Run Streamlit helper tests**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py::test_streamlit_agent_loop_trace_rows_are_stable agent_app/tests/test_agent_loop.py::test_streamlit_artifact_summary_uses_build_log -v
```

Expected: PASS.

- [ ] **Step 5: Run full agent loop tests**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Streamlit changes**

Run:

```bash
git add agent_app/gui.py agent_app/tests/test_agent_loop.py
git commit -m "feat: add agent loop Streamlit console"
```

## Task 5: Final Verification

**Files:**
- No planned source changes.

- [ ] **Step 1: Run focused UI tests**

Run:

```bash
pytest agent_app/tests/test_agent_loop.py -v
```

Expected: PASS.

- [ ] **Step 2: Run broader regression tests**

Run:

```bash
pytest agent_app/tests -v
```

Expected: PASS. If failures appear, capture the exact failing tests and error messages before changing code.

- [ ] **Step 3: Run diff whitespace check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 4: Inspect workspace status**

Run:

```bash
git status --short
```

Expected: only unrelated pre-existing changes remain, such as `.superpowers/` visual companion files or earlier local edits not touched by this plan.
