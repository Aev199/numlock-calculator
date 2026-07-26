(function () {
  'use strict';

  const MODE_CALCULATOR = 'calculator';
  const MODE_UNITS = 'units';
  const patchedApis = new WeakSet();
  const plainNumber = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i;

  let api = null;
  let mode = MODE_CALCULATOR;
  let categories = [];
  let converterState = {
    category: 'length',
    from_unit: 'm',
    to_unit: 'mm',
    expression: '',
    imported_revision: 0,
  };
  let latestHandoff = { revision: 0, value: '' };
  let pendingLocalHandoff = '';
  let converterPreview = null;
  let previewSequence = 0;
  let previewTimer = null;
  let saveTimer = null;
  let calculatorSnapshot = null;

  function normalize(value) {
    return String(value || '').trim();
  }

  function isPlainNumber(value) {
    return plainNumber.test(normalize(value));
  }

  function elements() {
    return {
      input: document.getElementById('expressionInput'),
      resultValue: document.getElementById('resultValue'),
      resultError: document.getElementById('resultError'),
      calculatorTab: document.getElementById('calculatorModeTab'),
      unitsTab: document.getElementById('unitsModeTab'),
      editorLabel: document.querySelector('.editor-label'),
      historyCard: document.querySelector('.history-card:not(.unit-converter-card)'),
      converterCard: document.getElementById('unitConverterCard'),
      category: document.getElementById('unitCategory'),
      source: document.getElementById('sourceUnitSelect'),
      target: document.getElementById('targetUnitSelect'),
      swap: document.getElementById('swapUnitsButton'),
      sourceBadge: document.getElementById('sourceUnitBadge'),
      targetBadge: document.getElementById('targetUnitBadge'),
      completion: document.getElementById('completionPopover'),
    };
  }

  function setResultText(value, error = '') {
    const { resultValue, resultError } = elements();
    if (!resultValue || !resultError) return;
    if (error) {
      resultValue.textContent = '—';
      resultValue.classList.add('muted');
      resultError.textContent = error;
      resultError.classList.remove('hidden');
      return;
    }
    resultValue.textContent = value || 'Введите значение';
    resultValue.classList.toggle('muted', !value);
    resultError.classList.add('hidden');
    resultError.textContent = '';
  }

  function snapshotCalculator() {
    const { input, resultValue, resultError } = elements();
    if (!input || !resultValue || !resultError) return;
    calculatorSnapshot = {
      expression: input.value,
      result: resultValue.textContent || '',
      resultMuted: resultValue.classList.contains('muted'),
      error: resultError.textContent || '',
      errorHidden: resultError.classList.contains('hidden'),
    };
  }

  function restoreCalculator() {
    const { input, resultValue, resultError } = elements();
    if (!input || !resultValue || !resultError) return;
    const snapshot = calculatorSnapshot || {
      expression: '',
      result: 'Введите выражение',
      resultMuted: true,
      error: '',
      errorHidden: true,
    };
    input.value = snapshot.expression;
    resultValue.textContent = snapshot.result;
    resultValue.classList.toggle('muted', snapshot.resultMuted);
    resultError.textContent = snapshot.error;
    resultError.classList.toggle('hidden', snapshot.errorHidden);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus({ preventScroll: true });
    input.setSelectionRange(input.value.length, input.value.length);
  }

  function categoryById(categoryId) {
    return categories.find(item => item.id === categoryId) || categories[0] || null;
  }

  function unitLabel(symbol) {
    const category = categoryById(converterState.category);
    const unit = category?.units?.find(item => item.symbol === symbol);
    return unit?.symbol || symbol || '';
  }

  function fillSelect(select, items, selected) {
    if (!select) return;
    select.innerHTML = '';
    items.forEach(item => {
      const option = document.createElement('option');
      option.value = item.symbol ?? item.id;
      option.textContent = item.symbol
        ? `${item.label} — ${item.symbol}`
        : item.label;
      option.selected = option.value === selected;
      select.appendChild(option);
    });
  }

  function renderCategoryOptions() {
    const { category } = elements();
    if (!category) return;
    category.innerHTML = '';
    categories.forEach(item => {
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = item.label;
      option.selected = item.id === converterState.category;
      category.appendChild(option);
    });
  }

  function renderUnitOptions(resetInvalid = true) {
    const { source, target } = elements();
    const category = categoryById(converterState.category);
    const units = category?.units || [];
    const symbols = units.map(item => item.symbol);
    if (resetInvalid && !symbols.includes(converterState.from_unit)) {
      converterState.from_unit = symbols[0] || '';
    }
    if (resetInvalid && !symbols.includes(converterState.to_unit)) {
      converterState.to_unit = symbols[1] || symbols[0] || '';
    }
    fillSelect(source, units, converterState.from_unit);
    fillSelect(target, units, converterState.to_unit);
    updateUnitBadges();
  }

  function updateUnitBadges() {
    const { sourceBadge, targetBadge } = elements();
    if (sourceBadge) sourceBadge.textContent = unitLabel(converterState.from_unit);
    if (targetBadge) targetBadge.textContent = unitLabel(converterState.to_unit);
  }

  function renderMode() {
    const {
      calculatorTab,
      unitsTab,
      editorLabel,
      historyCard,
      converterCard,
      sourceBadge,
      targetBadge,
      input,
      completion,
    } = elements();
    const units = mode === MODE_UNITS;
    document.body.dataset.appMode = mode;
    calculatorTab?.classList.toggle('active', !units);
    unitsTab?.classList.toggle('active', units);
    calculatorTab?.setAttribute('aria-selected', String(!units));
    unitsTab?.setAttribute('aria-selected', String(units));
    historyCard?.classList.toggle('hidden', units);
    converterCard?.classList.toggle('hidden', !units);
    sourceBadge?.classList.toggle('hidden', !units);
    targetBadge?.classList.toggle('hidden', !units);
    completion?.classList.add('hidden');
    if (editorLabel) editorLabel.textContent = units ? 'Исходное значение' : 'Выражение';
    if (input) {
      input.placeholder = units
        ? 'Например: (100 + 25) / 2'
        : 'Например: (120 + 30) / 5';
      input.setAttribute(
        'aria-label',
        units ? 'Введите исходное значение' : 'Введите выражение',
      );
    }
  }

  function freshestHandoff() {
    if (pendingLocalHandoff && isPlainNumber(pendingLocalHandoff)) {
      return {
        revision: Number(latestHandoff.revision || 0),
        value: pendingLocalHandoff,
        local: true,
      };
    }
    return {
      revision: Number(latestHandoff.revision || 0),
      value: normalize(latestHandoff.value),
      local: false,
    };
  }

  function importFreshCalculatorResult() {
    const handoff = freshestHandoff();
    const imported = Number(converterState.imported_revision || 0);
    if (!handoff.value) return false;
    if (!handoff.local && handoff.revision <= imported) return false;
    converterState.expression = handoff.value;
    if (handoff.revision > imported) {
      converterState.imported_revision = handoff.revision;
      pendingLocalHandoff = '';
    }
    return true;
  }

  function setConverterInput(value, dispatch = false) {
    const { input } = elements();
    if (!input) return;
    input.value = String(value ?? '');
    input.focus({ preventScroll: true });
    input.setSelectionRange(input.value.length, input.value.length);
    if (dispatch) input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  async function ensureConverterBootstrap(force = false) {
    if (!api || (!force && categories.length)) return;
    const data = await api.units_bootstrap();
    categories = Array.isArray(data?.categories) ? data.categories : [];
    converterState = { ...converterState, ...(data?.state || {}) };
    latestHandoff = { ...latestHandoff, ...(data?.calculator_handoff || {}) };
    renderCategoryOptions();
    renderUnitOptions();
  }

  function persistStateSoon() {
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(() => {
      if (!api) return;
      api.save_unit_converter_state({ ...converterState }).catch(() => {});
    }, 180);
  }

  function renderConversion(response) {
    converterPreview = response?.ok ? {
      expression: normalize(elements().input?.value),
      source_value: String(response.source_value),
      result: String(response.result),
    } : null;
    if (!response?.ok) {
      setResultText('', response?.error || 'Ошибка преобразования');
      return;
    }
    setResultText(String(response.result));
  }

  function scheduleConversion(delay = 14) {
    window.clearTimeout(previewTimer);
    const current = ++previewSequence;
    previewTimer = window.setTimeout(async () => {
      if (mode !== MODE_UNITS || !api) return;
      const { input } = elements();
      const expression = input?.value || '';
      converterState.expression = expression;
      persistStateSoon();
      if (!normalize(expression)) {
        converterPreview = null;
        setResultText('');
        return;
      }
      try {
        const response = await api.convert_units(
          expression,
          converterState.category,
          converterState.from_unit,
          converterState.to_unit,
          false,
          converterState.imported_revision,
        );
        if (current === previewSequence && mode === MODE_UNITS) {
          renderConversion(response);
        }
      } catch (_) {
        if (current === previewSequence) {
          setResultText('', 'Нет связи с вычислительным движком');
        }
      }
    }, delay);
  }

  async function commitConversion() {
    if (!api || mode !== MODE_UNITS) return;
    const { input } = elements();
    const expression = normalize(input?.value);
    if (!expression) return;

    const matchingPreview = converterPreview?.expression === expression
      ? converterPreview
      : null;
    if (matchingPreview?.source_value) {
      converterState.expression = matchingPreview.source_value;
      setConverterInput(matchingPreview.source_value);
    }

    try {
      const response = await api.convert_units(
        expression,
        converterState.category,
        converterState.from_unit,
        converterState.to_unit,
        true,
        converterState.imported_revision,
      );
      if (!response?.ok) {
        renderConversion(response);
        return;
      }
      converterState = { ...converterState, ...(response.state || {}) };
      setConverterInput(response.source_value);
      renderConversion(response);
    } catch (_) {
      setResultText('', 'Нет связи с вычислительным движком');
    }
  }

  async function switchMode(nextMode) {
    if (nextMode === mode) return;
    if (nextMode === MODE_UNITS) {
      snapshotCalculator();
      mode = MODE_UNITS;
      renderMode();
      await ensureConverterBootstrap();
      importFreshCalculatorResult();
      renderCategoryOptions();
      renderUnitOptions();
      setConverterInput(converterState.expression);
      scheduleConversion(0);
      persistStateSoon();
      return;
    }

    converterState.expression = elements().input?.value || converterState.expression;
    persistStateSoon();
    mode = MODE_CALCULATOR;
    renderMode();
    restoreCalculator();
  }

  function patchApi(candidate) {
    if (!candidate || patchedApis.has(candidate)) return candidate;
    if (typeof candidate.commit !== 'function') return candidate;
    const originalCommit = candidate.commit.bind(candidate);

    const trackedCommit = async expression => {
      const response = await originalCommit(expression);
      const handoff = response?.calculator_handoff;
      if (handoff) {
        latestHandoff = { ...latestHandoff, ...handoff };
        if (
          pendingLocalHandoff
          && normalize(handoff.value) === normalize(pendingLocalHandoff)
        ) {
          if (
            mode === MODE_UNITS
            && normalize(converterState.expression) === normalize(pendingLocalHandoff)
          ) {
            converterState.imported_revision = Number(handoff.revision || 0);
            persistStateSoon();
          }
          pendingLocalHandoff = '';
        }
      }
      return response;
    };

    try {
      candidate.commit = trackedCommit;
      if (candidate.commit === trackedCommit) {
        patchedApis.add(candidate);
        return candidate;
      }
    } catch (_) {
      // pywebview may expose a read-only proxy.
    }

    try {
      const proxy = new Proxy(candidate, {
        get(target, property, receiver) {
          if (property === 'commit') return trackedCommit;
          return Reflect.get(target, property, receiver);
        },
      });
      patchedApis.add(candidate);
      patchedApis.add(proxy);
      if (window.pywebview?.api === candidate) window.pywebview.api = proxy;
      return proxy;
    } catch (_) {
      patchedApis.add(candidate);
      return candidate;
    }
  }

  function installBridgePatch() {
    if (window.pywebview?.api) patchApi(window.pywebview.api);
    window.addEventListener('pywebviewready', () => {
      patchApi(window.pywebview?.api);
    }, { once: true });
  }

  function installUi() {
    const {
      input,
      calculatorTab,
      unitsTab,
      category,
      source,
      target,
      swap,
    } = elements();
    if (!input || !calculatorTab || !unitsTab) return;

    calculatorTab.addEventListener('click', () => switchMode(MODE_CALCULATOR));
    unitsTab.addEventListener('click', () => switchMode(MODE_UNITS));

    category?.addEventListener('change', () => {
      converterState.category = category.value;
      renderUnitOptions(true);
      scheduleConversion(0);
      persistStateSoon();
    });
    source?.addEventListener('change', () => {
      converterState.from_unit = source.value;
      updateUnitBadges();
      scheduleConversion(0);
      persistStateSoon();
    });
    target?.addEventListener('change', () => {
      converterState.to_unit = target.value;
      updateUnitBadges();
      scheduleConversion(0);
      persistStateSoon();
    });
    swap?.addEventListener('click', () => {
      const previousSource = converterState.from_unit;
      converterState.from_unit = converterState.to_unit;
      converterState.to_unit = previousSource;
      const converted = converterPreview?.result;
      renderUnitOptions(false);
      if (converted) {
        converterState.expression = converted;
        setConverterInput(converted);
      }
      scheduleConversion(0);
      persistStateSoon();
    });

    input.addEventListener('input', event => {
      if (mode !== MODE_UNITS) return;
      event.stopImmediatePropagation();
      converterState.expression = input.value;
      scheduleConversion();
    }, true);

    input.addEventListener('keydown', event => {
      if (mode === MODE_CALCULATOR) {
        if (event.key === 'Enter' && !event.isComposing && !event.repeat) {
          window.queueMicrotask(() => {
            window.queueMicrotask(() => {
              const value = normalize(input.value);
              if (isPlainNumber(value)) pendingLocalHandoff = value;
            });
          });
        }
        return;
      }

      event.stopImmediatePropagation();
      if (event.key === 'Enter') {
        event.preventDefault();
        commitConversion();
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        if (input.value) {
          input.value = '';
          converterState.expression = '';
          converterPreview = null;
          setResultText('');
          persistStateSoon();
        } else {
          api?.hide_app?.();
        }
      }
    }, true);

    document.addEventListener('keydown', event => {
      if (mode !== MODE_UNITS) return;
      if ((event.ctrlKey || event.metaKey) && event.code === 'KeyK') {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);

    renderMode();
    ensureConverterBootstrap().catch(() => {});
  }

  async function initializeApi() {
    if (window.pywebview?.api) {
      api = patchApi(window.pywebview.api);
      return;
    }
    api = await new Promise(resolve => {
      window.addEventListener(
        'pywebviewready',
        () => resolve(patchApi(window.pywebview?.api)),
        { once: true },
      );
    });
  }

  installBridgePatch();
  initializeApi().then(() => ensureConverterBootstrap()).catch(() => {});
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', installUi, { once: true });
  } else {
    installUi();
  }
})();
