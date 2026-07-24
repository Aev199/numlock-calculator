import types
import unittest
from pathlib import Path

import app_compact


class CompactShellTests(unittest.TestCase):
    def make_app(self):
        calls = []

        def create_window(*args, **kwargs):
            calls.append((args, kwargs))
            return object()

        class AppApi:
            def commit(self, _expression):
                return {"ok": True}

            def commit_and_insert(self, _expression):
                return {"ok": True}

        source = """<html><head><style>base</style></head><body data-theme="dark">
<script>
async function commitExpression(insertIntoDocument = false) {
      const evaluation = insertIntoDocument
        ? await api.commit_and_insert(expression)
        : await api.commit(expression);
      setStatus(insertIntoDocument ? 'Результат вставлен' : 'Готово');
}
function handler(event) {
      commitExpression(event.ctrlKey || event.metaKey);
}
function history(entry) {
      meta.textContent = [
        entry.angle_mode,
        entry.number_base,
        shortTime(entry.created_at),
      ].filter(Boolean).join(' · ');
}
</script></body></html>"""

        app = types.SimpleNamespace(
            AppApi=AppApi,
            RENDERER_DIR=Path(__file__).resolve().parents[1] / "renderer",
            build_html=lambda: source,
            webview=types.SimpleNamespace(create_window=create_window),
        )
        return app, calls

    def test_window_size_overrides_prototype_dimensions(self):
        app, calls = self.make_app()
        app_compact.install(app)

        app.webview.create_window(
            "NumLock Calc",
            width=540,
            height=650,
            min_size=(420, 430),
        )

        self.assertEqual(len(calls), 1)
        kwargs = calls[0][1]
        self.assertEqual(kwargs["width"], app_compact.DEFAULT_WIDTH)
        self.assertEqual(kwargs["height"], app_compact.DEFAULT_HEIGHT)
        self.assertEqual(kwargs["min_size"], app_compact.MIN_SIZE)

    def test_secondary_actions_and_standard_modes_are_simplified(self):
        app, _ = self.make_app()
        app_compact.install(app)
        html = app.build_html()

        self.assertIn("async function commitExpression()", html)
        self.assertIn("const evaluation = await api.commit(expression);", html)
        self.assertIn("commitExpression();", html)
        self.assertNotIn("api.commit_and_insert(expression)", html)
        self.assertNotIn("Результат вставлен", html)
        self.assertIn("angle !== 'DEG'", html)
        self.assertIn("base !== 'DEC'", html)
        self.assertFalse(hasattr(app.AppApi, "commit_and_insert"))

    def test_enter_uses_cached_preview_and_updates_history_optimistically(self):
        app, _ = self.make_app()
        app_compact.install(app)
        html = app.build_html()

        self.assertIn("nlcalc-enter-fast", html)
        self.assertIn("cachedResultFor(expression)", html)
        self.assertIn("window.queueMicrotask", html)
        self.assertIn("expression: stillOnCommittedValue ? result : currentValue", html)
        self.assertIn("input.setSelectionRange(end, end)", html)
        self.assertIn("showOptimisticHistory(expression, result)", html)
        self.assertIn("markHistoryForSilentReconcile", html)
        self.assertIn("history-reconciling", html)
        self.assertLess(
            html.index("nlcalc-enter-fast"),
            html.index("async function commitExpression()"),
        )

    def test_compact_visual_rows_and_result_actions_are_hidden(self):
        css = (
            Path(__file__).resolve().parents[1]
            / "renderer"
            / "polish-v3.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".hint-row,", css)
        self.assertIn(".statusbar,", css)
        self.assertIn(".result-actions", css)
        self.assertIn("display: none !important", css)
        self.assertIn("grid-template-columns: auto minmax(0, 1fr)", css)

    def test_expression_focus_ring_stays_inside_toolbar_boundary(self):
        css = (
            Path(__file__).resolve().parents[1]
            / "renderer"
            / "polish-v3.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".expression-input:focus-visible", css)
        self.assertIn("box-shadow: inset 0 0 0 2px var(--accent)", css)
        self.assertIn("margin-bottom: 5px", css)

    def test_history_reconciliation_does_not_replay_all_row_animations(self):
        css = (
            Path(__file__).resolve().parents[1]
            / "renderer"
            / "polish-v3.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".history-entry-optimistic", css)
        self.assertIn(".history-list.history-reconciling .history-entry", css)
        self.assertIn("animation: none !important", css)

    def test_install_is_idempotent(self):
        app, _ = self.make_app()
        app_compact.install(app)
        first_create_window = app.webview.create_window
        first_build_html = app.build_html
        app_compact.install(app)
        self.assertIs(first_create_window, app.webview.create_window)
        self.assertIs(first_build_html, app.build_html)


if __name__ == "__main__":
    unittest.main()
