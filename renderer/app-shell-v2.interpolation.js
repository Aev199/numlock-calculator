  const INTERPOLATION_FIELDS = ['x0', 'y0', 'x1', 'y1', 'x'];

  function interpolationField(name) {
    return dom.interpolation1dForm?.querySelector(
      `[data-interpolation-field="${name}"]`,
    );
  }

  function interpolationValues() {
    return Object.fromEntries(
      INTERPOLATION_FIELDS.map(name => [
        name,
        String(state.interpolation.one_d[name] ?? ''),
      ]),
    );
  }

  function interpolationComplete(values) {
    return INTERPOLATION_FIELDS.every(
      name => String(values[name] ?? '').trim() !== '',
    );
  }

  function renderInterpolationResult(response = state.interpolation.result) {
    state.interpolation.result = response || null;
    const ok = Boolean(response?.ok);
    dom.interpolationResultValue.textContent = ok
      ? String(response.result || '—')
      : (response?.error ? 'Ошибка ввода' : 'Введите исходные данные');
    dom.interpolationResultValue.classList.toggle('muted', !ok);
    dom.interpolationResultFormula.textContent = ok ? String(response.formula || '') : '';
    dom.interpolationResultError.textContent = response?.error || '';
    dom.interpolationResultError.classList.toggle('hidden', !response?.error);
  }

  function renderInterpolation() {
    const values = interpolationValues();
    for (const name of INTERPOLATION_FIELDS) {
      const field = interpolationField(name);
      if (field && field.value !== values[name]) field.value = values[name];
    }
    renderInterpolationResult();
  }

  function loadInterpolationState(saved) {
    if (!saved || typeof saved !== 'object') return;
    const source = saved.one_d;
    if (!source || typeof source !== 'object') return;
    for (const name of INTERPOLATION_FIELDS) {
      state.interpolation.one_d[name] = String(source[name] ?? '').slice(0, 80);
    }
  }

  function saveInterpolationStateSoon() {
    window.clearTimeout(state.interpolation.saveTimer);
    state.interpolation.saveTimer = window.setTimeout(() => {
      state.api?.save_interpolation_state?.({
        one_d: { ...state.interpolation.one_d },
      }).catch?.(() => {});
    }, SAVE_DELAY);
  }

  function interpolationFieldChanged(event) {
    const name = event.currentTarget.dataset.interpolationField;
    state.interpolation.one_d[name] = String(event.currentTarget.value || '').slice(0, 80);
    state.interpolation.result = null;
    renderInterpolationResult(null);
    saveInterpolationStateSoon();
    window.clearTimeout(state.interpolation.calculateTimer);
    state.interpolation.calculateTimer = window.setTimeout(
      () => { void calculateInterpolation(); },
      PREVIEW_DELAY,
    );
  }

  async function calculateInterpolation() {
    const values = interpolationValues();
    if (!interpolationComplete(values)) {
      renderInterpolationResult(null);
      return null;
    }
    const request = ++state.interpolation.requestSequence;
    try {
      const response = await state.api.interpolate({ mode: '1d', values });
      if (request !== state.interpolation.requestSequence || state.mode !== 'interpolation') {
        return response;
      }
      renderInterpolationResult(response);
      return response;
    } catch (_) {
      const response = { ok: false, error: 'Нет связи с вычислительным движком' };
      if (request === state.interpolation.requestSequence) renderInterpolationResult(response);
      return response;
    }
  }

  function clearInterpolation() {
    for (const name of INTERPOLATION_FIELDS) state.interpolation.one_d[name] = '';
    state.interpolation.result = null;
    renderInterpolation();
    saveInterpolationStateSoon();
    interpolationField(INTERPOLATION_FIELDS[0])?.focus();
  }

  async function copyInterpolationResult() {
    let response = state.interpolation.result;
    if (!response?.ok) response = await calculateInterpolation();
    if (!response?.ok) {
      showToast(response?.error || 'Нет результата для копирования');
      return;
    }
    const values = interpolationValues();
    const text = `y(${values.x}) = ${response.result}`;
    try {
      await copyText(text, 'Результат скопирован');
    } catch (_) {
      showToast('Не удалось скопировать результат');
    }
  }

  function bindInterpolationEvents() {
    dom.interpolationTab.addEventListener('click', () => switchMode('interpolation'));
    dom.interpolationPanel.querySelectorAll('[data-interpolation-field]').forEach(field => {
      field.addEventListener('input', interpolationFieldChanged);
      field.addEventListener('keydown', event => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        void calculateInterpolation();
      });
    });
    dom.interpolationCalculateButton.addEventListener('click', () => {
      void calculateInterpolation();
    });
    dom.interpolationClearButton.addEventListener('click', clearInterpolation);
    dom.interpolationCopyButton.addEventListener('click', () => {
      void copyInterpolationResult();
    });
  }
