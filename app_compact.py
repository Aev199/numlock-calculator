"""Compact and simplified keyboard-first shell."""

from __future__ import annotations

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

    # The old prototype API is created before refinement layers are installed.
    # Remove its document-insertion endpoint from the keyboard-first build so the
    # feature cannot be called by renderer code or the pywebview bridge.
    api_class = getattr(app, "AppApi", None)
    if api_class is not None and hasattr(api_class, "commit_and_insert"):
        delattr(api_class, "commit_and_insert")

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
        return html

    def create_window(*args: Any, **kwargs: Any) -> Any:
        # With the instructional rows and result action buttons removed, the shell
        # can be smaller while preserving a useful expression editor and history.
        kwargs["width"] = DEFAULT_WIDTH
        kwargs["height"] = DEFAULT_HEIGHT
        kwargs["min_size"] = MIN_SIZE
        return original_create_window(*args, **kwargs)

    app.build_html = build_html
    app.webview.create_window = create_window
