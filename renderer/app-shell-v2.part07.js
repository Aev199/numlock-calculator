      if (action === 'delete') {
        event.stopPropagation();
        await deleteHistoryEntry(entry);
        return;
      }
      // The number goes into the expression; the rest of the row opens it.
      if (event.target.closest('.history-result')) {
        event.stopPropagation();
        insertHistoryResult(entry);
        return;
      }
      loadHistoryEntry(entry);
    });

    dom.clearHistoryButton.addEventListener('click', async () => {
      if (state.calculator.pendingCommits > 0) {
        showToast('Дождитесь сохранения текущего вычисления');
        return;
      }
      // No confirmation: the toast offers to bring everything back.
      const cleared = state.calculator.history.filter(entry => !entry.pending);
      ++state.calculator.historyEpoch;
      state.calculator.history = [];
      reconcileHistory();
      try {
        await state.api.clear_history();
        showToast('История очищена', {
          label: 'Вернуть',
          run: () => void restoreHistoryEntries(cleared),
        });
      } catch (_) {
        showToast('Не удалось очистить историю');
        const data = await state.api.bootstrap().catch(() => null);
        if (data?.history) {
          state.calculator.history = data.history;
          reconcileHistory();
        }
      }
    });

    dom.category.addEventListener('change', () => {
      state.units.category = dom.category.value;
      renderUnitControls(true);
      ++state.units.previewSequence;
      state.units.preview = null;
      scheduleUnitsPreview(0);
      persistUnitsSoon();
    });
    dom.sourceUnit.addEventListener('change', () => {
      state.units.from_unit = dom.sourceUnit.value;
      renderUnitControls();
      ++state.units.previewSequence;
      state.units.preview = null;
      scheduleUnitsPreview(0);
      persistUnitsSoon();
    });
    dom.targetUnit.addEventListener('change', () => {
      state.units.to_unit = dom.targetUnit.value;
      renderUnitControls();
      ++state.units.previewSequence;
      state.units.preview = null;
      scheduleUnitsPreview(0);
      persistUnitsSoon();
    });
    dom.swapUnits.addEventListener('click', () => {
      const previous = state.units.from_unit;
      state.units.from_unit = state.units.to_unit;
      state.units.to_unit = previous;
      if (state.units.preview?.ok && state.units.preview.result) {
        state.units.expression = String(state.units.preview.result);
        setInputValue(state.units.expression);
      }
      renderUnitControls();
      ++state.units.previewSequence;
      state.units.preview = null;
      scheduleUnitsPreview(0);
      persistUnitsSoon();
    });

    dom.paletteButton.addEventListener('click', openPalette);
    dom.memoryButton.addEventListener('click', () => openDrawer('memory'));
    dom.variablesButton.addEventListener('click', () => openDrawer('variables'));
    dom.formulasButton.addEventListener('click', () => openDrawer('formulas'));
    dom.drawerClose.addEventListener('click', () => closeDrawer());
    dom.paletteOverlay.addEventListener('mousedown', event => {
      if (event.target === dom.paletteOverlay) closePalette();
    });
    dom.drawerOverlay.addEventListener('mousedown', event => {
      if (event.target === dom.drawerOverlay) closeDrawer();
    });

    dom.paletteSearch.addEventListener('input', filterPalette);
    dom.paletteSearch.addEventListener('keydown', event => {
      if (
        event.key === 'Tab'
        && !event.ctrlKey
        && !event.metaKey
        && !event.altKey
      ) {
        event.preventDefault();
        event.stopPropagation();
        closePalette();
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        closePalette();
        return;
      }
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        if (!state.palette.groups.length) return;
        const delta = event.key === 'ArrowRight' ? 1 : -1;
        state.palette.groupIndex = (
          state.palette.groupIndex + delta + state.palette.groups.length
        ) % state.palette.groups.length;
        state.palette.itemIndex = 0;
        renderPalette();
        return;
      }
      const items = activePaletteItems();
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (!items.length) return;
        const delta = event.key === 'ArrowDown' ? 1 : -1;
        state.palette.itemIndex = (
          state.palette.itemIndex + delta + items.length
        ) % items.length;
        renderPalette();
        return;
      }
      if (event.key === 'Enter') {
        event.preventDefault();
        const item = items[state.palette.itemIndex];
        if (item) insertSuggestion(item);
      }
    });

    dom.angleMode.addEventListener('click', async () => {
      if (state.mode !== 'calculator') return;
      const modes = ['DEG', 'RAD', 'GRAD'];
      const next = modes[
        (modes.indexOf(state.settings.angle_mode) + 1) % modes.length
      ];
      applySettings(await state.api.set_settings({ angle_mode: next }));
      scheduleCalculatorPreview(0);
    });
    dom.numberBase.addEventListener('click', async () => {
      if (state.mode !== 'calculator') return;
      const bases = ['DEC', 'HEX', 'OCT', 'BIN'];
      const next = bases[
        (bases.indexOf(state.settings.number_base) + 1) % bases.length
      ];
      applySettings(await state.api.set_settings({ number_base: next }));
      scheduleCalculatorPreview(0);
    });
    dom.themeButton.addEventListener('click', () => {
      setTheme(state.ui.theme === 'dark' ? 'light' : 'dark');
    });
    dom.hideButton.addEventListener('click', () => state.api.hide_app());
    dom.quitButton.addEventListener('click', () => state.api.quit_app());

    document.addEventListener('keydown', event => {
      if (!isPaletteShortcut(event)) return;
      event.preventDefault();
      event.stopPropagation();
      if (state.mode !== 'calculator') return;
      if (paletteIsOpen()) closePalette();
      else openPalette();
    });

    // Drawers opened by mouse keep focus on their toolbar button, so Escape is
    // handled at document level. Capture runs before the editor clears itself.
    document.addEventListener('keydown', event => {
      if (event.key !== 'Escape' || dom.drawerOverlay.classList.contains('hidden')) return;
      if (event.target?.classList?.contains('is-listening')) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      closeDrawer();
    }, { capture: true });

    window.addEventListener('focus', () => {
      state.api?.window_focus_changed(true).catch(() => {});
    });
    window.addEventListener('blur', () => {
      state.api?.window_focus_changed(false).catch(() => {});
    });
  }

  async function initialize() {
    document.documentElement.dataset.renderer = RENDERER_MARKER;
    state.api = await waitForBridge();
    const data = await state.api.bootstrap();
    state.settings = { ...state.settings, ...(data.settings || {}) };
    state.ui = { ...state.ui, ...(data.ui_settings || {}) };
    state.variables = data.variables || {};
    state.memories = data.memories || Array(10).fill('0');
    state.formulas = data.formulas || [];
    state.profiles = data.profiles || [];
    state.activeProfileId = data.active_profile_id || null;
    state.activeProfile = data.active_profile || null;
    state.profileConstants = data.profile_constants || {};
    state.calculator.history = data.history || [];
    setCatalog(data.suggestions || []);

    const unitData = data.unit_converter || {};
    state.units.categories = unitData.categories || [];
    Object.assign(state.units, unitData.state || {});
    state.calculator.handoff = {
      ...state.calculator.handoff,
      ...(unitData.calculator_handoff || {}),
    };
    loadInterpolationState(data.interpolation);

    applySettings(state.settings);
    setTheme(state.ui.theme, false);
    renderUnitControls(true);
