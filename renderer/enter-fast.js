(function () {
  'use strict';

  const ENTER_FAST_MARKER = 'nlcalc-enter-fast';
  const patchedApis = new WeakSet();
  const pendingHistory = [];
  let optimisticSequence = 0;
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

  function shortTimeNow() {
    return new Date().toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function currentModeMeta() {
    const parts = [];
    const angle = String(document.getElementById('angleMode')?.textContent || '')
      .trim()
      .toUpperCase();
    const base = String(document.getElementById('numberBase')?.textContent || '')
      .trim()
      .toUpperCase();
    if (angle && angle !== 'DEG') parts.push(angle);
    if (base && base !== 'DEC') parts.push(base);
    parts.push(shortTimeNow());
    return parts.filter(Boolean).join(' · ');
  }

  function historyQueryMatches(expression, result) {
    const query = String(document.getElementById('historySearch')?.value || '')
      .trim()
      .toLowerCase();
    if (!query) return true;
    return `${expression} ${result}`.toLowerCase().includes(query);
  }

  function updateHistoryCounter(delta) {
    const counter = document.getElementById('historyCounter');
    if (!counter) return;
    const current = Number.parseInt(counter.textContent || '0', 10);
    counter.textContent = String(Math.max(0, (Number.isFinite(current) ? current : 0) + delta));
  }

  function loadExpressionIntoEditor(expression) {
    const input = document.getElementById('expressionInput');
    if (!input) return;
    input.value = expression;
    input.focus({ preventScroll: true });
    const end = input.value.length;
    input.setSelectionRange(end, end);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function createOptimisticHistoryRow(expression, result, token) {
    const row = document.createElement('article');
    row.className = 'history-entry history-entry-optimistic';
    row.dataset.optimisticHistory = token;
    row.tabIndex = 0;
    row.title = 'Загрузить выражение для редактирования';

    const left = document.createElement('div');
    const expressionNode = document.createElement('div');
    expressionNode.className = 'history-expression';
    expressionNode.textContent = expression;
    const meta = document.createElement('div');
    meta.className = 'history-meta';
    meta.textContent = currentModeMeta();
    left.append(expressionNode, meta);

    const resultNode = document.createElement('div');
    resultNode.className = 'history-result';
    resultNode.textContent = result;
    resultNode.title = 'Нажмите, чтобы скопировать результат';

    const load = () => loadExpressionIntoEditor(expression);
    row.addEventListener('click', load);
    row.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        load();
      }
    });
    resultNode.addEventListener('click', event => {
      event.stopPropagation();
      window.pywebview?.api?.copy_text?.(result).catch?.(() => {});
    });

    row.append(left, resultNode);
    return row;
  }

  function showOptimisticHistory(expression, result) {
    const token = `optimistic-${Date.now()}-${++optimisticSequence}`;
    const record = {
      token,
      expression,
      result,
      row: null,
      counted: false,
    };
    pendingHistory.push(record);

    if (!historyQueryMatches(expression, result)) return record;

    const list = document.getElementById('historyList');
    if (!list) return record;
    list.querySelector('.history-empty')?.remove();

    const row = createOptimisticHistoryRow(expression, result, token);
    record.row = row;
    record.counted = true;
    list.prepend(row);
    list.scrollTop = 0;
    updateHistoryCounter(1);
    return record;
  }

  function takePendingHistory(expression, result = '') {
    const index = pendingHistory.findIndex(record => (
      record.expression === expression
      && (!result || record.result === result)
    ));
    if (index < 0) return null;
    return pendingHistory.splice(index, 1)[0];
  }

  function restoreEmptyHistoryMessage(list) {
    if (!list || list.children.length) return;
    const empty = document.createElement('div');
    empty.className = 'history-empty';
    empty.innerHTML = '<div><strong>История пуста</strong>Введите выражение и нажмите Enter</div>';
    list.appendChild(empty);
  }

  function rollbackOptimisticHistory(expression, result = '') {
    const record = takePendingHistory(expression, result);
    if (!record?.row?.isConnected) return;
    const list = record.row.parentElement;
    record.row.remove();
    if (record.counted) updateHistoryCounter(-1);
    restoreEmptyHistoryMessage(list);
  }

  function markHistoryForSilentReconcile(expression, result = '') {
    takePendingHistory(expression, result);
    const list = document.getElementById('historyList');
    if (!list) return;
    list.classList.add('history-reconciling');
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        list.classList.remove('history-reconciling');
      });
    });
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
      const originalExpression = normalizeExpression(expression);
      const optimisticResult = cachedResultFor(originalExpression);
      const response = await originalCommit(expression);
      if (!response?.ok || response.result === undefined || response.result === null) {
        rollbackOptimisticHistory(originalExpression, optimisticResult);
        return response;
      }

      const result = String(response.result).trim();
      const input = document.getElementById('expressionInput');
      const currentValue = input?.value ?? '';
      const currentExpression = normalizeExpression(currentValue);
      const stillOnCommittedValue = (
        currentExpression === originalExpression
        || currentExpression === optimisticResult
      );

      cachedPreview = { expression: result, result };
      markHistoryForSilentReconcile(originalExpression, optimisticResult || result);

      // script-v2.js writes evaluation.expression back into the editor after the
      // await. Return the result while the user is still on this calculation, but
      // preserve any newer typing that happened while persistence was finishing.
      return {
        ...response,
        expression: stillOnCommittedValue ? result : currentValue,
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
      if (event.key !== 'Enter' || event.isComposing || event.repeat) return;

      const expression = normalizeExpression(input.value);
      const result = cachedResultFor(expression);
      if (!expression || !result) return;

      // The existing keydown handler must first read the original expression and
      // start api.commit(). A microtask then updates the editor and history before
      // the browser paints, removing both visible bridge and persistence delays.
      window.queueMicrotask(() => {
        applyResultToEditor(input, expression, result);
        showOptimisticHistory(expression, result);
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