
  // A single calculator glyph reveals leftward from the native caret. The live
  // textarea still owns input, selection and caret movement; fixed mirror layers
  // exist only for the brief visual hand-off, preventing first-frame flashes.
  const CARET_GLYPH_DURATION = 128;
  const CARET_GLYPH_MAX_TEXT = 512;
  const CARET_GLYPH_SOURCE = /^[0-9+\-*/.,%^]$/;
  const CARET_GLYPH_FINAL = /^[0-9+\-⋅/.,%^]$/;
  let caretGlyphPending = null;
  let caretGlyphMotion = null;
  let skipNextCaretGlyphInput = false;

  function removeCaretGlyphNode(node) {
    try { node?.remove(); } catch (_) {}
  }

  function reportCaretGlyphFailure(error) {
    try {
      if (typeof reportRendererDiagnostic === 'function') {
        void reportRendererDiagnostic(
          'caret-glyph',
          String(error?.message || error || 'Typing motion failed'),
          String(error?.stack || ''),
        );
      }
    } catch (_) {}
  }

  function settleCaretGlyphMotion() {
    const pending = caretGlyphPending;
    const active = caretGlyphMotion;
    caretGlyphPending = null;
    caretGlyphMotion = null;

    if (pending) {
      pending.cancelled = true;
      removeCaretGlyphNode(pending.viewport);
    }
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
    return { viewport, hiddenSpan, box };
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

  function handOffCaretGlyph(active) {
    if (active.cancelled || caretGlyphMotion !== active) return;
    if (active.hiddenSpan) active.hiddenSpan.style.opacity = '1';
    active.glyph.style.opacity = '0';

    requestAnimationFrame(() => {
      if (active.cancelled || caretGlyphMotion !== active) return;
      dom.input.classList.remove('caret-glyph-mirroring');
      active.viewport.style.opacity = '0';
      requestAnimationFrame(() => {
        if (caretGlyphMotion === active) caretGlyphMotion = null;
        removeCaretGlyphNode(active.viewport);
        removeCaretGlyphNode(active.glyph);
      });
    });
  }

  function beginCaretGlyphMotion(event) {
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
    };
    caretGlyphPending = pending;
    dom.input.classList.add('caret-glyph-mirroring');

    // A cancelled beforeinput has no matching input event. Restore native text in
    // the same task, before the browser has a chance to paint a stale mirror.
    queueMicrotask(() => {
      if (caretGlyphPending === pending) settleCaretGlyphMotion();
    });
  }

  function completeCaretGlyphMotion(event) {
    const pending = caretGlyphPending;
    if (!pending) return;

    const finalText = dom.input.value;
    const insertion = singleCaretInsertion(pending.before, finalText);
    if (
      pending.cancelled
      || event.isComposing
      || !insertion
      || (dom.input.selectionStart ?? insertion.end) !== insertion.end
    ) {
      settleCaretGlyphMotion();
      return;
    }

    const startPoint = caretPoint(insertion.start);
    const endPoint = caretPoint(insertion.end);
    const lineHeight = Number.parseFloat(startPoint.style.lineHeight || '0')
      || Number.parseFloat(startPoint.style.fontSize || '18') * 1.45;
    const width = endPoint.left - startPoint.left;
    if (
      !Number.isFinite(width)
      || width <= 0
      || Math.abs(endPoint.top - startPoint.top) > lineHeight * .35
    ) {
      settleCaretGlyphMotion();
      return;
    }

    const mirror = createCaretTypingMirror(
      finalText,
      insertion.start,
      insertion.end,
    );
    removeCaretGlyphNode(pending.viewport);
    caretGlyphPending = null;

    const glyph = document.createElement('span');
    glyph.className = 'nlcalc-caret-glyph';
    glyph.textContent = insertion.text;
    Object.assign(glyph.style, {
      left: `${startPoint.left}px`,
      top: `${startPoint.top}px`,
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
    active.animation = glyph.animate(
      [
        {
          opacity: .18,
          clipPath: 'inset(0 0 0 100%)',
          transform: 'translate3d(1.1px,0,0) scaleX(.84)',
        },
        {
          opacity: 1,
          offset: .72,
          clipPath: 'inset(0 0 0 10%)',
          transform: 'translate3d(.12px,0,0) scaleX(.99)',
        },
        {
          opacity: 1,
          clipPath: 'inset(0 0 0 0)',
          transform: 'translate3d(0,0,0) scaleX(1)',
        },
      ],
      {
        duration: CARET_GLYPH_DURATION,
        easing: 'cubic-bezier(.2,.82,.2,1)',
        fill: 'both',
      },
    );
    active.animation.finished.then(
      () => handOffCaretGlyph(active),
      () => {},
    );
  }

  const baseOnInputCaretMotion = onInput;
  onInput = function (event) {
    baseOnInputCaretMotion(event);
    try {
      completeCaretGlyphMotion(event);
    } catch (error) {
      settleCaretGlyphMotion();
      reportCaretGlyphFailure(error);
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
  }, { capture: true });
  dom.input.addEventListener('pointerdown', settleCaretGlyphMotion, { capture: true });
  dom.input.addEventListener('scroll', settleCaretGlyphMotion, { passive: true });
  dom.input.addEventListener('blur', settleCaretGlyphMotion);
  window.addEventListener('resize', settleCaretGlyphMotion, { passive: true });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) settleCaretGlyphMotion();
  });
