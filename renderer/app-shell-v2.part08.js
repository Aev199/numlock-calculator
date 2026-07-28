    if (data.storage_warning) showToast(data.storage_warning);
    reconcileHistory();
    bindEvents();
    setInputValue(state.calculator.expression);
    renderResult(null);
    restoreEditorFocus();

    function reportRendererDiagnostic(source, message, details = '') {
      try {
        const pending = state.api?.report_diagnostic(source, message, details);
        pending?.catch?.(() => {});
      } catch (_) {}
    }

    window.addEventListener('error', event => {
      reportRendererDiagnostic(
        'renderer',
        event.message || 'JavaScript error',
        event.error?.stack || `${event.filename || ''}:${event.lineno || 0}:${event.colno || 0}`,
      );
    });
    window.addEventListener('unhandledrejection', event => {
      const reason = event.reason;
      reportRendererDiagnostic(
        'renderer-promise',
        reason?.message || String(reason || 'Unhandled promise rejection'),
        reason?.stack || '',
      );
    });

    await state.api.window_focus_changed(document.hasFocus());
  }

  // Post-UX input fixes. Keep the live textarea native while correcting the
  // visual expression and giving beforeinput enough time to reach input.
  const CARET_INPUT_WATCHDOG_MS = 80;

  const displayExpressionWithoutImplicitMultiply = displayExpression;
  displayExpression = function (value) {
    const visual = displayExpressionWithoutImplicitMultiply(value);
    // A number or closing bracket immediately followed by an opening bracket is
    // implicit multiplication. Show the operation explicitly in the editor,
    // history and clipboard: 150(5) -> 150⋅(5), (2)(3) -> (2)⋅(3).
    return visual.replace(/([0-9)])\s*(?=\()/g, `$1${DISPLAY_MULTIPLY}`);
  };

  const settleCaretGlyphMotionWithWatchdog = settleCaretGlyphMotion;
  settleCaretGlyphMotion = function () {
    const pending = caretGlyphPending;
    if (pending?.watchdog !== undefined) {
      window.clearTimeout(pending.watchdog);
      pending.watchdog = undefined;
    }
    return settleCaretGlyphMotionWithWatchdog();
  };

  // The old microtask fallback ran before WebView2 completed its native edit,
  // cancelling the pending animation before the input event. This short timer is
  // only a safety net for a cancelled beforeinput event.
  beginCaretGlyphMotion = function (event) {
    settleCaretGlyphMotion();
    const skip = skipNextCaretGlyphInput;
    skipNextCaretGlyphInput = false;

    const data = String(event.data ?? '');
    const start = dom.input.selectionStart;
    const end = dom.input.selectionEnd;
    if (
      skip
      || !event.isTrusted
      || event.isComposing
      || event.inputType !== 'insertText'
      || !CARET_GLYPH_SOURCE.test(data)
      || reducedMotion()
      || dom.input.value.length > CARET_GLYPH_MAX_TEXT
      || start === null
      || end === null
      || start !== end
    ) return;

    const mirror = createCaretTypingMirror(dom.input.value);
    const pending = {
      cancelled: false,
      before: dom.input.value,
      start,
      data,
      viewport: mirror.viewport,
      watchdog: undefined,
    };
    caretGlyphPending = pending;
    dom.input.classList.add('caret-glyph-mirroring');

    pending.watchdog = window.setTimeout(() => {
      if (caretGlyphPending === pending) settleCaretGlyphMotion();
    }, CARET_INPUT_WATCHDOG_MS);
  };

  initialize().catch(error => {
    try {
      const pending = state.api?.report_diagnostic(
        'renderer-initialize',
        error?.message || String(error || 'Initialization failed'),
        error?.stack || '',
      );
      pending?.catch?.(() => {});
    } catch (_) {}
    dom.resultValue.textContent = '—';
    dom.resultValue.classList.add('muted');
    dom.resultError.textContent = 'Python API недоступен';
    dom.resultError.classList.remove('hidden');
  });
})();
