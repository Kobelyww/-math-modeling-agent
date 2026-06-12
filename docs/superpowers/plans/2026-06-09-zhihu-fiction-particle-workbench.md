# Zhihu Fiction Particle Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle `zhihu_fiction` into a dark content-production workbench with a subtle native particle network background and targeted workspace UX fixes.

**Architecture:** Keep the current single-file Alpine page and add a small native canvas particle system plus scoped CSS utility classes. The backend/API surface remains unchanged; all changes are frontend presentation, client-side error state, and smoke verification.

**Tech Stack:** HTML, CSS, Tailwind CDN utilities, Alpine.js, native Canvas 2D, FastAPI local server, pytest, Playwright.

---

## File Structure

- Modify `zhihu_fiction/static/index.html`
  - Add app shell and particle canvas.
  - Add dark workbench CSS variables/classes.
  - Initialize native particle network from Alpine `init()`.
  - Update visual classes for header, nav, panels, forms, buttons, lists, and status chips.
  - Add workspace error state and small workspace UX fixes.
- Create `zhihu_fiction/tests/test_static_particle_workbench.py`
  - Static checks for required markup, CSS hooks, JS function, reduced motion handling, accessibility hooks, and button gating markers.
- No backend files change.
- No new frontend dependency files.

---

## Task 1: Add Particle Workbench Shell

**Files:**
- Modify: `zhihu_fiction/static/index.html`
- Create: `zhihu_fiction/tests/test_static_particle_workbench.py`

- [ ] **Step 1: Write failing static test for shell and particle hooks**

Create `zhihu_fiction/tests/test_static_particle_workbench.py`:

```python
from pathlib import Path


STATIC_INDEX = Path(__file__).resolve().parents[1] / "static" / "index.html"


def _html() -> str:
    return STATIC_INDEX.read_text(encoding="utf-8")


def test_particle_workbench_shell_markers_exist():
    html = _html()

    assert 'class="app-shell' in html
    assert 'id="particleNetwork"' in html
    assert 'class="particle-canvas"' in html
    assert 'aria-hidden="true"' in html
    assert "function initParticleNetwork()" in html
    assert "prefers-reduced-motion: reduce" in html
    assert "requestAnimationFrame" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_static_particle_workbench.py::test_particle_workbench_shell_markers_exist -q
```

Expected:

```text
FAILED ... assert 'class="app-shell' in html
```

- [ ] **Step 3: Add shell markup and dark workbench CSS**

In `zhihu_fiction/static/index.html`, replace:

```html
<body class="bg-gray-50 min-h-screen" x-data="app()" x-init="init()">
```

with:

```html
<body class="app-shell min-h-screen" x-data="app()" x-init="init()">
<canvas id="particleNetwork" class="particle-canvas" aria-hidden="true"></canvas>
<div class="app-content">
```

Before `</body>`, close the wrapper:

```html
</div>
```

Add these CSS rules inside the existing `<style>` block:

```css
  :root {
    --bg-0: #0b1117;
    --bg-1: #111a22;
    --surface: rgba(15, 23, 31, 0.82);
    --surface-strong: rgba(18, 27, 37, 0.94);
    --surface-muted: rgba(148, 163, 184, 0.08);
    --border-soft: rgba(148, 163, 184, 0.18);
    --text-main: #e5edf5;
    --text-muted: #93a4b8;
    --accent: #2dd4bf;
    --accent-cyan: #67e8f9;
    --danger: #fb7185;
    --warning: #fbbf24;
  }
  [x-cloak] { display: none !important; }
  .app-shell {
    position: relative;
    min-height: 100vh;
    background:
      radial-gradient(circle at 12% 8%, rgba(45, 212, 191, 0.16), transparent 24%),
      radial-gradient(circle at 86% 2%, rgba(103, 232, 249, 0.1), transparent 26%),
      linear-gradient(145deg, var(--bg-0), var(--bg-1) 56%, #0d1218);
    color: var(--text-main);
  }
  .particle-canvas {
    position: fixed;
    inset: 0;
    z-index: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }
  .app-content {
    position: relative;
    z-index: 1;
    min-height: 100vh;
  }
  .surface {
    background: var(--surface);
    border: 1px solid var(--border-soft);
    box-shadow: 0 18px 54px rgba(0, 0, 0, 0.24);
    backdrop-filter: blur(14px);
  }
  .surface-strong {
    background: var(--surface-strong);
    border: 1px solid var(--border-soft);
    box-shadow: 0 18px 54px rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(14px);
  }
  .surface-muted {
    background: var(--surface-muted);
    border: 1px solid var(--border-soft);
  }
  .tab-active {
    border-bottom: 2px solid var(--accent-cyan);
    color: var(--accent-cyan);
  }
  .nav-tab {
    color: var(--text-muted);
  }
  .nav-tab:hover {
    color: var(--text-main);
  }
  .status-chip {
    display: inline-flex;
    align-items: center;
    min-height: 1.375rem;
    border-radius: 999px;
    border: 1px solid var(--border-soft);
    background: rgba(148, 163, 184, 0.12);
    color: #cbd5e1;
  }
  .form-control {
    background: rgba(2, 6, 12, 0.42);
    border: 1px solid rgba(148, 163, 184, 0.22);
    color: var(--text-main);
  }
  .form-control::placeholder {
    color: #64748b;
  }
  .form-control:focus {
    outline: none;
    border-color: rgba(103, 232, 249, 0.72);
    box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.16);
  }
  @media (prefers-reduced-motion: reduce) {
    .progress-bar {
      transition: none;
    }
  }
```

