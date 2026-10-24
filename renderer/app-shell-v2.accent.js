  // Accent colour: a row of swatches in Settings, saved with the UI settings.
  // The colours match app-shell-accent.css; blue is the original accent.
  const ACCENTS = [
    { id: 'blue', label: 'Синий', light: '#526dff', dark: '#788cff' },
    { id: 'violet', label: 'Фиолетовый', light: '#7c4dff', dark: '#a48bff' },
    { id: 'green', label: 'Зелёный', light: '#1a7f45', dark: '#4cc38a' },
    { id: 'teal', label: 'Бирюзовый', light: '#0b7f92', dark: '#3bc9db' },
    { id: 'orange', label: 'Оранжевый', light: '#c2410c', dark: '#ff8f4d' },
    { id: 'pink', label: 'Розовый', light: '#c92a64', dark: '#f06595' },
    { id: 'graphite', label: 'Графит', light: '#495057', dark: '#adb5bd' },
  ];

  function knownAccent(accent) {
    return ACCENTS.some(item => item.id === accent) ? accent : ACCENTS[0].id;
  }

  function applyAccent(accent) {
    const next = knownAccent(accent);
    state.ui.accent = next;
    if (next === ACCENTS[0].id) delete document.body.dataset.accent;
    else document.body.dataset.accent = next;
    renderAccentOptions();
  }

  function renderAccentOptions() {
    const group = dom.drawerContent.querySelector('.accent-options');
    if (!group) return;
    const theme = state.ui.theme === 'light' ? 'light' : 'dark';
    const current = knownAccent(state.ui.accent);
    group.querySelectorAll('.accent-option').forEach(option => {
      const accent = ACCENTS.find(item => item.id === option.dataset.accent);
      const selected = accent.id === current;
      option.style.setProperty('--swatch', accent[theme]);
      option.setAttribute('aria-checked', String(selected));
      option.tabIndex = selected ? 0 : -1;
    });
  }

  function chooseAccent(accent, focus = false) {
    applyAccent(accent);
    state.api?.set_ui_settings?.({ accent: state.ui.accent }).catch?.(() => {
      showToast('Не удалось сохранить цвет');
    });
    if (focus) {
      dom.drawerContent.querySelector(`.accent-option[data-accent="${state.ui.accent}"]`)?.focus();
    }
  }

  // Swatches show the variant of the current theme, so they follow theme changes.
  const setThemeWithoutAccent = setTheme;
  setTheme = function (theme, persist = true) {
    const result = setThemeWithoutAccent(theme, persist);
    applyAccent(state.ui.accent);
    return result;
  };

  const renderSettingsDrawerWithoutAccent = renderSettingsDrawer;
  renderSettingsDrawer = function renderSettingsDrawerWithAccent() {
    renderSettingsDrawerWithoutAccent();
    const content = dom.drawerContent.querySelector('.settings-content');
    if (!content || content.querySelector('.settings-accent')) return;

    const section = document.createElement('section');
    section.className = 'settings-section settings-accent';
    const label = document.createElement('span');
    label.className = 'settings-label';
    label.id = 'accentLabel';
    label.textContent = 'Цвет акцента';
    const group = document.createElement('div');
    group.className = 'accent-options';
    group.setAttribute('role', 'radiogroup');
    group.setAttribute('aria-labelledby', 'accentLabel');
    for (const accent of ACCENTS) {
      const option = document.createElement('button');
      option.type = 'button';
      option.className = 'accent-option';
      option.dataset.accent = accent.id;
      option.setAttribute('role', 'radio');
      option.title = accent.label;
      option.setAttribute('aria-label', accent.label);
      option.addEventListener('click', () => chooseAccent(accent.id));
      group.appendChild(option);
    }
    // Arrow keys move the choice, as in any radio group.
    group.addEventListener('keydown', event => {
      const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
      if (!step) return;
      event.preventDefault();
      const index = ACCENTS.findIndex(item => item.id === knownAccent(state.ui.accent));
      chooseAccent(ACCENTS[(index + step + ACCENTS.length) % ACCENTS.length].id, true);
    });
    section.append(label, group);

    const compact = content.querySelector('.settings-compact-section');
    if (compact) compact.after(section);
    else content.prepend(section);
    renderAccentOptions();
  };
