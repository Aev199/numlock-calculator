(function () {
  'use strict';

  const POLISH_MARKER = 'nlcalc-polish-v3';
  const AMBIGUOUS_WRAP_DELAY = 240;
  const FUNCTION_FALLBACK = [
    'sin', 'cos', 'tan', 'asin', 'acos', 'atan',
    'sqrt', 'cbrt', 'ln', 'log', 'log10', 'exp',
    'fact', 'factorial', 'abs', 'floor', 'ceil', 'round',
    'min', 'max', 'mean', 'sum',
  ];

  const functionNames = new Set(FUNCTION_FALLBACK);
  let composing = false;
  let pendingVisualTimer = null;
  let ambiguousWrapTimer = null;

  function expressionInput() {
    return document.getElementById('expressionInput');
  }

  function resultBlock() {
    return document.getElementById('resultBlock');
  }

  function reducedMotion() {
    return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  }

  function animateElement(element, keyframes, options) {
    if (!element || reducedMotion() || typeof element.animate !== 'function') return;
    element.getAnimations?.().forEach(animation => animation.cancel());
    element.animate(keyframes, options);
  }

  function markPreviewPending() {
    const block = resultBlock();
    if (!block) return;
    block.classList.add('is-pending');
    window.clearTimeout(pendingVisualTimer);
    pendingVisualTimer = window.setTimeout(
      () => block.classList.remove('is-pending'),
      320,
    );
  }

  function settlePreview() {
    resultBlock()?.classList.remove('is-pending');
    window.clearTimeout(pendingVisualTimer);
  }

  function installResultAnimations() {
    const value = document.getElementById('resultValue');
    const error = document.getElementById('resultError');
    const status = document.getElementById('statusText');

    if (value) {
      new MutationObserver(() => {
        settlePreview();
        animateElement(
          value,
          [
            { opacity: 0.48, transform: 'translateY(3px)' },
            { opacity: 1, transform: 'translateY(0)' },
          ],
          { duration: 150, easing: 'cubic-bezier(.22,1,.36,1)' },
        );
      }).observe(value, { childList: true, characterData: true, subtree: true });
    }

    if (error) {
      new MutationObserver(() => {
        if (error.classList.contains('hidden') || !error.textContent) return;
        settlePreview();
        animateElement(
          error,
          [
            { opacity: 0, transform: 'translateY(-2px)' },
            { opacity: 1, transform: 'translateY(0)' },
          ],
          { duration: 140, easing: 'ease-out' },
        );
      }).observe(error, { childList: true, characterData: true, subtree: true });
    }

    if (status) {
      new MutationObserver(() => {
        animateElement(
          status,
          [{ opacity: 0.45 }, { opacity: 1 }],
          { duration: 130, easing: 'ease-out' },
        );
      }).observe(status, { childList: true, characterData: true, subtree: true });
    }
  }

  function patchBridge(api) {
    if (!api || api.__nlcalcPolishV3) return;

    try {
      Object.defineProperty(api, '__nlcalcPolishV3', {
        value: true,
        configurable: false,
        enumerable: false,
      });
    } catch (_) {
      try { api.__nlcalcPolishV3 = true; } catch (_) { /* read-only proxy */ }
    }

    if (typeof api.suggestions !== 'function') return;

    const originalSuggestions = api.suggestions.bind(api);
    let catalog = [];
    let catalogPromise = null;
    let catalogExpiresAt = 0;

    function updateFunctionNames(items) {
      items
        .filter(item => item?.kind === 'function')
        .forEach(item => functionNames.add(String(item.label || '').toLowerCase()));
    }

    function loadCatalog(force = false) {
      const now = Date.now();
      if (!force && catalog.length && now < catalogExpiresAt) {
        return Promise.resolve(catalog);
      }
      if (!force && catalogPromise) return catalogPromise;

      catalogPromise = Promise.resolve(originalSuggestions(''))
        .then(items => {
          catalog = Array.isArray(items) ? items : [];
          catalogExpiresAt = Date.now() + 30000;
          updateFunctionNames(catalog);
          return catalog;
        })
        .finally(() => {
          catalogPromise = null;
        });
      return catalogPromise;
    }

    function filterCatalog(items, query) {
      const needle = String(query || '').trim().toLowerCase();
      if (!needle) return items.slice();
      return items.filter(item => [
        item?.label,
        item?.insert,
        item?.description,
        item?.group,
        item?.kind,
      ].some(value => String(value || '').toLowerCase().includes(needle)));
    }

    const cachedSuggestions = async query => filterCatalog(
      await loadCatalog(),
      query,
    );

    let methodPatched = false;
    try {
      api.suggestions = cachedSuggestions;
      methodPatched = api.suggestions === cachedSuggestions;
    } catch (_) {
      methodPatched = false;
    }

    if (!methodPatched && window.pywebview?.api === api) {
      try {
        window.pywebview.api = new Proxy(api, {
          get(target, property, receiver) {
            if (property === 'suggestions') return cachedSuggestions;
            return Reflect.get(target, property, receiver);
          },
        });
      } catch (_) {
        // Preloading still supplies the function list when the API object is fixed.
      }
    }

    function invalidateAfter(methodName) {
      if (typeof api[methodName] !== 'function') return;
      const original = api[methodName].bind(api);
      try {
        api[methodName] = async (...args) => {
          const response = await original(...args);
          catalogExpiresAt = 0;
          return response;
        };
      } catch (_) {
        // Read-only API proxy; the short TTL remains a safe fallback.
      }
    }

    invalidateAfter('commit');
    invalidateAfter('commit_and_insert');
    invalidateAfter('set_memory');
    loadCatalog().catch(() => {});
  }

  function installBridgePatch() {
    if (window.pywebview?.api) patchBridge(window.pywebview.api);
    window.addEventListener(
      'pywebviewready',
      () => patchBridge(window.pywebview?.api),
      { once: true },
    );
  }

  function tokenBeforeCursor(input) {
    const cursor = input.selectionStart ?? input.value.length;
    if ((input.selectionEnd ?? cursor) !== cursor) return null;
    const before = input.value.slice(0, cursor);
    const match = before.match(/[A-Za-z_][A-Za-z0-9_]*$/);
    if (!match) return null;
    return {
      name: match[0],
      start: cursor - match[0].length,
      cursor,
    };
  }

  function hasLongerFunctionPrefix(name) {
    const normalized = name.toLowerCase();
    return [...functionNames].some(candidate => (
      candidate !== normalized && candidate.startsWith(normalized)
    ));
  }

  function pulseFunctionWrap(input) {
    markPreviewPending();
    animateElement(
      input.closest('.editor-card'),
      [
        { boxShadow: 'var(--card-shadow)' },
        { boxShadow: '0 0 0 3px var(--accent-soft), var(--card-shadow)' },
        { boxShadow: 'var(--card-shadow)' },
      ],
      { duration: 240, easing: 'ease-out' },
    );
  }

  function wrapTokenNow(input, token, dispatchInput = false) {
    const fresh = tokenBeforeCursor(input);
    if (!fresh || fresh.name.toLowerCase() !== token.name.toLowerCase()) return;
    if (fresh.cursor !== token.cursor || input.value[fresh.cursor] === '(') return;

    input.setRangeText('()', fresh.cursor, fresh.cursor, 'end');
    input.setSelectionRange(fresh.cursor + 1, fresh.cursor + 1);
    pulseFunctionWrap(input);

    if (dispatchInput) {
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  function wrapTypedFunction(event) {
    const input = expressionInput();
    if (!input || event.target !== input) return;
    if (composing || event.isComposing) return;
    if (event.inputType !== 'insertText' || !event.data) return;
    if (!/^[A-Za-z]$/.test(event.data)) return;

    window.clearTimeout(ambiguousWrapTimer);
    const token = tokenBeforeCursor(input);
    if (!token || !functionNames.has(token.name.toLowerCase())) return;
    if (input.value[token.cursor] === '(') return;

    if (hasLongerFunctionPrefix(token.name)) {
      ambiguousWrapTimer = window.setTimeout(
        () => wrapTokenNow(input, token, true),
        AMBIGUOUS_WRAP_DELAY,
      );
      return;
    }

    wrapTokenNow(input, token);
  }

  function handlePairedParenthesis(event) {
    const input = expressionInput();
    if (!input || event.target !== input) return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;

    const start = input.selectionStart ?? 0;
    const end = input.selectionEnd ?? start;
    if (start !== end) return;

    if (
      event.key === '('
      && input.value[start - 1] === '('
      && input.value[start] === ')'
    ) {
      event.preventDefault();
      return;
    }

    if (event.key === ')' && input.value[start] === ')') {
      event.preventDefault();
      input.setSelectionRange(start + 1, start + 1);
    }
  }

  function installEditorPolish() {
    const input = expressionInput();
    if (!input) return;

    input.addEventListener('compositionstart', () => {
      composing = true;
      window.clearTimeout(ambiguousWrapTimer);
    }, true);
    input.addEventListener('compositionend', () => { composing = false; }, true);
    input.addEventListener('input', event => {
      markPreviewPending();
      wrapTypedFunction(event);
    }, true);
    input.addEventListener('keydown', handlePairedParenthesis, true);

    for (const id of ['angleMode', 'numberBase', 'themeButton']) {
      document.getElementById(id)?.addEventListener('click', event => {
        animateElement(
          event.currentTarget,
          [
            { transform: 'scale(1)' },
            { transform: 'scale(.94)' },
            { transform: 'scale(1)' },
          ],
          { duration: 150, easing: 'cubic-bezier(.22,1,.36,1)' },
        );
      });
    }
  }

  function install() {
    document.documentElement.dataset.polish = POLISH_MARKER;
    installEditorPolish();
    installResultAnimations();
  }

  installBridgePatch();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
})();
