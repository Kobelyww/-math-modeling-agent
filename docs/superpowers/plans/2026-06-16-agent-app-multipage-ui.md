# Agent App Multipage UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the one-page paper chat console into a multipage research workflow UI with dashboard, paper workflow, review center, artifacts, and knowledge pages.

**Architecture:** Keep FastAPI + Jinja + vanilla JavaScript. Add server-rendered page routes and read-only REST APIs for run state recovery. Split the current large single-page JavaScript into shared utilities plus page-specific modules while preserving existing paper workflow and stage review APIs.

**Tech Stack:** FastAPI, Jinja2 templates, vanilla JavaScript, CSS, pytest, node syntax checks.

---

## File Structure

**Create:**

- `agent_app/web/templates/base.html` — shared shell, navigation, header, content slots.
- `agent_app/web/templates/dashboard.html` — `/` overview page.
- `agent_app/web/templates/paper.html` — `/paper` workflow page.
- `agent_app/web/templates/reviews.html` — `/reviews` stage review center.
- `agent_app/web/templates/artifacts.html` — `/artifacts` generated deliverables page.
- `agent_app/web/templates/knowledge.html` — `/knowledge` RAG and Nature Skills page.
- `agent_app/web/static/paper.js` — paper workflow WebSocket, chat, PDF upload.
- `agent_app/web/static/reviews.js` — review loading, details, decisions.
- `agent_app/web/static/artifacts.js` — artifact loading and readiness display.
- `agent_app/web/static/knowledge.js` — RAG and skills UI.
- `agent_app/tests/test_web_pages.py` — page route and read API tests.

**Modify:**

- `agent_app/web/templates/index.html` — replace with compatibility wrapper or remove page-specific contents after `/` uses `dashboard.html`.
- `agent_app/web/routes.py` — add page routes and read-only run/review/artifact APIs.
- `agent_app/web/static/app.js` — reduce to shared state, helpers, render utilities, event reducer.
- `agent_app/web/static/style.css` — add app shell, navigation, page layouts, split-view/table styles.
- Existing tests that expect the old single-page root to contain the whole paper console.

---

### Task 1: Page Route Tests and Template Shell

**Files:**

- Create: `agent_app/tests/test_web_pages.py`
- Create: `agent_app/web/templates/base.html`
- Create: `agent_app/web/templates/dashboard.html`
- Create: `agent_app/web/templates/paper.html`
- Create: `agent_app/web/templates/reviews.html`
- Create: `agent_app/web/templates/artifacts.html`
- Create: `agent_app/web/templates/knowledge.html`
- Modify: `agent_app/web/routes.py`
- Modify: `agent_app/web/static/style.css`

- [ ] **Step 1: Write failing page route tests**

Create `agent_app/tests/test_web_pages.py` with:

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from agent_app.web.main import app


def test_multipage_routes_render_expected_pages():
    client = TestClient(app)

    expected = {
        "/": "工作台总览",
        "/paper": "论文生产",
        "/reviews": "阶段审阅",
        "/artifacts": "产物中心",
        "/knowledge": "知识库",
    }

    for path, marker in expected.items():
        response = client.get(path)
        assert response.status_code == 200
        assert marker in response.text
        assert 'href="/paper"' in response.text
        assert 'href="/reviews"' in response.text
        assert 'href="/artifacts"' in response.text
        assert 'href="/knowledge"' in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest agent_app/tests/test_web_pages.py::test_multipage_routes_render_expected_pages -q
```

Expected: FAIL because `/paper`, `/reviews`, `/artifacts`, and `/knowledge` do not exist.

- [ ] **Step 3: Add page route helper**

Modify `agent_app/web/routes.py` near the existing `index` route:

```python
def _page_context(request: Request, active_page: str) -> dict:
    return {
        "request": request,
        "active_page": active_page,
        "rag_ready": _rag.is_ready,
    }


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", _page_context(request, "dashboard"))


@router.get("/paper", response_class=HTMLResponse)
async def paper_page(request: Request):
    return templates.TemplateResponse(request, "paper.html", _page_context(request, "paper"))


@router.get("/reviews", response_class=HTMLResponse)
async def reviews_page(request: Request):
    return templates.TemplateResponse(request, "reviews.html", _page_context(request, "reviews"))


@router.get("/artifacts", response_class=HTMLResponse)
async def artifacts_page(request: Request):
    return templates.TemplateResponse(request, "artifacts.html", _page_context(request, "artifacts"))


@router.get("/knowledge", response_class=HTMLResponse)
async def knowledge_page(request: Request):
    return templates.TemplateResponse(request, "knowledge.html", _page_context(request, "knowledge"))
