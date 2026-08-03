(function () {
  'use strict';

  const RENDERER_MARKER = 'nlcalc-consolidated-v2';
  const PREVIEW_DELAY = 60;
  const SAVE_DELAY = 180;
  const FUNCTION_WRAP_DELAY = 230;
  const PLAIN_NUMBER = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i;
  const byId = id => document.getElementById(id);

  const dom = {
    input: byId('expressionInput'),
    fieldShell: byId('expressionFieldShell'),
    resultValue: byId('resultValue'),
    resultError: byId('resultError'),
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
    formulasButton: byId('formulasButton'),
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
    settings: {
      angle_mode: 'DEG',
      number_base: 'DEC',
      precision: 12,
      number_format: 'auto',
      decimal_separator: '.',
    },
    ui: { theme: 'dark', select_result_on_enter: true },
    variables: {},
    memories: Array(10).fill('0'),
    formulas: [],
    profiles: [],
    activeProfileId: null,
    activeProfile: null,
    profileConstants: {},
    catalog: [],
    functionNames: new Set(),
    calculator: {
      expression: '',
      preview: null,
      previewExpression: '',
      previewSequence: 0,
      previewTimer: null,
      commitSequence: 0,
      pendingCommits: 0,
      historyEpoch: 0,
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
      previewContext: '',
      previewSequence: 0,
      previewTimer: null,
      saveTimer: null,
      commitSequence: 0,
    },
    completion: { items: [], index: 0 },
    palette: { items: [], groups: [], groupIndex: 0, itemIndex: 0 },
    selection: { start: 0, end: 0, restoring: false },
    clearArmedUntil: 0,
    toastTimer: null,
    typingTimer: null,
    functionWrapTimer: null,
  };

  const normalize = value => String(value ?? '').trim();
  const isPlainNumber = value => PLAIN_NUMBER.test(normalize(value));
  const reducedMotion = () => {
    if (document.body?.dataset.motion === 'full') return false;
    return Boolean(
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
    );
  };

  function waitForBridge() {
    if (window.pywebview?.api) return Promise.resolve(window.pywebview.api);
    return new Promise(resolve => {
      window.addEventListener(
        'pywebviewready',
        () => resolve(window.pywebview.api),
        { once: true },
      );
    });
  }

  function showToast(message) {
    dom.toast.textContent = message;
    dom.toast.classList.remove('hidden');
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(
      () => dom.toast.classList.add('hidden'),
      1750,
    );
  }

  function setTheme(theme, persist = true) {
    const next = theme === 'light' ? 'light' : 'dark';
    state.ui.theme = next;
    document.body.dataset.theme = next;
    if (persist && state.api) {
      state.api.set_ui_settings({ theme: next }).catch(() => {});
    }
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
    state.selection.end = Math.max(
      state.selection.start,
      Math.min(length, end),
    );
    dom.input.setSelectionRange(state.selection.start, state.selection.end);
  }

  function setInputValue(value, selectEnd = true) {
    const next = String(value ?? '');
    if (dom.input.value === next) {
      if (selectEnd) setSelection(next.length);
      return false;
    }
    dom.input.value = next;
    if (selectEnd) setSelection(dom.input.value.length);
    return true;
  }

  function selectEditorResultAfterEnter() {
    if (state.ui.select_result_on_enter === false) return false;
    try {
      dom.input.focus({ preventScroll: true });
    } catch (_) {
      dom.input.focus();
    }
    dom.input.select();
    state.selection.start = 0;
    state.selection.end = dom.input.value.length;
    return true;
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
      window.requestAnimationFrame(() => {
        state.selection.restoring = false;
      });
    });
  }

  function closeTransientUi() {
    hideCompletion();
    closePalette(false);
    closeDrawer(false);
  }

  window.__nlcalcRestoreEditorFocus = function (selectAll = true) {
    closeTransientUi();
    restoreEditorFocus(Boolean(selectAll));
  };

  function typingFeedback(event) {
    if (!event.isTrusted || event.isComposing) return;
    if (!String(event.inputType || '').startsWith('insert')) return;
    dom.fieldShell.classList.remove('is-typing');
    void dom.fieldShell.offsetWidth;
    dom.fieldShell.classList.add('is-typing');
    window.clearTimeout(state.typingTimer);
    state.typingTimer = window.setTimeout(
      () => dom.fieldShell.classList.remove('is-typing'),
      185,
    );
  }

  function renderResult(evaluation) {
    const expression = state.mode === 'calculator'
      ? state.calculator.expression
      : state.units.expression;
    const empty = state.mode === 'calculator'
      ? 'Введите выражение'
      : 'Введите значение';
