    const insert = item.insert || item.label;
    insertAtSelection(
      insert,
      item.kind === 'function' && insert.endsWith('()') ? 1 : 0,
    );
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
    if (state.mode !== 'calculator') return;
    if (event.isComposing || event.inputType !== 'insertText') return;
    if (!/^[A-Za-z]$/.test(String(event.data || ''))) return;
    const token = currentToken().token;
    const lower = token.toLowerCase();
    if (!state.functionNames.has(lower)) return;
    window.clearTimeout(state.functionWrapTimer);
    const ambiguous = [...state.functionNames].some(
      name => name !== lower && name.startsWith(lower),
    );
    if (ambiguous) {
      state.functionWrapTimer = window.setTimeout(
        () => wrapFunctionToken(token),
        FUNCTION_WRAP_DELAY,
      );
    } else {
      wrapFunctionToken(token);
    }
  }

  function isPaletteShortcut(event) {
    return Boolean(
      (event.ctrlKey || event.metaKey)
      && !event.altKey
      && event.code === 'KeyK',
    );
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
    return state.palette.items.filter(
      item => (item.group || item.kind || 'Команды') === group,
    );
  }

  function renderPaletteGroups() {
    dom.paletteGroups.replaceChildren();
    state.palette.groups.forEach((name, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `palette-group${
        index === state.palette.groupIndex ? ' active' : ''
      }`;
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
    dom.paletteGroups.querySelector('.active')?.scrollIntoView({
      block: 'nearest',
      inline: 'nearest',
    });
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
    state.palette.itemIndex = Math.max(
      0,
      Math.min(state.palette.itemIndex, items.length - 1),
    );
    items.slice(0, 50).forEach((item, index) => {
      const button = suggestionButton(
        item,
        index === state.palette.itemIndex,
        'palette-item',
      );
      button.addEventListener('click', () => insertSuggestion(item));
      dom.paletteResults.appendChild(button);
    });
    dom.paletteResults.querySelector('.active')?.scrollIntoView({
      block: 'nearest',
    });
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
    if (state.mode !== 'calculator' && kind !== 'settings' && kind !== 'formulas') return;
    dom.drawerOverlay.dataset.drawerKind = kind;
    dom.drawerOverlay.classList.remove('hidden');
    dom.drawerOverlay.setAttribute('aria-hidden', 'false');
    if (kind === 'memory') renderMemoryDrawer();
    else if (kind === 'settings') renderSettingsDrawer();
    else if (kind === 'formulas') renderFormulasDrawer();
    else renderVariablesDrawer();
  }

  function closeDrawer(focus = true) {
    dom.drawerOverlay.classList.add('hidden');
    dom.drawerOverlay.setAttribute('aria-hidden', 'true');
    delete dom.drawerOverlay.dataset.drawerKind;
    if (focus) restoreEditorFocus();
  }

  function renderMemoryDrawer() {
    dom.drawerTitle.textContent = 'Память';
    dom.drawerSubtitle.textContent = '10 ячеек памяти';
    dom.drawerContent.replaceChildren();
    state.memories.forEach((value, index) => {
      const row = document.createElement('div');
      row.className = 'memory-row';
      const slot = document.createElement('span');
      slot.className = 'memory-slot';
      slot.textContent = `M${index}`;
      const display = document.createElement('span');
      display.className = 'memory-value';
      display.textContent = value;
      const actions = document.createElement('div');
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
        const response = await state.api.set_memory(
          index,
          state.calculator.expression,
        );
        if (!response?.ok) {
          showToast(response?.error || 'Не удалось записать память');
          return;
        }
        state.memories[index] = response.memory;
        renderMemoryDrawer();
        showToast(`M${index} обновлена`);
      });
      actions.append(insert, save);
      row.append(slot, display, actions);
      dom.drawerContent.appendChild(row);
    });
  }
