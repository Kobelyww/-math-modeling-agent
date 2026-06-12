# Agent App Full Feature Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the DeepAgent paper workflow into an industrial workspace with uploadable assets, run history, real experiment execution, quality revision loops, output profiles, and specialized subagents.

**Architecture:** Add focused domain models and services first, then expose them through FastAPI routes and the Web UI. Keep `CompetitionPaperRunner` as the stable orchestration entrypoint; do not expand legacy `Orchestrator` for new paper features. Each phase must preserve a runnable app and add tests around the public contracts before moving on.

**Tech Stack:** Python dataclasses, FastAPI, Jinja/static JS, JSON-on-disk stores, DeepAgent/LangGraph, pytest.

---

## Scope And Sequencing

This plan covers the full six-phase expansion from `docs/superpowers/specs/2026-06-12-agent-app-full-feature-expansion-design.md`.

Implement phases in order:

1. Asset upload and input selection.
2. Run history, event persistence, recovery, and download.
3. Real experiment execution and result capture.
4. Quality revision loop.
5. Output profiles.
6. Specialized DeepAgent subagents.

Phase 1 is the first execution batch and is intentionally detailed down to test names and core implementation shapes. Later phases are written as separate implementation tasks with clear file ownership and acceptance checks; before starting each later phase, expand its task into the same red-green-refactor granularity using this plan as the contract.

## Working Tree Safety

Before starting implementation:

- Run `git status --short`.
- Preserve existing uncommitted changes in `agent_app/deepagent/coordinator.py`, `agent_app/deepagent/middleware.py`, `agent_app/deepagent/runner.py`, `agent_app/web/paper_stream.py`, `agent_app/web/static/style.css`, and related tests. Those changes came from the paper stream debugging work and must not be reverted.
- Keep commits focused. Do not mix Phase 1 asset work with experiment execution, profiles, or subagents.

## File Structure Map

Create or modify these files.

### Phase 1 Files

- Create `agent_app/services/asset_store.py`
  - Owns uploaded asset persistence, metadata, validation, soft deletion, and path resolution.
- Modify `agent_app/domain/models.py`
  - Adds `AssetKind`, `AssetStatus`, `InputAsset`, and `AssetManifest`.
- Modify `agent_app/domain/serialization.py`
  - Ensures new dataclasses/enums serialize and deserialize through existing helpers.
- Modify `agent_app/services/ingestion.py`
  - Includes asset metadata in `inputs_manifest.json` when assets are selected.
- Modify `agent_app/web/routes.py`
  - Adds asset APIs and accepts `asset_ids` in paper chat start.
- Modify `agent_app/web/paper_stream.py`
  - Extends `PaperChatRequest` with selected asset IDs or resolved asset metadata.
- Modify `agent_app/web/templates/index.html`
  - Adds upload and asset selection UI in the left rail.
- Modify `agent_app/web/static/app.js`
  - Handles upload, asset list refresh, selection, and passes selected `asset_ids`.
- Modify `agent_app/web/static/style.css`
  - Adds compact asset-list and upload styles.
- Create `agent_app/tests/test_asset_store.py`
  - Unit coverage for asset validation and metadata persistence.
- Modify `agent_app/tests/test_paper_chat_stream.py`
  - Route-level coverage for `asset_ids` resolution.
- Create or extend `agent_app/tests/test_web_assets.py`
  - FastAPI tests for upload, list, get, delete.

### Phase 2 Files

- Create `agent_app/services/run_events.py`
  - Appends and reads JSONL run events.
- Extend `agent_app/services/run_store.py`
  - Adds `list_runs`, `load_summary`, and bundle helpers.
- Modify `agent_app/web/paper_stream.py`
  - Wraps `emit` so every event is persisted.
- Modify `agent_app/web/routes.py`
  - Adds `/api/runs` endpoints and download endpoint.
- Modify `agent_app/web/static/app.js`
  - Adds history load/replay behavior.
- Modify `agent_app/web/static/style.css`
  - Adds history and quality-panel styles.
- Add tests in `agent_app/tests/test_run_events.py` and `agent_app/tests/test_web_runs.py`.

### Phase 3 Files

- Modify `agent_app/domain/models.py`
  - Adds `ExecutionAttempt`, `ExecutionPolicy`, and enriches `ExperimentResult`.
- Modify `agent_app/services/code_execution.py`
  - Runs `solve.py` in a bounded working directory and returns structured attempts.
- Create `agent_app/services/experiment_results.py`
  - Scans output directories for figures, tables, metrics.
- Modify `agent_app/tools/competition.py`
  - `run_experiment` executes generated code and may call repair flow.
- Add tests in `agent_app/tests/test_experiment_execution.py`.

### Phase 4 Files

- Modify `agent_app/domain/models.py`
  - Adds `RevisionPlan`, `RevisionAttempt`, `QualityThresholds`.
- Create `agent_app/services/revision_service.py`
  - Applies revision plans to paper artifacts.
- Modify `agent_app/tools/competition.py`
  - Adds `revise_paper` tool and quality-loop support.
- Modify `agent_app/deepagent/middleware.py`
  - Allows revision tools in review stage.
