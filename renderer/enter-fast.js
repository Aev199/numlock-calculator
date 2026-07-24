(function () {
  'use strict';

  const ENTER_FAST_MARKER = 'nlcalc-enter-fast';
  const patchedApis = new WeakSet();
  let cachedPreview = {
    expression: '',
    result: '',
  };

  function normalizeExpression(value) {
    return String(value || '').trim();
  }

  function rememberPreview(expression, evaluation) {
    const normalized = normalizeExpression(expression);
    if (evaluation?.ok && evaluation.result !== undefined && evaluation.result !== null) {
      cachedPreview = {
        expression: normalized,
        result: String(evaluation.result).trim(),
      };
    } else if (cachedPreview.expression === normalized) {
      cachedPreview = { expression: normalized, result: '' };
    }
    return evaluation;
  }

  function cachedResultFor(expression) {
    const normalized = normalizeExpression(expression);
    if (!normalized || cachedPreview.expression !== normalized) return '';
    return cachedPreview.result;
  }

  function applyResultToEditor(input, originalExpression, result) {
    if (!input || normalizeExpression(input.value) !== originalExpression) return;

    input.value = result;
    input.focus({ preventScroll: true });
    const end = input.value.length;
    input.setSelectionRange(end, end);

    // Keep script-v2.js selection/history state synchronized with the optimistic
    // replacement. The normal commit continues in parallel with the original text.
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function wrapApi(api) {
    if (!api || patchedApis.has(api)) return api;
    if (typeof api.preview !== 'function' || typeof api.commit !== 'function') return api;

    const originalPreview = api.preview.bind(api);
    const originalCommit = api.commit.bind(api);

    const fastPreview = async expression => rememberPreview(
      expression,
      await originalPreview(expression),
    );

    const fastCommit = async expression => {
      const response = await originalCommit(expression);
      if (!response?.ok || response.result === undefined || response.result === null) {
        return response;
      }

      const result = String(response.result).trim();
      cachedPreview = { expression: result, result };

      // script-v2.js writes evaluation.expression back into the editor after the
      // await. Returning the result here preserves the original expression inside
      // history_entry while making the editor behave like a classic calculator.
      return {
        ...response,
        expression: result,
      };
    };

    let methodsPatched = false;
    try {
      api.preview = fastPreview;
      api.commit = fastCommit;
      methodsPatched = api.preview === fastPreview && api.commit === fastCommit;
    } catch (_) {
      methodsPatched = false;
    }

    patchedApis.add(api);
    if (methodsPatched) return api;

    try {
      const proxy = new Proxy(api, {
        get(target, property, receiver) {
          if (property === 'preview') return fastPreview;
          if (property === 'commit') return fastCommit;
          return Reflect.get(target, property, receiver);
        },
      });
      patchedApis.add(proxy);
      if (window.pywebview?.api === api) window.pywebview.api = proxy;
      return proxy;
    } catch (_) {
      return api;
    }
  }

  function installBridgePatch() {
    if (window.pywebview?.api) wrapApi(window.pywebview.api);
    window.addEventListener(
      'pywebviewready',
      () => wrapApi(window.pywebview?.api),
      { once: true },
    );
  }

  function installEditorHandler() {
    const input = document.getElementById('expressionInput');
    if (!input) return;

    input.addEventListener('keydown', event => {
      if (event.key !== 'Enter' || event.isComposing) return;

      const expression = normalizeExpression(input.value);
      const result = cachedResultFor(expression);
      if (!expression || !result) return;

      // The existing keydown handler must first read the original expression and
      // start api.commit(). A microtask then updates the editor before the browser
      // paints, removing the visible bridge/storage delay.
      window.queueMicrotask(() => {
        applyResultToEditor(input, expression, result);
      });
    }, true);
  }

  function install() {
    document.documentElement.dataset.enterFast = ENTER_FAST_MARKER;
    installEditorHandler();
  }

  installBridgePatch();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
})();
