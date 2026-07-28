
  // Present implicit multiplication explicitly without changing the backend
  // expression grammar. This function is also used for history and clipboard.
  const displayExpressionWithoutImplicitMultiply = displayExpression;
  displayExpression = function (value) {
    const visual = displayExpressionWithoutImplicitMultiply(value);
    return visual.replace(/([0-9)])\s*(?=\()/g, `$1${DISPLAY_MULTIPLY}`);
  };

  // A single calculator glyph reveals leftward from the new native caret. The
  // browser remains the only owner of editing, selection, undo and composition.
  // We remember the pre-edit snapshot on keydown/beforeinput and also keep an
  // input-only fallback for WebView2 builds that omit beforeinput.
  const CARET_GLYPH_DURATION = 190;
  const CARET_GLYPH_MAX_TEXT = 512;
  const CARET_GLYPH_SOURCE = /^[0-9+\-*/.,%^]$/;
  const CARET_GLYPH_FINAL = /^[0-9+\-⋅/.,%^]$/;
  let caretGlyphPending = null;
  let caretGlyphMotion = null;
  let skipNextCaretGlyphInput = false;
  let caretInputSnapshot = {
    value: dom.input.value,
    start: dom.input.selectionStart ?? 0,
    end: dom.input.selectionEnd ?? 0,
  };

  // The user explicitly requested this local typing effect. Keep it enabled even
  // when Windows globally reduces decorative motion; other application motion
  // continues to respect prefers-reduced-motion.
  document.body.dataset.typingMotion = 'full';

  function removeCaretGlyphNode(node) {
    try { node?.remove(); } catch (_) {}
  }

  function reportCaretGlyphFailure(error) {
    try {
      const pending = state.api?.report_diagnostic(
        'caret-glyph',
        String(error?.message || error || 'Typing motion failed'),
        String(error?.stack || ''),
      );
      pending?.catch?.(() => {});
    } catch (_) {}
  }

  function syncCaretInputSnapshot() {
    caretInputSnapshot = {
      value: dom.input.value,
      start: dom.input.selectionStart ?? dom.input.value.length,
      end: dom.input.selectionEnd ?? dom.input.selectionStart ?? dom.input.value.length,
    };
  }

  function settleCaretGlyphMotion() {
    const active = caretGlyphMotion;
    caretGlyphPending = null;
    caretGlyphMotion = null;

    if (active) {
      active.cancelled = true;
      try { active.animation?.cancel(); } catch (_) {}
      removeCaretGlyphNode(active.viewport);
      removeCaretGlyphNode(active.glyph);
    }
    dom.input.classList.remove('caret-glyph-mirroring');
  }

  function appendCaretMirrorExpression(container, text, hiddenStart = -1, hiddenEnd = -1) {
    let plainStart = 0;
    let depth = 0;
    const stack = [];
    let hiddenSpan = null;

    const appendPlain = end => {
      if (end > plainStart) {
        container.appendChild(document.createTextNode(text.slice(plainStart, end)));
      }
    };

    for (let index = 0; index < text.length; index += 1) {
      const char = text[index];
      const hidden = index >= hiddenStart && index < hiddenEnd;
      const bracket = char === '(' || char === ')';
      if (!hidden && !bracket) continue;

      appendPlain(index);
      const span = document.createElement('span');
      span.textContent = char;
      const classes = [];

      if (bracket) {
        let bracketDepth;
        if (char === '(') {
          bracketDepth = depth;
          stack.push(depth);
          depth += 1;
        } else {
          depth = Math.max(0, depth - 1);
          bracketDepth = stack.length ? stack.pop() : depth;
        }
        classes.push('bracket', `depth-${Math.abs(bracketDepth) % 6}`);
      }
      if (hidden) {
        classes.push('nlcalc-typing-static-hidden');
        hiddenSpan = span;
      }
      span.className = classes.join(' ');
      container.appendChild(span);
      plainStart = index + 1;
    }
    appendPlain(text.length);
    return hiddenSpan;
  }

  function createCaretTypingMirror(text, hiddenStart = -1, hiddenEnd = -1) {
    const box = inputContentRect();
    const viewport = document.createElement('div');
    viewport.className = 'nlcalc-typing-mirror';
    Object.assign(viewport.style, {
      left: `${box.left}px`,
      top: `${box.top}px`,
      width: `${box.width}px`,
      height: `${box.height}px`,
    });

    const content = document.createElement('div');
    content.className = 'nlcalc-typing-mirror-text';
    Object.assign(content.style, {
      width: `${box.width}px`,
      fontFamily: box.style.fontFamily,
      fontSize: box.style.fontSize,
      fontWeight: box.style.fontWeight,
      fontStyle: box.style.fontStyle,
      lineHeight: box.style.lineHeight,
      letterSpacing: box.style.letterSpacing,
      textAlign: box.style.textAlign,
      direction: box.style.direction,
      tabSize: box.style.tabSize,
      transform: `translate3d(${-dom.input.scrollLeft}px, ${-dom.input.scrollTop}px, 0)`,
    });
    const hiddenSpan = appendCaretMirrorExpression(
      content,
      String(text ?? ''),
      hiddenStart,
      hiddenEnd,
    );
    viewport.appendChild(content);
    document.body.appendChild(viewport);
    return { viewport, hiddenSpan };
  }

  function singleCaretInsertion(before, after) {
    let start = 0;
    while (
      start < before.length
      && start < after.length
      && before[start] === after[start]
    ) start += 1;

    let beforeEnd = before.length;
    let afterEnd = after.length;
    while (
      beforeEnd > start
      && afterEnd > start
      && before[beforeEnd - 1] === after[afterEnd - 1]
    ) {
      beforeEnd -= 1;
      afterEnd -= 1;
    }

    if (beforeEnd !== start) return null;
    const inserted = after.slice(start, afterEnd);
    if (inserted.length !== 1 || !CARET_GLYPH_FINAL.test(inserted)) return null;
    return { start, end: afterEnd, text: inserted };
  }

  function measureCaretGlyphWidth(text, style) {
    const probe = document.createElement('span');
    probe.textContent = text;
    Object.assign(probe.style, {
      position: 'fixed',
      left: '-10000px',
      top: '-10000px',
      visibility: 'hidden',
      whiteSpace: 'pre',
      fontFamily: style.fontFamily,
      fontSize: style.fontSize,
      fontWeight: style.fontWeight,
      fontStyle: style.fontStyle,
      letterSpacing: style.letterSpacing,
    });
    document.body.appendChild(probe);
    const width = probe.getBoundingClientRect().width;
    probe.remove();
    return width;
  }

  function handOffCaretGlyph(active) {
    if (active.cancelled || caretGlyphMotion !== active) return;
    if (active.hiddenSpan) active.hiddenSpan.style.opacity = '1';
    active.glyph.style.opacity = '0';

    requestAnimationFrame(() => {
      if (active.cancelled || caretGlyphMotion !== active) return;
      dom.input.classList.remove('caret-glyph-mirroring');
      removeCaretGlyphNode(active.viewport);
      removeCaretGlyphNode(active.glyph);
      caretGlyphMotion = null;
    });
  }

  function beginCaretGlyphMotion(event, fallbackData = '') {
    settleCaretGlyphMotion();
    const skip = skipNextCaretGlyphInput;
    skipNextCaretGlyphInput = false;

    const data = String(event?.data ?? fallbackData ?? '');
    const start = dom.input.selectionStart;
    const end = dom.input.selectionEnd;
    const inputType = String(event?.inputType || 'insertText');
    if (
      skip
      || event?.isTrusted === false
      || event?.isComposing
      || inputType !== 'insertText'
      || !CARET_GLYPH_SOURCE.test(data)
      || dom.input.value.length > CARET_GLYPH_MAX_TEXT
      || start === null
      || end === null
      || start !== end
    ) return;

    caretGlyphPending = {
      before: dom.input.value,
      start,
      end,
      data,
    };
  }

  function pendingFromSnapshot(event) {
    const data = String(event?.data ?? '');
    if (
      event?.isTrusted === false
      || event?.isComposing
      || String(event?.inputType || '') !== 'insertText'
      || !CARET_GLYPH_SOURCE.test(data)
      || caretInputSnapshot.start !== caretInputSnapshot.end
    ) return null;
    return {
      before: caretInputSnapshot.value,
      start: caretInputSnapshot.start,
      end: caretInputSnapshot.end,
      data,
    };
  }

  function completeCaretGlyphMotion(event, pending) {
    caretGlyphPending = null;
    if (!pending || event?.isComposing || event?.isTrusted === false) return;

    const finalText = dom.input.value;
    const insertion = singleCaretInsertion(pending.before, finalText);
    if (
      !insertion
      || insertion.start !== pending.start
      || (dom.input.selectionStart ?? insertion.end) !== insertion.end
    ) return;

    const startPoint = caretPoint(insertion.start);
    const endPoint = caretPoint(insertion.end);
    const lineHeight = Number.parseFloat(startPoint.style.lineHeight || '0')
      || Number.parseFloat(startPoint.style.fontSize || '18') * 1.45;
    let width = endPoint.left - startPoint.left;
    if (!Number.isFinite(width) || width <= 0) {
      width = measureCaretGlyphWidth(insertion.text, startPoint.style);
    }
    if (
      !Number.isFinite(width)
      || width <= 0
      || Math.abs(endPoint.top - startPoint.top) > lineHeight * .35
    ) return;

    const mirror = createCaretTypingMirror(
      finalText,
      insertion.start,
      insertion.end,
    );
    dom.input.classList.add('caret-glyph-mirroring');

    const glyph = document.createElement('span');
    glyph.className = 'nlcalc-caret-glyph';
    glyph.textContent = insertion.text;
    Object.assign(glyph.style, {
      left: `${endPoint.left - width}px`,
      top: `${endPoint.top}px`,
      width: `${width}px`,
      fontFamily: startPoint.style.fontFamily,
      fontSize: startPoint.style.fontSize,
      fontWeight: startPoint.style.fontWeight,
      fontStyle: startPoint.style.fontStyle,
      lineHeight: startPoint.style.lineHeight,
      letterSpacing: startPoint.style.letterSpacing,
      textAlign: 'left',
      clipPath: 'inset(0 0 0 100%)',
      opacity: '0',
    });
    document.body.appendChild(glyph);

    const active = {
      cancelled: false,
      viewport: mirror.viewport,
      hiddenSpan: mirror.hiddenSpan,
      glyph,
      animation: null,
    };
    caretGlyphMotion = active;

    if (typeof glyph.animate !== 'function') {
      handOffCaretGlyph(active);
      return;
    }

    active.animation = glyph.animate(
      [
        {
          opacity: .08,
          clipPath: 'inset(0 0 0 100%)',
          transform: 'translate3d(3.4px,0,0) scaleX(.62)',
        },
        {
          opacity: 1,
          offset: .7,
          clipPath: 'inset(0 0 0 9%)',
          transform: 'translate3d(.18px,0,0) scaleX(.99)',
        },
        {
          opacity: 1,
          clipPath: 'inset(0 0 0 0)',
          transform: 'translate3d(0,0,0) scaleX(1)',
        },
      ],
      {
        duration: CARET_GLYPH_DURATION,
        easing: 'cubic-bezier(.16,.86,.22,1)',
        fill: 'both',
      },
    );
    active.animation.finished.then(
      () => handOffCaretGlyph(active),
      () => {},
    );
  }

  const baseSetInputValueCaretMotion = setInputValue;
  setInputValue = function (value, selection = null) {
    settleCaretGlyphMotion();
    baseSetInputValueCaretMotion(value, selection);
    syncCaretInputSnapshot();
  };

  const baseOnInputCaretMotion = onInput;
  onInput = function (event) {
    const pending = caretGlyphPending || pendingFromSnapshot(event);
    baseOnInputCaretMotion(event);
    try {
      completeCaretGlyphMotion(event, pending);
    } catch (error) {
      settleCaretGlyphMotion();
      reportCaretGlyphFailure(error);
    } finally {
      syncCaretInputSnapshot();
    }
  };

  dom.input.addEventListener('beforeinput', event => {
    try {
      beginCaretGlyphMotion(event);
    } catch (error) {
      settleCaretGlyphMotion();
      reportCaretGlyphFailure(error);
    }
  }, { capture: true });

  document.addEventListener('keydown', event => {
    if (event.target !== dom.input) return;
    settleCaretGlyphMotion();
    skipNextCaretGlyphInput = Boolean(
      event.repeat && CARET_GLYPH_SOURCE.test(String(event.key || '')),
    );
    if (
      event.defaultPrevented
      || event.ctrlKey
      || event.metaKey
      || event.altKey
      || event.isComposing
      || event.repeat
      || !CARET_GLYPH_SOURCE.test(String(event.key || ''))
    ) return;
    try {
      beginCaretGlyphMotion(event, event.key);
    } catch (error) {
      settleCaretGlyphMotion();
      reportCaretGlyphFailure(error);
    }
  }, { capture: true });

  dom.input.addEventListener('compositionstart', settleCaretGlyphMotion, { capture: true });
  dom.input.addEventListener('compositionend', syncCaretInputSnapshot, { capture: true });
  dom.input.addEventListener('pointerdown', settleCaretGlyphMotion, { capture: true });
  dom.input.addEventListener('pointerup', syncCaretInputSnapshot, { capture: true });
  dom.input.addEventListener('keyup', syncCaretInputSnapshot, { capture: true });
  dom.input.addEventListener('select', syncCaretInputSnapshot, { capture: true });
  dom.input.addEventListener('scroll', settleCaretGlyphMotion, { passive: true });
  dom.input.addEventListener('blur', () => {
    settleCaretGlyphMotion();
    syncCaretInputSnapshot();
  });
  window.addEventListener('resize', settleCaretGlyphMotion, { passive: true });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) settleCaretGlyphMotion();
  });