Remove the older `.tab-active` rule so the new one is not overridden:

```css
  .tab-active { border-bottom: 2px solid #6366f1; color: #6366f1; }
```

- [ ] **Step 4: Add particle initializer**

In the Alpine `init()` method, after `this.loadScheduler();`, add:

```javascript
      initParticleNetwork();
```

Before `function app()`, add:

```javascript
function initParticleNetwork() {
  const canvas = document.getElementById('particleNetwork');
  if (!canvas) return;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  let width = 0;
  let height = 0;
  let particles = [];
  let animationId = null;
  const particleCount = 42;

  function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * window.devicePixelRatio);
    canvas.height = Math.floor(height * window.devicePixelRatio);
    ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
    particles = Array.from({ length: particleCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.22,
      vy: (Math.random() - 0.5) * 0.22,
      r: 1 + Math.random() * 1.8,
      a: 0.24 + Math.random() * 0.38,
    }));
    draw();
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);
    for (let i = 0; i < particles.length; i += 1) {
      const a = particles[i];
      for (let j = i + 1; j < particles.length; j += 1) {
        const b = particles[j];
        const distance = Math.hypot(a.x - b.x, a.y - b.y);
        if (distance < 128) {
          ctx.strokeStyle = `rgba(45, 212, 191, ${(1 - distance / 128) * 0.13})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }
    for (const p of particles) {
      ctx.fillStyle = `rgba(103, 232, 249, ${p.a})`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function tick() {
    for (const p of particles) {
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < -10) p.x = width + 10;
      if (p.x > width + 10) p.x = -10;
      if (p.y < -10) p.y = height + 10;
      if (p.y > height + 10) p.y = -10;
    }
    draw();
    animationId = requestAnimationFrame(tick);
  }

  resize();
  window.addEventListener('resize', resize);
  if (!reducedMotion) {
    animationId = requestAnimationFrame(tick);
  }
}
```

- [ ] **Step 5: Run shell static test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_static_particle_workbench.py::test_particle_workbench_shell_markers_exist -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Commit shell**

Run:

```bash
git add zhihu_fiction/static/index.html zhihu_fiction/tests/test_static_particle_workbench.py
git commit -m "feat: add particle workbench shell"
```

---

## Task 2: Apply Dark Workbench Styling To Existing UI

**Files:**
- Modify: `zhihu_fiction/static/index.html`
- Test: `zhihu_fiction/tests/test_static_particle_workbench.py`

- [ ] **Step 1: Add failing static test for dark surface usage**

Append this test to `zhihu_fiction/tests/test_static_particle_workbench.py`:

```python
def test_dark_workbench_surface_classes_are_applied():
    html = _html()

    assert 'class="surface-strong' in html
    assert 'class="surface ' in html
    assert "nav-tab" in html
    assert "form-control" in html
    assert "status-chip" in html
    assert "bg-white rounded" not in html
    assert "bg-gray-50" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_static_particle_workbench.py::test_dark_workbench_surface_classes_are_applied -q
