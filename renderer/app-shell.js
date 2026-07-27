(function () {
  'use strict';

  const RENDERER_MARKER = 'nlcalc-consolidated-v1';
  const PREVIEW_DELAY = 18;
  const SAVE_DELAY = 180;
  const FUNCTION_WRAP_DELAY = 230;
  const PLAIN_NUMBER = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i;

  const byId = id => document.getElementById(id);
  const dom = {
    input: byId('expressionInput'),
    fieldShell: byId('expressionFieldShell'),
    commitOverlay: byId('commitOverlay'),
    resultValue: byId('resultValue'),
    resultError: byId('resultError'),
    resultBlock: byId('resultBlock'),
    sourceBadge: byId('sourceUnitBadge'),
    targetBadge: byId('targetUnitBadge'),
    editorLabel: byId('editorLabel'),
    completion: byId('completionPopover'),
    angleMode: byId('angleMode'),
    numberBase: byId('numberBase'),
    themeButton: byId('themeButton'),
    hideButton: byId('hideButton'),
    quitButton: byId('quitButton'),
    paletteButton: byId('paletteButton'),
    memoryButton: byId('memoryButton'),
    variablesButton: byId('variablesButton'),
    calculatorTab: byId('calculatorModeTab'),
    unitsTab: byId('unitsModeTab'),
    calculatorPanel: byId('calculatorPanel'),
    unitsPanel: byId('unitsPanel'),
    historyList: byId('historyList'),
    historyCounter: byId('historyCounter'),
    historySearch: byId('historySearch'),
    clearHistoryButton: byId('clearHistoryButton'),
    category: byId('unitCategory'),
    sourceUnit: byId('sourceUnitSelect'),
    targetUnit: byId('targetUnitSelect'),
    swapUnits: byId('swapUnitsButton'),
    paletteOverlay: byId('paletteOverlay'),
    paletteSearch: byId('paletteSearch'),
    paletteGroups: byId('paletteGroups'),
    paletteResults: byId('paletteResults'),
    drawerOverlay: byId('drawerOverlay'),
    drawerTitle: byId('drawerTitle'),
    drawerSubtitle: byId('drawerSubtitle'),
    drawerContent: byId('drawerContent'),
    drawerClose: byId('drawerClose'),
    toast: byId('toast'),
  };

  const state = {
    api: null,
    mode: 'calculator',
    settings: { angle_mode: 'DEG', number_base: 'DEC', precision: 12 },
    ui: { theme: 'dark' },
    variables: {},
    memories: Array(10).fill('0'),
    catalog: [],
    functionNames: new Set(),
    calculator: {
      expression: '',
      preview: null,
      previewExpression: '',
      previewSequence: 0,
      previewTimer: null,
      commitSequence: 0,
      history: [],
      historyNodes: new Map(),
      historyCursor: -1,
      historyDraft: '',
      handoff: { revision: 0, value: '', updated_at: '' },
    },
    units: {
      categories: [],
      category: 'length',
      from_unit: 'm',
      to_unit: 'mm',
      expression: '',
      imported_revision: 0,
      preview: null,
      previewExpression: '',
      previewSequence: 0,
      previewTimer: null,
      saveTimer: null,
    },
    completion: { items: [], index: 0 },
    palette: { items: [], groups: [], groupIndex: 0, itemIndex: 0 },
    selection: { start: 0, end: 0, restoring: false },
    clearArmedUntil: 0,
    toastTimer: null,
    typingTimer: null,
    functionWrapTimer: null,
  };

  function reducedMotion() {
    return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
  }

  function waitForBridge() {
    if (window.pywebview?.api) return Promise.resolve(window.pywebview.api);
    return new Promise(resolve => {
      window.addEventListener('pywebviewready', () => resolve(window.pywebview.api), { once: true });
    });
  }

  function normalize(value) {
    return String(value ?? '').trim();
  }

  function isPlainNumber(value) {
    return PLAIN_NUMBER.test(normalize(value));
  }

  function showToast(message) {
    dom.toast.textContent = message;
    dom.toast.classList.remove('hidden');
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(() => dom.toast.classList.add('hidden'), 1750);
  }

  function setTheme(theme, persist = true) {
    const normalized = theme === 'light' ? 'light' : 'dark';
    state.ui.theme = normalized;
    document.body.dataset.theme = normalized;
    if (persist && state.api) state.api.set_ui_settings({ theme: normalized }).catch(() => {});
  }

  function applySettings(next) {
    state.settings = { ...state.settings, ...(next || {}) };
    dom.angleMode.textContent = state.settings.angle_mode;
    dom.numberBase.textContent = state.settings.number_base;
  }

  function rememberSelection() {
    if (state.selection.restoring || document.activeElement !== dom.input) return;
    state.selection.start = dom.input.selectionStart ?? dom.input.value.length;
    state.selection.end = dom.input.selectionEnd ?? state.selection.start;
  }

  function setSelection(start, end = start) {
    const length = dom.input.value.length;
    state.selection.start = Math.max(0, Math.min(length, start));
    state.selection.end = Math.max(state.selection.start, Math.min(length, end));
    dom.input.setSelectionRange(state.selection.start, state.selection.end);
  }

  function closeTransientUi() {
    hideCompletion();
    closePalette(false);
    closeDrawer(false);
  }

  function restoreEditorFocus(selectAll = false) {
    state.selection.restoring = true;
    window.requestAnimationFrame(() => {
      dom.input.focus({ preventScroll: true });
      if (selectAll) {
        dom.input.select();
        state.selection.start = 0;
        state.selection.end = dom.input.value.length;
      } else {
        setSelection(state.selection.start, state.selection.end);
      }
      window.requestAnimationFrame(() => { state.selection.restoring = false; });
    });
  }

  window.__nlcalcRestoreEditorFocus = function () {
    closeTransientUi();
    restoreEditorFocus(true);
  };

  function typingFeedback(event) {
    if (!event.isTrusted || event.isComposing || !String(event.inputType || '').startsWith('insert')) return;
    dom.fieldShell.classList.add('is-typing');
    window.clearTimeout(state.typingTimer);
    state.typingTimer = window.setTimeout(() => dom.fieldShell.classList.remove('is-typing'), 105);
  }

  function setInputValue(value, selectEnd = true) {
    dom.input.value = String(value ?? '');
    if (selectEnd) setSelection(dom.input.value.length);
  }

  function renderResult(evaluation) {
    const expression = state.mode === 'calculator'
      ? state.calculator.expression
      : state.units.expression;
    const emptyLabel = state.mode === 'calculator' ? 'Введите выражение' : 'Введите значение';

    if (!normalize(expression)) {
      dom.resultValue.textContent = emptyLabel;
      dom.resultValue.classList.add('muted');
      dom.resultError.classList.add('hidden');
      dom.resultError.textContent = '';
      return;
    }

    if (!evaluation || !evaluation.ok) {
      dom.resultValue.textContent = evaluation?.incomplete ? '…' : '—';
      dom.resultValue.classList.add('muted');
      if (evaluation?.incomplete) {
        dom.resultError.classList.add('hidden');
      } else {
        dom.resultError.textContent = evaluation?.error || 'Ошибка вычисления';
        dom.resultError.classList.remove('hidden');
      }
      return;
    }

    dom.resultValue.textContent = String(evaluation.result);
    dom.resultValue.classList.remove('muted');
    dom.resultError.classList.add('hidden');
    dom.resultError.textContent = '';
  }

  function markResultUpdating() {
    dom.resultValue.classList.add('updating');
  }

  function settleResult() {
    dom.resultValue.classList.remove('updating');
  }

  function scheduleCalculatorPreview(delay = PREVIEW_DELAY) {
    window.clearTimeout(state.calculator.previewTimer);
    const current = ++state.calculator.previewSequence;
    const expression = state.calculator.expression;
    state.calculator.previewTimer = window.setTimeout(async () => {
      if (state.mode !== 'calculator') return;
      if (!normalize(expression)) {
        state.calculator.preview = null;
        state.calculator.previewExpression = '';
        renderResult(null);
        return;
      }
      markResultUpdating();
      try {
        const evaluation = await state.api.preview(expression);
        if (current !== state.calculator.previewSequence || state.mode !== 'calculator') return;
        state.calculator.preview = evaluation;
        state.calculator.previewExpression = expression;
        renderResult(evaluation);
      } catch (_) {
        if (current === state.calculator.previewSequence) {
          renderResult({ ok: false, error: 'Нет связи с вычислительным движком' });
        }
      } finally {
        if (current === state.calculator.previewSequence) settleResult();
      }
    }, delay);
  }

  function currentUnitCategory() {
    return state.units.categories.find(item => item.id === state.units.category)
      || state.units.categories[0]
      || null;
  }

  function normalizeUnitSelection() {
    const category = currentUnitCategory();
    const symbols = (category?.units || []).map(item => item.symbol);
    if (!symbols.includes(state.units.from_unit)) state.units.from_unit = symbols[0] || '';
    if (!symbols.includes(state.units.to_unit)) state.units.to_unit = symbols[1] || symbols[0] || '';
    if (state.units.from_unit === state.units.to_unit && symbols.length > 1) {
      state.units.to_unit = symbols.find(symbol => symbol !== state.units.from_unit) || symbols[0];
    }
  }

  function fillSelect(select, items, selected, category = false) {
    const fragment = document.createDocumentFragment();
    for (const item of items) {
      const option = document.createElement('option');
      option.value = category ? item.id : item.symbol;
      option.textContent = category ? item.label : `${item.label} — ${item.symbol}`;
      option.selected = option.value === selected;
      fragment.appendChild(option);
    }
    select.replaceChildren(fragment);
  }

  function renderUnitControls() {
    normalizeUnitSelection();
    fillSelect(dom.category, state.units.categories, state.units.category, true);
    const units = currentUnitCategory()?.units || [];
    fillSelect(dom.sourceUnit, units, state.units.from_unit);
    fillSelect(dom.targetUnit, units, state.units.to_unit);
    dom.sourceBadge.textContent = state.units.from_unit;
    dom.targetBadge.textContent = state.units.to_unit;
  }

  function persistUnitsSoon() {
    window.clearTimeout(state.units.saveTimer);
    state.units.saveTimer = window.setTimeout(() => {
      if (!state.api) return;
      state.api.save_unit_converter_state({
        category: state.units.category,
        from_unit: state.units.from_unit,
        to_unit: state.units.to_unit,
        expression: state.units.expression,
        imported_revision: state.units.imported_revision,
      }).catch(() => {});
    }, SAVE_DELAY);
  }

  function scheduleUnitsPreview(delay = PREVIEW_DELAY) {
    window.clearTimeout(state.units.previewTimer);
    const current = ++state.units.previewSequence;
    const expression = state.units.expression;
    state.units.previewTimer = window.setTimeout(async () => {
      if (state.mode !== 'units') return;
      persistUnitsSoon();
      if (!normalize(expression)) {
        state.units.preview = null;
        state.units.previewExpression = '';
        renderResult(null);
        return;
      }
      markResultUpdating();
      try {
        const response = await state.api.convert_units(
          expression,
          state.units.category,
          state.units.from_unit,
          state.units.to_unit,
          false,
          state.units.imported_revision,
        );
        if (current !== state.units.previewSequence || state.mode !== 'units') return;
        state.units.preview = response;
        state.units.previewExpression = expression;
        renderResult(response);
      } catch (_) {
        if (current === state.units.previewSequence) {
          renderResult({ ok: false, error: 'Нет связи с вычислительным движком' });
        }
      } finally {
        if (current === state.units.previewSequence) settleResult();
      }
    }, delay);
  }

  function shortTime(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    });
  }

  function historyMeta(entry) {
    const parts = [];
    const angle = String(entry.angle_mode || '').toUpperCase();
    const base = String(entry.number_base || '').toUpperCase();
    if (angle && angle !== 'DEG') parts.push(angle);
    if (base && base !== 'DEC') parts.push(base);
    const time = shortTime(entry.created_at);
    if (time) parts.push(time);
    return parts.join(' · ');
  }

  function historyMatches(entry, query) {
    if (!query) return true;
    return `${entry.expression} ${entry.result}`.toLowerCase().includes(query.toLowerCase());
  }

  function createHistoryNode(entry, animate = false) {
    const slot = document.createElement('div');
    slot.className = `history-slot${animate ? ' entering' : ''}`;
    const inner = document.createElement('div');
    inner.className = 'history-slot-inner';
    const row = document.createElement('article');
    row.className = 'history-entry';
    row.tabIndex = 0;
    row.title = 'Загрузить выражение для редактирования';
    row.innerHTML = [
      '<div class="history-left">',
      '  <div class="history-expression"></div>',
      '  <div class="history-meta"></div>',
      '</div>',
      '<div class="history-result" title="Нажмите, чтобы скопировать результат"></div>',
      '<div class="history-entry-actions">',
      '  <button class="history-action" type="button" data-history-action="copy" title="Копировать результат">⧉</button>',
      '  <button class="history-action delete" type="button" data-history-action="delete" title="Удалить запись">×</button>',
      '</div>',
    ].join('');
    inner.appendChild(row);
    slot.appendChild(inner);
    updateHistoryNode(slot, entry);
    return slot;
  }

  function updateHistoryNode(slot, entry) {
    slot.dataset.historyId = entry.id;
    const row = slot.querySelector('.history-entry');
    row.classList.toggle('pending', Boolean(entry.pending));
    row.dataset.historyId = entry.id;
    slot.querySelector('.history-expression').textContent = entry.expression;
    slot.querySelector('.history-meta').textContent = historyMeta(entry);
    slot.querySelector('.history-result').textContent = entry.result;
  }

  function reconcileHistory(options = {}) {
    const query = normalize(dom.historySearch.value);
    const filtered = state.calculator.history.filter(entry => historyMatches(entry, query));
    const visibleIds = new Set(filtered.map(entry => entry.id));
    dom.historyCounter.textContent = String(filtered.length);

    for (const [id, node] of state.calculator.historyNodes) {
      if (!state.calculator.history.some(entry => entry.id === id)) {
        node.remove();
        state.calculator.historyNodes.delete(id);
      } else if (!visibleIds.has(id)) {
        node.remove();
      }
    }

    const existingEmpty = dom.historyList.querySelector('.history-empty');
    existingEmpty?.remove();

    if (!filtered.length) {
      const empty = document.createElement('div');
      empty.className = 'history-empty';
      empty.innerHTML = query
        ? '<div><strong>Ничего не найдено</strong>Измените запрос</div>'
        : '<div><strong>История пуста</strong>Введите выражение и нажмите Enter</div>';
      dom.historyList.appendChild(empty);
      return;
    }

    const fragment = document.createDocumentFragment();
    for (const entry of filtered) {
      let node = state.calculator.historyNodes.get(entry.id);
      if (!node) {
        node = createHistoryNode(entry, options.animateId === entry.id);
        state.calculator.historyNodes.set(entry.id, node);
      } else {
        updateHistoryNode(node, entry);
      }
      fragment.appendChild(node);
    }
    dom.historyList.appendChild(fragment);

    if (options.animateId) {
      const node = state.calculator.historyNodes.get(options.animateId);
      window.requestAnimationFrame(() => node?.classList.remove('entering'));
    }
  }

  function optimisticHistoryEntry(expression, result) {
    const id = `local-${Date.now()}-${state.calculator.commitSequence}`;
    const entry = {
      id,
      expression,
      result,
      angle_mode: state.settings.angle_mode,
      number_base: state.settings.number_base,
      created_at: new Date().toISOString(),
      pending: true,
    };
    state.calculator.history.unshift(entry);
    reconcileHistory({ animateId: id });
    dom.historyList.scrollTop = 0;
    return id;
  }

  function confirmHistoryEntry(localId, persisted) {
    const index = state.calculator.history.findIndex(entry => entry.id === localId);
    if (index < 0 || !persisted) return;
    state.calculator.history[index] = { ...persisted, pending: false };
    const node = state.calculator.historyNodes.get(localId);
    state.calculator.historyNodes.delete(localId);
    if (node) {
      state.calculator.historyNodes.set(persisted.id, node);
      updateHistoryNode(node, state.calculator.history[index]);
    }
    reconcileHistory();
  }

  function rollbackHistoryEntry(localId) {
    const index = state.calculator.history.findIndex(entry => entry.id === localId);
    if (index >= 0) state.calculator.history.splice(index, 1);
    const node = state.calculator.historyNodes.get(localId);
    state.calculator.historyNodes.delete(localId);
    if (!node) {
      reconcileHistory();
      return;
    }
    node.classList.add('removing');
    window.setTimeout(() => {
      node.remove();
      reconcileHistory();
    }, reducedMotion() ? 0 : 215);
  }

  function animateCommit(result) {
    if (reducedMotion() || typeof dom.commitOverlay.animate !== 'function') return Promise.resolve();
    const sourceRect = dom.resultValue.getBoundingClientRect();
    const targetRect = dom.input.getBoundingClientRect();
    if (!sourceRect.width || !targetRect.width) return Promise.resolve();

    const sourceStyle = getComputedStyle(dom.resultValue);
    const targetStyle = getComputedStyle(dom.input);
    const targetLeft = targetRect.left + Number.parseFloat(targetStyle.paddingLeft || '0');
    const targetTop = targetRect.top + Number.parseFloat(targetStyle.paddingTop || '0');
    const sourceFont = Number.parseFloat(sourceStyle.fontSize || '20');
    const targetFont = Number.parseFloat(targetStyle.fontSize || '16');
    const scale = sourceFont ? targetFont / sourceFont : 1;

    dom.commitOverlay.textContent = result;
    dom.commitOverlay.style.left = `${sourceRect.left}px`;
    dom.commitOverlay.style.top = `${sourceRect.top}px`;
    dom.commitOverlay.style.fontFamily = sourceStyle.fontFamily;
    dom.commitOverlay.style.fontSize = sourceStyle.fontSize;
    dom.commitOverlay.style.fontWeight = sourceStyle.fontWeight;
    dom.commitOverlay.style.lineHeight = sourceStyle.lineHeight;
    dom.commitOverlay.classList.add('active');
    dom.input.classList.add('commit-hidden');

    const dx = targetLeft - sourceRect.left;
    const dy = targetTop - sourceRect.top;
    const animation = dom.commitOverlay.animate(
      [
        { opacity: .96, transform: 'translate3d(0, 0, 0) scale(1)' },
        { opacity: 1, offset: .72, transform: `translate3d(${dx}px, ${dy}px, 0) scale(${scale})` },
        { opacity: 0, transform: `translate3d(${dx}px, ${dy}px, 0) scale(${scale})` },
      ],
      { duration: 225, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'both' },
    );

    return animation.finished.catch(() => {}).finally(() => {
      dom.input.classList.remove('commit-hidden');
      dom.commitOverlay.classList.remove('active');
      dom.commitOverlay.textContent = '';
    });
  }

  async function refreshSessionData(refreshCatalog = false) {
    const data = await state.api.bootstrap();
    state.variables = data.variables || {};
    state.memories = data.memories || Array(10).fill('0');
    if (refreshCatalog) setCatalog(data.suggestions || []);
  }

  async function commitCalculator() {
    const expression = normalize(state.calculator.expression);
    if (!expression) return;
    hideCompletion();

    const preview = state.calculator.previewExpression === state.calculator.expression
      ? state.calculator.preview
      : null;
    const optimisticResult = preview?.ok ? normalize(preview.result) : '';
    const commitId = ++state.calculator.commitSequence;
    let localId = null;

    if (optimisticResult) {
      localId = optimisticHistoryEntry(expression, optimisticResult);
      state.calculator.expression = optimisticResult;
      setInputValue(optimisticResult);
      state.calculator.preview = { ...preview, expression: optimisticResult, result: optimisticResult };
      state.calculator.previewExpression = optimisticResult;
      renderResult(state.calculator.preview);
      animateCommit(optimisticResult);

      if (isPlainNumber(optimisticResult)) {
        state.calculator.handoff = {
          revision: Number(state.calculator.handoff.revision || 0) + 1,
          value: optimisticResult,
          updated_at: new Date().toISOString(),
          optimistic: true,
        };
      }
    }

    try {
      const response = await state.api.commit(expression);
      if (!response?.ok) {
        if (localId) rollbackHistoryEntry(localId);
        if (state.calculator.commitSequence === commitId && state.calculator.expression === optimisticResult) {
          state.calculator.expression = expression;
          setInputValue(expression);
        }
        state.calculator.preview = response;
        state.calculator.previewExpression = state.calculator.expression;
        renderResult(response);
        return;
      }

      const result = normalize(response.result);
      if (localId && response.history_entry) confirmHistoryEntry(localId, response.history_entry);
      else if (response.history_entry) {
        state.calculator.history.unshift(response.history_entry);
        reconcileHistory({ animateId: response.history_entry.id });
      }

      if (!optimisticResult && state.calculator.commitSequence === commitId) {
        state.calculator.expression = result || expression;
        setInputValue(state.calculator.expression);
        renderResult(response);
      }

      state.calculator.preview = { ...response, expression: result, result };
      state.calculator.previewExpression = state.calculator.expression;
      if (response.calculator_handoff) {
        state.calculator.handoff = { ...response.calculator_handoff, optimistic: false };
      }
      state.calculator.historyCursor = -1;
      state.calculator.historyDraft = '';
      if (response.assigned_variable) await refreshSessionData(true);
    } catch (_) {
      if (localId) rollbackHistoryEntry(localId);
      showToast('Ошибка связи с приложением');
    }
  }

  async function commitUnits() {
    const expression = normalize(state.units.expression);
    if (!expression) return;
    const preview = state.units.previewExpression === state.units.expression
      ? state.units.preview
      : null;
    if (preview?.ok && preview.source_value) {
      state.units.expression = String(preview.source_value);
      setInputValue(state.units.expression);
      renderResult(preview);
    }

    try {
      const response = await state.api.convert_units(
        expression,
        state.units.category,
        state.units.from_unit,
        state.units.to_unit,
        true,
        state.units.imported_revision,
      );
      if (!response?.ok) {
        renderResult(response);
        return;
      }
      state.units = { ...state.units, ...(response.state || {}), preview: response };
      state.units.previewExpression = state.units.expression;
      setInputValue(response.source_value);
      renderResult(response);
    } catch (_) {
      renderResult({ ok: false, error: 'Нет связи с вычислительным движком' });
    }
  }

  function importCalculatorHandoff() {
    const handoff = state.calculator.handoff || {};
    const revision = Number(handoff.revision || 0);
    if (!handoff.value || revision <= Number(state.units.imported_revision || 0)) return false;
    state.units.expression = String(handoff.value);
    state.units.imported_revision = revision;
    persistUnitsSoon();
    return true;
  }

  function switchMode(mode) {
    if (mode !== 'calculator' && mode !== 'units') return;
    if (mode === state.mode) return;

    if (state.mode === 'calculator') state.calculator.expression = dom.input.value;
    else {
      state.units.expression = dom.input.value;
      persistUnitsSoon();
    }

    state.mode = mode;
    document.body.dataset.appMode = mode;
    const calculator = mode === 'calculator';
    dom.calculatorTab.classList.toggle('active', calculator);
    dom.unitsTab.classList.toggle('active', !calculator);
    dom.calculatorTab.setAttribute('aria-selected', String(calculator));
    dom.unitsTab.setAttribute('aria-selected', String(!calculator));
    dom.calculatorPanel.classList.toggle('active', calculator);
    dom.unitsPanel.classList.toggle('active', !calculator);
    dom.calculatorPanel.setAttribute('aria-hidden', String(!calculator));
    dom.unitsPanel.setAttribute('aria-hidden', String(calculator));
    dom.editorLabel.textContent = calculator ? 'Выражение' : 'Исходное значение';
    dom.input.placeholder = calculator ? 'Например: (120 + 30) / 5' : 'Например: (100 + 25) / 2';
    dom.input.setAttribute('aria-label', calculator ? 'Введите выражение' : 'Введите исходное значение');
    hideCompletion();

    if (calculator) {
      setInputValue(state.calculator.expression);
      renderResult(state.calculator.previewExpression === state.calculator.expression
        ? state.calculator.preview
        : null);
      scheduleCalculatorPreview(0);
    } else {
      importCalculatorHandoff();
      renderUnitControls();
      setInputValue(state.units.expression);
      renderResult(state.units.previewExpression === state.units.expression
        ? state.units.preview
        : null);
      scheduleUnitsPreview(0);
    }
    restoreEditorFocus();
  }

  function setCatalog(items) {
    state.catalog = Array.isArray(items) ? items : [];
    state.functionNames = new Set(
      state.catalog
        .filter(item => item?.kind === 'function')
        .map(item => String(item.label || '').toLowerCase()),
    );
  }

  function filteredCatalog(query) {
    const needle = normalize(query).toLowerCase();
    if (!needle) return state.catalog.slice();
    return state.catalog.filter(item => [
      item.label, item.insert, item.description, item.group, item.kind,
    ].some(value => String(value || '').toLowerCase().includes(needle)));
  }

  function currentToken() {
    const cursor = dom.input.selectionStart ?? dom.input.value.length;
    const before = dom.input.value.slice(0, cursor);
    const match = before.match(/[A-Za-zА-Яа-я_][\wА-Яа-я]*$/);
    return {
      token: match ? match[0] : '',
      start: match ? cursor - match[0].length : cursor,
      end: cursor,
    };
  }

  function suggestionButton(item, active, className) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `${className}${active ? ' active' : ''}`;
    const kind = document.createElement('span');
    kind.className = 'item-kind';
    kind.textContent = ({ function: 'ƒx', variable: 'var', constant: 'const', memory: 'mem' })[item.kind]
      || item.kind
      || 'cmd';
    const label = document.createElement('span');
    label.className = 'item-label';
    label.textContent = item.label;
    const description = document.createElement('span');
    description.className = 'item-description';
    description.textContent = item.description || '';
    button.append(kind, label, description);
    return button;
  }

  function updateCompletion(force = false) {
    if (state.mode !== 'calculator') {
      hideCompletion();
      return;
    }
    const token = currentToken();
    if (!force && token.token.length < 2) {
      hideCompletion();
      return;
    }
    state.completion.items = filteredCatalog(token.token).slice(0, 7);
    state.completion.index = 0;
    renderCompletion();
  }

  function renderCompletion() {
    dom.completion.replaceChildren();
    if (!state.completion.items.length) {
      hideCompletion();
      return;
    }
    state.completion.items.forEach((item, index) => {
      const button = suggestionButton(item, index === state.completion.index, 'completion-item');
      button.addEventListener('mousedown', event => event.preventDefault());
      button.addEventListener('click', () => insertSuggestion(item));
      dom.completion.appendChild(button);
    });
    dom.completion.classList.remove('hidden');
  }

  function hideCompletion() {
    dom.completion.classList.add('hidden');
    state.completion.items = [];
  }

  function insertAtSelection(text, cursorBack = 0) {
    const start = dom.input.selectionStart ?? dom.input.value.length;
    const end = dom.input.selectionEnd ?? start;
    dom.input.setRangeText(text, start, end, 'end');
    const cursor = Math.max(0, (dom.input.selectionStart ?? dom.input.value.length) - cursorBack);
    setSelection(cursor);
    if (state.mode === 'calculator') {
      state.calculator.expression = dom.input.value;
      scheduleCalculatorPreview();
      updateCompletion();
    } else {
      state.units.expression = dom.input.value;
      scheduleUnitsPreview();
    }
    restoreEditorFocus();
  }

  function insertSuggestion(item) {
    const token = currentToken();
    dom.input.setSelectionRange(token.start, token.end);
    const insert = item.insert || item.label;
    insertAtSelection(insert, item.kind === 'function' && insert.endsWith('()') ? 1 : 0);
    hideCompletion();
    closePalette(false);
  }

  function wrapFunctionToken(token) {
    if (state.mode !== 'calculator') return;
    const cursor = dom.input.selectionStart ?? dom.input.value.length;
    const fresh = currentToken();
    if (!fresh.token || fresh.token.toLowerCase() !== token.toLowerCase()) return;
    if (fresh.end !== cursor || dom.input.value[cursor] === '(') return;
    dom.input.setRangeText('()', cursor, cursor, 'end');
    setSelection(cursor + 1);
    state.calculator.expression = dom.input.value;
    scheduleCalculatorPreview();
  }

  function maybeWrapTypedFunction(event) {
    if (state.mode !== 'calculator' || event.isComposing || event.inputType !== 'insertText') return;
    if (!/^[A-Za-z]$/.test(String(event.data || ''))) return;
    const token = currentToken().token;
    const normalized = token.toLowerCase();
    if (!state.functionNames.has(normalized)) return;
    window.clearTimeout(state.functionWrapTimer);
    const ambiguous = [...state.functionNames].some(name => name !== normalized && name.startsWith(normalized));
    if (ambiguous) {
      state.functionWrapTimer = window.setTimeout(() => wrapFunctionToken(token), FUNCTION_WRAP_DELAY);
    } else {
      wrapFunctionToken(token);
    }
  }

  function isPaletteShortcut(event) {
    return Boolean((event.ctrlKey || event.metaKey) && !event.altKey && event.code === 'KeyK');
  }

  function paletteIsOpen() {
    return !dom.paletteOverlay.classList.contains('hidden');
  }

  function rebuildPaletteGroups(preferred = null) {
    const previous = preferred || state.palette.groups[state.palette.groupIndex];
    state.palette.groups = [];
    for (const item of state.palette.items) {
      const group = item.group || item.kind || 'Команды';
      if (!state.palette.groups.includes(group)) state.palette.groups.push(group);
    }
    const previousIndex = state.palette.groups.indexOf(previous);
    state.palette.groupIndex = previousIndex >= 0 ? previousIndex : 0;
    state.palette.itemIndex = 0;
  }

  function activePaletteItems() {
    const group = state.palette.groups[state.palette.groupIndex];
    return state.palette.items.filter(item => (item.group || item.kind || 'Команды') === group);
  }

  function renderPaletteGroups() {
    dom.paletteGroups.replaceChildren();
    state.palette.groups.forEach((name, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `palette-group${index === state.palette.groupIndex ? ' active' : ''}`;
      button.textContent = name;
      button.tabIndex = -1;
      button.addEventListener('mousedown', event => event.preventDefault());
      button.addEventListener('click', () => {
        state.palette.groupIndex = index;
        state.palette.itemIndex = 0;
        renderPalette();
        dom.paletteSearch.focus();
      });
      dom.paletteGroups.appendChild(button);
    });
    dom.paletteGroups.querySelector('.active')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }

  function renderPalette() {
    renderPaletteGroups();
    dom.paletteResults.replaceChildren();
    const items = activePaletteItems();
    if (!items.length) {
      const empty = document.createElement('div');
      empty.className = 'history-empty';
      empty.textContent = 'Ничего не найдено';
      dom.paletteResults.appendChild(empty);
      return;
    }
    state.palette.itemIndex = Math.max(0, Math.min(state.palette.itemIndex, items.length - 1));
    items.slice(0, 50).forEach((item, index) => {
      const button = suggestionButton(item, index === state.palette.itemIndex, 'palette-item');
      button.addEventListener('click', () => insertSuggestion(item));
      dom.paletteResults.appendChild(button);
    });
    dom.paletteResults.querySelector('.active')?.scrollIntoView({ block: 'nearest' });
  }

  function openPalette() {
    if (state.mode !== 'calculator') return;
    hideCompletion();
    dom.paletteOverlay.classList.remove('hidden');
    dom.paletteOverlay.setAttribute('aria-hidden', 'false');
    dom.paletteSearch.value = '';
    state.palette.items = state.catalog.slice();
    rebuildPaletteGroups();
    renderPalette();
    window.setTimeout(() => dom.paletteSearch.focus(), 0);
  }

  function closePalette(focus = true) {
    dom.paletteOverlay.classList.add('hidden');
    dom.paletteOverlay.setAttribute('aria-hidden', 'true');
    if (focus) restoreEditorFocus();
  }

  function filterPalette() {
    const previous = state.palette.groups[state.palette.groupIndex];
    state.palette.items = filteredCatalog(dom.paletteSearch.value);
    rebuildPaletteGroups(previous);
    renderPalette();
  }

  function openDrawer(kind) {
    if (state.mode !== 'calculator') return;
    dom.drawerOverlay.classList.remove('hidden');
    dom.drawerOverlay.setAttribute('aria-hidden', 'false');
    if (kind === 'memory') renderMemoryDrawer();
    else renderVariablesDrawer();
  }

  function closeDrawer(focus = true) {
    dom.drawerOverlay.classList.add('hidden');
    dom.drawerOverlay.setAttribute('aria-hidden', 'true');
    if (focus) restoreEditorFocus();
  }

  function renderMemoryDrawer() {
    dom.drawerTitle.textContent = 'Память';
    dom.drawerSubtitle.textContent = '10 ячеек, совместимых с классическим NumLock Calculator';
    dom.drawerContent.replaceChildren();
    state.memories.forEach((value, index) => {
      const row = document.createElement('div');
      row.className = 'memory-row';
      row.innerHTML = `<span class="memory-slot">M${index}</span><span class="memory-value"></span><div class="memory-actions"></div>`;
      row.querySelector('.memory-value').textContent = value;
      const actions = row.querySelector('.memory-actions');
      const insert = document.createElement('button');
      insert.type = 'button';
      insert.className = 'row-button';
      insert.textContent = 'Вставить';
      const save = document.createElement('button');
      save.type = 'button';
      save.className = 'row-button';
      save.textContent = 'Записать';
      insert.addEventListener('click', () => {
        insertAtSelection(value);
        closeDrawer();
      });
      save.addEventListener('click', async () => {
        const response = await state.api.set_memory(index, state.calculator.expression);
        if (!response.ok) {
          showToast(response.error || 'Не удалось записать память');
          return;
        }
        state.memories[index] = response.memory;
        await refreshSessionData(true);
        renderMemoryDrawer();
        showToast(`M${index} обновлена`);
      });
      actions.append(insert, save);
      dom.drawerContent.appendChild(row);
    });
  }

  function renderVariablesDrawer() {
    dom.drawerTitle.textContent = 'Переменные';
    dom.drawerSubtitle.textContent = 'Создание: имя := выражение';
    dom.drawerContent.replaceChildren();
    const entries = Object.entries(state.variables);
    if (!entries.length) {
      const empty = document.createElement('div');
      empty.className = 'history-empty';
      empty.innerHTML = '<div><strong>Переменных пока нет</strong>Пример: span := 6</div>';
      dom.drawerContent.appendChild(empty);
      return;
    }
    for (const [name, value] of entries) {
      const row = document.createElement('div');
      row.className = 'variable-row';
      const label = document.createElement('span');
      label.className = 'memory-slot';
      label.textContent = name;
      const display = document.createElement('span');
      display.className = 'variable-value';
      display.textContent = value;
      const insert = document.createElement('button');
      insert.type = 'button';
      insert.className = 'row-button';
      insert.textContent = 'Вставить';
      insert.addEventListener('click', () => {
        insertAtSelection(name);
        closeDrawer();
      });
      row.append(label, display, insert);
      dom.drawerContent.appendChild(row);
    }
  }

  function navigateHistory(direction) {
    const history = state.calculator.history.filter(entry => !entry.pending);
    if (!history.length) return;
    if (state.calculator.historyCursor === -1) state.calculator.historyDraft = dom.input.value;
    state.calculator.historyCursor = Math.max(
      -1,
      Math.min(history.length - 1, state.calculator.historyCursor + direction),
    );
    state.calculator.expression = state.calculator.historyCursor === -1
      ? state.calculator.historyDraft
      : history[state.calculator.historyCursor].expression;
    setInputValue(state.calculator.expression);
    scheduleCalculatorPreview(0);
  }

  function loadHistoryEntry(entry) {
    state.calculator.expression = entry.expression;
    setInputValue(entry.expression);
    state.calculator.historyCursor = -1;
    scheduleCalculatorPreview(0);
    restoreEditorFocus();
  }

  async function copyText(text) {
    const copied = await state.api.copy_text(text);
    showToast(copied ? 'Результат скопирован' : 'Не удалось открыть буфер обмена');
  }

  function onInput(event) {
    typingFeedback(event);
    rememberSelection();
    if (state.mode === 'calculator') {
      state.calculator.expression = dom.input.value;
      state.calculator.historyCursor = -1;
      scheduleCalculatorPreview();
      updateCompletion();
      maybeWrapTypedFunction(event);
    } else {
      state.units.expression = dom.input.value;
      scheduleUnitsPreview();
    }
  }

  function onInputKeydown(event) {
    if (isPaletteShortcut(event)) {
      event.preventDefault();
      if (state.mode === 'calculator') openPalette();
      return;
    }

    if (state.mode === 'calculator' && (event.ctrlKey || event.metaKey) && event.key === ' ') {
      event.preventDefault();
      updateCompletion(true);
      return;
    }

    if (state.mode === 'calculator' && !dom.completion.classList.contains('hidden')) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const delta = event.key === 'ArrowDown' ? 1 : -1;
        state.completion.index = (
          state.completion.index + delta + state.completion.items.length
        ) % state.completion.items.length;
        renderCompletion();
        return;
      }
      if (event.key === 'Tab') {
        event.preventDefault();
        insertSuggestion(state.completion.items[state.completion.index]);
        return;
      }
    }

    if (event.key === '(' && dom.input.selectionStart === dom.input.selectionEnd) {
      const cursor = dom.input.selectionStart ?? 0;
      if (dom.input.value[cursor - 1] === '(' && dom.input.value[cursor] === ')') {
        event.preventDefault();
        return;
      }
    }
    if (event.key === ')' && dom.input.selectionStart === dom.input.selectionEnd) {
      const cursor = dom.input.selectionStart ?? 0;
      if (dom.input.value[cursor] === ')') {
        event.preventDefault();
        setSelection(cursor + 1);
        return;
      }
    }

    if (event.key === 'Enter') {
      event.preventDefault();
      if (state.mode === 'calculator') commitCalculator();
      else commitUnits();
      return;
    }

    if (state.mode === 'calculator' && event.key === 'ArrowUp'
      && dom.input.selectionStart === 0 && dom.input.selectionEnd === 0) {
      event.preventDefault();
      navigateHistory(1);
      return;
    }

    if (state.mode === 'calculator' && event.key === 'ArrowDown'
      && dom.input.selectionStart === dom.input.value.length) {
      event.preventDefault();
      navigateHistory(-1);
      return;
    }

    if (event.key === 'Escape') {
      event.preventDefault();
      if (!dom.completion.classList.contains('hidden')) {
        hideCompletion();
      } else if (dom.input.value) {
        setInputValue('');
        if (state.mode === 'calculator') {
          state.calculator.expression = '';
          state.calculator.preview = null;
        } else {
          state.units.expression = '';
          state.units.preview = null;
          persistUnitsSoon();
        }
        renderResult(null);
      } else {
        state.api.hide_app();
      }
    }
  }

  function bindEvents() {
    dom.input.addEventListener('input', onInput);
    dom.input.addEventListener('keydown', onInputKeydown);
    ['click', 'keyup', 'mouseup', 'select', 'blur'].forEach(type => dom.input.addEventListener(type, rememberSelection));

    dom.calculatorTab.addEventListener('click', () => switchMode('calculator'));
    dom.unitsTab.addEventListener('click', () => switchMode('units'));

    dom.historySearch.addEventListener('input', () => reconcileHistory());
    dom.historyList.addEventListener('click', async event => {
      const slot = event.target.closest('.history-slot');
      if (!slot) return;
      const id = slot.dataset.historyId;
      const entry = state.calculator.history.find(item => item.id === id);
      if (!entry) return;
      const action = event.target.closest('[data-history-action]')?.dataset.historyAction;
      if (action === 'copy') {
        event.stopPropagation();
        await copyText(entry.result);
        return;
      }
      if (action === 'delete') {
        event.stopPropagation();
        state.calculator.history = await state.api.delete_history(entry.id);
        reconcileHistory();
        showToast('Запись удалена');
        return;
      }
      if (event.target.closest('.history-result')) {
        event.stopPropagation();
        await copyText(entry.result);
        return;
      }
      loadHistoryEntry(entry);
    });
    dom.historyList.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      const slot = event.target.closest('.history-slot');
      const entry = state.calculator.history.find(item => item.id === slot?.dataset.historyId);
      if (!entry) return;
      event.preventDefault();
      loadHistoryEntry(entry);
    });

    dom.clearHistoryButton.addEventListener('click', async () => {
      const now = Date.now();
      if (now > state.clearArmedUntil) {
        state.clearArmedUntil = now + 3000;
        showToast('Нажмите ещё раз, чтобы очистить историю');
        return;
      }
      state.clearArmedUntil = 0;
      await state.api.clear_history();
      state.calculator.history = [];
      reconcileHistory();
      showToast('История очищена');
    });

    dom.category.addEventListener('change', () => {
      state.units.category = dom.category.value;
      normalizeUnitSelection();
      renderUnitControls();
      scheduleUnitsPreview(0);
      persistUnitsSoon();
    });
    dom.sourceUnit.addEventListener('change', () => {
      state.units.from_unit = dom.sourceUnit.value;
      renderUnitControls();
      scheduleUnitsPreview(0);
      persistUnitsSoon();
    });
    dom.targetUnit.addEventListener('change', () => {
      state.units.to_unit = dom.targetUnit.value;
      renderUnitControls();
      scheduleUnitsPreview(0);
      persistUnitsSoon();
    });
    dom.swapUnits.addEventListener('click', () => {
      const previous = state.units.from_unit;
      state.units.from_unit = state.units.to_unit;
      state.units.to_unit = previous;
      if (state.units.preview?.ok && state.units.preview.result) {
        state.units.expression = String(state.units.preview.result);
        setInputValue(state.units.expression);
      }
      renderUnitControls();
      scheduleUnitsPreview(0);
      persistUnitsSoon();
    });

    dom.paletteButton.addEventListener('click', openPalette);
    dom.memoryButton.addEventListener('click', () => openDrawer('memory'));
    dom.variablesButton.addEventListener('click', () => openDrawer('variables'));
    dom.drawerClose.addEventListener('click', () => closeDrawer());
    dom.paletteOverlay.addEventListener('mousedown', event => {
      if (event.target === dom.paletteOverlay) closePalette();
    });
    dom.drawerOverlay.addEventListener('mousedown', event => {
      if (event.target === dom.drawerOverlay) closeDrawer();
    });

    dom.paletteSearch.addEventListener('input', filterPalette);
    dom.paletteSearch.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closePalette();
        return;
      }
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        if (!state.palette.groups.length) return;
        const delta = event.key === 'ArrowRight' ? 1 : -1;
        state.palette.groupIndex = (
          state.palette.groupIndex + delta + state.palette.groups.length
        ) % state.palette.groups.length;
        state.palette.itemIndex = 0;
        renderPalette();
        return;
      }
      const items = activePaletteItems();
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (!items.length) return;
        const delta = event.key === 'ArrowDown' ? 1 : -1;
        state.palette.itemIndex = (state.palette.itemIndex + delta + items.length) % items.length;
        renderPalette();
        return;
      }
      if (event.key === 'Enter') {
        event.preventDefault();
        if (items[state.palette.itemIndex]) insertSuggestion(items[state.palette.itemIndex]);
      }
    });

    dom.angleMode.addEventListener('click', async () => {
      if (state.mode !== 'calculator') return;
      const modes = ['DEG', 'RAD', 'GRAD'];
      const next = modes[(modes.indexOf(state.settings.angle_mode) + 1) % modes.length];
      applySettings(await state.api.set_settings({ angle_mode: next }));
      scheduleCalculatorPreview(0);
    });
    dom.numberBase.addEventListener('click', async () => {
      if (state.mode !== 'calculator') return;
      const bases = ['DEC', 'HEX', 'OCT', 'BIN'];
      const next = bases[(bases.indexOf(state.settings.number_base) + 1) % bases.length];
      applySettings(await state.api.set_settings({ number_base: next }));
      scheduleCalculatorPreview(0);
    });
    dom.themeButton.addEventListener('click', () => setTheme(state.ui.theme === 'dark' ? 'light' : 'dark'));
    dom.hideButton.addEventListener('click', () => state.api.hide_app());
    dom.quitButton.addEventListener('click', () => state.api.quit_app());

    document.addEventListener('keydown', event => {
      if (!isPaletteShortcut(event)) return;
      event.preventDefault();
      event.stopPropagation();
      if (state.mode !== 'calculator') return;
      if (paletteIsOpen()) closePalette();
      else openPalette();
    });

    window.addEventListener('focus', () => state.api?.window_focus_changed(true).catch(() => {}));
    window.addEventListener('blur', () => state.api?.window_focus_changed(false).catch(() => {}));
  }

  async function initialize() {
    document.documentElement.dataset.renderer = RENDERER_MARKER;
    state.api = await waitForBridge();
    const data = await state.api.bootstrap();
    state.settings = { ...state.settings, ...(data.settings || {}) };
    state.ui = { ...state.ui, ...(data.ui_settings || {}) };
    state.variables = data.variables || {};
    state.memories = data.memories || Array(10).fill('0');
    state.calculator.history = data.history || [];
    setCatalog(data.suggestions || []);

    const unitData = data.unit_converter || {};
    state.units.categories = unitData.categories || [];
    Object.assign(state.units, unitData.state || {});
    state.calculator.handoff = {
      ...state.calculator.handoff,
      ...(unitData.calculator_handoff || {}),
    };

    applySettings(state.settings);
    setTheme(state.ui.theme, false);
    renderUnitControls();
    reconcileHistory();
    bindEvents();
    setInputValue(state.calculator.expression);
    renderResult(null);
    restoreEditorFocus();
    await state.api.window_focus_changed(document.hasFocus());
  }

  initialize().catch(() => {
    dom.resultValue.textContent = '—';
    dom.resultValue.classList.add('muted');
    dom.resultError.textContent = 'Python API недоступен';
    dom.resultError.classList.remove('hidden');
  });
})();
