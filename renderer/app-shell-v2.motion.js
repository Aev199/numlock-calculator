  // Feedback motion: short, transform and opacity only, never in the way of
  // typing. Every effect is skipped when Windows asks for reduced motion.
  const MOTION_EASE = 'cubic-bezier(.2, .8, .2, 1)';

  function play(element, keyframes, duration) {
    if (!element || reducedMotion() || typeof element.animate !== 'function') return;
    element.animate(keyframes, { duration, easing: MOTION_EASE });
  }

  function accent(alpha) {
    const rgb = getComputedStyle(document.body).getPropertyValue('--accent-rgb').trim() || '82, 109, 255';
    return `rgba(${rgb}, ${alpha})`;
  }

  function glowBackground(element) {
    play(element, [{ backgroundColor: accent(0.16) }, { backgroundColor: accent(0) }], 360);
  }

  function glowRing(element) {
    play(element, [{ boxShadow: `0 0 0 3px ${accent(0.35)}` }, { boxShadow: `0 0 0 3px ${accent(0)}` }], 360);
  }

  // Enter: the result settles into place.
  const commitCalculatorWithoutMotion = commitCalculator;
  commitCalculator = function commitCalculatorWithMotion() {
    const before = dom.input.value;
    const pending = commitCalculatorWithoutMotion();
    if (dom.input.value !== before) {
      play(dom.resultValue, [
        { opacity: 0.35, transform: 'translateY(4px)' },
        { opacity: 1, transform: 'none' },
      ], 140);
    }
    return pending;
  };

  // Ctrl+C: what was copied lights up where it is.
  const copyCurrentCalculationWithoutMotion = copyCurrentCalculation;
  copyCurrentCalculation = async function copyCurrentCalculationWithMotion() {
    const started = performance.now();
    const result = await copyCurrentCalculationWithoutMotion();
    if ((state.lastCopiedAt || 0) >= started) glowBackground(byId('resultBlock'));
    return result;
  };

  // Insert from history: the field and the source row answer together.
  const insertHistoryResultWithoutMotion = insertHistoryResult;
  insertHistoryResult = function insertHistoryResultWithMotion(entry) {
    const result = insertHistoryResultWithoutMotion(entry);
    if (entry && !entry.pending) {
      glowRing(dom.input);
      glowBackground(state.calculator.historyNodes.get(entry.id)?.querySelector('.history-entry'));
    }
    return result;
  };

  // Theme and accent changes flow instead of flipping every colour at once.
  function blendColours() {
    if (reducedMotion()) return;
    const root = document.documentElement;
    root.classList.add('colour-blend');
    window.clearTimeout(state.colourBlendTimer);
    state.colourBlendTimer = window.setTimeout(() => root.classList.remove('colour-blend'), 200);
  }

  const setThemeWithoutBlend = setTheme;
  setTheme = function setThemeWithBlend(theme, persist = true) {
    if (persist) blendColours();
    return setThemeWithoutBlend(theme, persist);
  };

  const chooseAccentWithoutBlend = chooseAccent;
  chooseAccent = function chooseAccentWithBlend(accent, focus = false) {
    blendColours();
    return chooseAccentWithoutBlend(accent, focus);
  };