```

Replace the existing `index` function instead of keeping two `@router.get("/")` handlers.

- [ ] **Step 4: Add shared `base.html`**

Create `agent_app/web/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{% block title %}数模 DeepAgent 论文生产系统{% endblock %}</title>
<link rel="stylesheet" href="/static/style.css">
{% block head_extra %}{% endblock %}
</head>
<body>
<div id="app" class="app-shell">
  <header class="app-header">
    <div>
      <h1>数模 DeepAgent 论文生产系统</h1>
      <p>{% block subtitle %}Research Workflow Console{% endblock %}</p>
    </div>
    <span class="badge">DeepAgent · Stage Review</span>
  </header>

  <div class="app-frame">
    <nav class="app-nav" aria-label="主导航">
      <a class="{{ 'active' if active_page == 'dashboard' else '' }}" href="/">工作台</a>
      <a class="{{ 'active' if active_page == 'paper' else '' }}" href="/paper">论文生产</a>
      <a class="{{ 'active' if active_page == 'reviews' else '' }}" href="/reviews">阶段审阅</a>
      <a class="{{ 'active' if active_page == 'artifacts' else '' }}" href="/artifacts">产物中心</a>
      <a class="{{ 'active' if active_page == 'knowledge' else '' }}" href="/knowledge">知识库</a>
    </nav>

    <main class="page-main">
      {% block content %}{% endblock %}
    </main>
  </div>
