
  state.ui.compact_mode = state.ui.compact_mode === true;

  const COMPACT_OVERLAY_HEIGHT = 340;
  let compactResizeFrame = null;

  function compactModeEnabled() {
    return state.ui.compact_mode === true;
  }

  function compactOverlayOpen() {
    return (
      !dom.drawerOverlay.classList.contains('hidden')
      || !dom.paletteOverlay.classList.contains('hidden')
      || !dom.onboardingOverlay.classList.contains('hidden')
    );
  }

  function compactVisibleContentHeight() {
    const topbar = document.querySelector('.topbar');
    const editor = document.querySelector('.editor-card');
    if (!topbar || !editor) return 188;
    const height = Math.ceil(
      topbar.getBoundingClientRect().height
      + editor.getBoundingClientRect().height
      + 2,
    );
    return Math.max(160, height);
  }

  function scheduleCompactWindowFit() {
    if (!compactModeEnabled() || compactOverlayOpen()) return;
    window.cancelAnimationFrame(compactResizeFrame);
    compactResizeFrame = window.requestAnimationFrame(() => {
      compactResizeFrame = null;
      if (!compactModeEnabled() || compactOverlayOpen()) return;
      state.api?.set_compact_window?.(
        true,
        compactVisibleContentHeight(),
      ).catch?.(() => {});
    });
  }

  function expandCompactForOverlay() {
    if (!compactModeEnabled()) return;
    window.cancelAnimationFrame(compactResizeFrame);
    compactResizeFrame = null;
    state.api?.set_compact_window?.(true, COMPACT_OVERLAY_HEIGHT).catch?.(() => {});
  }

  async function persistCompactMode(enabled) {
    const response = await state.api.set_ui_settings({ compact_mode: Boolean(enabled) });
    state.ui = { ...state.ui, ...(response || {}) };
    applyCompactMode(compactModeEnabled());
    return compactModeEnabled();
  }

  function applyCompactMode(enabled, options = {}) {
    const compact = Boolean(enabled);
    const resize = options.resize !== false;
    const focus = options.focus !== false;
    state.ui.compact_mode = compact;
    document.body.dataset.compactMode = compact ? 'true' : 'false';

    if (compact && state.mode !== 'calculator') {
      switchMode('calculator');
    }

    if (resize && state.api?.set_compact_window) {
      if (compact) scheduleCompactWindowFit();
      else state.api.set_compact_window(false).catch(() => {});
    }
    const drawerOpen = !dom.drawerOverlay.classList.contains('hidden');
    if (focus && !drawerOpen && !paletteIsOpen()) {
      restoreEditorFocus(false);
    }
  }

  const switchModeWithFullLayout = switchMode;
  switchMode = function (mode) {
    if (compactModeEnabled() && mode !== 'calculator') return;
    return switchModeWithFullLayout(mode);
  };

  // initialize() merges persisted UI settings immediately before setTheme().
  // Activate compact CSS immediately, then measure the rendered topbar + editor
  // on the next frame so startup does not keep a hard-coded blank strip.
  const setThemeWithCompactMode = setTheme;
  setTheme = function (theme, persist = true) {
    const result = setThemeWithCompactMode(theme, persist);
    if (!persist) {
      applyCompactMode(state.ui.compact_mode === true, {
        resize: false,
        focus: false,
      });
      if (state.ui.compact_mode === true) scheduleCompactWindowFit();
    }
    return result;
  };

  // Compact windows are intentionally very short. Temporarily grow them while
  // any modal/palette is visible, then collapse back to measured content.
  const openDrawerWithoutCompactResize = openDrawer;
  openDrawer = function (kind) {
    if (compactModeEnabled()) expandCompactForOverlay();
    return openDrawerWithoutCompactResize(kind);
  };

  const closeDrawerWithoutCompactResize = closeDrawer;
  closeDrawer = function (focus = true) {
    const result = closeDrawerWithoutCompactResize(focus);
    if (compactModeEnabled()) scheduleCompactWindowFit();
    return result;
  };

  const openPaletteWithoutCompactResize = openPalette;
  openPalette = function () {
    if (compactModeEnabled()) expandCompactForOverlay();
    return openPaletteWithoutCompactResize();
  };

  const closePaletteWithoutCompactResize = closePalette;
  closePalette = function (focus = true) {
    const result = closePaletteWithoutCompactResize(focus);
    if (compactModeEnabled()) scheduleCompactWindowFit();
    return result;
  };

  const showOnboardingWithoutCompactResize = showOnboarding;
  showOnboarding = function () {
    if (compactModeEnabled()) expandCompactForOverlay();
    return showOnboardingWithoutCompactResize();
  };

  const closeOnboardingWithoutCompactResize = closeOnboarding;
  closeOnboarding = function () {
    const result = closeOnboardingWithoutCompactResize();
    if (compactModeEnabled()) scheduleCompactWindowFit();
    return result;
  };

  function renderCompactHistoryDrawer() {
    dom.drawerTitle.textContent = 'История';
    dom.drawerSubtitle.textContent = 'Ctrl+H';
    dom.drawerContent.replaceChildren();

    const shell = document.createElement('div');
    shell.className = 'compact-history-shell';
    const search = document.createElement('input');
    search.className = 'compact-history-search';
    search.type = 'search';
    search.placeholder = 'Поиск в истории';
    search.autocomplete = 'off';
    search.setAttribute('aria-label', 'Поиск в истории');
    const list = document.createElement('div');
    list.className = 'compact-history-list';
    shell.append(search, list);
    dom.drawerContent.appendChild(shell);

    const renderList = () => {
      const query = normalize(search.value);
      const entries = state.calculator.history.filter(
        entry => !entry.pending && historyMatches(entry, query),
      );
      list.replaceChildren();
      if (!entries.length) {
        const empty = document.createElement('div');
        empty.className = 'compact-history-empty';
        empty.textContent = query ? 'Ничего не найдено' : 'История пуста';
        list.appendChild(empty);
        return;
      }

      for (const entry of entries) {
        const row = document.createElement('div');
        row.className = 'compact-history-row';
        const load = document.createElement('button');
        load.type = 'button';
        load.className = 'compact-history-load';
        load.dataset.historyId = entry.id;
        const expression = document.createElement('span');
        expression.className = 'compact-history-expression';
        expression.textContent = displayExpression(entry.expression);
        const result = document.createElement('strong');
        result.className = 'compact-history-result';
        result.textContent = historyResultText(entry);
        result.classList.toggle('is-status', isDefinitionEntry(entry));
        load.append(expression, result);
        load.addEventListener('click', () => {
          closeDrawer(false);
          loadHistoryEntry(entry);
        });

        const copy = document.createElement('button');
        copy.type = 'button';
        copy.className = 'compact-history-copy';
        copy.textContent = 'Копировать';
        copy.title = 'Копировать результат';
        copy.addEventListener('click', () => void copyText(entry.result));
        row.append(load, copy);
        list.appendChild(row);
      }
    };

    search.addEventListener('input', renderList);
    search.addEventListener('keydown', event => {
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
      const rows = [...list.querySelectorAll('.compact-history-load')];
      if (!rows.length) return;
      event.preventDefault();
      const target = event.key === 'ArrowDown' ? rows[0] : rows[rows.length - 1];
      target.focus();
    });
    list.addEventListener('keydown', event => {
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
      const rows = [...list.querySelectorAll('.compact-history-load')];
      const current = rows.indexOf(event.target.closest('.compact-history-load'));
      if (current < 0 || !rows.length) return;
      event.preventDefault();
      const delta = event.key === 'ArrowDown' ? 1 : -1;
      const next = Math.max(0, Math.min(rows.length - 1, current + delta));
      rows[next].focus();
    });

    renderList();
    window.setTimeout(() => search.focus(), 0);
  }

  function openCompactHistory() {
    closePalette(false);
    expandCompactForOverlay();
    dom.drawerOverlay.dataset.drawerKind = 'compact-history';
    dom.drawerOverlay.classList.remove('hidden');
    dom.drawerOverlay.setAttribute('aria-hidden', 'false');
    renderCompactHistoryDrawer();
  }

  function compactHistoryOpen() {
    return (
      !dom.drawerOverlay.classList.contains('hidden')
      && dom.drawerOverlay.dataset.drawerKind === 'compact-history'
    );
  }

  const renderSettingsDrawerWithoutCompact = renderSettingsDrawer;
  renderSettingsDrawer = function () {
    renderSettingsDrawerWithoutCompact();
    const content = dom.drawerContent.querySelector('.settings-content');
    if (!content || content.querySelector('#compactMode')) return;

    const section = document.createElement('section');
    section.className = 'settings-section settings-compact-section';
    const compactLabel = document.createElement('label');
    compactLabel.className = 'settings-checkbox';
    compactLabel.innerHTML = `
      <input id="compactMode" type="checkbox">
      <span>Компактный режим</span>
    `;
    const compactHelp = document.createElement('p');
    compactHelp.className = 'settings-compact-help';
    compactHelp.textContent = 'Alt+↑ — компактный, Alt+↓ — полный, Ctrl+H — история.';
    section.append(compactLabel, compactHelp);
    content.prepend(section);

    const checkbox = compactLabel.querySelector('#compactMode');
    checkbox.checked = compactModeEnabled();
    checkbox.addEventListener('change', async () => {
      const enabled = checkbox.checked;
      checkbox.disabled = true;
      try {
        const compact = await persistCompactMode(enabled);
        checkbox.checked = compact;
        if (compact) closeDrawer(false);
      } catch (_) {
        checkbox.checked = compactModeEnabled();
        showToast('Не удалось переключить компактный режим');
      } finally {
        checkbox.disabled = false;
      }
    });
  };

  document.addEventListener('keydown', event => {
    // Escape for compact history is handled at capture level so the textarea's
    // normal Escape behavior cannot clear the expression or hide the app first.
    if (event.key === 'Escape' && compactHistoryOpen()) {
      event.preventDefault();
      event.stopImmediatePropagation();
      closeDrawer();
      return;
    }

    if (!dom.onboardingOverlay.classList.contains('hidden')) return;

    if (
      event.altKey
      && !event.ctrlKey
      && !event.metaKey
      && !event.shiftKey
      && (event.key === 'ArrowUp' || event.key === 'ArrowDown')
    ) {
      event.preventDefault();
      event.stopImmediatePropagation();
      closeTransientUi();
      const enableCompact = event.key === 'ArrowUp';
      if (compactModeEnabled() !== enableCompact) {
        void persistCompactMode(enableCompact)
          .catch(() => showToast('Не удалось переключить режим'));
      } else if (enableCompact) {
        scheduleCompactWindowFit();
      }
      return;
    }

    if (
      (event.ctrlKey || event.metaKey)
      && !event.shiftKey
      && !event.altKey
      && event.code === 'KeyH'
    ) {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (compactModeEnabled()) {
        if (compactHistoryOpen()) {
          closeDrawer();
        } else {
          closeTransientUi();
          openCompactHistory();
        }
      } else {
        closeTransientUi();
        if (state.mode !== 'calculator') switchMode('calculator');
        window.requestAnimationFrame(() => {
          dom.historySearch.focus();
          dom.historySearch.select();
        });
      }
    }
  }, { capture: true });

  if (typeof ResizeObserver === 'function') {
    const compactContentObserver = new ResizeObserver(() => {
      if (compactModeEnabled()) scheduleCompactWindowFit();
    });
    const topbar = document.querySelector('.topbar');
    const editor = document.querySelector('.editor-card');
    if (topbar) compactContentObserver.observe(topbar);
    if (editor) compactContentObserver.observe(editor);
  }