- Modify Web UI to show quality gate cards and revision attempts.
- Add tests in `agent_app/tests/test_revision_loop.py`.

### Phase 5 Files

- Create `agent_app/profiles.py`
  - Defines profile registry and default profile aliases.
- Modify `agent_app/domain/models.py`
  - Adds `OutputProfile` dataclass if not kept in `profiles.py`.
- Modify `agent_app/tools/competition.py`
  - Passes profile config into drafting, review, and package tools.
- Modify `agent_app/web/routes.py`
  - Adds `GET /api/profiles` and accepts `output_profile`.
- Modify Web UI to expose the selector.
- Add tests in `agent_app/tests/test_profiles.py`.

### Phase 6 Files

- Create `agent_app/deepagent/subagents.py`
  - Defines subagent specs for data, modeling, experiment, writing, review, packaging.
- Modify `agent_app/deepagent/coordinator.py`
  - Passes subagents into `create_deep_agent`.
- Modify `agent_app/deepagent/prompts.py`
  - Updates coordinator prompt to delegate by stage.
- Add tests in `agent_app/tests/test_deepagent_subagents.py`.

---

## Phase 1: Asset Upload And Input Asset Management

### Task 1: Add Asset Domain Models

**Files:**
- Modify: `agent_app/domain/models.py`
- Test: `agent_app/tests/test_domain_models.py`

- [ ] **Step 1: Write the failing serialization test**

Add this test to `agent_app/tests/test_domain_models.py`:

```python
def test_input_asset_round_trips_through_json():
    from pathlib import Path

    from agent_app.domain.models import AssetKind, AssetStatus, InputAsset
    from agent_app.domain.serialization import from_json_dict, to_json_dict

    asset = InputAsset(
        asset_id="asset_abc123",
        original_name="traffic.csv",
        stored_path=Path("assets/asset_abc123/traffic.csv"),
        kind=AssetKind.DATA,
        status=AssetStatus.VALIDATED,
        size=18,
        suffix=".csv",
        content_type="text/csv",
        created_at="2026-06-12T12:00:00",
    )

    payload = to_json_dict(asset)
    restored = from_json_dict(InputAsset, payload)

    assert payload["kind"] == "data"
    assert payload["status"] == "validated"
    assert restored == asset
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest agent_app/tests/test_domain_models.py::test_input_asset_round_trips_through_json -q
```

Expected: FAIL because `InputAsset`, `AssetKind`, or `AssetStatus` is not defined.

- [ ] **Step 3: Implement the minimal domain models**

Add to `agent_app/domain/models.py` after `RunStage`:

```python
class AssetKind(str, Enum):
    QUESTION = "question"
    DATA = "data"
    REFERENCE = "reference"
    IMAGE = "image"
    OTHER = "other"


class AssetStatus(str, Enum):
    UPLOADED = "uploaded"
    VALIDATED = "validated"
    REJECTED = "rejected"
    DELETED = "deleted"
```

Add after `RunOptions`:

```python
@dataclass
class InputAsset:
    asset_id: str
    original_name: str
    stored_path: Path
    kind: AssetKind
    status: AssetStatus
    size: int
    suffix: str
    content_type: str = ""
    created_at: str = ""
    deleted_at: str = ""
    validation_error: str = ""


@dataclass
class AssetManifest:
    asset_ids: list[str] = field(default_factory=list)
    data_files: list[Path] = field(default_factory=list)
    reference_files: list[Path] = field(default_factory=list)
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
pytest agent_app/tests/test_domain_models.py::test_input_asset_round_trips_through_json -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_app/domain/models.py agent_app/tests/test_domain_models.py
git commit -m "feat: add input asset domain models"
```

### Task 2: Implement AssetStore Validation And Persistence

**Files:**
- Create: `agent_app/services/asset_store.py`
- Test: `agent_app/tests/test_asset_store.py`

- [ ] **Step 1: Write failing asset store tests**

Create `agent_app/tests/test_asset_store.py`:

```python
from __future__ import annotations

import pytest

from agent_app.domain.models import AssetKind, AssetStatus
from agent_app.services.asset_store import AssetStore


def test_asset_store_uploads_valid_csv(tmp_path):
    source = tmp_path / "traffic.csv"
    source.write_text("flow,speed\n10,40\n", encoding="utf-8")
    store = AssetStore(tmp_path / "assets")

    asset = store.upload(source, content_type="text/csv")
    loaded = store.load(asset.asset_id)

    assert asset.asset_id.startswith("asset_")
    assert asset.kind == AssetKind.DATA
    assert asset.status == AssetStatus.VALIDATED
    assert asset.original_name == "traffic.csv"
    assert store.resolve(asset.asset_id).read_text(encoding="utf-8") == "flow,speed\n10,40\n"
    assert loaded == asset


def test_asset_store_rejects_unsupported_suffix(tmp_path):
    source = tmp_path / "binary.exe"
    source.write_bytes(b"not allowed")
    store = AssetStore(tmp_path / "assets")

    with pytest.raises(ValueError, match="unsupported file type"):
        store.upload(source)


def test_asset_store_soft_deletes_asset(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("# ref\n", encoding="utf-8")
    store = AssetStore(tmp_path / "assets")
    asset = store.upload(source)

    deleted = store.delete(asset.asset_id)

    assert deleted.status == AssetStatus.DELETED
    assert store.load(asset.asset_id).status == AssetStatus.DELETED
    with pytest.raises(FileNotFoundError):
        store.resolve(asset.asset_id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest agent_app/tests/test_asset_store.py -q
```

