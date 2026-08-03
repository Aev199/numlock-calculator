
  const INTERPOLATION_FIELDS = {
    '1d': ['x0', 'y0', 'x1', 'y1', 'x'],
    '2d': ['x0', 'x1', 'y0', 'y1', 'z00', 'z10', 'z01', 'z11', 'x', 'y'],
  };

  function interpolationMode(value = state.interpolation.mode) {
    return String(value) === '2d' ? '2d' : '1d';
  }

  function interpolationForm(mode = state.interpolation.mode) {
    return mode === '2d' ? dom.interpolation2dForm : dom.interpolation1dForm;
  }

  function interpolationField(mode, name) {
    return interpolationForm(mode)?.querySelector(
      `[data-interpolation-field="${name}"]`,
    );
  }

  function interpolationValues(mode = state.interpolation.mode) {
    const normalizedMode = interpolationMode(mode);
    const values = state.interpolation[normalizedMode === '2d' ? 'two_d' : 'one_d'];
    return Object.fromEntries(
      INTERPOLATION_FIELDS[normalizedMode].map(name => [name, String(values[name] ?? '')]),
    );
  }

  function interpolationComplete(values, mode = state.interpolation.mode) {
    return INTERPOLATION_FIELDS[interpolationMode(mode)]
      .every(name => String(values[name] ?? '').trim() !== '');
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
    const mode = interpolationMode();
    dom.interpolation1dTab.classList.toggle('active', mode === '1d');
    dom.interpolation2dTab.classList.toggle('active', mode === '2d');
    dom.interpolation1dTab.setAttribute('aria-selected', String(mode === '1d'));
    dom.interpolation2dTab.setAttribute('aria-selected', String(mode === '2d'));
    dom.interpolation1dForm.classList.toggle('hidden', mode !== '1d');
    dom.interpolation2dForm.classList.toggle('hidden', mode !== '2d');

    const values = interpolationValues(mode);
    for (const name of INTERPOLATION_FIELDS[mode]) {
      const field = interpolationField(mode, name);
      if (field && field.value !== values[name]) field.value = values[name];
    }
    renderInterpolationResult();
  }

  function loadInterpolationState(saved) {
    if (!saved || typeof saved !== 'object') return;
    state.interpolation.mode = interpolationMode(saved.mode);
    for (const [section, target] of [
      ['one_d', state.interpolation.one_d],
      ['two_d', state.interpolation.two_d],
    ]) {
      const source = saved[section];
      if (!source || typeof source !== 'object') continue;
      for (const name of Object.keys(target)) {
        target[name] = String(source[name] ?? '').slice(0, 80);
      }
    }
  }

  function saveInterpolationStateSoon() {
    window.clearTimeout(state.interpolation.saveTimer);
    state.interpolation.saveTimer = window.setTimeout(() => {
      const payload = {
        mode: interpolationMode(),
        one_d: { ...state.interpolation.one_d },
        two_d: { ...state.interpolation.two_d },
      };
      state.api?.save_interpolation_state?.(payload).catch?.(() => {});
    }, SAVE_DELAY);
  }

  function interpolationFieldChanged(event) {
    const mode = interpolationMode();
    const name = event.currentTarget.dataset.interpolationField;
    const section = mode === '2d' ? state.interpolation.two_d : state.interpolation.one_d;
    section[name] = String(event.currentTarget.value || '').slice(0, 80);
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
    const mode = interpolationMode();
    const values = interpolationValues(mode);
    if (!interpolationComplete(values, mode)) {
      renderInterpolationResult(null);
      return null;
    }
    const request = ++state.interpolation.requestSequence;
    try {
      const response = await state.api.interpolate({ mode, values });
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

  function selectInterpolationMode(mode) {
    const next = interpolationMode(mode);
    if (next === interpolationMode()) return;
    state.interpolation.mode = next;
    state.interpolation.result = null;
    renderInterpolation();
    saveInterpolationStateSoon();
    window.requestAnimationFrame(() => interpolationField(next, INTERPOLATION_FIELDS[next][0])?.focus());
  }

  function clearInterpolation() {
    const mode = interpolationMode();
    const section = mode === '2d' ? state.interpolation.two_d : state.interpolation.one_d;
    for (const name of INTERPOLATION_FIELDS[mode]) section[name] = '';
    state.interpolation.result = null;
    renderInterpolation();
    saveInterpolationStateSoon();
    interpolationField(mode, INTERPOLATION_FIELDS[mode][0])?.focus();
  }

  async function copyInterpolationResult() {
    let response = state.interpolation.result;
    if (!response?.ok) response = await calculateInterpolation();
    if (!response?.ok) {
      showToast(response?.error || 'Нет результата для копирования');
      return;
    }
    const values = interpolationValues();
    const text = interpolationMode() === '1d'
      ? `y(${values.x}) = ${response.result}`
      : `z(${values.x}; ${values.y}) = ${response.result}`;
    try {
      const copied = await state.api.copy_text(text);
      showToast(copied ? 'Результат скопирован' : 'Не удалось открыть буфер обмена');
    } catch (_) {
      showToast('Не удалось скопировать результат');
    }
  }

  function bindInterpolationEvents() {
    dom.interpolationTab.addEventListener('click', () => switchMode('interpolation'));
    dom.interpolation1dTab.addEventListener('click', () => selectInterpolationMode('1d'));
    dom.interpolation2dTab.addEventListener('click', () => selectInterpolationMode('2d'));
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
