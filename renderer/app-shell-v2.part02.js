    return parts.join(' · ');
  }

  function historyMatches(entry, query) {
    if (!query) return true;
    return `${entry.expression} ${entry.normalized_expression || entry.normalized || ''} ${entry.result}`
      .toLowerCase()
      .includes(query.toLowerCase());
  }

  function createHistoryNode(entry, animate = false) {
    const slot = document.createElement('div');
    slot.className = `history-slot${animate ? ' entering' : ''}`;
    const inner = document.createElement('div');
    inner.className = 'history-slot-inner';
    const row = document.createElement('article');
    row.className = 'history-entry';
    row.tabIndex = 0;
    row.title = 'Загрузить выражение для редактирования';
    row.innerHTML = [
      '<div class="history-left">',
      '  <div class="history-expression"></div>',
      '  <div class="history-meta"></div>',
      '</div>',
      '<div class="history-result" title="Нажмите, чтобы скопировать результат"></div>',
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

  function updateHistoryNode(slot, entry) {
    slot.dataset.historyId = entry.id;
    const row = slot.querySelector('.history-entry');
    row.classList.toggle('pending', Boolean(entry.pending));
    row.dataset.historyId = entry.id;
    row.title = entry.normalized_expression && entry.normalized_expression !== entry.expression
      ? `Загрузить выражение для редактирования\nНормализовано: ${entry.normalized_expression}`
      : 'Загрузить выражение для редактирования';
    slot.querySelector('.history-expression').textContent = entry.expression;
    slot.querySelector('.history-meta').textContent = historyMeta(entry);
    slot.querySelector('.history-result').textContent = entry.result;
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
    if (!filtered.length) {
      const empty = document.createElement('div');
      empty.className = 'history-empty';
      empty.innerHTML = query
        ? '<div><strong>Ничего не найдено</strong>Измените запрос</div>'
        : '<div><strong>История пуста</strong>Введите выражение и нажмите Enter</div>';
      dom.historyList.appendChild(empty);
      return;
    }

    const fragment = document.createDocumentFragment();
    for (const entry of filtered) {
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
      if (oldPersistedNode && oldPersistedNode !== localNode) oldPersistedNode.remove();
      state.calculator.historyNodes.set(persisted.id, localNode);
      updateHistoryNode(localNode, persisted);
    }
    reconcileHistory();
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

  function cancelCommitAnimation() {
    const active = state.commitAnimation;
    state.commitAnimation = null;
    if (active) {
      try { active.cancel(); } catch (_) {}
    }
    dom.input.classList.remove('commit-hidden');
    dom.commitOverlay.classList.remove('active');
    dom.commitOverlay.textContent = '';
  }

  function animateCommit(result) {
    cancelCommitAnimation();
    if (reducedMotion() || typeof dom.commitOverlay.animate !== 'function') {
      return;
    }
    const sourceRect = dom.resultValue.getBoundingClientRect();
    const targetRect = dom.input.getBoundingClientRect();
    if (!sourceRect.width || !targetRect.width) return;

    const sourceStyle = getComputedStyle(dom.resultValue);
    const targetStyle = getComputedStyle(dom.input);
    const targetLeft = targetRect.left + Number.parseFloat(targetStyle.paddingLeft || '0');
    const targetTop = targetRect.top + Number.parseFloat(targetStyle.paddingTop || '0');
    const sourceFont = Number.parseFloat(sourceStyle.fontSize || '20');
    const targetFont = Number.parseFloat(targetStyle.fontSize || '16');
    const scale = sourceFont ? targetFont / sourceFont : 1;

    dom.commitOverlay.textContent = result;
    dom.commitOverlay.style.left = `${sourceRect.left}px`;
    dom.commitOverlay.style.top = `${sourceRect.top}px`;
    dom.commitOverlay.style.fontFamily = sourceStyle.fontFamily;
    dom.commitOverlay.style.fontSize = sourceStyle.fontSize;
    dom.commitOverlay.style.fontWeight = sourceStyle.fontWeight;
    dom.commitOverlay.style.lineHeight = sourceStyle.lineHeight;
    dom.commitOverlay.classList.add('active');
    dom.input.classList.add('commit-hidden');

    const dx = targetLeft - sourceRect.left;
    const dy = targetTop - sourceRect.top;
    const animation = dom.commitOverlay.animate(
      [
        { opacity: .96, transform: 'translate3d(0,0,0) scale(1)' },
        {
          opacity: 1,
          offset: .72,
          transform: `translate3d(${dx}px,${dy}px,0) scale(${scale})`,
        },
        {
          opacity: 0,
          transform: `translate3d(${dx}px,${dy}px,0) scale(${scale})`,