Expected: FAIL because `agent_app.services.asset_store` does not exist.

- [ ] **Step 3: Implement `AssetStore`**

Create `agent_app/services/asset_store.py`:

```python
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from agent_app.domain.models import AssetKind, AssetStatus, InputAsset
from agent_app.domain.serialization import from_json_dict, to_json_dict


ALLOWED_SUFFIXES = {
    ".csv": AssetKind.DATA,
    ".xlsx": AssetKind.DATA,
    ".json": AssetKind.DATA,
    ".txt": AssetKind.REFERENCE,
    ".md": AssetKind.REFERENCE,
    ".pdf": AssetKind.REFERENCE,
    ".png": AssetKind.IMAGE,
    ".jpg": AssetKind.IMAGE,
    ".jpeg": AssetKind.IMAGE,
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class AssetStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def upload(self, source: Path, content_type: str = "") -> InputAsset:
        source = Path(source).expanduser().resolve()
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(str(source))
        suffix = source.suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise ValueError(f"unsupported file type: {suffix}")
        size = source.stat().st_size
        if size <= 0:
            raise ValueError("empty files are not supported")
        if size > MAX_UPLOAD_BYTES:
            raise ValueError(f"file too large: {size} bytes")

        asset_id = f"asset_{uuid4().hex[:12]}"
        asset_dir = self.root / asset_id
        asset_dir.mkdir(parents=True, exist_ok=False)
        stored_path = asset_dir / source.name
        shutil.copy2(source, stored_path)
        asset = InputAsset(
            asset_id=asset_id,
            original_name=source.name,
            stored_path=stored_path.relative_to(self.root),
            kind=ALLOWED_SUFFIXES[suffix],
            status=AssetStatus.VALIDATED,
            size=size,
            suffix=suffix,
            content_type=content_type,
            created_at=self._now(),
        )
        self._write_metadata(asset)
        return asset

    def load(self, asset_id: str) -> InputAsset:
        path = self._asset_dir(asset_id) / "asset.json"
        if not path.exists():
            raise FileNotFoundError(asset_id)
        return from_json_dict(InputAsset, json.loads(path.read_text(encoding="utf-8")))

    def list(self, include_deleted: bool = False) -> list[InputAsset]:
        assets = []
        for metadata in sorted(self.root.glob("asset_*/asset.json")):
            asset = from_json_dict(InputAsset, json.loads(metadata.read_text(encoding="utf-8")))
            if include_deleted or asset.status != AssetStatus.DELETED:
                assets.append(asset)
        return assets

    def resolve(self, asset_id: str) -> Path:
        asset = self.load(asset_id)
        if asset.status == AssetStatus.DELETED:
            raise FileNotFoundError(asset_id)
        path = (self.root / asset.stored_path).resolve()
        if self.root not in path.parents:
            raise ValueError("asset path escapes asset store")
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(asset_id)
        return path

    def delete(self, asset_id: str) -> InputAsset:
        asset = self.load(asset_id)
        asset.status = AssetStatus.DELETED
        asset.deleted_at = self._now()
        self._write_metadata(asset)
        return asset

    def _write_metadata(self, asset: InputAsset) -> None:
        path = self._asset_dir(asset.asset_id) / "asset.json"
        path.write_text(json.dumps(to_json_dict(asset), ensure_ascii=False, indent=2), encoding="utf-8")

    def _asset_dir(self, asset_id: str) -> Path:
        if not asset_id.startswith("asset_") or "/" in asset_id or "\\" in asset_id:
            raise ValueError("invalid asset id")
        return self.root / asset_id

    @staticmethod
    def _now() -> str:
        return datetime.now().replace(microsecond=0).isoformat()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest agent_app/tests/test_asset_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Run related serialization tests**

Run:

```bash
pytest agent_app/tests/test_domain_models.py agent_app/tests/test_asset_store.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agent_app/services/asset_store.py agent_app/tests/test_asset_store.py
git commit -m "feat: add asset store service"
```

### Task 3: Add Asset API Routes

**Files:**
- Modify: `agent_app/web/routes.py`
- Test: `agent_app/tests/test_web_assets.py`

- [ ] **Step 1: Write failing API tests**

Create `agent_app/tests/test_web_assets.py`:

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from agent_app.web.main import app


def test_upload_list_get_and_delete_asset(tmp_path, monkeypatch):
    from agent_app.web import routes

    monkeypatch.setattr(routes, "ASSET_DIR", tmp_path / "assets")
    client = TestClient(app)

    response = client.post(
        "/api/assets/upload",
        files={"file": ("traffic.csv", b"flow,speed\n10,40\n", "text/csv")},
    )
    assert response.status_code == 200
    uploaded = response.json()
    assert uploaded["asset_id"].startswith("asset_")
    assert uploaded["kind"] == "data"
    assert uploaded["status"] == "validated"

    list_response = client.get("/api/assets")
    assert list_response.status_code == 200
    assert [asset["asset_id"] for asset in list_response.json()["assets"]] == [uploaded["asset_id"]]

    get_response = client.get(f"/api/assets/{uploaded['asset_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["original_name"] == "traffic.csv"

    delete_response = client.delete(f"/api/assets/{uploaded['asset_id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"

    assert client.get("/api/assets").json()["assets"] == []


def test_upload_rejects_unsupported_asset(tmp_path, monkeypatch):
    from agent_app.web import routes

    monkeypatch.setattr(routes, "ASSET_DIR", tmp_path / "assets")
    client = TestClient(app)

    response = client.post(
        "/api/assets/upload",
        files={"file": ("malware.exe", b"bad", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "unsupported file type" in response.json()["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest agent_app/tests/test_web_assets.py -q
```

