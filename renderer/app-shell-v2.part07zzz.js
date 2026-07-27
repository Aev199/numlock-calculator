
  // Reference-matched number motion. Typing is prepared during beforeinput so
  // WebView2 never paints the inserted glyph before the reveal animation.
  function inputContentRect() {
    const rect = dom.input.getBoundingClientRect();
    const style = getComputedStyle(dom.input);
    const paddingLeft = Number.parseFloat(style.paddingLeft || '0');
    const paddingTop = Number.parseFloat(style.paddingTop || '0');
    return {
      left: rect.left + paddingLeft,
      top: rect.top + paddingTop,
      width: Math.max(1, rect.width - paddingLeft - Number.parseFloat(style.paddingRight || '0')),
      height: Math.max(1, rect.height - paddingTop - Number.parseFloat(style.paddingBottom || '0')),
      style,
    };
  }

  function makeInputTextLayer(text, className = '') {
    const box = inputContentRect();
    const layer = document.createElement('div');
    layer.className = `input-motion-layer ${className}`.trim();
    layer.textContent = text;
    Object.assign(layer.style, {
      left: `${box.left}px`,
      top: `${box.top}px`,
      width: `${box.width}px`,
      minHeight: `${box.height}px`,
      font: box.style.font,
      letterSpacing: box.style.letterSpacing,
      lineHeight: box.style.lineHeight,
      textAlign: box.style.textAlign,
      whiteSpace: 'pre-wrap',
      overflowWrap: 'break-word',
    });
    document.body.appendChild(layer);
    return layer;
  }

  function measuredTextWidth(text, style) {
    const canvas = measuredTextWidth.canvas || (
      measuredTextWidth.canvas = document.createElement('canvas')
    );
    const context = canvas.getContext('2d');
    context.font = style.font;
    const spacing = Number.parseFloat(style.letterSpacing || '0');
    return Math.max(1, context.measureText(text).width + spacing * Math.max(0, text.length - 1));
  }

  function clearTypingMotion(revealInput = true) {
    const active = state.typingAnimation;
    state.typingAnimation = null;
    if (active) {
      try { active.cancel(); } catch (_) {}
    }
    state.pendingTypingMotion = null;
    if (revealInput) dom.input.classList.remove('typing-hidden');
    document.querySelectorAll(
      '.input-motion-layer.typing-copy, .typing-reveal, .typing-caret-copy',
    ).forEach(node => node.remove());
  }

  function prepareTypingMotion(event) {
    if (!event.isTrusted || event.isComposing || event.inputType !== 'insertText') return;
    const inserted = String(event.data || '');
    if (!inserted || inserted.includes('\n') || inserted.length > 3 || reducedMotion()) return;

    // beforeinput runs before textarea.value changes. Hide the live control in
    // this same task so Chromium cannot paint the final glyph for one frame.
    clearTypingMotion(false);
    const start = dom.input.selectionStart ?? dom.input.value.length;
    const oldValue = dom.input.value;
    const point = caretPoint(start);
    const oldLayer = makeInputTextLayer(oldValue, 'typing-copy');
    const width = measuredTextWidth(inserted, point.style);

    const reveal = document.createElement('span');
    reveal.className = 'typing-reveal';
    Object.assign(reveal.style, {
      left: `${point.left}px`,
      top: `${point.top}px`,
      width: '0px',
      height: point.style.lineHeight,
      font: point.style.font,
      letterSpacing: point.style.letterSpacing,
      lineHeight: point.style.lineHeight,
    });
    const glyph = document.createElement('span');
    glyph.textContent = inserted;
    reveal.appendChild(glyph);

    const caret = document.createElement('span');
    caret.className = 'typing-caret-copy';
    Object.assign(caret.style, {
      left: `${point.left}px`,
      top: `${point.top}px`,
      height: point.style.lineHeight,
    });
    document.body.append(reveal, caret);
    dom.input.classList.add('typing-hidden');
    state.pendingTypingMotion = { inserted, start, width, oldLayer, reveal, caret };
  }

  dom.input.addEventListener('beforeinput', prepareTypingMotion, { capture: true });

  typingFeedback = function (event) {
    const pending = state.pendingTypingMotion;
    if (!pending || event.inputType !== 'insertText') {
      clearTypingMotion();
      return;
    }
    state.pendingTypingMotion = null;

    let cancelled = false;
    let revealAnimation;
    let caretAnimation;
    const { oldLayer, reveal, caret, width } = pending;
    const group = {
      cancel() {
        cancelled = true;
        try { revealAnimation?.cancel(); } catch (_) {}
        try { caretAnimation?.cancel(); } catch (_) {}
        oldLayer.remove();
        reveal.remove();
        caret.remove();
      },
    };
    state.typingAnimation = group;

    // Layers already exist before the value mutation. Starting immediately in
    // the input task preserves the visual order: old text -> reveal -> real text.
    revealAnimation = reveal.animate(
      [
        { width: '0px', opacity: 1 },
        { width: `${width}px`, opacity: 1 },
      ],
      { duration: 175, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'both' },
    );
    caretAnimation = caret.animate(
      [
        { transform: 'translate3d(0,0,0)', opacity: 1 },
        { transform: `translate3d(${width}px,0,0)`, opacity: 1 },
      ],
      { duration: 175, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'both' },
    );
    Promise.allSettled([revealAnimation.finished, caretAnimation.finished]).then(() => {
      if (cancelled || state.typingAnimation !== group) return;
      // Crossfade the visual copy into the live textarea instead of removing it
      // on the same frame.
      dom.input.style.opacity = '0';
      dom.input.classList.remove('typing-hidden');
      const liveFade = dom.input.animate(
        [{ opacity: 0 }, { opacity: 1 }],
        { duration: 55, easing: 'linear', fill: 'both' },
      );
      const copyFade = reveal.animate(
        [{ opacity: 1 }, { opacity: 0 }],
        { duration: 55, easing: 'linear', fill: 'both' },
      );
      oldLayer.animate(
        [{ opacity: 1 }, { opacity: 0 }],
        { duration: 55, easing: 'linear', fill: 'both' },
      );
      Promise.allSettled([liveFade.finished, copyFade.finished]).then(() => {
        if (state.typingAnimation !== group) return;
        dom.input.style.removeProperty('opacity');
        clearTypingMotion();
      });
    });
  };

  const cancelReferenceCommitMotion = cancelCommitAnimation;
  cancelCommitAnimation = function () {
    cancelReferenceCommitMotion();
    document.querySelectorAll('.input-motion-layer.commit-outgoing, .input-motion-layer.commit-incoming')
      .forEach(node => node.remove());
    dom.input.classList.remove('commit-hidden');
    dom.input.style.removeProperty('opacity');
  };

  animateCommit = function (result) {
    cancelCommitAnimation();
    clearTypingMotion();
    if (reducedMotion() || !result) return;
    const pending = state.calculator.history.find(entry => entry.pending);
    const outgoing = pending?.expression || state.calculator.historyDraft || '';
    if (!outgoing) return;

    const oldLayer = makeInputTextLayer(outgoing, 'commit-outgoing');
    const newLayer = makeInputTextLayer(result, 'commit-incoming');
    dom.input.classList.add('commit-hidden');

    let cancelled = false;
    let oldAnimation;
    let newAnimation;
    const group = {
      cancel() {
        cancelled = true;
        try { oldAnimation?.cancel(); } catch (_) {}
        try { newAnimation?.cancel(); } catch (_) {}
        oldLayer.remove();
        newLayer.remove();
        dom.input.classList.remove('commit-hidden');
        dom.input.style.removeProperty('opacity');
      },
    };
    state.commitAnimation = group;

    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (cancelled) return;
      oldAnimation = oldLayer.animate(
        [
          { opacity: 1, transform: 'translate3d(0,0,0)' },
          { opacity: .72, offset: .5, transform: 'translate3d(0,-8px,0)' },
          { opacity: 0, transform: 'translate3d(0,-22px,0)' },
        ],
        { duration: 330, easing: 'cubic-bezier(.4,0,.2,1)', fill: 'both' },
      );
      newAnimation = newLayer.animate(
        [
          { opacity: 0, transform: 'translate3d(0,22px,0)' },
          { opacity: 1, offset: .76, transform: 'translate3d(0,-1px,0)' },
          { opacity: 1, transform: 'translate3d(0,0,0)' },
        ],
        { duration: 330, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'both' },
      );
      Promise.allSettled([oldAnimation.finished, newAnimation.finished]).then(() => {
        if (state.commitAnimation !== group) return;
        // Avoid the bright duplicate frame: the real textarea fades in while the
        // final overlay fades out, preserving constant perceived opacity.
        dom.input.style.opacity = '0';
        dom.input.classList.remove('commit-hidden');
        const liveFade = dom.input.animate(
          [{ opacity: 0 }, { opacity: 1 }],
          { duration: 75, easing: 'linear', fill: 'both' },
        );
        const overlayFade = newLayer.animate(
          [{ opacity: 1 }, { opacity: 0 }],
          { duration: 75, easing: 'linear', fill: 'both' },
        );
        Promise.allSettled([liveFade.finished, overlayFade.finished]).then(() => {
          if (state.commitAnimation !== group) return;
          state.commitAnimation = null;
          dom.input.style.removeProperty('opacity');
          oldLayer.remove();
          newLayer.remove();
        });
      });
    }));
  };
