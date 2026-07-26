(function () {
  'use strict';

  const MOTION_MARKER = 'nlcalc-motion-v5';
  const IOS_EASE = 'cubic-bezier(.16,1,.3,1)';
  const SETTLE_EASE = 'cubic-bezier(.2,.8,.2,1)';
  const typingAnimations = new WeakMap();
  let replayingModeClick = false;
  let modeTransitioning = false;
  let enterSequence = 0;

  function reducedMotion() {
    return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  }

  function animateElement(element, keyframes, options) {
    if (!element || reducedMotion() || typeof element.animate !== 'function') {
      return null;
    }
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

    const length = Math.max(1, input.value.length);
    const cursor = input.selectionStart ?? length;
    const origin = Math.max(0, Math.min(100, (cursor / length) * 100));
    input.style.transformOrigin = `${origin}% 50%`;

    typingAnimations.get(input)?.cancel();
    const animation = animateElement(
      input,
      [
        { opacity: .9, transform: 'scale(.998)', filter: 'brightness(1.035)' },
        { opacity: 1, transform: 'scale(1)', filter: 'brightness(1)' },
      ],
      { duration: 125, easing: IOS_EASE },
    );
    if (animation) typingAnimations.set(input, animation);
  }

  function captureHistoryLayout() {
    const list = document.getElementById('historyList');
    const rows = list ? [...list.querySelectorAll('.history-entry')] : [];
    return {
      list,
      rows,
      rects: new Map(rows.map(row => [row, row.getBoundingClientRect()])),
      first: rows[0] || null,
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
    layer.style.padding = [
      style.paddingTop,
      style.paddingRight,
      style.paddingBottom,
      style.paddingLeft,
    ].join(' ');
    layer.style.left = `${-input.scrollLeft}px`;
    layer.style.top = `${-input.scrollTop}px`;
    if (document.body.dataset.appMode === 'units') layer.style.right = '68px';
    shell.appendChild(layer);
    return layer;
  }

  function animateHistoryInsertion(snapshot) {
    if (!snapshot?.list || document.body.dataset.appMode === 'units') return;
    const currentRows = [...snapshot.list.querySelectorAll('.history-entry')];

    for (const row of snapshot.rows) {
      if (!row.isConnected) continue;
      const before = snapshot.rects.get(row);
      const after = row.getBoundingClientRect();
      const deltaY = before ? before.top - after.top : 0;
      if (Math.abs(deltaY) < .5) continue;
      animateElement(
        row,
        [
          { transform: `translateY(${deltaY}px)` },
          { transform: 'translateY(0)' },
        ],
        { duration: 260, easing: IOS_EASE },
      );
    }

    const inserted = currentRows.find(row => !snapshot.rects.has(row));
    if (inserted) {
      animateElement(
        inserted,
        [
          { opacity: 0, transform: 'translateY(-6px) scale(.992)' },
          { opacity: 1, transform: 'translateY(0) scale(1)' },
        ],
        { duration: 230, easing: IOS_EASE },
      );
    }
  }

  async function animateEnterCompletion(snapshot) {
    const input = expressionInput();
    if (!input) return;

    await nextFrame();
    const oldLayer = createOldValueLayer(input, snapshot.value);
    const resultValue = document.getElementById('resultValue');
    const resultBlock = document.getElementById('resultBlock');

    const oldAnimation = animateElement(
      oldLayer,
      [
        { opacity: .56, transform: 'translateY(0) scale(1)' },
        { opacity: 0, transform: 'translateY(-5px) scale(.992)' },
      ],
      { duration: 210, easing: SETTLE_EASE, fill: 'both' },
    );
    animateElement(
      input,
      [
        { opacity: .58, transform: 'translateY(5px) scale(.995)' },
        { opacity: 1, transform: 'translateY(0) scale(1)' },
      ],
      { duration: 250, easing: IOS_EASE },
    );
    animateElement(
      resultValue,
      [
        { opacity: .72, transform: 'translateY(2px)' },
        { opacity: 1, transform: 'translateY(0)' },
      ],
      { duration: 180, easing: IOS_EASE },
    );
    animateElement(
      resultBlock,
      [
        { filter: 'brightness(1.035)' },
        { filter: 'brightness(1)' },
      ],
      { duration: 220, easing: SETTLE_EASE },
    );
    animateHistoryInsertion(snapshot.history);

    Promise.resolve(oldAnimation?.finished)
      .catch(() => {})
      .finally(() => oldLayer?.remove());
  }

  function waitForInputChange(input, previousValue, sequence) {
    return new Promise(resolve => {
      const startedAt = performance.now();
      const tick = () => {
        if (sequence !== enterSequence) {
          resolve(false);
          return;
        }
        if (input.value !== previousValue) {
          resolve(true);
          return;
        }
        if (performance.now() - startedAt > 650) {
          resolve(false);
          return;
        }
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
    const snapshot = {
      value: input.value,
      history: captureHistoryLayout(),
    };
    waitForInputChange(input, snapshot.value, sequence).then(changed => {
      if (changed) animateEnterCompletion(snapshot);
    });
  }

  function replayModeClick(tab) {
    replayingModeClick = true;
    try {
      tab.click();
    } finally {
      replayingModeClick = false;
    }
  }

  function visibleModePanel() {
    if (document.body.dataset.appMode === 'units') {
      return document.getElementById('unitConverterCard');
    }
    return document.querySelector('.history-card:not(.unit-converter-card)');
  }

  function animateSharedEditor() {
    const editor = document.querySelector('.editor-card');
    const toolbar = editor?.querySelector('.editor-toolbar');
    const result = editor?.querySelector('.result-block');
    for (const element of [toolbar, result]) {
      animateElement(
        element,
        [
          { opacity: .72, transform: 'translateY(3px)' },
          { opacity: 1, transform: 'translateY(0)' },
        ],
        { duration: 230, easing: IOS_EASE },
      );
    }
  }

  function fallbackModeTransition(tab) {
    const outgoing = visibleModePanel();
    const outgoingAnimation = animateElement(
      outgoing,
      [
        { opacity: 1, transform: 'translateY(0) scale(1)' },
        { opacity: .58, transform: 'translateY(4px) scale(.995)' },
      ],
      { duration: 85, easing: 'ease-in', fill: 'both' },
    );

    Promise.resolve(outgoingAnimation?.finished).catch(() => {}).then(() => {
      replayModeClick(tab);
      window.requestAnimationFrame(() => {
        const incoming = visibleModePanel();
        animateElement(
          incoming,
          [
            { opacity: .42, transform: 'translateY(-5px) scale(.995)' },
            { opacity: 1, transform: 'translateY(0) scale(1)' },
          ],
          { duration: 270, easing: IOS_EASE, fill: 'both' },
        );
        animateSharedEditor();
        window.setTimeout(() => { modeTransitioning = false; }, 280);
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

    if (typeof document.startViewTransition === 'function') {
      const transition = document.startViewTransition(() => replayModeClick(tab));
      transition.finished.catch(() => {}).finally(() => {
        modeTransitioning = false;
      });
      return;
    }

    fallbackModeTransition(tab);
  }

  function installPressedState() {
    document.addEventListener('pointerdown', event => {
      const control = event.target?.closest?.('button, .converter-select');
      if (!control || reducedMotion()) return;
      animateElement(
        control,
        [
          { transform: 'scale(1)' },
          { transform: 'scale(.975)' },
        ],
        { duration: 90, easing: 'ease-out', fill: 'forwards' },
      );
    }, true);
    document.addEventListener('pointerup', event => {
      const control = event.target?.closest?.('button, .converter-select');
      if (!control || reducedMotion()) return;
      animateElement(
        control,
        [
          { transform: 'scale(.975)' },
          { transform: 'scale(1)' },
        ],
        { duration: 180, easing: IOS_EASE },
      );
    }, true);
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