Expected: FAIL because `/api/assets/upload` is not implemented.

- [ ] **Step 3: Add route-level asset store helper**

Modify `agent_app/web/routes.py` imports:

```python
import tempfile
```

Add imports:

```python
from ..domain.serialization import to_json_dict
from ..services.asset_store import AssetStore
```

Add after `PAPER_INPUT_DIR`:

```python
ASSET_DIR = PAPER_INPUT_DIR / "assets"


def _asset_store() -> AssetStore:
    return AssetStore(ASSET_DIR)
```

- [ ] **Step 4: Add asset API endpoints**

Add these endpoints before `/api/paper/run` in `agent_app/web/routes.py`:

```python
@router.post("/api/assets/upload")
async def upload_asset(file: UploadFile = File(...)):
    if not file.filename:
        return JSONResponse({"error": "文件名不能为空"}, status_code=400)
    try:
        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)
            content = await file.read()
            tmp.write(content)
        try:
            asset = _asset_store().upload(tmp_path, content_type=file.content_type or "")
        finally:
            tmp_path.unlink(missing_ok=True)
        return to_json_dict(asset)
    except (FileNotFoundError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.get("/api/assets")
async def list_assets():
    return {"assets": [to_json_dict(asset) for asset in _asset_store().list()]}


@router.get("/api/assets/{asset_id}")
async def get_asset(asset_id: str):
    try:
        return to_json_dict(_asset_store().load(asset_id))
    except (FileNotFoundError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)


@router.delete("/api/assets/{asset_id}")
async def delete_asset(asset_id: str):
    try:
        return to_json_dict(_asset_store().delete(asset_id))
    except (FileNotFoundError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest agent_app/tests/test_web_assets.py -q
```

Expected: PASS.

- [ ] **Step 6: Run web regression tests**

Run:

```bash
pytest agent_app/tests/test_web_assets.py agent_app/tests/test_paper_chat_stream.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add agent_app/web/routes.py agent_app/tests/test_web_assets.py
git commit -m "feat: expose asset upload api"
```

### Task 4: Resolve Asset IDs For Paper Runs

**Files:**
- Modify: `agent_app/web/paper_stream.py`
- Modify: `agent_app/web/routes.py`
- Test: `agent_app/tests/test_paper_chat_stream.py`

- [ ] **Step 1: Write failing route test**

Add this test to `agent_app/tests/test_paper_chat_stream.py`:

```python
def test_paper_chat_start_resolves_selected_asset_ids(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from agent_app.web import routes
    from agent_app.web.main import app

    monkeypatch.setattr(routes, "ASSET_DIR", tmp_path / "assets")
    client = TestClient(app)

    upload = client.post(
        "/api/assets/upload",
        files={"file": ("traffic.csv", b"flow,speed\n10,40\n", "text/csv")},
    ).json()

    response = client.post(
        "/api/paper/chat/start",
        json={"question": "建立交通流预测模型", "asset_ids": [upload["asset_id"]]},
    )

    assert response.status_code == 200
    task_id = response.json()["task_id"]
    request = routes._paper_tasks[task_id]
    assert request.data_files
    assert request.data_files[0].name == "traffic.csv"
    assert request.asset_ids == [upload["asset_id"]]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest agent_app/tests/test_paper_chat_stream.py::test_paper_chat_start_resolves_selected_asset_ids -q
```

Expected: FAIL because `asset_ids` is ignored or `PaperChatRequest.asset_ids` is missing.

- [ ] **Step 3: Extend `PaperChatRequest`**

Modify `agent_app/web/paper_stream.py`:

```python
@dataclass
class PaperChatRequest:
    question: str
    data_files: list[Path] = field(default_factory=list)
    reference_files: list[Path] = field(default_factory=list)
    messages: list[dict[str, str]] = field(default_factory=list)
    asset_ids: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Add asset resolution helper**

Add this helper to `agent_app/web/routes.py` near `_asset_store()`:

```python
def _resolve_asset_ids(asset_ids: list[str]) -> tuple[list[Path], list[Path]]:
    data_files: list[Path] = []
    reference_files: list[Path] = []
    store = _asset_store()
    for asset_id in asset_ids:
        asset = store.load(asset_id)
        path = store.resolve(asset_id)
        if asset.kind.value in {"data", "image"}:
            data_files.append(path)
        elif asset.kind.value in {"reference", "question"}:
            reference_files.append(path)
        else:
            reference_files.append(path)
    return data_files, reference_files
