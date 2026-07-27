(function () {
  'use strict';

  const MOTION_MARKER = 'nlcalc-motion-v6';
  const IOS_EASE = 'cubic-bezier(.16,1,.3,1)';
  let replayingModeClick = false;
  let modeTransitioning = false;
  let enterSequence = 0;
  let pressedControl = null;

  function reducedMotion() {
    return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  }

  function animateElement(element, keyframes, options) {
    if (!element || reducedMotion() || typeof element.animate !== 'function') return null;
    element.getAnimations?.().forEach(animation => animation.cancel());
    return element.animate(keyframes, options);
  }

  function expressionInput() {
    return document.getElementById('expressionInput');
  }

  function nextFrame() {
    return new Promise(resolve => window.requestAnimationFrame(resolve));
  }

  function animateTyping(event) {
    const input = expressionInput();
    if (!input || event.target !== input || !event.isTrusted || reducedMotion()) return;
    if (event.isComposing || !String(event.inputType || '').startsWith('insert')) return;

    const shell = input.closest('.expression-field-shell') || input;
    animateElement(
      shell,
      [
        { backgroundColor: 'color-mix(in srgb, var(--accent-soft) 34%, transparent)' },
        { backgroundColor: 'transparent' },
      ],
      { duration: 150, easing: IOS_EASE },
    );
  }

  function captureHistoryState() {
    const list = document.getElementById('historyList');
    return {
      list,
      first: list?.firstElementChild || null,
    };
  }

  function createOldValueLayer(input, text) {
    const shell = input.closest('.expression-field-shell') || input.parentElement;
    if (!shell || !text) return null;

    const style = window.getComputedStyle(input);
    const layer = document.createElement('div');
    layer.className = 'nlcalc-enter-old-value';
    layer.textContent = text;
    layer.style.fontFamily = style.fontFamily;
    layer.style.fontSize = style.fontSize;
    layer.style.fontStyle = style.fontStyle;
    layer.style.fontWeight = style.fontWeight;
    layer.style.lineHeight = style.lineHeight;
    layer.style.letterSpacing = style.letterSpacing;
    layer.style.padding = [style.paddingTop, style.paddingRight, style.paddingBottom, style.paddingLeft].join(' ');
    layer.style.left = `${-input.scrollLeft}px`;
    layer.style.top = `${-input.scrollTop}px`;
    if (document.body.dataset.appMode === 'units') layer.style.right = '68px';
    shell.appendChild(layer);
    return layer;
  }

  function animateHistoryInsertion(snapshot) {
    if (!snapshot?.list || document.body.dataset.appMode === 'units') return;
    const inserted = snapshot.list.firstElementChild;
    if (!inserted || inserted === snapshot.first) return;
    animateElement(
      inserted,
      [{ opacity: 0 }, { opacity: 1 }],
      { duration: 220, easing: IOS_EASE },
    );
  }

  async function animateEnterCompletion(snapshot) {
    const input = expressionInput();
    if (!input) return;

    await nextFrame();
    const oldLayer = createOldValueLayer(input, snapshot.value);
    const resultValue = document.getElementById('resultValue');

    const oldAnimation = animateElement(
      oldLayer,
      [{ opacity: .62 }, { opacity: 0 }],
      { duration: 170, easing: 'ease-out', fill: 'both' },
    );
    animateElement(
      input,
      [{ opacity: .62 }, { opacity: 1 }],
      { duration: 210, easing: IOS_EASE },
    );
    animateElement(
      resultValue,
      [{ opacity: .76 }, { opacity: 1 }],
      { duration: 170, easing: IOS_EASE },
    );
    animateHistoryInsertion(snapshot.history);

    Promise.resolve(oldAnimation?.finished).catch(() => {}).finally(() => oldLayer?.remove());
  }

  function waitForInputChange(input, previousValue, sequence) {
    return new Promise(resolve => {
      const startedAt = performance.now();
      const tick = () => {
        if (sequence !== enterSequence) return resolve(false);
        if (input.value !== previousValue) return resolve(true);
        if (performance.now() - startedAt > 650) return resolve(false);
        window.requestAnimationFrame(tick);
      };
      window.requestAnimationFrame(tick);
    });
  }

  function captureEnter(event) {
    const input = expressionInput();
    if (!input || event.target !== input) return;
    if (event.key !== 'Enter' || event.isComposing || event.repeat) return;

    const sequence = ++enterSequence;
    const snapshot = { value: input.value, history: captureHistoryState() };
    waitForInputChange(input, snapshot.value, sequence).then(changed => {
      if (changed) animateEnterCompletion(snapshot);
    });
  }

  function replayModeClick(tab) {
    replayingModeClick = true;
    try { tab.click(); } finally { replayingModeClick = false; }
  }

  function visibleModePanel() {
    if (document.body.dataset.appMode === 'units') {
      return document.getElementById('unitConverterCard');
    }
    return document.querySelector('.history-card:not(.unit-converter-card)');
  }

  function fallbackModeTransition(tab) {
    const outgoing = visibleModePanel();
    const outgoingAnimation = animateElement(
      outgoing,
      [{ opacity: 1 }, { opacity: 0 }],
      { duration: 90, easing: 'ease-in', fill: 'both' },
    );

    Promise.resolve(outgoingAnimation?.finished).catch(() => {}).then(() => {
      replayModeClick(tab);
      window.requestAnimationFrame(() => {
        const incoming = visibleModePanel();
        const incomingAnimation = animateElement(
          incoming,
          [{ opacity: 0 }, { opacity: 1 }],
          { duration: 230, easing: IOS_EASE, fill: 'both' },
        );
        Promise.resolve(incomingAnimation?.finished).catch(() => {}).finally(() => {
          modeTransitioning = false;
        });
      });
    });
  }

  function captureModeClick(event) {
    const tab = event.target?.closest?.('#calculatorModeTab, #unitsModeTab');
    if (!tab || replayingModeClick || tab.classList.contains('active')) return;
    if (modeTransitioning) {
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    if (reducedMotion()) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    modeTransitioning = true;
    fallbackModeTransition(tab);
  }

  function releasePressedControl() {
    const control = pressedControl;
    pressedControl = null;
    if (!control || reducedMotion()) return;
    animateElement(control, [{ opacity: .82 }, { opacity: 1 }], { duration: 140, easing: IOS_EASE });
  }

  function installPressedState() {
    document.addEventListener('pointerdown', event => {
      const control = event.target?.closest?.('button, .converter-select');
      if (!control || reducedMotion()) return;
      pressedControl = control;
      animateElement(control, [{ opacity: 1 }, { opacity: .82 }], { duration: 70, easing: 'ease-out', fill: 'forwards' });
    }, true);
    document.addEventListener('pointerup', releasePressedControl, true);
    document.addEventListener('pointercancel', releasePressedControl, true);
    window.addEventListener('blur', releasePressedControl);
  }

  function install() {
    document.documentElement.dataset.motion = MOTION_MARKER;
    document.addEventListener('input', animateTyping, true);
    document.addEventListener('keydown', captureEnter, true);
    document.addEventListener('click', captureModeClick, true);
    installPressedState();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
})();