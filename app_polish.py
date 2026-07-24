"""Renderer polish applied after the stabilized keyboard-first shell."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


PREVIEW_DELAY_MS = 18


def install(app: Any) -> None:
    """Wrap ``build_html`` with cached suggestions, fast preview and motion."""

    if getattr(app, "_polish_v3_installed", False):
        return
    app._polish_v3_installed = True

    original_build_html: Callable[[], str] = app.build_html

    def build_html() -> str:
        html = original_build_html()
        renderer = Path(app.RENDERER_DIR)
        polish_css = (renderer / "polish-v3.css").read_text(encoding="utf-8")
        polish_js = (renderer / "polish-v3.js").read_text(encoding="utf-8")

        # style-v2.css is already inlined by app_stability. Append the small polish
        # layer to the same style block so the packaged renderer remains offline.
        html = html.replace(
            "</style>",
            f"\n{polish_css}\n</style>",
            1,
        )

        # Install the API cache and capture-phase editor helpers before script-v2
        # registers its listeners. This lets manual function wrapping modify the
        # input before the normal completion and preview handlers see the event.
        script_marker = "<script>\n(function () {\n  'use strict';"
        html = html.replace(
            script_marker,
            f"<script>\n{polish_js}\n</script>\n{script_marker}",
            1,
        )

        # The original 90 ms debounce was visible on top of pywebview bridge
        # latency. Suggestion traffic is now cached, so a short debounce is enough
        # to coalesce key repeats without making the result feel delayed.
        html = html.replace(
            "function schedulePreview(delay = 90)",
            f"function schedulePreview(delay = {PREVIEW_DELAY_MS})",
            1,
        )
        return html

    app.build_html = build_html
