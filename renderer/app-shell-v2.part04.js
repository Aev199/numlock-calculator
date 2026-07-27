      if (!stillCurrent) {
        persistUnitsSoon();
        return;
      }

      Object.assign(state.units, response.state || {});
      state.units.preview = response;
      state.units.previewExpression = state.units.expression;
      state.units.previewContext = unitContext();
      if (state.mode === 'units') {
        setInputValue(response.source_value);
        renderResult(response);
      }
    } catch (_) {
      const stillCurrent = (
        state.units.commitSequence === commitId
        && state.units.expression === optimisticValue
        && unitContext() === context
      );
      if (stillCurrent && state.mode === 'units') {
        renderResult({ ok: false, error: 'Нет связи с вычислительным движком' });
      }
    }
  }

  function importCalculatorHandoff() {
    const handoff = state.calculator.handoff || {};
    const revision = Number(handoff.revision || 0);
    if (!handoff.value) return false;
    if (revision <= Number(state.units.imported_revision || 0)) return false;
    state.units.expression = String(handoff.value);
    state.units.imported_revision = revision;
    state.units.preview = null;
    state.units.previewExpression = '';
    state.units.previewContext = '';
    persistUnitsSoon();
    return true;
  }

  function switchMode(mode) {
    if (!['calculator', 'units'].includes(mode) || mode === state.mode) return;
    cancelCommitAnimation();
    hideCompletion();

    if (state.mode === 'calculator') {
      state.calculator.expression = dom.input.value;
      ++state.calculator.previewSequence;
    } else {
      state.units.expression = dom.input.value;
      ++state.units.previewSequence;
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
    dom.input.placeholder = calculator
      ? 'Например: (120 + 30) / 5'
      : 'Например: (100 + 25) / 2';
    dom.input.setAttribute(
      'aria-label',
      calculator ? 'Введите выражение' : 'Введите исходное значение',
    );

    if (calculator) {
      setInputValue(state.calculator.expression);
      const currentPreview = (
        state.calculator.previewExpression === state.calculator.expression
      ) ? state.calculator.preview : null;
      renderResult(currentPreview);
      scheduleCalculatorPreview(0);
    } else {
      importCalculatorHandoff();
      renderUnitControls();
      setInputValue(state.units.expression);
      const currentPreview = (
        state.units.previewExpression === state.units.expression
        && state.units.previewContext === unitContext()
      ) ? state.units.preview : null;
      renderResult(currentPreview);
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
      item.label,
      item.insert,
      item.description,
      item.group,
      item.kind,
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
    kind.textContent = ({
      function: 'ƒx',
      variable: 'var',
      constant: 'const',
      memory: 'mem',
    })[item.kind] || item.kind || 'cmd';
    const label = document.createElement('span');
    label.className = 'item-label';
    label.textContent = item.label;
    const description = document.createElement('span');
    description.className = 'item-description';
    description.textContent = item.description || '';
    button.append(kind, label, description);
    return button;
  }

  function hideCompletion() {
    dom.completion.classList.add('hidden');
    state.completion.items = [];
  }

  function renderCompletion() {
    dom.completion.replaceChildren();
    if (!state.completion.items.length) {
      hideCompletion();
      return;
    }
    state.completion.items.forEach((item, index) => {
      const button = suggestionButton(
        item,
        index === state.completion.index,
        'completion-item',
      );
      button.addEventListener('mousedown', event => event.preventDefault());
      button.addEventListener('click', () => insertSuggestion(item));
      dom.completion.appendChild(button);
    });
    dom.completion.classList.remove('hidden');
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

  function insertAtSelection(text, cursorBack = 0) {
    const start = dom.input.selectionStart ?? dom.input.value.length;
    const end = dom.input.selectionEnd ?? start;
    dom.input.setRangeText(text, start, end, 'end');
    const cursor = Math.max(
      0,
      (dom.input.selectionStart ?? dom.input.value.length) - cursorBack,
    );
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
