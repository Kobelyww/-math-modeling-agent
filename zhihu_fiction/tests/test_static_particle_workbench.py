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
