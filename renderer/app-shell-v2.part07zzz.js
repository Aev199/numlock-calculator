
  // Character input stays completely native. Only Enter uses temporary visual
  // layers; the textarea is never intercepted or rewritten for ordinary typing.
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

  // Disable every earlier decorative typing hook while preserving the normal
  // input handler, preview updates, completion and function wrapping.
  typingFeedback = function () {};

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
