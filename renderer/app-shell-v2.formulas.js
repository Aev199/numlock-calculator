
  let formulaDrawerTab = 'formulas';
  let editingFormulaId = null;
  let editingProfileId = null;
  let runningFormulaId = null;

  function refreshFormulaState(data) {
    if (!data) return;
    state.formulas = Array.isArray(data.formulas) ? data.formulas : state.formulas;
    state.profiles = Array.isArray(data.profiles) ? data.profiles : state.profiles;
    state.activeProfileId = data.active_profile_id || null;
    state.activeProfile = data.active_profile || null;
    state.profileConstants = data.profile_constants || {};
    if (data.unit_converter_state) {
      Object.assign(state.units, data.unit_converter_state);
      renderUnitControls();
    }
    if (data.suggestions) setCatalog(data.suggestions);
  }

  async function refreshFormulaData() {
    try {
      const data = await state.api.formula_bootstrap();
      refreshFormulaState(data);
      if (data.settings) applySettings(data.settings);
      return data;
    } catch (_) {
      return null;
    }
  }

  function formulaIsVisible(formula) {
    const selected = state.activeProfile?.formula_ids || [];
    return !state.activeProfileId
      || !selected.length
      || selected.includes(formula.id);
  }

  function drawerButton(label, className = 'row-button') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.textContent = label;
    return button;
  }

  function drawerField(labelText, value, options = {}) {
    const label = document.createElement('label');
    label.className = options.className || 'formula-field';
    const caption = document.createElement('span');
    caption.textContent = labelText;
    const input = document.createElement(options.multiline ? 'textarea' : 'input');
    input.className = options.inputClass || 'formula-input';
    input.value = String(value ?? '');
    if (options.placeholder) input.placeholder = options.placeholder;
    if (options.rows) input.rows = options.rows;
    if (options.id) input.id = options.id;
    if (options.name) input.name = options.name;
    if (options.type) input.type = options.type;
    label.append(caption, input);
    return label;
  }

  function formulaParameterText(formula) {
    return (formula?.parameters || [])
      .map(parameter => `${parameter.name} = ${parameter.default || ''}`.trimEnd())
      .join('\n');
  }

  function parseFormulaParameters(text) {
    return String(text || '')
      .split(/\r?\n/)
      .map(line => line.trim())
      .filter(Boolean)
      .map(line => {
        const separator = line.indexOf('=');
        if (separator < 0) return { name: line, label: line, default: '' };
        const name = line.slice(0, separator).trim();
        return {
          name,
          label: name,
          default: line.slice(separator + 1).trim(),
        };
      });
  }

  function formulaTabs(active) {
    const tabs = document.createElement('div');
    tabs.className = 'formula-tabs';
    for (const [key, label] of [['formulas', 'Формулы'], ['profiles', 'Профили']]) {
      const button = drawerButton(label, `formula-tab${active === key ? ' active' : ''}`);
      button.addEventListener('click', () => {
        formulaDrawerTab = key;
        editingFormulaId = null;
        editingProfileId = null;
        runningFormulaId = null;
        renderFormulasDrawer();
      });
      tabs.appendChild(button);
    }
    return tabs;
  }

  function activeProfileSelector() {
    const wrap = document.createElement('label');
    wrap.className = 'formula-profile-selector';
    const caption = document.createElement('span');
    caption.textContent = 'Инженерный профиль';
    const select = document.createElement('select');
    select.className = 'settings-select';
    const none = document.createElement('option');
    none.value = '';
    none.textContent = 'Без профиля';
    select.appendChild(none);
    for (const profile of state.profiles) {
      const option = document.createElement('option');
      option.value = profile.id;
      option.textContent = profile.name;
      option.selected = profile.id === state.activeProfileId;
      select.appendChild(option);
    }
    select.value = state.activeProfileId || '';
    select.addEventListener('change', async () => {
      select.disabled = true;
      try {
        const response = await state.api.set_active_profile(select.value || null);
        if (!response?.ok) {
          showToast(response?.error || 'Не удалось выбрать профиль');
          return;
        }
        state.activeProfileId = response.active_profile_id || null;
        state.activeProfile = response.active_profile || null;
        state.profileConstants = response.profile_constants || {};
        if (response.unit_converter_state) {
          Object.assign(state.units, response.unit_converter_state);
          renderUnitControls();
          scheduleUnitsPreview(0);
        }
        if (response.suggestions) setCatalog(response.suggestions);
        if (response.settings) {
          applySettings(response.settings);
          scheduleCalculatorPreview(0);
        }
        showToast(state.activeProfileId ? 'Профиль активирован' : 'Профиль отключён');
        renderFormulasDrawer();
      } catch (_) {
        showToast('Не удалось выбрать профиль');
      } finally {
        select.disabled = false;
      }
    });
    wrap.append(caption, select);
    return wrap;
  }

  function renderFormulaEditor(formula = null) {
    dom.drawerTitle.textContent = formula ? 'Изменить формулу' : 'Новая формула';
    dom.drawerSubtitle.textContent = 'Шаблон с именованными параметрами';
    dom.drawerContent.replaceChildren();
    const content = document.createElement('div');
    content.className = 'formula-content';
    const back = drawerButton('← К формулам');
    back.addEventListener('click', () => {
      editingFormulaId = null;
      renderFormulasDrawer();
    });
    content.appendChild(back);

    const form = document.createElement('form');
    form.className = 'formula-editor';
    form.append(
      drawerField('Название', formula?.name || '', { id: 'formulaName', placeholder: 'Например: Давление под подошвой' }),
      drawerField('Выражение', formula?.expression || state.calculator.expression || '', { id: 'formulaExpression', placeholder: 'N / A' }),
      drawerField('Описание', formula?.description || '', { id: 'formulaDescription', placeholder: 'Краткое пояснение', multiline: true, rows: 2 }),
      drawerField('Параметры', formulaParameterText(formula), {
        id: 'formulaParameters',
        placeholder: 'N = 1200 кН\nA = 10 м2',
        multiline: true,
        rows: 4,
      }),
    );
    const settingsTitle = document.createElement('span');
    settingsTitle.className = 'settings-label';
    settingsTitle.textContent = 'Формат формулы';
    const settingsGrid = document.createElement('div');
    settingsGrid.className = 'format-settings-grid';
    const formulaSettings = formula?.settings || {};
    settingsGrid.append(
      drawerField('Вид', formulaSettings.number_format || state.settings.number_format, { id: 'formulaFormat' }),
      drawerField('Знаков', formulaSettings.precision || state.settings.precision, { id: 'formulaPrecision', type: 'number' }),
      drawerField('Разделитель', formulaSettings.decimal_separator || state.settings.decimal_separator, { id: 'formulaSeparator' }),
    );
    form.append(settingsTitle, settingsGrid);
    const help = document.createElement('p');
    help.className = 'formula-help';
    help.textContent = 'Один параметр на строку: имя = значение по умолчанию. Единицы можно указывать прямо в значении.';
    form.appendChild(help);
    const status = document.createElement('div');
    status.className = 'formula-status';
    const actions = document.createElement('div');
    actions.className = 'formula-actions';
    const cancel = drawerButton('Отмена');
    const save = drawerButton('Сохранить', 'row-button primary');
    cancel.addEventListener('click', () => {
      editingFormulaId = null;
      renderFormulasDrawer();
    });
    save.addEventListener('click', async () => {
      const payload = {
        ...(formula || {}),
        name: form.querySelector('#formulaName').value.trim(),
        expression: form.querySelector('#formulaExpression').value.trim(),
        description: form.querySelector('#formulaDescription').value.trim(),
        parameters: parseFormulaParameters(form.querySelector('#formulaParameters').value),
        settings: {
          number_format: form.querySelector('#formulaFormat input').value.trim(),
          precision: Number.parseInt(form.querySelector('#formulaPrecision input').value, 10) || state.settings.precision,
          decimal_separator: form.querySelector('#formulaSeparator input').value.trim(),
        },
      };
      save.disabled = true;
      status.textContent = 'Сохранение…';
      try {
        const response = await state.api.save_formula(payload);
        if (!response?.ok) {
          status.textContent = response?.error || 'Не удалось сохранить формулу';
          save.disabled = false;
          return;
        }
        state.formulas = response.formulas || state.formulas;
        editingFormulaId = null;
        await refreshFormulaData();
        showToast('Формула сохранена');
        renderFormulasDrawer();
      } catch (_) {
        status.textContent = 'Не удалось сохранить формулу';
        save.disabled = false;
      }
    });
    actions.append(cancel, save);
    form.append(status, actions);
    form.addEventListener('submit', event => event.preventDefault());
    content.appendChild(form);
    dom.drawerContent.appendChild(content);
  }

  function renderFormulaRunner(formula) {
    dom.drawerTitle.textContent = formula.name;
    dom.drawerSubtitle.textContent = formula.description || formula.expression;
    dom.drawerContent.replaceChildren();
    const content = document.createElement('div');
    content.className = 'formula-content';
    const back = drawerButton('← К формулам');
    back.addEventListener('click', () => {
      runningFormulaId = null;
      renderFormulasDrawer();
    });
    content.appendChild(back);

    const expression = document.createElement('code');
    expression.className = 'formula-expression-preview';
    expression.textContent = formula.expression;
    content.appendChild(expression);

    const form = document.createElement('form');
    form.className = 'formula-runner';
    for (const parameter of formula.parameters || []) {
      const field = drawerField(
        `${parameter.label || parameter.name}${parameter.unit ? `, ${parameter.unit}` : ''}`,
        parameter.default || '',
        { name: parameter.name, placeholder: parameter.description || parameter.default || 'Введите значение' },
      );
      form.appendChild(field);
    }
    const status = document.createElement('div');
    status.className = 'formula-status';
    const actions = document.createElement('div');
    actions.className = 'formula-actions';
    const run = drawerButton('Вычислить', 'row-button primary');
    actions.appendChild(run);
    form.append(status, actions);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const values = {};
      for (const input of form.querySelectorAll('input[name]')) values[input.name] = input.value.trim();
      run.disabled = true;
      status.textContent = 'Вычисление…';
      try {
        const response = await state.api.evaluate_formula(formula.id, values, true);
        if (!response?.ok) {
          status.textContent = response?.error || 'Не удалось вычислить формулу';
          run.disabled = false;
          return;
        }
        if (response.history_entry) {
          state.calculator.history.unshift(response.history_entry);
          state.calculator.history = state.calculator.history.slice(0, 500);
          reconcileHistory({ animateId: response.history_entry.id });
        }
        state.calculator.expression = response.result;
        state.calculator.preview = { ...response, expression: response.result };
        state.calculator.previewExpression = response.result;
        setInputValue(response.result);
        renderResult(state.calculator.preview);
        runningFormulaId = null;
        closeDrawer();
        showToast('Формула вычислена');
      } catch (_) {
        status.textContent = 'Не удалось вычислить формулу';
        run.disabled = false;
      }
    });
    content.appendChild(form);
    dom.drawerContent.appendChild(content);
    window.setTimeout(() => form.querySelector('input')?.focus(), 0);
  }

  function renderFormulaList() {
    dom.drawerTitle.textContent = 'Формулы и профили';
    dom.drawerSubtitle.textContent = 'Сохраняемые шаблоны инженерных расчётов';
    dom.drawerContent.replaceChildren();
    const content = document.createElement('div');
    content.className = 'formula-content';
    content.append(formulaTabs('formulas'), activeProfileSelector());
    const toolbar = document.createElement('div');
    toolbar.className = 'formula-toolbar';
    const hint = document.createElement('span');
    hint.className = 'formula-help';
    hint.textContent = 'Формулы не меняют обычные переменные калькулятора.';
    const add = drawerButton('+ Новая', 'row-button primary');
    add.addEventListener('click', () => {
      editingFormulaId = '';
      renderFormulasDrawer();
    });
    toolbar.append(hint, add);
    content.appendChild(toolbar);

    const list = document.createElement('div');
    list.className = 'formula-list';
    const visibleFormulas = state.formulas.filter(formulaIsVisible);
    if (!visibleFormulas.length) {
      const empty = document.createElement('div');
      empty.className = 'history-empty formula-empty';
      empty.innerHTML = state.activeProfileId
        ? '<div><strong>В активном профиле нет формул</strong>Добавьте формулы в настройках профиля</div>'
        : '<div><strong>Формул пока нет</strong>Сохраните шаблон N / A или создайте его вручную</div>';
      list.appendChild(empty);
    }
    for (const formula of visibleFormulas) {
      const row = document.createElement('article');
      row.className = 'formula-row';
      const main = document.createElement('div');
      const name = document.createElement('strong');
      name.textContent = formula.name;
      const expression = document.createElement('code');
      expression.textContent = formula.expression;
      const description = document.createElement('span');
      description.className = 'formula-row-description';
      description.textContent = formula.description || `${(formula.parameters || []).length} параметров`;
      main.append(name, expression, description);
      const actions = document.createElement('div');
      actions.className = 'formula-row-actions';
      const run = drawerButton('Запуск');
      const insert = drawerButton('Вставить');
      const edit = drawerButton('Изменить');
      const remove = drawerButton('×', 'row-button formula-delete');
      run.addEventListener('click', () => {
        runningFormulaId = formula.id;
        renderFormulasDrawer();
      });
      insert.addEventListener('click', () => {
        state.calculator.expression = formula.expression;
        setInputValue(formula.expression);
        closeDrawer();
        scheduleCalculatorPreview(0);
      });
      edit.addEventListener('click', () => {
        editingFormulaId = formula.id;
        renderFormulasDrawer();
      });
      remove.addEventListener('click', async () => {
        if (!window.confirm(`Удалить формулу «${formula.name}»?`)) return;
        const response = await state.api.delete_formula(formula.id).catch(() => null);
        if (!response?.ok) {
          showToast(response?.error || 'Не удалось удалить формулу');
          return;
        }
        await refreshFormulaData();
        showToast('Формула удалена');
        renderFormulasDrawer();
      });
      actions.append(run, insert, edit, remove);
      row.append(main, actions);
      list.appendChild(row);
    }
    content.appendChild(list);
    dom.drawerContent.appendChild(content);
  }

  function profileFormulaPicker(profile) {
    const section = document.createElement('div');
    section.className = 'formula-profile-formulas';
    const title = document.createElement('span');
    title.className = 'settings-label';
    title.textContent = 'Формулы профиля';
    section.appendChild(title);
    if (!state.formulas.length) {
      const empty = document.createElement('p');
      empty.className = 'formula-help';
      empty.textContent = 'Сначала создайте хотя бы одну формулу.';
      section.appendChild(empty);
      return section;
    }
    const selected = new Set(profile?.formula_ids || []);
    for (const formula of state.formulas) {
      const label = document.createElement('label');
      label.className = 'formula-check';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = formula.id;
      checkbox.checked = selected.has(formula.id);
      const text = document.createElement('span');
      text.textContent = formula.name;
      label.append(checkbox, text);
      section.appendChild(label);
    }
    return section;
  }

  function renderProfileEditor(profile = null) {
    dom.drawerTitle.textContent = profile ? 'Изменить профиль' : 'Новый профиль';
    dom.drawerSubtitle.textContent = 'Формулы, константы и настройки инженера';
    dom.drawerContent.replaceChildren();
    const content = document.createElement('div');
    content.className = 'formula-content';
    const back = drawerButton('← К профилям');
    back.addEventListener('click', () => {
      editingProfileId = null;
      renderFormulasDrawer();
    });
    content.appendChild(back);

    const form = document.createElement('form');
    form.className = 'formula-editor';
    form.append(
      drawerField('Название', profile?.name || '', { id: 'profileName', placeholder: 'Например: Железобетон' }),
      drawerField('Описание', profile?.description || '', { id: 'profileDescription', placeholder: 'Краткое пояснение', multiline: true, rows: 2 }),
      drawerField('Константы', Object.entries(profile?.constants || {}).map(([name, value]) => `${name} = ${value}`).join('\n'), {
        id: 'profileConstants',
        placeholder: 'gamma = 25 кН/м3\nE = 30 ГПа',
        multiline: true,
        rows: 3,
      }),
      drawerField('Предпочтительные единицы', (profile?.preferred_units || []).join(', '), {
        id: 'profileUnits',
        placeholder: 'кН, МПа, м, м2',
      }),
    );
    form.appendChild(profileFormulaPicker(profile));

    const settingsTitle = document.createElement('span');
    settingsTitle.className = 'settings-label';
    settingsTitle.textContent = 'Формат профиля';
    form.appendChild(settingsTitle);
    const settingsGrid = document.createElement('div');
    settingsGrid.className = 'format-settings-grid';
    const profileSettings = profile?.settings || {};
    const angle = drawerField('Углы', profileSettings.angle_mode || state.settings.angle_mode, { id: 'profileAngle' });
    angle.querySelector('input').setAttribute('list', 'profile-angle-options');
    const format = drawerField('Формат', profileSettings.number_format || state.settings.number_format, { id: 'profileFormat' });
    const precision = drawerField('Знаков', profileSettings.precision || state.settings.precision, { id: 'profilePrecision', type: 'number' });
    const separator = drawerField('Разделитель', profileSettings.decimal_separator || state.settings.decimal_separator, { id: 'profileSeparator' });
    settingsGrid.append(angle, format, precision, separator);
    form.appendChild(settingsGrid);
    const help = document.createElement('p');
    help.className = 'formula-help';
    help.textContent = 'Профиль не удаляет пользовательские переменные. Его константы доступны при запуске формулы.';
    form.appendChild(help);
    const status = document.createElement('div');
    status.className = 'formula-status';
    const actions = document.createElement('div');
    actions.className = 'formula-actions';
    const cancel = drawerButton('Отмена');
    const save = drawerButton('Сохранить', 'row-button primary');
    cancel.addEventListener('click', () => {
      editingProfileId = null;
      renderFormulasDrawer();
    });
    save.addEventListener('click', async () => {
      const constants = {};
      for (const line of form.querySelector('#profileConstants').value.split(/\r?\n/)) {
        const separatorIndex = line.indexOf('=');
        if (separatorIndex < 0) continue;
        const name = line.slice(0, separatorIndex).trim();
        const value = line.slice(separatorIndex + 1).trim();
        if (name) constants[name] = value;
      }
      const payload = {
        ...(profile || {}),
        name: form.querySelector('#profileName').value.trim(),
        description: form.querySelector('#profileDescription').value.trim(),
        constants,
        preferred_units: form.querySelector('#profileUnits').value.split(',').map(value => value.trim()).filter(Boolean),
        formula_ids: [...form.querySelectorAll('.formula-check input:checked')].map(input => input.value),
        settings: {
          angle_mode: form.querySelector('#profileAngle input').value.trim(),
          number_format: form.querySelector('#profileFormat input').value.trim(),
          precision: Number.parseInt(form.querySelector('#profilePrecision input').value, 10) || state.settings.precision,
          decimal_separator: form.querySelector('#profileSeparator input').value.trim(),
        },
      };
      save.disabled = true;
      status.textContent = 'Сохранение…';
      try {
        const response = await state.api.save_profile(payload);
        if (!response?.ok) {
          status.textContent = response?.error || 'Не удалось сохранить профиль';
          save.disabled = false;
          return;
        }
        await refreshFormulaData();
        editingProfileId = null;
        showToast('Профиль сохранён');
        renderFormulasDrawer();
      } catch (_) {
        status.textContent = 'Не удалось сохранить профиль';
        save.disabled = false;
      }
    });
    actions.append(cancel, save);
    form.append(status, actions);
    form.addEventListener('submit', event => event.preventDefault());
    content.appendChild(form);
    dom.drawerContent.appendChild(content);
  }

  function renderProfileList() {
    dom.drawerTitle.textContent = 'Формулы и профили';
    dom.drawerSubtitle.textContent = 'Сохраняемые инженерные настройки';
    dom.drawerContent.replaceChildren();
    const content = document.createElement('div');
    content.className = 'formula-content';
    content.append(formulaTabs('profiles'), activeProfileSelector());
    const toolbar = document.createElement('div');
    toolbar.className = 'formula-toolbar';
    const hint = document.createElement('span');
    hint.className = 'formula-help';
    hint.textContent = 'Профиль задаёт константы, набор формул, единицы и формат, но не стирает переменные.';
    const add = drawerButton('+ Новый', 'row-button primary');
    add.addEventListener('click', () => {
      editingProfileId = '';
      renderFormulasDrawer();
    });
    toolbar.append(hint, add);
    content.appendChild(toolbar);
    const list = document.createElement('div');
    list.className = 'formula-list';
    if (!state.profiles.length) {
      const empty = document.createElement('div');
      empty.className = 'history-empty formula-empty';
      empty.innerHTML = '<div><strong>Профилей пока нет</strong>Создайте профиль с константами и часто используемыми единицами</div>';
      list.appendChild(empty);
    }
    for (const profile of state.profiles) {
      const row = document.createElement('article');
      row.className = `formula-row${profile.id === state.activeProfileId ? ' active' : ''}`;
      const main = document.createElement('div');
      const name = document.createElement('strong');
      name.textContent = `${profile.name}${profile.id === state.activeProfileId ? ' · активен' : ''}`;
      const description = document.createElement('span');
      description.className = 'formula-row-description';
      description.textContent = profile.description || `${Object.keys(profile.constants || {}).length} констант · ${(profile.preferred_units || []).join(', ') || 'единицы не заданы'}`;
      main.append(name, description);
      const actions = document.createElement('div');
      actions.className = 'formula-row-actions';
      const activate = drawerButton(profile.id === state.activeProfileId ? 'Отключить' : 'Активировать');
      const edit = drawerButton('Изменить');
      const remove = drawerButton('×', 'row-button formula-delete');
      activate.addEventListener('click', async () => {
        const response = await state.api.set_active_profile(profile.id === state.activeProfileId ? null : profile.id).catch(() => null);
        if (!response?.ok) {
          showToast(response?.error || 'Не удалось изменить профиль');
          return;
        }
        state.activeProfileId = response.active_profile_id || null;
        state.activeProfile = response.active_profile || null;
        state.profileConstants = response.profile_constants || {};
        if (response.unit_converter_state) {
          Object.assign(state.units, response.unit_converter_state);
          renderUnitControls();
          scheduleUnitsPreview(0);
        }
        if (response.suggestions) setCatalog(response.suggestions);
        if (response.settings) applySettings(response.settings);
        showToast(state.activeProfileId ? 'Профиль активирован' : 'Профиль отключён');
        renderFormulasDrawer();
      });
      edit.addEventListener('click', () => {
        editingProfileId = profile.id;
        renderFormulasDrawer();
      });
      remove.addEventListener('click', async () => {
        if (!window.confirm(`Удалить профиль «${profile.name}»?`)) return;
        const response = await state.api.delete_profile(profile.id).catch(() => null);
        if (!response?.ok) {
          showToast(response?.error || 'Не удалось удалить профиль');
          return;
        }
        await refreshFormulaData();
        showToast('Профиль удалён');
        renderFormulasDrawer();
      });
      actions.append(activate, edit, remove);
      row.append(main, actions);
      list.appendChild(row);
    }
    content.appendChild(list);
    dom.drawerContent.appendChild(content);
  }

  function renderFormulasDrawer() {
    const formula = state.formulas.find(item => item.id === editingFormulaId);
    const profile = state.profiles.find(item => item.id === editingProfileId);
    if (runningFormulaId) {
      const running = state.formulas.find(item => item.id === runningFormulaId);
      if (running) {
        renderFormulaRunner(running);
        return;
      }
      runningFormulaId = null;
    }
    if (editingFormulaId !== null) {
      renderFormulaEditor(formula || null);
      return;
    }
    if (editingProfileId !== null) {
      renderProfileEditor(profile || null);
      return;
    }
    if (formulaDrawerTab === 'profiles') renderProfileList();
    else renderFormulaList();
  }