```

- [ ] **Step 5: Use asset IDs in `start_paper_chat`**

Modify `start_paper_chat` after path resolution:

```python
    asset_ids = data.get("asset_ids", [])
    try:
        asset_data_files, asset_reference_files = _resolve_asset_ids(asset_ids)
    except (FileNotFoundError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    data_files.extend(asset_data_files)
    reference_files.extend(asset_reference_files)
```

Modify `PaperChatRequest(...)`:

```python
            asset_ids=asset_ids,
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
pytest agent_app/tests/test_paper_chat_stream.py::test_paper_chat_start_resolves_selected_asset_ids -q
```

Expected: PASS.

- [ ] **Step 7: Run route regression tests**

Run:

```bash
pytest agent_app/tests/test_web_assets.py agent_app/tests/test_paper_chat_stream.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add agent_app/web/routes.py agent_app/web/paper_stream.py agent_app/tests/test_paper_chat_stream.py
git commit -m "feat: resolve selected assets for paper runs"
```

### Task 5: Add Asset Upload And Selection UI

**Files:**
- Modify: `agent_app/web/templates/index.html`
- Modify: `agent_app/web/static/app.js`
- Modify: `agent_app/web/static/style.css`

- [ ] **Step 1: Add UI markup**

In `agent_app/web/templates/index.html`, inside the Paper Run panel after the PDF upload block, add:

```html
        <div class="asset-picker">
          <div class="panel-label">Input Assets</div>
          <label for="asset-file" class="btn-secondary">上传数据 / 参考文件</label>
          <input type="file" id="asset-file" onchange="onAssetSelected()" class="sr-only">
          <div id="asset-upload-status" class="status-text"></div>
          <div id="asset-list" class="asset-list">
            <div class="asset-note">暂无上传文件</div>
          </div>
        </div>
```

- [ ] **Step 2: Add JS state and API functions**

In `agent_app/web/static/app.js`, near the top:

```javascript
let assetRecords = [];
const selectedAssetIds = new Set();
```

Add:

```javascript
async function loadAssets() {
  const list = document.getElementById('asset-list');
  if (!list) return;
  try {
    const resp = await fetch('/api/assets');
    const data = await resp.json();
    assetRecords = data.assets || [];
    renderAssets();
  } catch (e) {
    list.innerHTML = '<div class="asset-note">资产列表加载失败</div>';
  }
}

function renderAssets() {
  const list = document.getElementById('asset-list');
  if (!list) return;
  if (!assetRecords.length) {
    list.innerHTML = '<div class="asset-note">暂无上传文件</div>';
    return;
  }
  list.innerHTML = assetRecords.map(asset => {
    const checked = selectedAssetIds.has(asset.asset_id) ? 'checked' : '';
    return '<label class="asset-row">' +
      '<input type="checkbox" data-asset-id="' + asset.asset_id + '" onchange="toggleAssetSelection(this)" ' + checked + '>' +
      '<span><strong>' + asset.original_name + '</strong><small>' + asset.kind + ' · ' + asset.size + ' bytes</small></span>' +
      '</label>';
  }).join('');
}

function toggleAssetSelection(input) {
  const id = input.dataset.assetId;
  if (!id) return;
  if (input.checked) selectedAssetIds.add(id);
  else selectedAssetIds.delete(id);
}

function onAssetSelected() {
  const input = document.getElementById('asset-file');
  const file = input.files[0];
  if (!file) return;
  const status = document.getElementById('asset-upload-status');
  status.textContent = '上传中...';
  status.style.color = '';
  const formData = new FormData();
  formData.append('file', file);
  fetch('/api/assets/upload', { method: 'POST', body: formData })
    .then(resp => resp.json().then(data => ({ ok: resp.ok, data })))
    .then(result => {
      if (!result.ok || result.data.error) throw new Error(result.data.error || '上传失败');
      selectedAssetIds.add(result.data.asset_id);
      status.textContent = '已上传：' + result.data.original_name;
      status.style.color = 'var(--green)';
      return loadAssets();
    })
    .catch(e => {
      status.textContent = '上传失败：' + e.message;
      status.style.color = 'var(--red)';
    });
  input.value = '';
}
```

- [ ] **Step 3: Send selected asset IDs when starting a paper task**

In `startPaperTask`, add `asset_ids`:

```javascript
        asset_ids: Array.from(selectedAssetIds),
```

The request body should include `question`, `data_files`, `reference_files`, `asset_ids`, and `messages`.

- [ ] **Step 4: Initialize asset loading**

At the bottom of `app.js`, before or after `loadSkills();`, add:

```javascript
loadAssets();
```

- [ ] **Step 5: Add CSS**

Add to `agent_app/web/static/style.css`:

```css
.asset-picker {
  margin-top: 12px;
}

.asset-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 180px;
  overflow-y: auto;
}

