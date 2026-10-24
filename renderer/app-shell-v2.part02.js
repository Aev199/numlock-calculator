    return parts.join(' · ');
  }

  function historyMatches(entry, query) {
    if (!query) return true;
    return `${entry.expression} ${entry.normalized_expression || entry.normalized || ''} ${entry.result}`
      .toLowerCase()
      .includes(query.toLowerCase());
  }

  const HISTORY_ROW_TITLE = 'Щелчок по числу или Enter — вставить число\n'
    + 'Щелчок по строке или Shift+Enter — изменить выражение';

  function createHistoryNode(entry, animate = false) {
    const slot = document.createElement('div');
    slot.className = `history-slot${animate ? ' entering' : ''}`;
    const inner = document.createElement('div');
    inner.className = 'history-slot-inner';
    const row = document.createElement('article');
    row.className = 'history-entry';
    row.tabIndex = 0;
    row.title = HISTORY_ROW_TITLE;
    row.innerHTML = [
      '<div class="history-left">',
      '  <div class="history-expression"></div>',
      '  <div class="history-meta"></div>',
      '</div>',
      '<div class="history-result" title="Вставить в выражение"></div>',
      '<div class="history-entry-actions">',
      '  <button class="history-action" type="button" data-history-action="copy" title="Копировать результат">⧉</button>',
      '  <button class="history-action" type="button" data-history-action="copy-calculation" title="Копировать выражение и результат">=</button>',
      '  <button class="history-action delete" type="button" data-history-action="delete" title="Удалить запись">×</button>',
      '</div>',
    ].join('');
    inner.appendChild(row);
    slot.appendChild(inner);
    updateHistoryNode(slot, entry);
    return slot;
  }

  // A function definition echoes itself as the result; a short status reads
  // better than repeating the expression in both columns.
  function isDefinitionEntry(entry) {
    return /:=/.test(String(entry?.result || ''));
  }

  function historyResultText(entry) {
    return isDefinitionEntry(entry) ? 'функция сохранена' : entry.result;
  }

  function updateHistoryNode(slot, entry) {
    slot.dataset.historyId = entry.id;
    const row = slot.querySelector('.history-entry');
    row.classList.toggle('pending', Boolean(entry.pending));
    row.dataset.historyId = entry.id;
    row.title = entry.normalized_expression && entry.normalized_expression !== entry.expression
      ? `${HISTORY_ROW_TITLE}\nНормализовано: ${entry.normalized_expression}`
      : HISTORY_ROW_TITLE;
    slot.querySelector('.history-expression').textContent = entry.expression;
    slot.querySelector('.history-meta').textContent = historyMeta(entry);
    const result = slot.querySelector('.history-result');
    result.textContent = historyResultText(entry);
    result.classList.toggle('is-status', isDefinitionEntry(entry));
    const remove = slot.querySelector('[data-history-action="delete"]');
    remove.disabled = Boolean(entry.pending);
    remove.title = entry.pending ? 'Сохранение записи…' : 'Удалить запись';
  }

  function reconcileHistory(options = {}) {
    const query = normalize(dom.historySearch.value);
    const filtered = state.calculator.history.filter(
      entry => historyMatches(entry, query),
    );
    const existingIds = new Set(state.calculator.history.map(entry => entry.id));
    const visibleIds = new Set(filtered.map(entry => entry.id));
    dom.historyCounter.textContent = String(filtered.length);

    for (const [id, node] of state.calculator.historyNodes) {
      if (!existingIds.has(id)) {
        node.remove();
        state.calculator.historyNodes.delete(id);
      } else if (!visibleIds.has(id)) {
        node.remove();
      }
    }

    dom.historyList.querySelector('.history-empty')?.remove();
    dom.historyList.querySelectorAll('.history-day').forEach(node => node.remove());
    if (!filtered.length) {
      const empty = document.createElement('div');
      empty.className = 'history-empty';
      empty.innerHTML = query
        ? '<div><strong>Ничего не найдено</strong></div>'
        : '<div><strong>История пуста</strong></div>';
      dom.historyList.appendChild(empty);
      return;
    }

    const fragment = document.createDocumentFragment();
    let day = null;
    for (const entry of filtered) {
      const key = historyDayKey(entry.created_at);
      if (key !== day) {
        day = key;
        const heading = document.createElement('div');
        heading.className = 'history-day';
        heading.textContent = historyDayLabel(entry.created_at);
        fragment.appendChild(heading);
      }
      let node = state.calculator.historyNodes.get(entry.id);
      if (!node) {
        node = createHistoryNode(entry, options.animateId === entry.id);
        state.calculator.historyNodes.set(entry.id, node);
      } else {
        updateHistoryNode(node, entry);
      }
      fragment.appendChild(node);
    }
    dom.historyList.appendChild(fragment);

    if (options.animateId) {
      const node = state.calculator.historyNodes.get(options.animateId);
      window.requestAnimationFrame(() => node?.classList.remove('entering'));
    }
  }

  // Mirrors history_rules.py: a bare number (Enter on a result) and a repeat
  // of the latest entry add nothing, so they never flash into the list.
  function historyWorthy(expression) {
    const canonical = value => String(value || '').replace(/\s+/g, '').replace(/[⋅×]/g, '*');
    const text = canonical(expression);
    if (!text || /^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:e[+-]?\d+)?$/i.test(text)) return false;
    return canonical(state.calculator.history[0]?.expression) !== text;
  }

  function optimisticHistoryEntry(expression, result) {
    const id = `local-${Date.now()}-${state.calculator.commitSequence}`;
    state.calculator.history.unshift({
      id,
      expression,
      normalized_expression: expression,
      result,
      angle_mode: state.settings.angle_mode,
      number_base: state.settings.number_base,
      precision: state.settings.precision,
      number_format: state.settings.number_format,
      decimal_separator: state.settings.decimal_separator,
      created_at: new Date().toISOString(),
      pending: true,
    });
    reconcileHistory({ animateId: id });
    dom.historyList.scrollTop = 0;
    return id;
  }

  function confirmHistoryEntry(localId, persisted, expectedEpoch) {
    if (!persisted || expectedEpoch !== state.calculator.historyEpoch) return;
    let needsReconcile = Boolean(normalize(dom.historySearch.value));
    const localIndex = state.calculator.history.findIndex(
      entry => entry.id === localId,
    );
    const persistedIndex = state.calculator.history.findIndex(
      entry => entry.id === persisted.id,
    );

    if (localIndex >= 0) {
      state.calculator.history[localIndex] = { ...persisted, pending: false };
      if (persistedIndex >= 0 && persistedIndex !== localIndex) {
        state.calculator.history.splice(persistedIndex, 1);
      }
    } else if (persistedIndex < 0) {
      state.calculator.history.unshift({ ...persisted, pending: false });
    }

    const localNode = state.calculator.historyNodes.get(localId);
    state.calculator.historyNodes.delete(localId);
    if (localNode) {
      const oldPersistedNode = state.calculator.historyNodes.get(persisted.id);
      if (oldPersistedNode && oldPersistedNode !== localNode) {
        oldPersistedNode.remove();
        needsReconcile = true;
      }
      state.calculator.historyNodes.set(persisted.id, localNode);
      updateHistoryNode(localNode, persisted);
    } else {
      needsReconcile = true;
    }
    if (needsReconcile) reconcileHistory();
  }

  function rollbackHistoryEntry(localId, expectedEpoch) {
    if (!localId || expectedEpoch !== state.calculator.historyEpoch) return;
    const index = state.calculator.history.findIndex(entry => entry.id === localId);
    if (index >= 0) state.calculator.history.splice(index, 1);
    const node = state.calculator.historyNodes.get(localId);
    state.calculator.historyNodes.delete(localId);
    if (!node) {
      reconcileHistory();
      return;
    }
    node.classList.add('removing');
    window.setTimeout(() => {
      node.remove();
      reconcileHistory();
    }, reducedMotion() ? 0 : 215);
  }
