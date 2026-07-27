
  // Physical-key typing path for Windows WebView2. beforeinput is not guaranteed
  // to run before the first native paint on every installed runtime, so printable
  // keys are cancelled at keydown and routed through the controlled insertion
  // pipeline that already owns the caret-reveal animation.
  const MOTION_INPUT_RUNTIME = 'keydown-v2';
  document.documentElement.dataset.motionInputRuntime = MOTION_INPUT_RUNTIME;
  window.__NLCALC_MOTION_INPUT_RUNTIME__ = MOTION_INPUT_RUNTIME;

  function shouldInterceptPrintableKey(event) {
    if (
      event.target !== dom.input
      || !event.isTrusted
      || event.isComposing
      || event.defaultPrevented
      || !event.cancelable
      || event.ctrlKey
      || event.metaKey
      || event.altKey
      || typeof event.key !== 'string'
      || event.key.length !== 1
      || typeof dom.input.animate !== 'function'
      || reducedMotion()
    ) return false;

    // Preserve the calculator's existing convenience behavior: typing a closing
    // parenthesis over an existing one advances the caret instead of inserting.
    const start = dom.input.selectionStart ?? 0;
    const end = dom.input.selectionEnd ?? start;
    if (event.key === ')' && start === end && dom.input.value[start] === ')') {
      return false;
    }
    return true;
  }

  function interceptPhysicalKey(event) {
    if (!shouldInterceptPrintableKey(event)) return;

    const inserted = event.key;
    event.preventDefault();
    event.stopImmediatePropagation();

    // Reuse the same controlled insertion path, but feed it a synthetic
    // beforeinput-shaped record. The physical key has already been cancelled,
    // therefore WebView2 has no native value mutation left to paint.
    interceptTextInsertion({
      isTrusted: true,
      isComposing: false,
      inputType: 'insertText',
      cancelable: true,
      data: inserted,
      preventDefault() {},
      stopImmediatePropagation() {},
    });
  }

  dom.input.addEventListener('keydown', interceptPhysicalKey, { capture: true });
