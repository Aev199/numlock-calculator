"""Compact and simplified keyboard-first shell."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

DEFAULT_WIDTH = 480
DEFAULT_HEIGHT = 540
MIN_SIZE = (390, 400)

_COMMIT_FUNCTION_OLD = """async function commitExpression(insertIntoDocument = false) {
"""
_COMMIT_FUNCTION_NEW = """async function commitExpression() {
"""

_COMMIT_CALL_OLD = """      const evaluation = insertIntoDocument
        ? await api.commit_and_insert(expression)
        : await api.commit(expression);
"""
_COMMIT_CALL_NEW = """      const evaluation = await api.commit(expression);
"""

_COMMIT_STATUS_OLD = """      setStatus(insertIntoDocument ? 'Результат вставлен' : 'Готово');
"""
_COMMIT_STATUS_NEW = """      setStatus('Готово');
"""

_ENTER_OLD = """      commitExpression(event.ctrlKey || event.metaKey);
"""
_ENTER_NEW = """      commitExpression();
"""

_HISTORY_META_OLD = """      meta.textContent = [
        entry.angle_mode,
        entry.number_base,
        shortTime(entry.created_at),
      ].filter(Boolean).join(' · ');
"""
_HISTORY_META_NEW = """      const metaParts = [];
      const angle = String(entry.angle_mode || '').toUpperCase();
      const base = String(entry.number_base || '').toUpperCase();
      if (angle && angle !== 'DEG') metaParts.push(angle);
      if (base && base !== 'DEC') metaParts.push(base);
      metaParts.push(shortTime(entry.created_at));
      meta.textContent = metaParts.filter(Boolean).join(' · ');
"""


def install(app: Any) -> None:
    """Remove secondary actions and override the prototype window dimensions."""

    if getattr(app, "_compact_shell_installed", False):
        return
    app._compact_shell_installed = True

    original_build_html: Callable[[], str] = app.build_html
    original_create_window = app.webview.create_window

    def build_html() -> str:
        html = original_build_html()
        replacements = (
            (_COMMIT_FUNCTION_OLD, _COMMIT_FUNCTION_NEW),
            (_COMMIT_CALL_OLD, _COMMIT_CALL_NEW),
            (_COMMIT_STATUS_OLD, _COMMIT_STATUS_NEW),
            (_ENTER_OLD, _ENTER_NEW),
            (_HISTORY_META_OLD, _HISTORY_META_NEW),
        )
        for old, new in replacements:
            html = html.replace(old, new, 1)

        # Install the optimistic Enter layer before the renderer registers its
        # normal keydown handler. It reuses a matching live-preview immediately,
        # while the original expression is still committed to history in parallel.
        renderer = Path(app.RENDERER_DIR)
        enter_fast_js = (renderer / "enter-fast.js").read_text(encoding="utf-8")
        body_marker = '<body data-theme="dark">'
        html = html.replace(
            body_marker,
            f'{body_marker}\n<script>\n{enter_fast_js}\n</script>',
            1,
        )
        return html

    def create_window(*args: Any, **kwargs: Any) -> Any:
        # With the instructional rows and result action buttons removed, the shell
        # can be smaller while preserving a useful expression editor and history.
        kwargs["width"] = DEFAULT_WIDTH
        kwargs["height"] = DEFAULT_HEIGHT
        kwargs["min_size"] = MIN_SIZE
        return original_create_window(*args, **kwargs)

    # The keyboard-first renderer no longer exposes the abandoned document-insert
    # workflow through pywebview, even though the legacy helper remains in app.py.
    if hasattr(app.AppApi, "commit_and_insert"):
        delattr(app.AppApi, "commit_and_insert")

    app.build_html = build_html
    app.webview.create_window = create_window
