
  // Long expressions stay on one physical line. These cues make hidden text
  // discoverable without introducing arrows, extra controls or wrapping.
  const EXPRESSION_SCROLL_EPSILON = 1;

  function updateExpressionScrollHints() {
    const maxScrollLeft = Math.max(0, dom.input.scrollWidth - dom.input.clientWidth);
    const scrollLeft = Math.max(0, dom.input.scrollLeft);
    const hasLeft = scrollLeft > EXPRESSION_SCROLL_EPSILON;
    const hasRight = maxScrollLeft - scrollLeft > EXPRESSION_SCROLL_EPSILON;

    dom.fieldShell.classList.toggle('has-scroll-left', hasLeft);
    dom.fieldShell.classList.toggle('has-scroll-right', hasRight);
  }

  const baseSetInputValueScrollHints = setInputValue;
  setInputValue = function (...args) {
    const changed = baseSetInputValueScrollHints(...args);
    window.requestAnimationFrame(updateExpressionScrollHints);
    return changed;
  };

  dom.input.addEventListener('input', updateExpressionScrollHints);
  dom.input.addEventListener('scroll', updateExpressionScrollHints, { passive: true });
  window.addEventListener('resize', updateExpressionScrollHints, { passive: true });

  if (typeof ResizeObserver === 'function') {
    const expressionScrollHintObserver = new ResizeObserver(updateExpressionScrollHints);
    expressionScrollHintObserver.observe(dom.input);
  }

  window.requestAnimationFrame(updateExpressionScrollHints);
