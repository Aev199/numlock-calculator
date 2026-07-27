
  // Reference-matched number motion. Native insertion is cancelled during
  // beforeinput; the real textarea is updated only after its visual layers exist.
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
    if (revealInput) dom.input.classList.remove('typing-hidden');
    dom.input.style.removeProperty('opacity');
    document.querySelectorAll(
      '.input-motion-layer.typing-copy, .typing-reveal, .typing-caret-copy',
    ).forEach(node => node.remove());
  }

  // onInput remains the single state/update owner. Typing motion is now fully
  // handled by beforeinput, so its normal callback must not start a second effect.
  typingFeedback = function () {};

  function interceptTextInsertion(event) {
    if (
      !event.isTrusted
      || event.isComposing
      || event.inputType !== 'insertText'
      || !event.cancelable
      || typeof dom.input.animate !== 'function'
    ) return;

    const inserted = String(event.data || '');
    if (!inserted || inserted.includes('\n') || inserted.length > 3 || reducedMotion()) return;

    // Prevent Chromium/WebView2 from ever committing and painting its own first
    // frame. From this point the value change is entirely controlled below.
    event.preventDefault();
    event.stopImmediatePropagation();
    clearTypingMotion(false);

    const oldValue = dom.input.value;
    const start = dom.input.selectionStart ?? oldValue.length;
    const end = dom.input.selectionEnd ?? start;
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
    const nextValue = oldValue.slice(0, start) + inserted + oldValue.slice(end);
    dom.input.value = nextValue;
    setSelection(start + inserted.length);

    let cancelled = false;
    let revealAnimation;
    let caretAnimation;
    let liveFade;
    let oldFade;
    let revealFade;
    const group = {
      cancel() {
        cancelled = true;
        for (const animation of [
          revealAnimation,
          caretAnimation,
          liveFade,
          oldFade,
          revealFade,
        ]) {
          try { animation?.cancel(); } catch (_) {}
        }
        oldLayer.remove();
        reveal.remove();
        caret.remove();
        dom.input.style.removeProperty('opacity');
      },
    };
    state.typingAnimation = group;

    // Update the calculator/converter state exactly once. Assigning .value does
    // not emit an input event, which is intentional because native insertion was
    // cancelled above.
    onInput({
      isTrusted: false,
      isComposing: false,
      inputType: 'insertText',
      data: inserted,
    });

    requestAnimationFrame(() => {
      if (cancelled || state.typingAnimation !== group) return;
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
        dom.input.style.opacity = '0';
        dom.input.classList.remove('typing-hidden');
        liveFade = dom.input.animate(
          [{ opacity: 0 }, { opacity: 1 }],
          { duration: 45, easing: 'linear', fill: 'both' },
        );
        oldFade = oldLayer.animate(
          [{ opacity: 1 }, { opacity: 0 }],
          { duration: 45, easing: 'linear', fill: 'both' },
        );
        revealFade = reveal.animate(
          [{ opacity: 1 }, { opacity: 0 }],
          { duration: 45, easing: 'linear', fill: 'both' },
        );
        Promise.allSettled([liveFade.finished, oldFade.finished, revealFade.finished]).then(() => {
          if (state.typingAnimation !== group) return;
          state.typingAnimation = null;
          dom.input.style.removeProperty('opacity');
          dom.input.classList.remove('typing-hidden');
          oldLayer.remove();
          reveal.remove();
          caret.remove();
        });
      });
    });
  }

  dom.input.addEventListener('beforeinput', interceptTextInsertion, { capture: true });

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

        // Prepare the real value invisibly behind the final overlay, then swap
        // the two in one animation frame. There is never a frame with two fully
        // visible copies or with neither copy visible.
        dom.input.style.opacity = '0';
        dom.input.classList.remove('commit-hidden');
        requestAnimationFrame(() => {
          if (state.commitAnimation !== group) return;
          newLayer.style.opacity = '0';
          dom.input.style.opacity = '1';
          requestAnimationFrame(() => {
            if (state.commitAnimation !== group) return;
            state.commitAnimation = null;
            dom.input.style.removeProperty('opacity');
            oldLayer.remove();
            newLayer.remove();
          });
        });
      });
    }));
  };
