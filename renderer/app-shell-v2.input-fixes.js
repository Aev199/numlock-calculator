
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

  // The original microtask fallback ran before WebView2 completed its native
  // edit, so the pending animation was cancelled before the input event. A short
  // timer is only a safety net for cancelled beforeinput events; normal native
  // input completes synchronously and clears the pending state first.
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
