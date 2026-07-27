
  // Motion refinements: animate isolated visual copies, never the live textarea.
  function caretPoint(index) {
    const input = dom.input;
    const rect = input.getBoundingClientRect();
    const style = getComputedStyle(input);
    const mirror = document.createElement('div');
    Object.assign(mirror.style, {
      position: 'fixed',
      zIndex: '-1',
      visibility: 'hidden',
      pointerEvents: 'none',
      left: `${rect.left}px`,
      top: `${rect.top}px`,
      width: `${rect.width}px`,
      height: `${rect.height}px`,
      overflow: 'hidden',
      whiteSpace: 'pre-wrap',
      overflowWrap: 'break-word',
      wordBreak: 'break-word',
      boxSizing: style.boxSizing,
      padding: style.padding,
      border: style.border,
      font: style.font,
      letterSpacing: style.letterSpacing,
      lineHeight: style.lineHeight,
      tabSize: style.tabSize,
    });
    mirror.textContent = input.value.slice(0, Math.max(0, index));
    const marker = document.createElement('span');
    marker.textContent = '\u200b';
    mirror.appendChild(marker);
    document.body.appendChild(mirror);
    const markerRect = marker.getBoundingClientRect();
    mirror.remove();
    return {
      left: markerRect.left - input.scrollLeft,
      top: markerRect.top - input.scrollTop,
      style,
    };
  }

  function animateInsertedGlyph(text, insertionStart) {
    if (!text || reducedMotion()) return;
    const printable = String(text).replace(/[\r\n]/g, '');
    if (!printable || printable.length > 6) return;
    const point = caretPoint(insertionStart);
    const glyph = document.createElement('span');
    glyph.className = 'typing-glyph';
    glyph.textContent = printable;
    Object.assign(glyph.style, {
      left: `${point.left}px`,
      top: `${point.top}px`,
      font: point.style.font,
      letterSpacing: point.style.letterSpacing,
      lineHeight: point.style.lineHeight,
    });
    document.body.appendChild(glyph);
    const animation = glyph.animate(
      [
        { opacity: 0, transform: 'translate3d(-2px,7px,0) scale(.86)' },
        { opacity: 1, offset: .58, transform: 'translate3d(0,0,0) scale(1)' },
        { opacity: 0, transform: 'translate3d(0,-1px,0) scale(1)' },
      ],
      {
        duration: 240,
        easing: 'cubic-bezier(.18,.78,.2,1)',
        fill: 'both',
      },
    );
    animation.finished.catch(() => {}).finally(() => glyph.remove());
  }

  typingFeedback = function (event) {
    if (!event.isTrusted || event.isComposing) return;
    if (!String(event.inputType || '').startsWith('insert')) return;
    const data = String(event.data || '');
    const end = dom.input.selectionStart ?? dom.input.value.length;
    const start = Math.max(0, end - data.length);
    animateInsertedGlyph(data, start);
  };

  cancelCommitAnimation = function () {
    const active = state.commitAnimation;
    state.commitAnimation = null;
    if (active) {
      try { active.cancel(); } catch (_) {}
    }
    dom.input.classList.remove('commit-hidden');
    dom.resultValue.classList.remove('commit-source-hidden');
    document.querySelectorAll('.commit-roll-layer').forEach(node => node.remove());
  };

  function makeRollLayer(text, rect, style, className) {
    const layer = document.createElement('div');
    layer.className = `commit-roll-layer ${className}`;
    layer.textContent = text;
    Object.assign(layer.style, {
      left: `${rect.left}px`,
      top: `${rect.top}px`,
      maxWidth: `${Math.max(1, rect.width)}px`,
      fontFamily: style.fontFamily,
      fontSize: style.fontSize,
      fontWeight: style.fontWeight,
      lineHeight: style.lineHeight,
      letterSpacing: style.letterSpacing,
    });
    document.body.appendChild(layer);
    return layer;
  }

  animateCommit = function (oldValue, newValue) {
    cancelCommitAnimation();
    if (reducedMotion() || !oldValue || !newValue) return;

    const inputRect = dom.input.getBoundingClientRect();
    const resultRect = dom.resultValue.getBoundingClientRect();
    const inputStyle = getComputedStyle(dom.input);
    const resultStyle = getComputedStyle(dom.resultValue);
    const inputOrigin = {
      left: inputRect.left + Number.parseFloat(inputStyle.paddingLeft || '0'),
      top: inputRect.top + Number.parseFloat(inputStyle.paddingTop || '0'),
      width: Math.max(1, inputRect.width - 12),
      height: Number.parseFloat(inputStyle.lineHeight || inputStyle.fontSize || '20'),
    };
    if (!inputRect.width || !resultRect.width) return;

    const oldLayer = makeRollLayer(oldValue, inputOrigin, inputStyle, 'outgoing');
    const newLayer = makeRollLayer(newValue, resultRect, resultStyle, 'incoming');
    dom.input.classList.add('commit-hidden');
    dom.resultValue.classList.add('commit-source-hidden');

    const targetScale = (
      Number.parseFloat(inputStyle.fontSize || '16')
      / Math.max(1, Number.parseFloat(resultStyle.fontSize || '24'))
    );
    const dx = inputOrigin.left - resultRect.left;
    const dy = inputOrigin.top - resultRect.top;
    let oldAnimation;
    let newAnimation;
    let cancelled = false;

    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (cancelled) return;
      oldAnimation = oldLayer.animate(
        [
          { opacity: 1, transform: 'translate3d(0,0,0) rotateX(0deg)' },
          { opacity: .7, offset: .48, transform: 'translate3d(0,-8px,0) rotateX(16deg)' },
          { opacity: 0, transform: 'translate3d(0,-20px,0) rotateX(42deg)' },
        ],
        { duration: 430, easing: 'cubic-bezier(.2,.7,.2,1)', fill: 'both' },
      );
      newAnimation = newLayer.animate(
        [
          { opacity: .15, transform: 'translate3d(0,8px,0) scale(1)' },
          { opacity: 1, offset: .72, transform: `translate3d(${dx}px,${dy}px,0) scale(${targetScale})` },
          { opacity: 1, transform: `translate3d(${dx}px,${dy}px,0) scale(${targetScale})` },
        ],
        { duration: 430, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'both' },
      );
      Promise.allSettled([oldAnimation.finished, newAnimation.finished]).then(() => {
        if (state.commitAnimation === group) cancelCommitAnimation();
      });
    }));

    const group = {
      cancel() {
        cancelled = true;
        try { oldAnimation?.cancel(); } catch (_) {}
        try { newAnimation?.cancel(); } catch (_) {}
        oldLayer.remove();
        newLayer.remove();
      },
    };
    state.commitAnimation = group;
  };

  function settleModePanels() {
    const calculator = state.mode === 'calculator';
    for (const [panel, active] of [
      [dom.calculatorPanel, calculator],
      [dom.unitsPanel, !calculator],
    ]) {
      panel.getAnimations().forEach(animation => animation.cancel());
      panel.classList.toggle('active', active);
      panel.style.removeProperty('z-index');
      panel.style.removeProperty('pointer-events');
    }
  }

  switchMode = function (mode) {
    if (!['calculator', 'units'].includes(mode) || mode === state.mode) return;
    cancelCommitAnimation();
    hideCompletion();
    const previousMode = state.mode;
    const outgoing = previousMode === 'calculator' ? dom.calculatorPanel : dom.unitsPanel;
    const incoming = mode === 'calculator' ? dom.calculatorPanel : dom.unitsPanel;
    const direction = mode === 'units' ? -1 : 1;

    if (previousMode === 'calculator') {
      state.calculator.expression = dom.input.value;
      ++state.calculator.previewSequence;
    } else {
      state.units.expression = dom.input.value;
      ++state.units.previewSequence;
      persistUnitsSoon();
    }

    state.mode = mode;
    document.body.dataset.appMode = mode;
    const calculator = mode === 'calculator';
    dom.calculatorTab.classList.toggle('active', calculator);
    dom.unitsTab.classList.toggle('active', !calculator);
    dom.calculatorTab.setAttribute('aria-selected', String(calculator));
    dom.unitsTab.setAttribute('aria-selected', String(!calculator));
    dom.editorLabel.textContent = calculator ? 'Выражение' : 'Исходное значение';
    dom.input.placeholder = calculator
      ? 'Например: (120 + 30) / 5'
      : 'Например: (100 + 25) / 2';
    dom.input.setAttribute(
      'aria-label',
      calculator ? 'Введите выражение' : 'Введите исходное значение',
    );

    if (calculator) {
      setInputValue(state.calculator.expression);
      const currentPreview = (
        state.calculator.previewExpression === state.calculator.expression
      ) ? state.calculator.preview : null;
      renderResult(currentPreview);
      scheduleCalculatorPreview(0);
    } else {
      importCalculatorHandoff();
      renderUnitControls();
      setInputValue(state.units.expression);
      const currentPreview = (
        state.units.previewExpression === state.units.expression
        && state.units.previewContext === unitContext()
      ) ? state.units.preview : null;
      renderResult(currentPreview);
      scheduleUnitsPreview(0);
    }

    incoming.classList.add('active');
    outgoing.classList.add('active');
    incoming.setAttribute('aria-hidden', 'false');
    outgoing.setAttribute('aria-hidden', 'true');
    incoming.style.zIndex = '2';
    outgoing.style.zIndex = '1';
    incoming.style.pointerEvents = 'none';
    outgoing.style.pointerEvents = 'none';

    if (reducedMotion() || typeof incoming.animate !== 'function') {
      settleModePanels();
      restoreEditorFocus();
      return;
    }

    const distance = 44;
    const outgoingAnimation = outgoing.animate(
      [
        { opacity: 1, transform: 'translate3d(0,0,0)' },
        { opacity: 0, transform: `translate3d(${direction * distance}px,0,0)` },
      ],
      { duration: 360, easing: 'cubic-bezier(.4,0,.6,1)', fill: 'both' },
    );
    const incomingAnimation = incoming.animate(
      [
        { opacity: 0, transform: `translate3d(${-direction * distance}px,0,0)` },
        { opacity: 1, transform: 'translate3d(0,0,0)' },
      ],
      { duration: 360, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'both' },
    );
    Promise.allSettled([outgoingAnimation.finished, incomingAnimation.finished]).then(() => {
      settleModePanels();
    });
    restoreEditorFocus();
  };