```

Expected:

```text
FAILED ... assert "bg-white" not in html
```

- [ ] **Step 3: Restyle header and nav**

In `zhihu_fiction/static/index.html`, change the header:

```html
<header class="bg-white shadow-sm border-b">
```

to:

```html
<header class="surface-strong border-b border-slate-800/70">
```

Change the header title classes to:

```html
<h1 class="text-lg font-bold text-slate-100">Zhihu Fiction Studio</h1>
<span class="text-xs text-slate-400">知乎爆款小说自动创作系统</span>
```

Change the nav:

```html
<nav class="bg-white border-b">
```

to:

```html
<nav class="surface-strong border-b border-slate-800/70">
```

For each tab button, replace:

```html
class="shrink-0 px-5 py-3 text-sm font-medium text-gray-500 hover:text-gray-700 transition"
```

with:

```html
class="nav-tab shrink-0 px-5 py-3 text-sm font-medium transition"
```

- [ ] **Step 4: Restyle cards and panels**

In `zhihu_fiction/static/index.html`, replace all remaining card shell classes:

```html
bg-white rounded-lg shadow
```

with:

```html
surface rounded-lg
```

Replace:

```html
bg-white rounded-lg shadow overflow-hidden
```

with:

```html
surface rounded-lg overflow-hidden
```

Replace:

```html
bg-white rounded-lg shadow p-6
```

with:

```html
surface rounded-lg p-6
```

Keep spacing classes such as `mb-4`, `p-4`, and grid classes intact.

- [ ] **Step 5: Restyle common text and borders**

In `zhihu_fiction/static/index.html`, apply these broad but explicit replacements:

```text
text-gray-800 -> text-slate-100
text-gray-700 -> text-slate-200
text-gray-600 -> text-slate-300
text-gray-500 -> text-slate-400
text-gray-400 -> text-slate-500
border-b -> border-b border-slate-800/70
divide-y -> divide-y divide-slate-800/70
hover:bg-gray-50 -> hover:bg-slate-800/55
bg-gray-100 -> bg-slate-800/80
bg-indigo-50 -> bg-cyan-400/10
text-indigo-600 -> text-cyan-300
hover:text-gray-600 -> hover:text-slate-200
```

After replacement, manually inspect any duplicated class fragments such as `border-b border-slate-800/70 border-slate-800/70` and remove duplicates.

- [ ] **Step 6: Restyle form controls**

For workspace form inputs, textareas, and selects, add `form-control` and remove light-only focus ring classes.

Example replacement:

```html
class="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
```

to:

```html
class="form-control w-full rounded px-3 py-2 text-sm"
```

Apply the same pattern to workspace `textarea` and `select` controls while preserving `resize-y`, `font-sans`, `leading-relaxed`, and grid classes.

- [ ] **Step 7: Restyle status badges**

For status spans in workspace lists that currently use:

```html
class="px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-500"
```

replace with:

```html
class="status-chip px-2 py-0.5 text-xs"
```

For the package platform chip, use:

```html
class="status-chip px-2 py-0.5 text-xs text-cyan-200"
```

- [ ] **Step 8: Run static surface test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_static_particle_workbench.py::test_dark_workbench_surface_classes_are_applied -q
```

Expected:

```text
1 passed
```

- [ ] **Step 9: Commit styling**

Run:

```bash
git add zhihu_fiction/static/index.html zhihu_fiction/tests/test_static_particle_workbench.py
git commit -m "style: apply dark workspace workbench theme"
```

---

## Task 3: Improve Workspace UX States

**Files:**
- Modify: `zhihu_fiction/static/index.html`
- Test: `zhihu_fiction/tests/test_static_particle_workbench.py`

- [ ] **Step 1: Add failing static test for UX state markers**

Append this test to `zhihu_fiction/tests/test_static_particle_workbench.py`:

```python
def test_workspace_ux_state_markers_exist():
    html = _html()

    assert "workspaceError" in html
    assert "loadWorkspaceList(" in html
    assert "selectedDraft?.status !== 'ready_for_package'" in html
    assert 'for="material-title"' in html
    assert 'id="material-title"' in html
    assert 'for="card-title"' in html
    assert 'id="card-title"' in html
    assert "break-words" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_static_particle_workbench.py::test_workspace_ux_state_markers_exist -q
```