.asset-row {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-muted);
  padding: 7px;
  margin: 0;
}

.asset-row input {
  width: auto;
  margin: 2px 0 0;
}

.asset-row strong,
.asset-row small,
.asset-note {
  display: block;
  word-break: break-word;
}

.asset-row small,
.asset-note {
  color: var(--text-dim);
  font-size: 11px;
}
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest agent_app/tests/test_web_assets.py agent_app/tests/test_paper_chat_stream.py -q
```

Expected: PASS.

- [ ] **Step 7: Browser smoke test**

Run the service:

```bash
python -m dotenv -f /Users/haobowang/Desktop/Code\ file/Python/LLM-Study/.env run -- python -m uvicorn agent_app.web.main:app --host 127.0.0.1 --port 8001
```

Open `http://127.0.0.1:8001`, upload a small CSV, confirm it appears selected, start a run, and verify stage events stream.

- [ ] **Step 8: Commit**

```bash
git add agent_app/web/templates/index.html agent_app/web/static/app.js agent_app/web/static/style.css
git commit -m "feat: add asset upload selection ui"
```

### Task 6: Phase 1 Regression And Documentation

**Files:**
- Modify: `agent_app/README.md`

- [ ] **Step 1: Update README with asset upload workflow**

Add this under Web usage or Quick Start:

```markdown
### Web asset workflow

The Web paper console supports uploading input assets directly. Upload CSV, Excel, JSON, Markdown, text, PDF, PNG, JPG, or JPEG files in the Input Assets panel, select the files to attach to a run, then start paper generation. Uploaded files are stored under `agent_app/data/paper_inputs/assets/<asset_id>/` with JSON metadata and are resolved server-side when the run starts.
```

- [ ] **Step 2: Run full test suite**

Run:

```bash
pytest agent_app/tests -q
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add agent_app/README.md
git commit -m "docs: document web asset workflow"
```

---

## Phase 2: Run History, Event Recovery, And Downloads

### Task 7: Add Run Event Store

**Files:**
- Create: `agent_app/services/run_events.py`
- Test: `agent_app/tests/test_run_events.py`

Implementation contract:

- `RunEventStore(run_dir: Path)`.
- `append(event: dict) -> None` writes one JSON object per line to `events.jsonl`.
- `list() -> list[dict]` returns events in order.
- Invalid JSON lines are skipped only if they are empty; malformed non-empty lines raise `ValueError`.

Required tests:

- Appending two events reads them back in order.
- Empty event file returns an empty list.
- Malformed line raises `ValueError`.

Commit:

```bash
git add agent_app/services/run_events.py agent_app/tests/test_run_events.py
git commit -m "feat: persist run event streams"
```

### Task 8: Persist WebSocket Events During Paper Runs

**Files:**
- Modify: `agent_app/web/paper_stream.py`
- Modify: `agent_app/deepagent/runner.py` if needed to expose `run_id` before execution.
- Test: `agent_app/tests/test_paper_chat_stream.py`

Implementation contract:

- Every emitted event after run creation is appended to `<run_dir>/events.jsonl`.
- The final `done` event is persisted.
- If the run fails, the error event is persisted.

Test shape:

```python
def test_paper_chat_stream_persists_events(tmp_path):
    collector = EventCollector()
    streamer = PaperChatStreamer(
        output_root=tmp_path / "runs",
        coordinator_factory=lambda run_store, **_: EventDrivingCoordinator(run_store, collector),
    )
    result = streamer.run(RunSpec(question="建立模型"), emit=collector)
    events_path = tmp_path / "runs" / result.run_id / "events.jsonl"
    assert events_path.exists()
    assert any('"type": "done"' in line for line in events_path.read_text(encoding="utf-8").splitlines())
```

Commit:

```bash
git add agent_app/web/paper_stream.py agent_app/tests/test_paper_chat_stream.py
git commit -m "feat: persist paper stream events"
```

### Task 9: Add Run History API

**Files:**
- Modify: `agent_app/services/run_store.py`
- Modify: `agent_app/web/routes.py`
- Test: `agent_app/tests/test_web_runs.py`

Implementation contract:

- `RunStore.list_runs(limit: int = 50) -> list[RunState]`.
- `GET /api/runs` returns summaries sorted newest first.
- `GET /api/runs/{run_id}` returns serialized run state.
- `GET /api/runs/{run_id}/events` returns persisted events.
- Invalid run IDs return 404 JSON.

Commit:

```bash
git add agent_app/services/run_store.py agent_app/web/routes.py agent_app/tests/test_web_runs.py
git commit -m "feat: expose run history api"
```

### Task 10: Add Download Bundle API

**Files:**
- Modify: `agent_app/services/run_store.py`
- Modify: `agent_app/web/routes.py`
- Test: `agent_app/tests/test_web_runs.py`

Implementation contract:

- `GET /api/runs/{run_id}/download` returns a zip file containing all top-level run files and nested result files.
- Exclude transient files like existing `submission.zip` from the zip to avoid recursion.
- Return 404 for missing run IDs.

Commit:

