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


def test_dark_workbench_surface_classes_are_applied():
    html = _html()

    assert 'class="surface-strong' in html
    assert 'class="surface ' in html
    assert "nav-tab" in html
    assert "form-control" in html
    assert "status-chip" in html
    assert "bg-white rounded" not in html
    assert "bg-gray-50" not in html
    assert "bg-gray-200" not in html
    assert "bg-gray-300" not in html
    assert " bg-red-50 " not in html
    assert " border-red-100 " not in html
    assert "border border-gray-300" not in html
    assert 'class="border-t hover:bg-slate-800/55' not in html
    assert 'class="border rounded' not in html
    assert 'class="w-full border rounded' not in html
    assert 'class="w-20 border rounded' not in html
    assert 'class="w-24 border rounded' not in html


def test_workspace_ux_state_markers_exist():
    html = _html()

    assert "workspaceError" in html
    assert "loadWorkspaceList(" in html
    assert "selectedDraft?.status !== 'ready_for_package'" in html
    for field_id in (
        "material-title",
        "material-tags",
        "material-excerpt",
        "material-content",
        "card-title",
        "card-genre",
        "card-platform",
        "card-target-reader",
        "card-hook",
        "card-angle",
        "card-risk-notes",
        "draft-title",
        "draft-tags",
        "draft-synopsis",
        "draft-body",
        "draft-editor-notes",
    ):
        assert f'for="{field_id}"' in html
        assert f'id="{field_id}"' in html
    assert "break-words" in html
