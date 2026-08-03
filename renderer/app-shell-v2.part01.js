
    if (!normalize(expression)) {
      dom.resultValue.textContent = empty;
      dom.resultValue.classList.add('muted');
      dom.resultError.textContent = '';
      dom.resultError.classList.add('hidden');
      return;
    }

    if (!evaluation || !evaluation.ok) {
      dom.resultValue.textContent = evaluation?.incomplete ? '…' : '—';
      dom.resultValue.classList.add('muted');
      if (evaluation?.incomplete) {
        dom.resultError.textContent = '';
        dom.resultError.classList.add('hidden');
      } else {
        dom.resultError.textContent = evaluation?.error || 'Ошибка вычисления';
        dom.resultError.classList.remove('hidden');
      }
      return;
    }

    dom.resultValue.textContent = String(evaluation.result);
    dom.resultValue.classList.remove('muted');
    dom.resultError.textContent = '';
    dom.resultError.classList.add('hidden');
  }

  function markResultUpdating() {
    dom.resultValue.classList.add('updating');
  }

  function settleResult() {
    dom.resultValue.classList.remove('updating');
  }

  function cancelCalculatorPreview() {
    window.clearTimeout(state.calculator.previewTimer);
    state.calculator.previewTimer = null;
    ++state.calculator.previewSequence;
    settleResult();
  }

  function cancelUnitsPreview() {
    window.clearTimeout(state.units.previewTimer);
    state.units.previewTimer = null;
    ++state.units.previewSequence;
    settleResult();
  }

  function scheduleCalculatorPreview(delay = PREVIEW_DELAY) {
    window.clearTimeout(state.calculator.previewTimer);
    const sequence = ++state.calculator.previewSequence;
    const expression = state.calculator.expression;
    state.calculator.previewTimer = window.setTimeout(async () => {
      state.calculator.previewTimer = null;
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
        if (
          sequence !== state.calculator.previewSequence
          || state.mode !== 'calculator'
          || state.calculator.expression !== expression
        ) return;
        state.calculator.preview = evaluation;
        state.calculator.previewExpression = expression;
        renderResult(evaluation);
      } catch (_) {
        if (
          sequence === state.calculator.previewSequence
          && state.mode === 'calculator'
          && state.calculator.expression === expression
        ) {
          renderResult({ ok: false, error: 'Нет связи с вычислительным движком' });
        }
      } finally {
        if (sequence === state.calculator.previewSequence) settleResult();
      }
    }, delay);
  }

  function currentUnitCategory() {
    return state.units.categories.find(item => item.id === state.units.category)
      || state.units.categories[0]
      || null;
  }

  function unitContext() {
    return [
      state.units.category,
      state.units.from_unit,
      state.units.to_unit,
    ].join('|');
  }

  function applyPreferredUnitSelection() {
    const preferred = state.activeProfile?.preferred_units || [];
    if (!preferred.length) return;
    const symbols = (currentUnitCategory()?.units || []).map(item => item.symbol);
    const matches = preferred.filter(symbol => symbols.includes(symbol));
    if (!matches.length) return;
    state.units.from_unit = matches[0];
    const target = matches.slice(1).find(symbol => symbol !== matches[0]);
    if (target) state.units.to_unit = target;
  }

  function normalizeUnitSelection(preferProfile = false) {
    const symbols = (currentUnitCategory()?.units || []).map(item => item.symbol);
    if (preferProfile) applyPreferredUnitSelection();
    if (!symbols.includes(state.units.from_unit)) {
      state.units.from_unit = symbols[0] || '';
    }
    if (!symbols.includes(state.units.to_unit)) {
      state.units.to_unit = symbols[1] || symbols[0] || '';
    }
    if (state.units.from_unit === state.units.to_unit && symbols.length > 1) {
      state.units.to_unit = symbols.find(
        symbol => symbol !== state.units.from_unit,
      ) || symbols[0];
    }
  }

  function fillSelect(select, items, selected, isCategory = false) {
    const fragment = document.createDocumentFragment();
    for (const item of items) {
      const option = document.createElement('option');
      option.value = isCategory ? item.id : item.symbol;
      option.textContent = isCategory
        ? item.label
        : `${item.label} — ${item.symbol}`;
      option.selected = option.value === selected;
      fragment.appendChild(option);
    }
    select.replaceChildren(fragment);
  }

  function renderUnitControls(preferProfile = false) {
    normalizeUnitSelection(preferProfile);
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
    const sequence = ++state.units.previewSequence;
    const expression = state.units.expression;
    const context = unitContext();
    state.units.previewTimer = window.setTimeout(async () => {
      state.units.previewTimer = null;
      if (state.mode !== 'units') return;
      persistUnitsSoon();
      if (!normalize(expression)) {
        state.units.preview = null;
        state.units.previewExpression = '';
        state.units.previewContext = '';
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
        if (
          sequence !== state.units.previewSequence
          || state.mode !== 'units'
          || state.units.expression !== expression
          || unitContext() !== context
        ) return;
        state.units.preview = response;
        state.units.previewExpression = expression;
        state.units.previewContext = context;
        renderResult(response);
      } catch (_) {
        if (
          sequence === state.units.previewSequence
          && state.mode === 'units'
          && state.units.expression === expression
          && unitContext() === context
        ) {
          renderResult({ ok: false, error: 'Нет связи с вычислительным движком' });
        }
      } finally {
        if (sequence === state.units.previewSequence) settleResult();
      }
    }, delay);
  }

  function shortTime(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
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