```bash
git add agent_app/services/run_store.py agent_app/web/routes.py agent_app/tests/test_web_runs.py
git commit -m "feat: add run download bundle"
```

### Task 11: Add Run History UI

**Files:**
- Modify: `agent_app/web/templates/index.html`
- Modify: `agent_app/web/static/app.js`
- Modify: `agent_app/web/static/style.css`

Implementation contract:

- Display recent runs in the right rail.
- Clicking a run replays events from `/api/runs/{run_id}/events`.
- Completed runs enable download.
- Partial/failed runs enable follow-up.

Manual verification:

- Start one run, refresh page, load it from history, and see prior stage/artifact events.

Commit:

```bash
git add agent_app/web/templates/index.html agent_app/web/static/app.js agent_app/web/static/style.css
git commit -m "feat: add run history ui"
```

---

## Phase 3: Real Experiment Execution

### Task 12: Add Execution Domain Models

**Files:**
- Modify: `agent_app/domain/models.py`
- Test: `agent_app/tests/test_domain_models.py`

Implementation contract:

- Add `ExecutionPolicy` enum with `local`, `docker`, `disabled`.
- Add `ExecutionAttempt` dataclass with command, exit code, stdout, stderr, duration, produced files.
- Extend `ExperimentResult` with `attempts: list[ExecutionAttempt]`.

Commit:

```bash
git add agent_app/domain/models.py agent_app/tests/test_domain_models.py
git commit -m "feat: add experiment execution domain models"
```

### Task 13: Run Generated `solve.py`

**Files:**
- Modify: `agent_app/services/code_execution.py`
- Test: `agent_app/tests/test_experiment_execution.py`

Implementation contract:

- Add `run_python_script(script_path: Path, cwd: Path, timeout_seconds: int) -> ExecutionAttempt`.
- Capture stdout/stderr.
- Timeout returns non-zero exit code and stderr containing timeout text.
- Do not allow cwd outside the run directory supplied by caller.

Commit:

```bash
git add agent_app/services/code_execution.py agent_app/tests/test_experiment_execution.py
git commit -m "feat: execute generated experiment scripts"
```

### Task 14: Capture Experiment Outputs

**Files:**
- Create: `agent_app/services/experiment_results.py`
- Modify: `agent_app/tools/competition.py`
- Test: `agent_app/tests/test_experiment_execution.py`

Implementation contract:

- Scan `results/` and `figures/`.
- Detect CSV/JSON/MD tables and PNG/JPG/PDF figures.
- Store discovered files in `ExperimentResult.result_files` and `figure_files`.
- `run_experiment` returns execution status, attempts, metrics, tables, and artifact paths.

Commit:

```bash
git add agent_app/services/experiment_results.py agent_app/tools/competition.py agent_app/tests/test_experiment_execution.py
git commit -m "feat: capture experiment outputs"
```

---

## Phase 4: Quality Revision Loop

### Task 15: Add Revision Domain And Tool

**Files:**
- Modify: `agent_app/domain/models.py`
- Create: `agent_app/services/revision_service.py`
- Modify: `agent_app/tools/competition.py`
- Test: `agent_app/tests/test_revision_loop.py`

Implementation contract:

- Add `RevisionPlan`, `RevisionAttempt`, and `QualityThresholds`.
- Add `revise_paper` tool.
- Revision writes versioned files such as `revisions/revision_1_paper.md`.
- Revision never overwrites the original without preserving a version.

Commit:

```bash
git add agent_app/domain/models.py agent_app/services/revision_service.py agent_app/tools/competition.py agent_app/tests/test_revision_loop.py
git commit -m "feat: add paper revision tool"
```

### Task 16: Wire Revision Loop Into DeepAgent Workflow

**Files:**
- Modify: `agent_app/deepagent/middleware.py`
- Modify: `agent_app/deepagent/prompts.py`
- Modify: `agent_app/tools/competition.py`
- Test: `agent_app/tests/test_revision_loop.py`

Implementation contract:

- Review stage allows `review_submission` and `revise_paper`.
- If required fixes remain after max attempts, run is `partial`.
- Passing revision emits quality reports and artifact events.

Commit:

```bash
git add agent_app/deepagent/middleware.py agent_app/deepagent/prompts.py agent_app/tools/competition.py agent_app/tests/test_revision_loop.py
git commit -m "feat: enable quality revision loop"
```

### Task 17: Show Quality Gates In Web

**Files:**
- Modify: `agent_app/web/static/app.js`
- Modify: `agent_app/web/static/style.css`
- Modify: `agent_app/web/templates/index.html`

Implementation contract:

- Add quality report panel.
- Handle `quality_gate` and revision events.
- Show score, pass/fail, required fixes, and revision count.

Commit:

```bash
git add agent_app/web/templates/index.html agent_app/web/static/app.js agent_app/web/static/style.css
git commit -m "feat: show quality gate revisions in web"
```

---

## Phase 5: Output Profiles

### Task 18: Add Profile Registry

**Files:**
- Create: `agent_app/profiles.py`
- Modify: `agent_app/domain/models.py` if `OutputProfile` belongs there.
- Test: `agent_app/tests/test_profiles.py`

