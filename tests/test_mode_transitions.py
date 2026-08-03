from pathlib import Path

import app_renderer


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "renderer"


def test_explicit_mode_motion_is_bundled_before_event_binding():
    motion_name = "app-shell-v2.mode-transitions.js"
    assert motion_name in app_renderer.SCRIPT_PARTS
    assert app_renderer.SCRIPT_PARTS.index(motion_name) < app_renderer.SCRIPT_PARTS.index(
        "app-shell-v2.part06.js"
    )


def test_mode_motion_uses_explicit_indicator_and_panel_animations():
    source = (RENDERER / "app-shell-v2.mode-transitions.js").read_text(
        encoding="utf-8"
    )
    assert "indicator.animate" in source
    assert "previousPanel.animate" in source
    assert "nextPanel.animate" in source
    assert "cancelModeMotion" in source
    assert "Promise.allSettled" in source


def test_conflicting_css_transitions_are_disabled():
    source = (RENDERER / "app-shell-mode-transitions.css").read_text(
        encoding="utf-8"
    )
    assert "view-transition-name: none !important" in source
    assert ".mode-indicator" in source
    assert "transition: none !important" in source
    assert "animation: none !important" in source
