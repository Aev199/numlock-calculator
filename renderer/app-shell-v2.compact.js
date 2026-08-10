
  state.ui.compact_mode = state.ui.compact_mode === true;

  function compactModeEnabled() {
    return state.ui.compact_mode === true;
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
      state.api.set_compact_window(compact).catch(() => {});
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
  // Hook that existing initialization point so compact CSS is active before
  // the first editor focus without adding another bootstrap path.
  const setThemeWithCompactMode = setTheme;
  setTheme = function (theme, persist = true) {
    const result = setThemeWithCompactMode(theme, persist);
    if (!persist) {
      applyCompactMode(state.ui.compact_mode === true, {
        resize: false,
        focus: false,
      });
    }
    return result;
  };

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
    compactHelp.textContent = 'Только калькулятор: без истории, единиц и интерполяции.';
    section.append(compactLabel, compactHelp);
    content.prepend(section);

    const checkbox = compactLabel.querySelector('#compactMode');
    checkbox.checked = compactModeEnabled();
    checkbox.addEventListener('change', async () => {
      const enabled = checkbox.checked;
      checkbox.disabled = true;
      try {
        const response = await state.api.set_ui_settings({ compact_mode: enabled });
        state.ui = { ...state.ui, ...(response || {}) };
        checkbox.checked = compactModeEnabled();
        if (compactModeEnabled()) closeDrawer(false);
        applyCompactMode(compactModeEnabled());
      } catch (_) {
        checkbox.checked = compactModeEnabled();
      } finally {
        checkbox.disabled = false;
      }
    });
  };