Expected:

```text
FAILED ... assert "workspaceError" in html
```

- [ ] **Step 3: Add workspace error banner**

After `<main class="max-w-5xl mx-auto px-4 py-6">`, add:

```html
  <div x-show="workspaceError" x-cloak class="surface-muted rounded-lg px-4 py-3 mb-4 text-sm text-amber-200">
    <div class="flex items-start justify-between gap-3">
      <span x-text="workspaceError"></span>
      <button type="button" @click="workspaceError=''" class="text-amber-100 hover:text-white">关闭</button>
    </div>
  </div>
```

- [ ] **Step 4: Add workspace error state and shared loader**

In the Alpine state, after `workspacePackages: [],`, add:

```javascript
    workspaceError: '',
```

Replace the five workspace list loaders:

```javascript
    async loadWorkspaceMaterials() { try { this.workspaceMaterials = await (await fetch('/api/workspace/materials')).json(); } catch(e) {} },
    async loadWorkspaceCards() { try { this.workspaceCards = await (await fetch('/api/workspace/topic-cards')).json(); } catch(e) {} },
    async loadWorkspaceTasks() { try { this.workspaceTasks = await (await fetch('/api/workspace/tasks')).json(); } catch(e) {} },
    async loadWorkspaceDrafts() { try { this.workspaceDrafts = await (await fetch('/api/workspace/drafts')).json(); } catch(e) {} },
    async loadWorkspacePackages() { try { this.workspacePackages = await (await fetch('/api/workspace/packages')).json(); } catch(e) {} },
```

with:

```javascript
    async loadWorkspaceList(url, target, label) {
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(await this.workspaceFailure(res));
        this[target] = await res.json();
        if (this.workspaceError.startsWith(label)) this.workspaceError = '';
      } catch(e) {
        this.workspaceError = label + '加载失败: ' + e.message;
      }
    },
    async loadWorkspaceMaterials() { await this.loadWorkspaceList('/api/workspace/materials', 'workspaceMaterials', '素材'); },
    async loadWorkspaceCards() { await this.loadWorkspaceList('/api/workspace/topic-cards', 'workspaceCards', '选题卡'); },
    async loadWorkspaceTasks() { await this.loadWorkspaceList('/api/workspace/tasks', 'workspaceTasks', '任务'); },
    async loadWorkspaceDrafts() { await this.loadWorkspaceList('/api/workspace/drafts', 'workspaceDrafts', '草稿'); },
    async loadWorkspacePackages() { await this.loadWorkspaceList('/api/workspace/packages', 'workspacePackages', '发布包'); },
```

- [ ] **Step 5: Add label associations for material form**

In the material form, change labels and controls:

```html
<label for="material-title" class="block text-sm text-slate-300 mb-1">标题</label>
<input id="material-title" x-model="materialForm.title" class="form-control w-full rounded px-3 py-2 text-sm">

<label for="material-tags" class="block text-sm text-slate-300 mb-1">标签</label>
<input id="material-tags" x-model="materialForm.tagsText" placeholder="悬疑, 反转" class="form-control w-full rounded px-3 py-2 text-sm">

<label for="material-excerpt" class="block text-sm text-slate-300 mb-1">摘要</label>
<textarea id="material-excerpt" x-model="materialForm.excerpt" rows="3" class="form-control w-full rounded px-3 py-2 text-sm resize-y"></textarea>

<label for="material-content" class="block text-sm text-slate-300 mb-1">正文</label>
<textarea id="material-content" x-model="materialForm.content" rows="6" class="form-control w-full rounded px-3 py-2 text-sm resize-y"></textarea>
```

- [ ] **Step 6: Add label associations for topic card form**

Use these ids in the topic card form:

```text
card-title
card-genre
card-platform
card-target-reader
card-hook
card-angle
card-risk-notes
```

Each visible `<label>` should get `for="<id>"`, and the corresponding input/select/textarea should get `id="<id>"`.

- [ ] **Step 7: Add label associations for draft edit form**

Use these ids in the draft edit form:

```text
draft-title
draft-tags
draft-synopsis
draft-body
draft-editor-notes
```

Each visible `<label>` should get `for="<id>"`, and the corresponding input/textarea should get `id="<id>"`.

- [ ] **Step 8: Gate package generation button**

Change the review tab package generation button:

