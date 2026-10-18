  function restoreFocusInCurrentMode(selectAll = true) {
    closeTransientUi();
    if (state.mode === 'interpolation') {
      interpolationField(INTERPOLATION_FIELDS[0])?.focus();
      return;
    }
    restoreEditorFocus(Boolean(selectAll));
  }

  // Returning focus to an already visible window must never change the current
  // tab. This is deliberately separate from showing a previously hidden window.
  window.__nlcalcRestoreEditorFocus = function (selectAll = true) {
    restoreFocusInCurrentMode(selectAll);
  };

  // Hidden -> shown may optionally reset to Calculator. The preference defaults
  // to true for the existing product behavior; disabling it preserves the tab
  // that was active when the window was hidden.
  window.__nlcalcRestoreEditorFocusFromHidden = function (selectAll = true) {
    closeTransientUi();
    if (
      state.ui.focus_calculator_on_restore !== false
      && state.mode !== 'calculator'
    ) {
      switchMode('calculator');
    }
    if (state.mode === 'interpolation') {
      interpolationField(INTERPOLATION_FIELDS[0])?.focus();
      return;
    }
    restoreEditorFocus(Boolean(selectAll));
  };

  const renderSettingsDrawerWithoutRestoreScope = renderSettingsDrawer;
  renderSettingsDrawer = function renderSettingsDrawerWithRestoreScope() {
    renderSettingsDrawerWithoutRestoreScope();
    const checkbox = dom.drawerContent.querySelector('#focusCalculatorOnRestore');
    const label = checkbox?.closest('.settings-checkbox')?.querySelector('span');
    if (label) {
      label.textContent = 'При открытии скрытого окна переходить в калькулятор';
    }

    const section = checkbox?.closest('.settings-section');
    if (section && !section.querySelector('.restore-mode-help')) {
      const help = document.createElement('p');
      help.className = 'settings-help restore-mode-help';
      help.textContent = 'Иначе остаётся последняя вкладка.';
      section.appendChild(help);
    }
  };
