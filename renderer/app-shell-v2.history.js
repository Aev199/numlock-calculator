  // History you can reach: a calculation that was used gets recorded even
  // without Enter, the list works from the keyboard, and a past result goes
  // into the current expression instead of replacing it.
  const HISTORY_ROW = '.history-entry';
  let lastRemembered = '';

  // Negative values and values with units keep their meaning inside an expression.
  function insertableResult(entry) {
    const text = normalize(entry.result);
    return /^[-−]/.test(text) || /[^\d\s.,eE+-]/.test(text) ? `(${text})` : text;
  }

  function insertHistoryResult(entry) {
    if (!entry || entry.pending) return;
    if (isDefinitionEntry(entry)) {
      loadHistoryEntry(entry);
      return;
    }
    if (state.mode !== 'calculator') switchMode('calculator');
    state.calculator.historyCursor = -1;
    insertAtSelection(insertableResult(entry));
  }

  // Copying a result or leaving the window means the calculation was used.
  async function rememberCurrentCalculation() {
    if (state.mode !== 'calculator' || state.calculator.pendingCommits) return;
    const expression = normalize(state.calculator.expression);
    const preview = state.calculator.previewExpression === state.calculator.expression
      ? state.calculator.preview
      : null;
    if (
      !expression
      || !preview?.ok
      || preview.assigned_variable
      || expression === lastRemembered
      || !historyWorthy(expression)
    ) return;
    lastRemembered = expression;
    const epoch = state.calculator.historyEpoch;
    try {
      const response = await state.api.remember_calculation(expression);
      const entry = response?.history_entry;
      if (
        !entry
        || epoch !== state.calculator.historyEpoch
        || state.calculator.history.some(item => item.id === entry.id)
      ) return;
      state.calculator.history.unshift(entry);
      reconcileHistory({ animateId: entry.id });
    } catch (_) {}
  }

  const copyCurrentCalculationWithoutHistory = copyCurrentCalculation;
  copyCurrentCalculation = async function copyCurrentCalculationIntoHistory() {
    const result = await copyCurrentCalculationWithoutHistory();
    void rememberCurrentCalculation();
    return result;
  };

  window.addEventListener('blur', () => void rememberCurrentCalculation());

  async function restoreHistoryEntries(entries) {
    try {
      const history = await state.api.restore_history(entries);
      if (Array.isArray(history)) {
        state.calculator.history = history;
        reconcileHistory();
      }
    } catch (_) {
      showToast('Не удалось вернуть записи');
    }
  }

  async function deleteHistoryEntry(entry) {
    if (!entry || entry.pending) return;
    await state.api.delete_history(entry.id);
    state.calculator.history = state.calculator.history.filter(item => item.id !== entry.id);
    reconcileHistory();
    showToast('Запись удалена', {
      label: 'Вернуть',
      run: () => void restoreHistoryEntries([entry]),
    });
  }

  function historyEntryFor(element) {
    const id = element?.closest('.history-slot')?.dataset.historyId;
    return state.calculator.history.find(item => item.id === id);
  }

  function historyRows() {
    return [...dom.historyList.querySelectorAll(HISTORY_ROW)];
  }

  dom.historyList.addEventListener('keydown', event => {
    const row = event.target.closest(HISTORY_ROW);
    if (!row || event.target !== row) return;
    const entry = historyEntryFor(row);
    if (!entry) return;
    const rows = historyRows();
    const index = rows.indexOf(row);

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (event.key === 'ArrowUp' && index === 0) {
        dom.historySearch.focus();
        return;
      }
      const step = event.key === 'ArrowDown' ? 1 : -1;
      rows[Math.max(0, Math.min(rows.length - 1, index + step))]?.focus();
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (event.shiftKey) loadHistoryEntry(entry);
      else insertHistoryResult(entry);
      return;
    }
    if (event.key === 'Delete') {
      event.preventDefault();
      const neighbour = rows[index + 1] || rows[index - 1];
      void deleteHistoryEntry(entry).then(() => neighbour?.focus());
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      restoreEditorFocus();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && !event.altKey && event.code === 'KeyC') {
      event.preventDefault();
      void copyText(`${copyExpression(entry.expression)} = ${entry.result}`);
    }
  });

  // Ctrl+H lands in the search field; Down or Enter steps into the list.
  dom.historySearch.addEventListener('keydown', event => {
    if (event.key !== 'ArrowDown' && event.key !== 'Enter') return;
    const first = historyRows()[0];
    if (!first) return;
    event.preventDefault();
    first.focus();
  });

  // Ctrl+Z brings back what was just deleted, unless a text field owns undo.
  document.addEventListener('keydown', event => {
    if (!(event.ctrlKey || event.metaKey) || event.altKey || event.code !== 'KeyZ') return;
    if (!state.toastAction || event.target.closest?.('input, textarea')) return;
    event.preventDefault();
    state.toastAction();
  });