```html
<button @click="generatePackage(selectedDraft.task_id, 'zhihu')"
  class="px-4 py-2 bg-gray-800 text-white rounded text-sm hover:bg-gray-900 transition">生成知乎包</button>
```

to:

```html
<button @click="generatePackage(selectedDraft.task_id, 'zhihu')"
  :disabled="selectedDraft?.status !== 'ready_for_package'"
  class="px-4 py-2 bg-slate-100 text-slate-950 rounded text-sm hover:bg-white disabled:opacity-45 disabled:cursor-not-allowed transition">生成知乎包</button>
```

- [ ] **Step 9: Harden long text wrapping**

Add `break-words` to:

- Task title element: `<h3 ... x-text="task.topic">`
- Package title element: `<h3 ... x-text="pkg.title">`
- Package path grid items containing `pkg.content_path` and `pkg.metadata_path`
- Topic card title element if it is not already safely truncated.

Expected examples:

```html
<h3 class="font-medium text-sm text-slate-100 break-words" x-text="task.topic"></h3>
<div class="truncate break-words">正文：<span x-text="pkg.content_path"></span></div>
```

- [ ] **Step 10: Run UX marker test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_static_particle_workbench.py::test_workspace_ux_state_markers_exist -q
```

Expected:

```text
1 passed
```

- [ ] **Step 11: Commit UX fixes**

Run:

```bash
git add zhihu_fiction/static/index.html zhihu_fiction/tests/test_static_particle_workbench.py
git commit -m "fix: polish workspace frontend states"
```

---

## Task 4: Final Verification And Visual QA

**Files:**
- No product files unless verification reveals a focused fix.

- [ ] **Step 1: Run static tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_static_particle_workbench.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 2: Run workspace API tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_api.py -q
```

Expected:

```text
passed
```

- [ ] **Step 3: Run all zhihu_fiction tests**

Run:

```bash
python -m pytest zhihu_fiction/tests -q
```

Expected:

```text
passed
```

- [ ] **Step 4: Start local server**

Use an available port. Prefer 8000, otherwise use 8001:

```bash
DEEPSEEK_API_KEY=test-key uvicorn zhihu_fiction.server:app --reload --port 8000
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8000
```

If `--reload` cannot run in the environment, use:

```bash
DEEPSEEK_API_KEY=test-key uvicorn zhihu_fiction.server:app --port 8000
```

- [ ] **Step 5: Run Playwright browser smoke**

Run this script, replacing `8000` with the active port if needed:

