(function () {
  'use strict';

  const expressionInput = document.getElementById('expressionInput');
  const resultValue = document.getElementById('resultValue');
  const resultError = document.getElementById('resultError');
  const copyButton = document.getElementById('copyButton');
  const insertButton = document.getElementById('insertButton');
  const historyList = document.getElementById('historyList');
  const historyCounter = document.getElementById('historyCounter');
  const historySearch = document.getElementById('historySearch');
  const completionPopover = document.getElementById('completionPopover');
  const angleMode = document.getElementById('angleMode');
  const numberBase = document.getElementById('numberBase');
  const themeButton = document.getElementById('themeButton');
  const hideButton = document.getElementById('hideButton');
  const quitButton = document.getElementById('quitButton');
  const paletteButton = document.getElementById('paletteButton');
  const memoryButton = document.getElementById('memoryButton');
  const variablesButton = document.getElementById('variablesButton');
  const clearHistoryButton = document.getElementById('clearHistoryButton');
  const statusText = document.getElementById('statusText');
  const paletteOverlay = document.getElementById('paletteOverlay');
  const paletteSearch = document.getElementById('paletteSearch');
  const paletteResults = document.getElementById('paletteResults');
  const drawerOverlay = document.getElementById('drawerOverlay');
  const drawerTitle = document.getElementById('drawerTitle');
  const drawerSubtitle = document.getElementById('drawerSubtitle');
  const drawerContent = document.getElementById('drawerContent');
  const drawerClose = document.getElementById('drawerClose');
  const toast = document.getElementById('toast');

  let api = null;
  let history = [];
  let settings = { angle_mode: 'DEG', number_base: 'DEC', precision: 12 };
  let uiSettings = { theme: 'dark' };
  let variables = {};
  let memories = Array(10).fill('0');
  let lastEvaluation = null;
  let previewTimer = null;
  let previewSequence = 0;
  let historyCursor = -1;
  let historyDraft = '';
  let completionItems = [];
  let completionIndex = 0;
  let paletteItems = [];
  let paletteIndex = 0;
  let toastTimer = null;
  let clearArmedUntil = 0;

  async function waitForBridge() {
    if (window.pywebview && window.pywebview.api) return window.pywebview.api;
    return new Promise(resolve => {
      window.addEventListener('pywebviewready', () => resolve(window.pywebview.api), { once: true });
    });
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.remove('hidden');
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.add('hidden'), 1800);
  }

  function setStatus(message) {
    statusText.textContent = message;
  }

  function setTheme(theme, persist = true) {
    const normalized = theme === 'light' ? 'light' : 'dark';
    uiSettings.theme = normalized;
    document.body.dataset.theme = normalized;
    if (persist && api) api.set_ui_settings({ theme: normalized }).catch(() => {});
  }

  function applySettings(next) {
    settings = { ...settings, ...next };
    angleMode.textContent = settings.angle_mode;
    numberBase.textContent = settings.number_base;
  }

  function setResult(evaluation) {
    lastEvaluation = evaluation;
    const valid = Boolean(evaluation && evaluation.ok && evaluation.result);
    copyButton.disabled = !valid;
    insertButton.disabled = !valid;

    if (!expressionInput.value.trim()) {
      resultValue.textContent = 'Введите выражение';
      resultValue.classList.add('muted');
      resultError.classList.add('hidden');
      return;
    }

    if (!evaluation || !evaluation.ok) {
      resultValue.textContent = evaluation?.incomplete ? '…' : '—';
      resultValue.classList.add('muted');
      if (evaluation?.incomplete) {
        resultError.classList.add('hidden');
      } else {
        resultError.textContent = evaluation?.error || 'Ошибка вычисления';
        resultError.classList.remove('hidden');
      }
      return;
    }

    resultValue.textContent = evaluation.result;
    resultValue.classList.remove('muted');
    resultError.classList.add('hidden');
  }

  function schedulePreview(delay = 90) {
    window.clearTimeout(previewTimer);
    const current = ++previewSequence;
    previewTimer = window.setTimeout(async () => {
      const expression = expressionInput.value;
      if (!expression.trim()) {
        setResult(null);
        hideCompletion();
        return;
      }
      try {
        const evaluation = await api.preview(expression);
        if (current !== previewSequence) return;
        setResult(evaluation);
      } catch (_) {
        if (current === previewSequence) setResult({ ok: false, error: 'Нет связи с вычислительным движком' });
      }
    }, delay);
  }

  async function commitExpression(insertIntoDocument = false) {
    const expression = expressionInput.value.trim();
    if (!expression) return;
    hideCompletion();
    setStatus('Вычисление…');
    try {
      const evaluation = insertIntoDocument
        ? await api.commit_and_insert(expression)
        : await api.commit(expression);
      setResult(evaluation);
      if (!evaluation.ok) {
        setStatus(evaluation.error || 'Ошибка вычисления');
        return;
      }
      if (evaluation.history_entry) {
        history.unshift(evaluation.history_entry);
        renderHistory();
      }
      expressionInput.value = evaluation.expression?.trim() || expression;
      expressionInput.setSelectionRange(expressionInput.value.length, expressionInput.value.length);
      historyCursor = -1;
      historyDraft = '';
      setStatus(insertIntoDocument ? 'Результат вставлен' : 'Готово');
      if (evaluation.assigned_variable) await refreshSessionData();
    } catch (_) {
      setStatus('Ошибка связи с приложением');
    }
  }

  async function refreshSessionData() {
    const data = await api.bootstrap();
    variables = data.variables || {};
    memories = data.memories || Array(10).fill('0');
  }

  function historyMatches(entry, query) {
    if (!query) return true;
    const haystack = `${entry.expression} ${entry.result}`.toLowerCase();
    return haystack.includes(query.toLowerCase());
  }

  function shortTime(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  }

  function renderHistory() {
    const query = historySearch.value.trim();
    const filtered = history.filter(entry => historyMatches(entry, query));
    historyCounter.textContent = String(filtered.length);
    historyList.innerHTML = '';

    if (!filtered.length) {
      const empty = document.createElement('div');
      empty.className = 'history-empty';
      empty.innerHTML = query
        ? '<div><strong>Ничего не найдено</strong>Измените запрос</div>'
        : '<div><strong>История пуста</strong>Введите выражение и нажмите Enter</div>';
      historyList.appendChild(empty);
      return;
    }

    filtered.forEach((entry, index) => {
      const row = document.createElement('article');
      row.className = 'history-entry';
      row.style.animationDelay = `${Math.min(index, 8) * 14}ms`;
      row.tabIndex = 0;
      row.title = 'Загрузить выражение для редактирования';

      const left = document.createElement('div');
      const expression = document.createElement('div');
      expression.className = 'history-expression';
      expression.textContent = entry.expression;
      const meta = document.createElement('div');
      meta.className = 'history-meta';
      meta.textContent = [entry.angle_mode, entry.number_base, shortTime(entry.created_at)].filter(Boolean).join(' · ');
      left.append(expression, meta);

      const result = document.createElement('div');
      result.className = 'history-result';
      result.textContent = entry.result;
      result.title = 'Нажмите, чтобы скопировать результат';

      const actions = document.createElement('div');
      actions.className = 'history-entry-actions';
      const copy = document.createElement('button');
      copy.type = 'button';
      copy.className = 'history-action';
      copy.textContent = '⧉';
      copy.title = 'Копировать результат';
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'history-action delete';
      remove.textContent = '×';
      remove.title = 'Удалить запись';
      actions.append(copy, remove);

      const load = () => loadHistoryEntry(entry);
      row.addEventListener('click', load);
      row.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          load();
        }
      });
      result.addEventListener('click', event => {
        event.stopPropagation();
        copyText(entry.result);
      });
      copy.addEventListener('click', event => {
        event.stopPropagation();
        copyText(entry.result);
      });
      remove.addEventListener('click', async event => {
        event.stopPropagation();
        history = await api.delete_history(entry.id);
        renderHistory();
        showToast('Запись удалена');
      });

      row.append(left, result, actions);
      historyList.appendChild(row);
    });
  }

  function loadHistoryEntry(entry) {
    expressionInput.value = entry.expression;
    expressionInput.focus();
    expressionInput.setSelectionRange(expressionInput.value.length, expressionInput.value.length);
    historyCursor = -1;
    schedulePreview(0);
  }

  async function copyText(text) {
    const copied = await api.copy_text(text);
    showToast(copied ? 'Результат скопирован' : 'Не удалось открыть буфер обмена');
  }

  function currentToken() {
    const cursor = expressionInput.selectionStart ?? expressionInput.value.length;
    const before = expressionInput.value.slice(0, cursor);
    const match = before.match(/[A-Za-zА-Яа-я_][\wА-Яа-я]*$/);
    return { token: match ? match[0] : '', start: match ? cursor - match[0].length : cursor, end: cursor };
  }

  async function updateCompletion(force = false) {
    const token = currentToken();
    if (!force && token.token.length < 2) {
      hideCompletion();
      return;
    }
    completionItems = await api.suggestions(token.token);
    completionItems = completionItems.slice(0, 7);
    completionIndex = 0;
    renderCompletion();
  }

  function renderCompletion() {
    completionPopover.innerHTML = '';
    if (!completionItems.length) {
      hideCompletion();
      return;
    }
    completionItems.forEach((item, index) => {
      const button = suggestionButton(item, index === completionIndex, 'completion-item');
      button.addEventListener('mousedown', event => event.preventDefault());
      button.addEventListener('click', () => insertSuggestion(item));
      completionPopover.appendChild(button);
    });
    completionPopover.classList.remove('hidden');
  }

  function hideCompletion() {
    completionPopover.classList.add('hidden');
    completionItems = [];
  }

  function suggestionButton(item, active, className) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `${className}${active ? ' active' : ''}`;
    const kind = document.createElement('span');
    kind.className = 'item-kind';
    kind.textContent = item.kind === 'function' ? 'ƒx' : item.kind === 'unit' ? 'unit' : 'var';
    const label = document.createElement('span');
    label.className = 'item-label';
    label.textContent = item.label;
    const description = document.createElement('span');
    description.className = 'item-description';
    description.textContent = item.description || '';
    button.append(kind, label, description);
    return button;
  }

  function insertAtSelection(text, cursorBack = 0) {
    const start = expressionInput.selectionStart ?? expressionInput.value.length;
    const end = expressionInput.selectionEnd ?? start;
    expressionInput.setRangeText(text, start, end, 'end');
    const cursor = Math.max(0, (expressionInput.selectionStart ?? expressionInput.value.length) - cursorBack);
    expressionInput.setSelectionRange(cursor, cursor);
    expressionInput.focus();
    schedulePreview();
  }

  function insertSuggestion(item) {
    const token = currentToken();
    expressionInput.setSelectionRange(token.start, token.end);
    const insert = item.insert || item.label;
    insertAtSelection(insert, item.kind === 'function' && insert.endsWith('()') ? 1 : 0);
    hideCompletion();
    closePalette();
  }

  async function openPalette() {
    hideCompletion();
    paletteOverlay.classList.remove('hidden');
    paletteOverlay.setAttribute('aria-hidden', 'false');
    paletteSearch.value = '';
    paletteItems = await api.suggestions('');
    paletteIndex = 0;
    renderPalette();
    window.setTimeout(() => paletteSearch.focus(), 0);
  }

  function closePalette() {
    paletteOverlay.classList.add('hidden');
    paletteOverlay.setAttribute('aria-hidden', 'true');
    expressionInput.focus();
  }

  function renderPalette() {
    paletteResults.innerHTML = '';
    if (!paletteItems.length) {
      const empty = document.createElement('div');
      empty.className = 'history-empty';
      empty.textContent = 'Ничего не найдено';
      paletteResults.appendChild(empty);
      return;
    }
    paletteItems.slice(0, 50).forEach((item, index) => {
      const button = suggestionButton(item, index === paletteIndex, 'palette-item');
      button.addEventListener('click', () => insertSuggestion(item));
      paletteResults.appendChild(button);
    });
    paletteResults.querySelector('.active')?.scrollIntoView({ block: 'nearest' });
  }

  async function filterPalette() {
    paletteItems = await api.suggestions(paletteSearch.value);
    paletteIndex = 0;
    renderPalette();
  }

  function openDrawer(kind) {
    drawerOverlay.classList.remove('hidden');
    drawerOverlay.setAttribute('aria-hidden', 'false');
    if (kind === 'memory') renderMemoryDrawer();
    else renderVariablesDrawer();
  }

  function closeDrawer() {
    drawerOverlay.classList.add('hidden');
    drawerOverlay.setAttribute('aria-hidden', 'true');
    expressionInput.focus();
  }

  function renderMemoryDrawer() {
    drawerTitle.textContent = 'Память';
    drawerSubtitle.textContent = '10 ячеек, совместимых с классическим NumLock Calculator';
    drawerContent.innerHTML = '';
    memories.forEach((value, index) => {
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
        const response = await api.set_memory(index, expressionInput.value);
        if (!response.ok) {
          showToast(response.error || 'Не удалось записать память');
          return;
        }
        memories[index] = response.memory;
        renderMemoryDrawer();
        showToast(`M${index} обновлена`);
      });
      actions.append(insert, save);
      row.append(slot, display, actions);
      drawerContent.appendChild(row);
    });
  }

  function renderVariablesDrawer() {
    drawerTitle.textContent = 'Переменные';
    drawerSubtitle.textContent = 'Создание: имя := выражение';
    drawerContent.innerHTML = '';
    const entries = Object.entries(variables);
    if (!entries.length) {
      const empty = document.createElement('div');
      empty.className = 'history-empty';
      empty.innerHTML = '<div><strong>Переменных пока нет</strong>Пример: span := 6 m</div>';
      drawerContent.appendChild(empty);
      return;
    }
    entries.forEach(([name, value]) => {
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
      drawerContent.appendChild(row);
    });
  }

  function navigateHistory(direction) {
    if (!history.length) return;
    if (historyCursor === -1) historyDraft = expressionInput.value;
    historyCursor = Math.max(-1, Math.min(history.length - 1, historyCursor + direction));
    expressionInput.value = historyCursor === -1 ? historyDraft : history[historyCursor].expression;
    expressionInput.setSelectionRange(expressionInput.value.length, expressionInput.value.length);
    schedulePreview(0);
  }

  expressionInput.addEventListener('input', () => {
    historyCursor = -1;
    schedulePreview();
    updateCompletion().catch(() => hideCompletion());
  });

  expressionInput.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      event.stopPropagation();
      openPalette();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key === ' ') {
      event.preventDefault();
      updateCompletion(true);
      return;
    }
    if (!completionPopover.classList.contains('hidden')) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const delta = event.key === 'ArrowDown' ? 1 : -1;
        completionIndex = (completionIndex + delta + completionItems.length) % completionItems.length;
        renderCompletion();
        return;
      }
      if (event.key === 'Tab') {
        event.preventDefault();
        insertSuggestion(completionItems[completionIndex]);
        return;
      }
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      commitExpression(event.ctrlKey || event.metaKey);
      return;
    }
    if (event.key === 'ArrowUp' && expressionInput.selectionStart === 0 && expressionInput.selectionEnd === 0) {
      event.preventDefault();
      navigateHistory(1);
      return;
    }
    if (event.key === 'ArrowDown' && expressionInput.selectionStart === expressionInput.value.length) {
      event.preventDefault();
      navigateHistory(-1);
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      if (!completionPopover.classList.contains('hidden')) {
        hideCompletion();
      } else if (expressionInput.value) {
        expressionInput.value = '';
        setResult(null);
      } else {
        api.hide_app();
      }
    }
  });

  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      openPalette();
    }
  });

  paletteSearch.addEventListener('input', () => filterPalette());
  paletteSearch.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      event.preventDefault();
      closePalette();
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!paletteItems.length) return;
      const delta = event.key === 'ArrowDown' ? 1 : -1;
      paletteIndex = (paletteIndex + delta + paletteItems.length) % paletteItems.length;
      renderPalette();
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (paletteItems[paletteIndex]) insertSuggestion(paletteItems[paletteIndex]);
    }
  });

  historySearch.addEventListener('input', renderHistory);
  copyButton.addEventListener('click', () => lastEvaluation?.ok && copyText(lastEvaluation.result));
  insertButton.addEventListener('click', () => commitExpression(true));
  paletteButton.addEventListener('click', openPalette);
  memoryButton.addEventListener('click', () => openDrawer('memory'));
  variablesButton.addEventListener('click', () => openDrawer('variables'));
  drawerClose.addEventListener('click', closeDrawer);
  paletteOverlay.addEventListener('mousedown', event => { if (event.target === paletteOverlay) closePalette(); });
  drawerOverlay.addEventListener('mousedown', event => { if (event.target === drawerOverlay) closeDrawer(); });

  angleMode.addEventListener('click', async () => {
    const modes = ['DEG', 'RAD', 'GRAD'];
    const next = modes[(modes.indexOf(settings.angle_mode) + 1) % modes.length];
    applySettings(await api.set_settings({ angle_mode: next }));
    schedulePreview(0);
  });

  numberBase.addEventListener('click', async () => {
    const bases = ['DEC', 'HEX', 'OCT', 'BIN'];
    const next = bases[(bases.indexOf(settings.number_base) + 1) % bases.length];
    applySettings(await api.set_settings({ number_base: next }));
    schedulePreview(0);
  });

  themeButton.addEventListener('click', () => setTheme(uiSettings.theme === 'dark' ? 'light' : 'dark'));
  hideButton.addEventListener('click', () => api.hide_app());
  quitButton.addEventListener('click', () => api.quit_app());

  clearHistoryButton.addEventListener('click', async () => {
    const now = Date.now();
    if (now > clearArmedUntil) {
      clearArmedUntil = now + 3000;
      showToast('Нажмите ещё раз, чтобы очистить историю');
      return;
    }
    clearArmedUntil = 0;
    await api.clear_history();
    history = [];
    renderHistory();
    showToast('История очищена');
  });

  async function initialize() {
    api = await waitForBridge();
    const data = await api.bootstrap();
    history = data.history || [];
    variables = data.variables || {};
    memories = data.memories || Array(10).fill('0');
    uiSettings = { ...uiSettings, ...(data.ui_settings || {}) };
    applySettings(data.settings || settings);
    setTheme(uiSettings.theme, false);
    renderHistory();
    setResult(null);
    expressionInput.focus();
  }

  initialize().catch(() => {
    setStatus('Не удалось запустить вычислительный движок');
    setResult({ ok: false, error: 'Python API недоступен' });
  });
})();
