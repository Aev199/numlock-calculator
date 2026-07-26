(function () {
  'use strict';

  const MOTION_MARKER = 'nlcalc-motion-v4';
  const TYPED_GLYPH_PATTERN = /^[0-9.,+\-−*/×÷^()%]+$/;
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

  function number(value, fallback = 0) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function textareaCaretRect(input, index) {
    const inputRect = input.getBoundingClientRect();
    const style = window.getComputedStyle(input);
    const mirror = document.createElement('div');

    const copied = [
      'boxSizing', 'fontFamily', 'fontSize', 'fontStyle', 'fontWeight',
      'fontStretch', 'fontVariant', 'lineHeight', 'letterSpacing',
      'textTransform', 'textIndent', 'textAlign', 'tabSize',
      'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
      'borderTopWidth', 'borderRightWidth', 'borderBottomWidth',
      'borderLeftWidth', 'wordSpacing',
    ];

    mirror.style.position = 'fixed';
    mirror.style.visibility = 'hidden';
    mirror.style.pointerEvents = 'none';
    mirror.style.left = `${inputRect.left - input.scrollLeft}px`;
    mirror.style.top = `${inputRect.top - input.scrollTop}px`;
    mirror.style.width = `${inputRect.width}px`;
    mirror.style.minHeight = `${inputRect.height}px`;
    mirror.style.whiteSpace = 'pre-wrap';
    mirror.style.overflowWrap = 'break-word';
    mirror.style.wordBreak = 'break-word';
    mirror.style.overflow = 'visible';
    mirror.style.zIndex = '-1';
    copied.forEach(property => {
      mirror.style[property] = style[property];
    });

    mirror.textContent = input.value.slice(0, index);
    const marker = document.createElement('span');
    marker.textContent = input.value.slice(index, index + 1) || '\u200b';
    mirror.appendChild(marker);
    document.body.appendChild(mirror);

    const markerRect = marker.getBoundingClientRect();
    const result = {
      left: markerRect.left,
      top: markerRect.top,
      height: markerRect.height || number(style.lineHeight, number(style.fontSize, 16)),
      style,
    };
    mirror.remove();
    return result;
  }

  function trimOldTypedGlyphs() {
    const glyphs = document.querySelectorAll('.nlcalc-typed-glyph');
    for (let index = 0; index < glyphs.length - 8; index += 1) {
      glyphs[index].remove();
    }
  }

  function animateTypedGlyph(event) {
    if (reducedMotion()) return;
    const input = expressionInput();
    if (!input || event.target !== input) return;
    if (event.isComposing || event.inputType !== 'insertText') return;
    const text = String(event.data || '');
    if (!text || text.length > 3 || !TYPED_GLYPH_PATTERN.test(text)) return;

    const caret = input.selectionStart ?? input.value.length;
    const start = Math.max(0, caret - text.length);
    const position = textareaCaretRect(input, start);
    const glyph = document.createElement('span');
    glyph.className = 'nlcalc-typed-glyph';
    glyph.textContent = text;
    glyph.style.left = `${position.left}px`;
    glyph.style.top = `${position.top}px`;
    glyph.style.height = `${position.height}px`;
    glyph.style.fontFamily = position.style.fontFamily;
    glyph.style.fontSize = position.style.fontSize;
    glyph.style.fontStyle = position.style.fontStyle;
    glyph.style.fontWeight = position.style.fontWeight;
    glyph.style.lineHeight = position.style.lineHeight;
    glyph.style.letterSpacing = position.style.letterSpacing;
    document.body.appendChild(glyph);
    trimOldTypedGlyphs();

    const animation = glyph.animate(
      [
        { opacity: 0, transform: 'translateY(5px) scale(.92)' },
        { opacity: .88, offset: .28, transform: 'translateY(0) scale(1.03)' },
        { opacity: 0, transform: 'translateY(-1px) scale(1)' },
      ],
      {
        duration: 170,
        easing: 'cubic-bezier(.22,1,.36,1)',
        fill: 'both',
      },
    );
    animation.finished.catch(() => {}).finally(() => glyph.remove());
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

  function createResultFlight(text, fromRect, input) {
    if (!text || reducedMotion()) return;
    const inputRect = input.getBoundingClientRect();
    const resultValue = document.getElementById('resultValue');
    const sourceStyle = resultValue ? window.getComputedStyle(resultValue) : null;
    const inputStyle = window.getComputedStyle(input);
    const targetLeft = inputRect.left + number(inputStyle.paddingLeft, 6);
    const targetTop = inputRect.top + number(inputStyle.paddingTop, 5);

    const flight = document.createElement('span');
    flight.className = 'nlcalc-enter-flight';
    flight.textContent = text;
    flight.style.left = `${fromRect.left}px`;
    flight.style.top = `${fromRect.top}px`;
    flight.style.fontFamily = sourceStyle?.fontFamily || inputStyle.fontFamily;
    flight.style.fontSize = sourceStyle?.fontSize || inputStyle.fontSize;
    flight.style.fontWeight = sourceStyle?.fontWeight || inputStyle.fontWeight;
    flight.style.lineHeight = sourceStyle?.lineHeight || inputStyle.lineHeight;
    document.body.appendChild(flight);

    const dx = targetLeft - fromRect.left;
    const dy = targetTop - fromRect.top;
    const animation = flight.animate(
      [
        { opacity: .9, transform: 'translate(0, 0) scale(1)' },
        { opacity: .72, offset: .55, transform: `translate(${dx * .72}px, ${dy * .72}px) scale(.91)` },
        { opacity: 0, transform: `translate(${dx}px, ${dy}px) scale(.86)` },
      ],
      {
        duration: 210,
        easing: 'cubic-bezier(.22,1,.36,1)',
        fill: 'both',
      },
    );
    animation.finished.catch(() => {}).finally(() => flight.remove());
  }

  function animateEnterCompletion(snapshot) {
    const input = expressionInput();
    if (!input) return;
    const mode = document.body.dataset.appMode || 'calculator';
    const editorCard = input.closest('.editor-card');
    const resultBlock = document.getElementById('resultBlock');
    const historyList = document.getElementById('historyList');
    const newHistoryRow = historyList?.firstElementChild;

    animateElement(
      input,
      [
        { opacity: .56, transform: 'translateY(3px) scale(.994)' },
        { opacity: 1, transform: 'translateY(0) scale(1)' },
      ],
      { duration: 170, easing: 'cubic-bezier(.22,1,.36,1)' },
    );
    animateElement(
      editorCard,
      [
        { boxShadow: 'var(--card-shadow)' },
        { boxShadow: '0 0 0 3px var(--accent-soft), var(--card-shadow)', offset: .42 },
        { boxShadow: 'var(--card-shadow)' },
      ],
      { duration: 260, easing: 'ease-out' },
    );
    animateElement(
      resultBlock,
      [
        { opacity: .7, transform: 'translateY(-2px)' },
        { opacity: 1, transform: 'translateY(0)' },
      ],
      { duration: 150, easing: 'ease-out' },
    );

    if (
      mode === 'calculator'
      && snapshot.resultText
      && snapshot.resultText.trim() === input.value.trim()
    ) {
      createResultFlight(snapshot.resultText, snapshot.resultRect, input);
    }

    if (
      mode === 'calculator'
      && newHistoryRow
      && newHistoryRow !== snapshot.historyFirst
    ) {
      animateElement(
        newHistoryRow,
        [
          { opacity: 0, transform: 'translateY(-8px) scale(.985)' },
          { opacity: 1, transform: 'translateY(0) scale(1)' },
        ],
        { duration: 190, easing: 'cubic-bezier(.22,1,.36,1)' },
      );
    }
  }

  function captureEnter(event) {
    const input = expressionInput();
    if (!input || event.target !== input) return;
    if (event.key !== 'Enter' || event.isComposing || event.repeat) return;

    const resultValue = document.getElementById('resultValue');
    const historyList = document.getElementById('historyList');
    const sequence = ++enterSequence;
    const snapshot = {
      value: input.value,
      resultText: String(resultValue?.textContent || '').trim(),
      resultRect: resultValue?.getBoundingClientRect() || input.getBoundingClientRect(),
      historyFirst: historyList?.firstElementChild || null,
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

  function fallbackModeTransition(tab) {
    const workspace = document.querySelector('.workspace');
    if (!workspace) {
      replayModeClick(tab);
      return;
    }

    const outgoing = animateElement(
      workspace,
      [
        { opacity: 1, transform: 'translateY(0) scale(1)' },
        { opacity: .68, transform: 'translateY(3px) scale(.997)' },
      ],
      { duration: 80, easing: 'ease-in', fill: 'both' },
    );

    Promise.resolve(outgoing?.finished).catch(() => {}).then(() => {
      replayModeClick(tab);
      window.requestAnimationFrame(() => {
        const incoming = animateElement(
          workspace,
          [
            { opacity: .58, transform: 'translateY(-3px) scale(.997)' },
            { opacity: 1, transform: 'translateY(0) scale(1)' },
          ],
          { duration: 170, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'both' },
        );
        Promise.resolve(incoming?.finished).catch(() => {}).finally(() => {
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

    if (typeof document.startViewTransition === 'function') {
      const transition = document.startViewTransition(() => replayModeClick(tab));
      transition.finished.catch(() => {}).finally(() => {
        modeTransitioning = false;
      });
      return;
    }

    fallbackModeTransition(tab);
  }

  function install() {
    document.documentElement.dataset.motion = MOTION_MARKER;
    document.addEventListener('input', animateTypedGlyph, true);
    document.addEventListener('keydown', captureEnter, true);
    document.addEventListener('click', captureModeClick, true);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
})();
