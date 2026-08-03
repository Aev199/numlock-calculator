
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
    if (state.calculator.historyCursor === -1) {
      state.calculator.historyDraft = dom.input.value;
    }
    state.calculator.historyCursor = Math.max(
      -1,
      Math.min(
        history.length - 1,
        state.calculator.historyCursor + direction,
      ),
    );
    state.calculator.expression = state.calculator.historyCursor === -1
      ? state.calculator.historyDraft
      : history[state.calculator.historyCursor].expression;
    setInputValue(state.calculator.expression);
    scheduleCalculatorPreview(0);
  }

  function loadHistoryEntry(entry) {
    if (entry.pending) return;
    state.calculator.expression = entry.expression;
    setInputValue(entry.expression);
    state.calculator.historyCursor = -1;
    scheduleCalculatorPreview(0);
    restoreEditorFocus();
  }

  async function copyText(text, successMessage = 'Результат скопирован') {
    const copied = await state.api.copy_text(text);
    showToast(
      copied ? successMessage : 'Не удалось открыть буфер обмена',
    );
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
    } else if (state.mode === 'units') {
      state.units.expression = dom.input.value;
      scheduleUnitsPreview();
    }
  }

  function onInputKeydown(event) {
    if (isPaletteShortcut(event)) {
      event.preventDefault();
      event.stopPropagation();
      if (state.mode === 'calculator') openPalette();
      return;
    }

    if (
      state.mode === 'calculator'
      && (event.ctrlKey || event.metaKey)
      && event.key === ' '
    ) {
      event.preventDefault();
      updateCompletion(true);
      return;
    }

    if (
      state.mode === 'calculator'
      && !dom.completion.classList.contains('hidden')
    ) {
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
        const item = state.completion.items[state.completion.index];
        if (item) insertSuggestion(item);
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
      if (event.repeat) return;
      if (state.mode === 'calculator') commitCalculator();
      else if (state.mode === 'units') commitUnits();
      return;
    }

    if (
      state.mode === 'calculator'
      && event.key === 'ArrowUp'
      && dom.input.selectionStart === 0
      && dom.input.selectionEnd === 0
    ) {
      event.preventDefault();
      navigateHistory(1);
      return;
    }

    if (
      state.mode === 'calculator'
      && event.key === 'ArrowDown'
      && dom.input.selectionStart === dom.input.value.length
    ) {
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
          ++state.calculator.previewSequence;
        } else {
          state.units.expression = '';
          state.units.preview = null;
          ++state.units.previewSequence;
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
    ['click', 'keyup', 'mouseup', 'select', 'blur'].forEach(type => {
      dom.input.addEventListener(type, rememberSelection);
    });

    dom.calculatorTab.addEventListener('click', () => switchMode('calculator'));
    dom.unitsTab.addEventListener('click', () => switchMode('units'));
    bindInterpolationEvents();
    bindOnboardingEvents();
    dom.historySearch.addEventListener('input', () => reconcileHistory());

    dom.historyList.addEventListener('click', async event => {
      const slot = event.target.closest('.history-slot');
      if (!slot) return;
      const entry = state.calculator.history.find(
        item => item.id === slot.dataset.historyId,
      );
      if (!entry) return;
      const action = event.target.closest('[data-history-action]')
        ?.dataset.historyAction;
      if (action === 'copy') {
        event.stopPropagation();
        await copyText(entry.result);
        return;
      }
      if (action === 'copy-calculation') {
        event.stopPropagation();
        await copyText(
          `${copyExpression(entry.expression)} = ${entry.result}`,
          'Вычисление скопировано',
        );
        return;
      }
