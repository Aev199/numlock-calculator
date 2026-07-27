    reconcileHistory();
    bindEvents();
    setInputValue(state.calculator.expression);
    renderResult(null);
    restoreEditorFocus();
    await state.api.window_focus_changed(document.hasFocus());
  }

  /* Final motion controller overrides. They run inside the same consolidated
     closure, so the rest of the UI still has one event/store owner. */
  const baseSwitchMode = switchMode;

  animateCommit = function (result) {
    cancelCommitAnimation();
    if (typeof dom.commitOverlay.animate !== 'function') return;

    const sourceRect = dom.resultValue.getBoundingClientRect();
    const targetRect = dom.input.getBoundingClientRect();
    if (!sourceRect.width || !targetRect.width) return;

    const sourceStyle = getComputedStyle(dom.resultValue);
    const targetStyle = getComputedStyle(dom.input);
    const targetLeft = targetRect.left + Number.parseFloat(targetStyle.paddingLeft || '0');
    const targetTop = targetRect.top + Number.parseFloat(targetStyle.paddingTop || '0');
    const sourceFont = Number.parseFloat(sourceStyle.fontSize || '20');
    const targetFont = Number.parseFloat(targetStyle.fontSize || '16');
    const scale = sourceFont ? targetFont / sourceFont : 1;
    const dx = targetLeft - sourceRect.left;
    const dy = targetTop - sourceRect.top;

    dom.commitOverlay.textContent = result;
    dom.commitOverlay.style.left = `${sourceRect.left}px`;
    dom.commitOverlay.style.top = `${sourceRect.top}px`;
    dom.commitOverlay.style.fontFamily = sourceStyle.fontFamily;
    dom.commitOverlay.style.fontSize = sourceStyle.fontSize;
    dom.commitOverlay.style.fontWeight = sourceStyle.fontWeight;
    dom.commitOverlay.style.lineHeight = sourceStyle.lineHeight;
    dom.commitOverlay.classList.add('active');
    dom.input.classList.add('commit-hidden');

    /* Give WebView2 one complete paint with the overlay at its source before
       starting the compositor animation. This removes the initial jump. */
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const animation = dom.commitOverlay.animate(
        [
          {
            opacity: 0,
            transform: 'translate3d(0, 3px, 0) scale(1)',
          },
          {
            opacity: 1,
            offset: .14,
            transform: 'translate3d(0, 0, 0) scale(1)',
          },
          {
            opacity: 1,
            offset: .78,
            transform: `translate3d(${dx}px, ${dy}px, 0) scale(${scale})`,
          },
          {
            opacity: 0,
            transform: `translate3d(${dx}px, ${dy}px, 0) scale(${scale})`,
          },
        ],
        {
          duration: 430,
          easing: 'cubic-bezier(.2,.72,.18,1)',
          fill: 'both',
        },
      );
      state.commitAnimation = animation;
      animation.finished.catch(() => {}).finally(() => {
        if (state.commitAnimation === animation) cancelCommitAnimation();
      });
    }));
  };

  switchMode = function (mode) {
    if (!['calculator', 'units'].includes(mode) || mode === state.mode) return;

    const indicator = byId('modeIndicator');
    const outgoing = state.mode === 'calculator' ? dom.calculatorPanel : dom.unitsPanel;
    const incoming = mode === 'calculator' ? dom.calculatorPanel : dom.unitsPanel;
    const oldIndicatorTransform = indicator ? getComputedStyle(indicator).transform : 'none';

    baseSwitchMode(mode);

    /* CSS state is applied first; animate isolated presentation layers from the
       previous visual state on the following frame. */
    requestAnimationFrame(() => {
      if (indicator?.animate) {
        const newIndicatorTransform = getComputedStyle(indicator).transform;
        indicator.animate(
          [
            { transform: oldIndicatorTransform },
            { transform: newIndicatorTransform },
          ],
          {
            duration: 360,
            easing: 'cubic-bezier(.2,.82,.2,1)',
          },
        );
      }

      if (incoming?.animate) {
        incoming.animate(
          [
            { opacity: 0, transform: 'translate3d(0, 7px, 0)' },
            { opacity: 1, transform: 'translate3d(0, 0, 0)' },
          ],
          {
            duration: 300,
            easing: 'cubic-bezier(.2,.72,.2,1)',
          },
        );
      }

      /* Keep the outgoing card visible only as a fading snapshot. It does not
         receive pointer events and is hidden again when the animation ends. */
      if (outgoing?.animate) {
        outgoing.style.visibility = 'visible';
        outgoing.style.pointerEvents = 'none';
        const fade = outgoing.animate(
          [
            { opacity: 1, transform: 'translate3d(0, 0, 0)' },
            { opacity: 0, transform: 'translate3d(0, -5px, 0)' },
          ],
          {
            duration: 210,
            easing: 'cubic-bezier(.4,0,.8,.2)',
          },
        );
        fade.finished.catch(() => {}).finally(() => {
          outgoing.style.visibility = '';
          outgoing.style.pointerEvents = '';
        });
      }
    });
  };

  initialize().catch(() => {
    dom.resultValue.textContent = '—';
    dom.resultValue.classList.add('muted');
    dom.resultError.textContent = 'Python API недоступен';
    dom.resultError.classList.remove('hidden');
  });
})();