</div>
<script src="/static/app.js"></script>
{% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 5: Add minimal page templates**

Create `agent_app/web/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}工作台总览 · 数模 DeepAgent{% endblock %}
{% block subtitle %}Dashboard{% endblock %}
{% block content %}
<section class="page-heading">
  <div>
    <div class="panel-label">Dashboard</div>
    <h2>工作台总览</h2>
  </div>
  <a class="page-action" href="/paper">新建论文任务</a>
</section>

<section class="dashboard-grid">
  <article class="summary-tile">
    <span>当前 Run</span>
    <strong id="dashboard-run-id">未选择</strong>
  </article>
  <article class="summary-tile">
    <span>待审阅</span>
    <strong id="dashboard-pending-reviews">0</strong>
  </article>
  <article class="summary-tile">
    <span>已过期</span>
    <strong id="dashboard-stale-reviews">0</strong>
  </article>
  <article class="summary-tile">
    <span>产物</span>
    <strong id="dashboard-artifacts">0</strong>
  </article>
</section>

<section class="panel">
  <div class="panel-label">Recent Runs</div>
  <div id="recent-runs" class="record-list">
    <div class="artifact-note">暂无运行记录。</div>
  </div>
</section>
{% endblock %}
```

Create `agent_app/web/templates/paper.html` by moving the paper input, chat workspace, compact stages, current review summary, and artifacts summary from the current `index.html`. Keep these DOM ids unchanged because existing JavaScript depends on them:

- `question`
- `data-files`
- `reference-files`
- `pdf-file`
- `pdf-name`
- `upload-status`
- `btn-paper`
- `status`
- `run-state`
- `chat-log`
- `followup-input`
- `btn-followup`
- `stage-list`
- `stage-review-list`
- `artifact-list`
- `btn-download-all`

Create `agent_app/web/templates/reviews.html`:

```html
{% extends "base.html" %}
{% block title %}阶段审阅 · 数模 DeepAgent{% endblock %}
{% block subtitle %}Review Center{% endblock %}
{% block content %}
<section class="page-heading">
  <div>
    <div class="panel-label">Review Center</div>
    <h2>阶段审阅</h2>
  </div>
  <div id="review-page-status" class="run-state">等待选择 Run</div>
</section>

<section class="split-workspace">
  <aside class="panel">
    <div class="panel-label">Review Queue</div>
    <div id="review-list" class="record-list"></div>
  </aside>
  <section class="panel review-detail">
    <div class="panel-label">Selected Output</div>
    <div id="review-detail">
      <div class="artifact-note">请选择一个阶段产物。</div>
    </div>
  </section>
</section>
{% endblock %}
{% block scripts %}
<script src="/static/reviews.js"></script>
{% endblock %}
```

Create `agent_app/web/templates/artifacts.html`:

```html
{% extends "base.html" %}
{% block title %}产物中心 · 数模 DeepAgent{% endblock %}
{% block subtitle %}Artifacts{% endblock %}
{% block content %}
<section class="page-heading">
  <div>
    <div class="panel-label">Artifacts</div>
    <h2>产物中心</h2>
  </div>
  <div id="artifact-page-status" class="run-state">等待选择 Run</div>
</section>

<section class="panel">
  <div class="panel-label">Submission Readiness</div>
  <div id="artifact-readiness" class="readiness-grid"></div>
</section>

<section class="panel">
  <div class="panel-label">Generated Files</div>
  <div id="artifact-table" class="record-list"></div>
</section>
{% endblock %}
{% block scripts %}
<script src="/static/artifacts.js"></script>
{% endblock %}
```

Create `agent_app/web/templates/knowledge.html` by moving the RAG and Nature Skills panels from the current root page. Keep these DOM ids:

- `rag-status`
- `rag-query`
- `rag-results`
- `skills-list`

Include:

```html
{% block scripts %}
<script src="/static/knowledge.js"></script>
{% endblock %}
```

- [ ] **Step 6: Add layout CSS**

Append to `agent_app/web/static/style.css`:

```css
.app-shell {
  min-height: 100vh;
}

.app-frame {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  min-height: calc(100vh - 65px);
}

.app-nav {
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.app-nav a {
  color: var(--text);
  text-decoration: none;
  border-radius: 6px;
  padding: 8px 10px;
  font-weight: 600;
}

.app-nav a.active,
.app-nav a:hover {
  background: var(--surface-muted);
  color: var(--accent);
}

.page-main {
  min-width: 0;
  padding: 14px;
}

.page-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.page-heading h2 {
  font-size: 18px;
}

.page-action {
  color: #fff;
  background: var(--accent);
  border-radius: 6px;
  padding: 8px 12px;
  text-decoration: none;
  font-weight: 700;
}

.dashboard-grid,
.readiness-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.summary-tile {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
}

.summary-tile span,
.summary-tile strong {
  display: block;
}

.summary-tile span {
  color: var(--text-dim);
  font-size: 12px;
}

.summary-tile strong {
  margin-top: 6px;
  font-size: 18px;
}

.split-workspace {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 12px;
}

.record-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.record-row {
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-muted);
  padding: 9px;
}

@media (max-width: 900px) {
  .app-frame,
  .console-shell,
  .paper-shell,
  .split-workspace {
    grid-template-columns: 1fr;
  }

  .app-nav {
    border-right: 0;
    border-bottom: 1px solid var(--border);
    flex-direction: row;
    overflow-x: auto;
  }

  .dashboard-grid,
  .readiness-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
```

- [ ] **Step 7: Run page route tests**

Run:

```bash
pytest agent_app/tests/test_web_pages.py::test_multipage_routes_render_expected_pages -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add agent_app/tests/test_web_pages.py agent_app/web/templates/base.html agent_app/web/templates/dashboard.html agent_app/web/templates/paper.html agent_app/web/templates/reviews.html agent_app/web/templates/artifacts.html agent_app/web/templates/knowledge.html agent_app/web/routes.py agent_app/web/static/style.css
git commit -m "feat: add multipage web shell"
```

---

### Task 2: Read-Only Run State APIs

**Files:**

- Modify: `agent_app/web/routes.py`
- Modify: `agent_app/tests/test_web_pages.py`

- [ ] **Step 1: Add failing API tests**

Append to `agent_app/tests/test_web_pages.py`:

```python
from pathlib import Path

from agent_app.domain.models import ArtifactRef, RunSpec, RunStatus
from agent_app.services.run_store import RunStore
from agent_app.services.stage_review_service import StageReviewService
from agent_app.web import routes


def test_run_read_apis_return_run_reviews_and_artifacts(tmp_path, monkeypatch):
    run_store = RunStore(tmp_path / "runs")
    state = run_store.create_run(RunSpec(question="建立交通流预测模型"))
    state.status = RunStatus.PARTIAL
    state.artifacts = [ArtifactRef(name="paper.tex", path=Path("paper.tex"), kind="latex")]
    run_store.save_state(state)
    StageReviewService(run_store).create_review(
        run_id=state.run_id,
        stage="understand_problem",
        stage_label="理解赛题",
        status="awaiting_user",
        summary="问题理解待确认。",
        review_payload={"objectives": ["预测交通流"]},
        input_payload={"question": state.spec.question},
    )
    monkeypatch.setattr(routes, "_paper_run_store", run_store)
    client = TestClient(app)

    runs = client.get("/api/runs")
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["run_id"] == state.run_id
    assert runs.json()["runs"][0]["pending_review_count"] == 1

    run_detail = client.get(f"/api/runs/{state.run_id}")
    assert run_detail.status_code == 200
    assert run_detail.json()["run"]["run_id"] == state.run_id

    reviews = client.get(f"/api/runs/{state.run_id}/stage-reviews")
    assert reviews.status_code == 200
    assert reviews.json()["reviews"][0]["stage"] == "understand_problem"

    artifacts = client.get(f"/api/runs/{state.run_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["artifacts"][0]["name"] == "paper.tex"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest agent_app/tests/test_web_pages.py::test_run_read_apis_return_run_reviews_and_artifacts -q
```

Expected: FAIL because the new API routes do not exist.

- [ ] **Step 3: Implement helpers in `routes.py`**

Add imports:

```python
from ..domain.serialization import to_json_dict
```

Add helper functions:

```python
def _list_run_ids() -> list[str]:
    if not _paper_run_store.output_root.exists():
        return []
    return sorted(
        [path.name for path in _paper_run_store.output_root.iterdir() if path.is_dir() and path.name.startswith("run_")],
        reverse=True,
    )


def _review_counts(run_id: str) -> dict[str, int]:
    reviews = StageReviewService(_paper_run_store).list_reviews(run_id)
    return {
        "pending_review_count": sum(1 for review in reviews if review.status == "awaiting_user"),
        "stale_review_count": sum(1 for review in reviews if review.status == "stale"),
    }


def _run_summary(run_id: str) -> dict:
    state = _paper_run_store.load_state(run_id)
    counts = _review_counts(run_id)
    return {
        "run_id": state.run_id,
        "status": state.status.value,
        "stage": state.stage.value,
        "summary": "",
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "artifact_count": len(state.artifacts),
        **counts,
    }
```

- [ ] **Step 4: Add read-only routes**

Add after the page routes:

```python
@router.get("/api/runs")
async def list_paper_runs():
    return {"runs": [_run_summary(run_id) for run_id in _list_run_ids()]}


@router.get("/api/runs/{run_id}")
async def get_paper_run(run_id: str):
    try:
        state = _paper_run_store.load_state(run_id)
    except FileNotFoundError:
        return JSONResponse({"error": "run not found"}, status_code=404)
    return {
        "run": to_json_dict(state),
        "summary": _run_summary(run_id),
    }


@router.get("/api/runs/{run_id}/stage-reviews")
async def list_stage_reviews(run_id: str):
    try:
        reviews = StageReviewService(_paper_run_store).list_reviews(run_id)
    except FileNotFoundError:
        return JSONResponse({"error": "run not found"}, status_code=404)
    return {"reviews": [review.to_event("stage_review_updated") for review in reviews]}


@router.get("/api/runs/{run_id}/artifacts")
async def list_run_artifacts(run_id: str):
    try:
        state = _paper_run_store.load_state(run_id)
    except FileNotFoundError:
        return JSONResponse({"error": "run not found"}, status_code=404)
    return {"artifacts": [to_json_dict(artifact) for artifact in state.artifacts]}
```

- [ ] **Step 5: Run API tests**

Run:

```bash
pytest agent_app/tests/test_web_pages.py::test_run_read_apis_return_run_reviews_and_artifacts -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agent_app/web/routes.py agent_app/tests/test_web_pages.py
git commit -m "feat: add run state read APIs"
```

---

### Task 3: Shared JavaScript Utilities

**Files:**

- Modify: `agent_app/web/static/app.js`
- Create: `agent_app/web/static/knowledge.js`
- Modify: `agent_app/web/templates/knowledge.html`

- [ ] **Step 1: Write syntax baseline command**

Run:

```bash
node --check agent_app/web/static/app.js
```

Expected: PASS before refactor.

- [ ] **Step 2: Reduce `app.js` to safe shared helpers**

Keep these functions in `agent_app/web/static/app.js` and make every DOM access null-safe:

```javascript
function getCurrentRunId() {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get('run_id');
  if (fromUrl) {
    localStorage.setItem('currentRunId', fromUrl);
    return fromUrl;
  }
  return localStorage.getItem('currentRunId') || '';
}

function setCurrentRunId(runId) {
  if (!runId) return;
  localStorage.setItem('currentRunId', runId);
  document.querySelectorAll('[data-current-run-id]').forEach(el => {
    el.textContent = runId;
  });
}

function preserveRunUrl(path) {
  const runId = getCurrentRunId();
  return runId ? path + '?run_id=' + encodeURIComponent(runId) : path;
}

function escapeHTML(text) {
  return String(text || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function classToken(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'unknown';
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function setStatus(id, msg, color) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.style.color = color || '';
}

async function fetchJSON(url, options) {
  const response = await fetch(url, options || {});
  const payload = await response.json();
  if (!response.ok || payload.error) {
    throw new Error(payload.error || 'HTTP ' + response.status);
  }
  return payload;
}
```

Move RAG and skills functions out to `knowledge.js`.

- [ ] **Step 3: Create `knowledge.js`**

Create `agent_app/web/static/knowledge.js`:

```javascript
async function searchRAG() {
  const q = document.getElementById('rag-query')?.value.trim();
  if (!q) return;
  try {
    const data = await fetchJSON('/api/rag/query?q=' + encodeURIComponent(q));
    const el = document.getElementById('rag-results');
    if (!el) return;
    if (!data.chunks.length) {
      el.innerHTML = '无匹配结果';
      return;
    }
    el.innerHTML = data.chunks.map((c, i) =>
      '<div class="record-row"><strong>' + (i + 1) + '. ' + escapeHTML(c.source) + '</strong><br>' +
      escapeHTML(c.content) + '</div>'
    ).join('');
  } catch (error) {
    setStatus('rag-results', '检索失败：' + error.message, 'var(--red)');
  }
}

async function rebuildRAG() {
  try {
    const data = await fetchJSON('/api/rag/rebuild', { method: 'POST' });
    setText('rag-status', '已就绪 · ' + data.files + ' 文件, ' + data.chunks + ' 片段');
  } catch (error) {
    setStatus('rag-status', '重建失败：' + error.message, 'var(--red)');
  }
}

async function loadSkills() {
  const el = document.getElementById('skills-list');
  if (!el) return;
  try {
    const data = await fetchJSON('/api/skills');
    el.innerHTML =
      '<div class="record-row"><strong>Rules</strong><br>' + escapeHTML(data.rules.join(', ')) + '</div>' +
      '<div class="record-row"><strong>Templates</strong><br>' + data.viz_templates.length + ' 个可视化模板</div>' +
      '<div class="record-row"><strong>Tools</strong><br>' + escapeHTML(data.tools.join(', ')) + '</div>';
  } catch (error) {
    el.textContent = '加载失败：' + error.message;
  }
}

document.addEventListener('DOMContentLoaded', loadSkills);
```

- [ ] **Step 4: Run JS checks**

Run:

```bash
node --check agent_app/web/static/app.js
node --check agent_app/web/static/knowledge.js
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/web/static/app.js agent_app/web/static/knowledge.js agent_app/web/templates/knowledge.html
git commit -m "refactor: split shared and knowledge frontend scripts"
```

---

### Task 4: Paper Workflow Page Script

**Files:**

- Create: `agent_app/web/static/paper.js`
- Modify: `agent_app/web/templates/paper.html`
- Modify: `agent_app/web/static/app.js`

- [ ] **Step 1: Move paper workflow functions to `paper.js`**

Create `agent_app/web/static/paper.js` containing the existing paper workflow functions from the old `app.js`:

- `simpleMarkdown`
- `parsePathLines`
- `clearChat`
- `appendChat`
- `appendEvent`
- `renderStages`
- `updateStage`
- `renderArtifacts`
- `addArtifact`
- `addStageReview`
- `markStageReviewInvalidated`
- `renderStageReviews`
- `startPaperRun`
- `sendFollowup`
- `startPaperTask`
- `connectPaperWS`
- `submitStageReviewDecision`
- `handlePaperEvent`
- `downloadAll`
- `downloadBlob`
- `onPDFSelected`

At the top of `paper.js`, initialize page-local arrays:

```javascript
let paperWs = null;
let paperTaskId = null;
let chatMessages = [];
let artifactRecords = [];
let stageReviewRecords = [];
let currentRunId = getCurrentRunId();
```

Use shared `escapeHTML`, `classToken`, `setCurrentRunId`, and `fetchJSON` from `app.js`.

- [ ] **Step 2: Add `paper.js` to template**

In `paper.html`, include:

```html
{% block scripts %}
<script src="/static/paper.js"></script>
{% endblock %}
```

- [ ] **Step 3: Ensure `app.js` no longer auto-loads paper-only behavior**

Remove direct calls such as:

```javascript
loadSkills();
renderStages(stageStatus);
```

from shared `app.js`. These belong in page-specific scripts.

- [ ] **Step 4: Run JS checks**

Run:

```bash
node --check agent_app/web/static/app.js
node --check agent_app/web/static/paper.js
```

Expected: PASS.

- [ ] **Step 5: Run paper stream tests**

Run:

```bash
pytest agent_app/tests/test_paper_chat_stream.py agent_app/tests/test_web_stage_reviews.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agent_app/web/static/app.js agent_app/web/static/paper.js agent_app/web/templates/paper.html agent_app/tests/test_paper_chat_stream.py agent_app/tests/test_web_stage_reviews.py
git commit -m "refactor: move paper workflow frontend script"
```

---

### Task 5: Review Center Page

**Files:**

- Create: `agent_app/web/static/reviews.js`
- Modify: `agent_app/web/templates/reviews.html`
- Modify: `agent_app/tests/test_web_pages.py`

- [ ] **Step 1: Add review API rendering test**

Append to `agent_app/tests/test_web_pages.py`:

```python
def test_reviews_page_has_review_center_mount_points():
    client = TestClient(app)

    response = client.get("/reviews")

    assert response.status_code == 200
    assert 'id="review-list"' in response.text
    assert 'id="review-detail"' in response.text
    assert '/static/reviews.js' in response.text
```

- [ ] **Step 2: Run test**

Run:

```bash
pytest agent_app/tests/test_web_pages.py::test_reviews_page_has_review_center_mount_points -q
```

Expected: PASS after Task 1 templates exist.

- [ ] **Step 3: Implement `reviews.js`**

Create `agent_app/web/static/reviews.js`:

```javascript
let reviews = [];
let selectedReviewId = '';

async function loadReviewsPage() {
  const runId = getCurrentRunId();
  const list = document.getElementById('review-list');
  if (!runId) {
    if (list) list.innerHTML = '<div class="artifact-note">请先在论文生产页创建或选择 Run。</div>';
    return;
  }
  setStatus('review-page-status', '加载 ' + runId);
  try {
    const data = await fetchJSON('/api/runs/' + encodeURIComponent(runId) + '/stage-reviews');
    reviews = data.reviews || [];
    renderReviewList();
    if (reviews.length) selectReview(reviews[0].output_id);
    setStatus('review-page-status', runId, 'var(--green)');
  } catch (error) {
    setStatus('review-page-status', '加载失败：' + error.message, 'var(--red)');
  }
}

function renderReviewList() {
  const list = document.getElementById('review-list');
  if (!list) return;
  if (!reviews.length) {
    list.innerHTML = '<div class="artifact-note">暂无阶段审阅记录。</div>';
    return;
  }
  list.innerHTML = reviews.map(review =>
    '<button type="button" class="record-row review-row ' + classToken(review.status) + '" onclick="selectReview(\\'' + escapeHTML(review.output_id) + '\\')">' +
    '<strong>' + escapeHTML(review.stage_label || review.stage) + '</strong>' +
    '<span>v' + escapeHTML(review.version) + ' · ' + escapeHTML(review.status) + '</span>' +
    '</button>'
  ).join('');
}

function selectReview(outputId) {
  selectedReviewId = outputId;
  const review = reviews.find(item => item.output_id === outputId);
  const detail = document.getElementById('review-detail');
  if (!detail || !review) return;
  const payload = review.review_payload || {};
  const fields = Object.keys(payload).map(key =>
    '<dt>' + escapeHTML(key) + '</dt><dd>' + escapeHTML(JSON.stringify(payload[key])) + '</dd>'
  ).join('');
  const actions = review.status === 'awaiting_user'
    ? '<textarea id="review-instruction" rows="4" placeholder="填写修改意见，或直接确认继续"></textarea>' +
      '<div class="button-row">' +
      '<button onclick="submitReviewDecision(\\'' + escapeHTML(review.output_id) + '\\', \\'approve\\')">确认继续</button>' +
      '<button class="btn-secondary" onclick="submitReviewDecision(\\'' + escapeHTML(review.output_id) + '\\', \\'revise\\')">要求重写</button>' +
      '</div>' +
      '<button class="btn-secondary" onclick="submitReviewDecision(\\'' + escapeHTML(review.output_id) + '\\', \\'stop\\')">停止在此</button>'
    : '<div class="artifact-note">该版本为只读状态。</div>';
  detail.innerHTML =
    '<h3>' + escapeHTML(review.stage_label || review.stage) + ' · v' + escapeHTML(review.version) + '</h3>' +
    '<p>' + escapeHTML(review.summary || '') + '</p>' +
    '<div class="status-pill ' + classToken(review.status) + '">' + escapeHTML(review.status) + '</div>' +
    '<dl>' + fields + '</dl>' +
    actions;
}

async function submitReviewDecision(outputId, action) {
  const runId = getCurrentRunId();
  const instruction = document.getElementById('review-instruction')?.value.trim() || '';
  try {
    const data = await fetchJSON('/api/runs/' + encodeURIComponent(runId) + '/stage-reviews/' + encodeURIComponent(outputId) + '/' + action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruction }),
    });
    if (data.review) mergeReview(data.review);
    (data.invalidated_events || []).forEach(mergeReview);
    (data.resume_events || []).forEach(event => {
      if (event.type === 'stage_review_created' || event.type === 'stage_review_updated') mergeReview(event);
      if (event.run_id) setCurrentRunId(event.run_id);
    });
    renderReviewList();
    selectReview((data.review && data.review.output_id) || outputId);
  } catch (error) {
    setStatus('review-page-status', '决策失败：' + error.message, 'var(--red)');
  }
}

function mergeReview(event) {
  const index = reviews.findIndex(item => item.output_id === event.output_id);
  if (index >= 0) {
    reviews[index] = { ...reviews[index], ...event };
  } else if (event.output_id) {
    reviews.push(event);
  }
}

document.addEventListener('DOMContentLoaded', loadReviewsPage);
```

- [ ] **Step 4: Run JS and tests**

Run:

```bash
node --check agent_app/web/static/reviews.js
pytest agent_app/tests/test_web_pages.py agent_app/tests/test_web_stage_reviews.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/web/static/reviews.js agent_app/web/templates/reviews.html agent_app/tests/test_web_pages.py
git commit -m "feat: add stage review center page"
```

---

### Task 6: Artifacts Page

**Files:**

- Create: `agent_app/web/static/artifacts.js`
- Modify: `agent_app/web/templates/artifacts.html`
- Modify: `agent_app/tests/test_web_pages.py`

- [ ] **Step 1: Add artifacts page mount test**

Append to `agent_app/tests/test_web_pages.py`:

```python
def test_artifacts_page_has_artifact_mount_points():
    client = TestClient(app)

    response = client.get("/artifacts")

    assert response.status_code == 200
    assert 'id="artifact-readiness"' in response.text
    assert 'id="artifact-table"' in response.text
    assert '/static/artifacts.js' in response.text
```

- [ ] **Step 2: Implement `artifacts.js`**

Create `agent_app/web/static/artifacts.js`:

```javascript
const CORE_ARTIFACTS = [
  { key: 'paper.tex', label: '论文 LaTeX' },
  { key: 'solve.py', label: '求解代码' },
  { key: 'modeling_report.md', label: '建模报告' },
  { key: 'final_synthesis.md', label: '最终综合' },
];

async function loadArtifactsPage() {
  const runId = getCurrentRunId();
  if (!runId) {
    setStatus('artifact-page-status', '请先选择 Run', 'var(--orange)');
    return;
  }
  try {
    const data = await fetchJSON('/api/runs/' + encodeURIComponent(runId) + '/artifacts');
    const artifacts = data.artifacts || [];
    renderReadiness(artifacts);
    renderArtifactsTable(artifacts);
    setStatus('artifact-page-status', runId, 'var(--green)');
  } catch (error) {
    setStatus('artifact-page-status', '加载失败：' + error.message, 'var(--red)');
  }
}

function renderReadiness(artifacts) {
  const el = document.getElementById('artifact-readiness');
  if (!el) return;
  const names = new Set(artifacts.map(item => String(item.path || item.name)));
  el.innerHTML = CORE_ARTIFACTS.map(item => {
    const ready = Array.from(names).some(name => name.endsWith(item.key));
    return '<article class="summary-tile ' + (ready ? 'completed' : 'partial') + '">' +
      '<span>' + escapeHTML(item.label) + '</span>' +
      '<strong>' + (ready ? '已生成' : '缺失') + '</strong>' +
      '</article>';
  }).join('');
}

function renderArtifactsTable(artifacts) {
  const el = document.getElementById('artifact-table');
  if (!el) return;
  if (!artifacts.length) {
    el.innerHTML = '<div class="artifact-note">暂无产物。</div>';
    return;
  }
  el.innerHTML = artifacts.map(item =>
    '<div class="record-row">' +
    '<strong>' + escapeHTML(item.name || 'artifact') + '</strong>' +
    '<span>' + escapeHTML(item.kind || 'file') + '</span>' +
    '<small>' + escapeHTML(item.path || '') + '</small>' +
    '</div>'
  ).join('');
}

document.addEventListener('DOMContentLoaded', loadArtifactsPage);
```

- [ ] **Step 3: Run JS and tests**

Run:

```bash
node --check agent_app/web/static/artifacts.js
pytest agent_app/tests/test_web_pages.py::test_artifacts_page_has_artifact_mount_points -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add agent_app/web/static/artifacts.js agent_app/web/templates/artifacts.html agent_app/tests/test_web_pages.py
git commit -m "feat: add artifacts page"
```

---

### Task 7: Dashboard Run Recovery

**Files:**

- Modify: `agent_app/web/static/app.js`
- Create or modify: `agent_app/web/static/dashboard.js`
- Modify: `agent_app/web/templates/dashboard.html`
- Modify: `agent_app/tests/test_web_pages.py`

- [ ] **Step 1: Add dashboard script mount test**

Append to `agent_app/tests/test_web_pages.py`:

```python
def test_dashboard_includes_recent_run_mount_points():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert 'id="recent-runs"' in response.text
    assert '/static/dashboard.js' in response.text
```

- [ ] **Step 2: Create `dashboard.js`**

Create `agent_app/web/static/dashboard.js`:

```javascript
async function loadDashboard() {
  try {
    const data = await fetchJSON('/api/runs');
    const runs = data.runs || [];
    renderRecentRuns(runs);
    const current = getCurrentRunId();
    const selected = runs.find(run => run.run_id === current) || runs[0];
    if (selected) {
      setCurrentRunId(selected.run_id);
      setText('dashboard-run-id', selected.run_id);
      setText('dashboard-pending-reviews', selected.pending_review_count);
      setText('dashboard-stale-reviews', selected.stale_review_count);
      setText('dashboard-artifacts', selected.artifact_count);
    }
  } catch (error) {
    const el = document.getElementById('recent-runs');
    if (el) el.innerHTML = '<div class="artifact-note">加载运行记录失败：' + escapeHTML(error.message) + '</div>';
  }
}

function renderRecentRuns(runs) {
  const el = document.getElementById('recent-runs');
  if (!el) return;
  if (!runs.length) {
    el.innerHTML = '<div class="artifact-note">暂无运行记录。</div>';
    return;
  }
  el.innerHTML = runs.map(run =>
    '<a class="record-row" href="/paper?run_id=' + encodeURIComponent(run.run_id) + '">' +
    '<strong>' + escapeHTML(run.run_id) + '</strong>' +
    '<span>' + escapeHTML(run.status) + ' · ' + escapeHTML(run.stage) + '</span>' +
    '<small>待审阅 ' + run.pending_review_count + ' · 产物 ' + run.artifact_count + '</small>' +
    '</a>'
  ).join('');
}

document.addEventListener('DOMContentLoaded', loadDashboard);
```

- [ ] **Step 3: Add script to dashboard template**

Add to `dashboard.html`:

```html
{% block scripts %}
<script src="/static/dashboard.js"></script>
{% endblock %}
```

- [ ] **Step 4: Run JS and tests**

Run:

```bash
node --check agent_app/web/static/dashboard.js
pytest agent_app/tests/test_web_pages.py::test_dashboard_includes_recent_run_mount_points -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/web/static/dashboard.js agent_app/web/templates/dashboard.html agent_app/tests/test_web_pages.py
git commit -m "feat: add dashboard run recovery"
```

---

### Task 8: Full Verification and Browser Inspection

**Files:**

- Modify only files needed to fix verification failures.

- [ ] **Step 1: Run backend tests**

Run:

```bash
pytest agent_app/tests/test_web_pages.py agent_app/tests/test_paper_chat_stream.py agent_app/tests/test_web_stage_reviews.py agent_app/tests/test_stage_review_service.py agent_app/tests/test_stage_review_pause_runner.py agent_app/tests/test_stage_decision_service.py -q
```

Expected: PASS.

- [ ] **Step 2: Run JavaScript syntax checks**

Run:

```bash
node --check agent_app/web/static/app.js
node --check agent_app/web/static/dashboard.js
node --check agent_app/web/static/paper.js
node --check agent_app/web/static/reviews.js
node --check agent_app/web/static/artifacts.js
node --check agent_app/web/static/knowledge.js
```

Expected: PASS.

- [ ] **Step 3: Start service**

Run:

```bash
uvicorn agent_app.web.main:app --host 127.0.0.1 --port 8001
```

Expected: service starts and serves:

- `http://127.0.0.1:8001/`
- `http://127.0.0.1:8001/paper`
- `http://127.0.0.1:8001/reviews`
- `http://127.0.0.1:8001/artifacts`
- `http://127.0.0.1:8001/knowledge`

- [ ] **Step 4: Browser verification**

Use browser QA or screenshots to inspect:

- Desktop width around 1440px.
- Mobile width around 390px.

Verify:

- Navigation is visible.
- Pages do not overlap.
- Text fits inside controls.
- Paper page can open without JavaScript console errors.
- Reviews, Artifacts, and Knowledge pages show clear empty states when no run is selected.

- [ ] **Step 5: Final commit**

If Task 8 required fixes:

```bash
git add agent_app
git commit -m "fix: polish multipage ui verification"
```

If no fixes were needed, no commit is required for Task 8.

---

## Self-Review

Spec coverage:

- Multipage routes are covered by Task 1.
- Read-only state recovery APIs are covered by Task 2.
- JavaScript split is covered by Tasks 3 through 7.
- Review Center behavior is covered by Task 5.
- Artifacts behavior is covered by Task 6.
- Knowledge behavior is covered by Task 3.
- Dashboard behavior is covered by Task 7.
- Verification and responsive inspection are covered by Task 8.

Placeholder scan:

- The plan contains no TODO or TBD placeholders.
- Each implementation task includes exact files, code, commands, and expected results.

Type consistency:

- Run APIs return `runs`, `run`, `summary`, `reviews`, and `artifacts`.
- Frontend functions use `getCurrentRunId`, `setCurrentRunId`, `fetchJSON`, `escapeHTML`, and `setStatus` consistently.