Implementation contract:

- Registry exposes `competition_paper`, `mcm_icm`, `cumcm`, and `research_paper`.
- `competition_paper` aliases to `mcm_icm` behavior.
- Each profile defines language, required sections, citation style, quality thresholds, and package expectations.

Commit:

```bash
git add agent_app/profiles.py agent_app/domain/models.py agent_app/tests/test_profiles.py
git commit -m "feat: add output profile registry"
```

### Task 19: Use Profiles In Runner And Tools

**Files:**
- Modify: `agent_app/deepagent/runner.py`
- Modify: `agent_app/tools/competition.py`
- Modify: `agent_app/deepagent/prompts.py`
- Test: `agent_app/tests/test_profiles.py`

Implementation contract:

- Runner includes profile details in user instruction.
- Draft/review/package tools receive profile ID and use profile-specific required sections.
- Existing runs without profile still work.

Commit:

```bash
git add agent_app/deepagent/runner.py agent_app/tools/competition.py agent_app/deepagent/prompts.py agent_app/tests/test_profiles.py
git commit -m "feat: apply output profiles to paper workflow"
```

### Task 20: Add Profile API And UI Selector

**Files:**
- Modify: `agent_app/web/routes.py`
- Modify: `agent_app/web/static/app.js`
- Modify: `agent_app/web/templates/index.html`
- Modify: `agent_app/web/static/style.css`
- Test: `agent_app/tests/test_profiles.py`

Implementation contract:

- `GET /api/profiles` returns profile summaries.
- Paper start accepts `output_profile`.
- UI selector sends selected profile and updates helper text.

Commit:

```bash
git add agent_app/web/routes.py agent_app/web/templates/index.html agent_app/web/static/app.js agent_app/web/static/style.css agent_app/tests/test_profiles.py
git commit -m "feat: expose paper output profiles"
```

---

## Phase 6: DeepAgent Subagents

### Task 21: Define Subagent Specs

**Files:**
- Create: `agent_app/deepagent/subagents.py`
- Test: `agent_app/tests/test_deepagent_subagents.py`

Implementation contract:

- Expose `make_competition_subagents()` returning data, modeling, experiment, writing, review, and packaging subagent specs.
- Each subagent has a focused prompt and tool access description.
- Subagents do not directly mutate run state except via tools.

Commit:

```bash
git add agent_app/deepagent/subagents.py agent_app/tests/test_deepagent_subagents.py
git commit -m "feat: define competition paper subagents"
```

### Task 22: Register Subagents With DeepAgent

**Files:**
- Modify: `agent_app/deepagent/coordinator.py`
- Modify: `agent_app/deepagent/prompts.py`
- Test: `agent_app/tests/test_deepagent_coordinator.py`

Implementation contract:

- `create_competition_paper_agent` passes `subagents=make_competition_subagents(...)` into `create_deep_agent`.
- Existing tests continue to assert `system_prompt`, not `instructions`.
- Coordinator prompt instructs the main agent to delegate stage-specific work.

Commit:

```bash
git add agent_app/deepagent/coordinator.py agent_app/deepagent/prompts.py agent_app/tests/test_deepagent_coordinator.py
git commit -m "feat: register deepagent competition subagents"
```

### Task 23: End-To-End Subagent Smoke Test

**Files:**
- Modify: `agent_app/tests/test_competition_smoke.py`
- Modify: `agent_app/tests/test_deepagent_subagents.py`

Implementation contract:

- Use a fake coordinator or fake model where possible to avoid network tests.
- Assert stage events still stream and package artifacts still appear.
- Assert subagent definitions are included in coordinator creation.

Commit:

```bash
git add agent_app/tests/test_competition_smoke.py agent_app/tests/test_deepagent_subagents.py
git commit -m "test: cover subagent paper workflow smoke"
```

---

## Final Verification

After all phases:

- [ ] Run full regression:

```bash
pytest agent_app/tests -q
```

Expected: PASS.

- [ ] Start Web service:

```bash
python -m dotenv -f /Users/haobowang/Desktop/Code\ file/Python/LLM-Study/.env run -- python -m uvicorn agent_app.web.main:app --host 127.0.0.1 --port 8001
```

- [ ] Browser QA:

1. Upload a CSV and a PDF/MD reference.
2. Select `mcm_icm`, start a paper run, and verify stage/tool/artifact events stream.
3. Refresh the page, load the run from history, and verify event replay.
4. Download the completed bundle.
5. Start a `research_paper` profile run and verify different section expectations.

- [ ] Stop the service after QA unless the user asks to keep it running.

## Self-Review Checklist

- Spec coverage:
  - Phase 1 covers upload and asset selection.
  - Phase 2 covers run history, recovery, and downloads.
  - Phase 3 covers experiment execution and result capture.
  - Phase 4 covers quality revision loop.
  - Phase 5 covers profiles.
  - Phase 6 covers subagents.
- No task should edit legacy `Orchestrator` for new paper features.
- No task should remove current path-based CLI compatibility.
- Every phase has tests and a commit boundary.
- Full regression remains `pytest agent_app/tests -q`.