```bash
python - <<'PY'
from pathlib import Path
from time import time
from playwright.sync_api import sync_playwright, expect

base = "http://127.0.0.1:8000"
stamp = str(int(time()))
material_title = f"粒子素材{stamp}"
card_title = f"粒子选题{stamp}"
screenshot = Path("/tmp/zhihu_particle_workbench.png")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.goto(base, wait_until="load", timeout=15000)
    page.wait_for_function("window.Alpine !== undefined", timeout=15000)

    for label in ["运行", "历史", "技能", "调度", "作品", "素材", "选题卡", "任务", "审核", "发布包"]:
        expect(page.get_by_role("button", name=label, exact=True)).to_be_visible(timeout=5000)

    canvas_box = page.locator("#particleNetwork").bounding_box()
    assert canvas_box and canvas_box["width"] > 200 and canvas_box["height"] > 200
    assert page.locator("body.app-shell").count() == 1

    page.get_by_role("button", name="素材", exact=True).click()
    material_section = page.locator("section[x-show=\"tab==='workspace_materials'\"]")
    material_section.get_by_label("标题", exact=True).fill(material_title)
    material_section.get_by_label("标签", exact=True).fill("QA, 粒子")
    material_section.get_by_label("摘要", exact=True).fill("用于粒子工作台烟测的素材摘要")
    material_section.get_by_label("正文", exact=True).fill("用于粒子工作台烟测的素材正文")
    material_section.get_by_role("button", name="新增素材", exact=True).click()
    expect(page.get_by_text(material_title)).to_be_visible(timeout=10000)
    material_section.locator("label", has_text=material_title).locator("input[type='checkbox']").check()

    page.get_by_role("button", name="选题卡", exact=True).click()
    card_section = page.locator("section[x-show=\"tab==='workspace_cards'\"]")
    expect(card_section.get_by_text("素材数 1")).to_be_visible(timeout=5000)
    card_section.get_by_label("标题", exact=True).fill(card_title)
    card_section.get_by_label("流派", exact=True).fill("悬疑")
    card_section.get_by_label("目标读者", exact=True).fill("知乎短篇读者")
    card_section.get_by_label("钩子", exact=True).fill("她醒来时，手机里多了一条来自未来的私信。")
    card_section.get_by_label("角度", exact=True).fill("以内容网络切入，逐步揭示反转。")
    card_section.get_by_label("风险备注", exact=True).fill("避免真实人物映射。")
    card_section.get_by_role("button", name="创建选题卡", exact=True).click()
    expect(page.get_by_text(card_title)).to_be_visible(timeout=10000)
    card_row = card_section.locator("div.p-4", has_text=card_title)
    card_row.get_by_role("button", name="通过", exact=True).click()
    expect(card_row.get_by_text("approved")).to_be_visible(timeout=10000)
    card_row.get_by_role("button", name="建任务", exact=True).click()

    page.get_by_role("button", name="任务", exact=True).click()
    expect(page.get_by_text(card_title)).to_be_visible(timeout=10000)

    page.get_by_role("button", name="审核", exact=True).click()
    expect(page.locator("section[x-show=\"tab==='workspace_review'\"]").locator("h2").filter(has_text="草稿")).to_be_visible(timeout=5000)

    page.get_by_role("button", name="发布包", exact=True).click()
    expect(page.locator("section[x-show=\"tab==='workspace_packages'\"]").locator("h2").filter(has_text="发布包")).to_be_visible(timeout=5000)

    assert console_errors == []
    page.screenshot(path=str(screenshot), full_page=True)
    browser.close()

print(f"particle workbench smoke ok screenshot={screenshot}")
PY
```

Expected:

```text
particle workbench smoke ok screenshot=/tmp/zhihu_particle_workbench.png
```

- [ ] **Step 6: Run mobile viewport smoke**

Run:

```bash
python - <<'PY'
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

base = "http://127.0.0.1:8000"
screenshot = Path("/tmp/zhihu_particle_workbench_mobile.png")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(base, wait_until="load", timeout=15000)
    page.wait_for_function("window.Alpine !== undefined", timeout=15000)
    expect(page.get_by_role("button", name="运行", exact=True)).to_be_visible(timeout=5000)
    expect(page.get_by_role("button", name="发布包", exact=True)).to_be_visible(timeout=5000)
    assert page.locator("nav .overflow-x-auto").count() >= 1
    page.screenshot(path=str(screenshot), full_page=True)
    browser.close()

print(f"mobile smoke ok screenshot={screenshot}")
PY
```

Expected:

```text
mobile smoke ok screenshot=/tmp/zhihu_particle_workbench_mobile.png
```

- [ ] **Step 7: Inspect screenshots**

Open or inspect:

```text
/tmp/zhihu_particle_workbench.png
/tmp/zhihu_particle_workbench_mobile.png
```

Acceptance criteria:

- Particle canvas is nonblank or visible through page background.
- Header/nav and panels use dark workbench styling.
- Text is readable.
- Controls do not overlap.
- Mobile nav scrolls horizontally and content remains usable.

- [ ] **Step 8: Stop local server**

Stop the uvicorn process with `Ctrl-C`.

Verify:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/ || true
```

Expected after shutdown:

```text
000
```

- [ ] **Step 9: Commit verification fix if needed**

If verification reveals a focused fix, commit it:

```bash
git add zhihu_fiction/static/index.html zhihu_fiction/tests/test_static_particle_workbench.py
git commit -m "fix: stabilize particle workbench UI"
```

If no fixes are needed, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: the plan covers app shell, particle canvas, dark workbench styles, reduced motion, label associations, workspace loading errors, package generation gating, long text wrapping, automated tests, desktop browser smoke, and mobile smoke.
- Scope: all product changes are frontend/static tests only. No backend/API/database changes are included.
- Dependency boundary: no new npm or Python package dependency is introduced.
- TDD: each implementation task starts with a failing static test before production HTML changes.
- Risk: the plan keeps `index.html` as a single file, matching current project structure. If future visual work grows larger, split CSS/JS into static assets in a separate follow-up.
