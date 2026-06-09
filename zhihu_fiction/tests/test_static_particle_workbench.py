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
