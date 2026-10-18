
  const utilityIcon = (paths, viewBox = '0 0 16 16') => `
    <svg class="ui-glyph" viewBox="${viewBox}" aria-hidden="true" focusable="false">
      ${paths}
    </svg>
  `;

  const utilityIcons = {
    theme: utilityIcon('<circle cx="8" cy="8" r="5.25"></circle><path d="M8 2.75a5.25 5.25 0 0 0 0 10.5V2.75Z"></path>'),
    settings: utilityIcon('<path d="M6.55 2.2h2.9l.35 1.55c.35.13.68.31.98.53l1.5-.48 1.45 2.5-1.15 1.08c.03.2.05.41.05.62s-.02.42-.05.62l1.15 1.08-1.45 2.5-1.5-.48c-.3.22-.63.4-.98.53l-.35 1.55h-2.9l-.35-1.55a4.8 4.8 0 0 1-.98-.53l-1.5.48-1.45-2.5 1.15-1.08A4 4 0 0 1 3.37 8c0-.21.02-.42.05-.62L2.27 6.3l1.45-2.5 1.5.48c.3-.22.63-.4.98-.53l.35-1.55Z"></path><circle cx="8" cy="8" r="1.75"></circle>'),
    help: utilityIcon('<circle cx="8" cy="8" r="5.5"></circle><path d="M6.65 6.1a1.65 1.65 0 1 1 2.48 1.43C8.36 8 8 8.43 8 9.2"></path><circle class="ui-glyph-dot" cx="8" cy="11.45" r=".65"></circle>'),
    hide: utilityIcon('<path d="M3 8h10"></path>'),
    search: utilityIcon('<circle cx="6.75" cy="6.75" r="3.75"></circle><path d="m9.6 9.6 3.15 3.15"></path>'),
    clear: utilityIcon('<path d="M4.25 5.25h7.5M6 5.25V3.5h4v1.75M5 5.25l.5 7.25h5l.5-7.25M7 7.25v3.5M9 7.25v3.5"></path>'),
    swap: utilityIcon('<path d="M3 5h8.5M9.5 3l2 2-2 2M13 11H4.5M6.5 9l-2 2 2 2"></path>'),
    close: utilityIcon('<path d="m4 4 8 8M12 4l-8 8"></path>'),
    functions: utilityIcon('<path d="M10.75 2.75c-1.55-.4-2.5.3-2.8 1.85L6.6 11.4c-.3 1.55-1.25 2.25-2.8 1.85M5 6.75h4.75"></path>'),
    memory: utilityIcon('<ellipse cx="8" cy="4.25" rx="4.5" ry="1.75"></ellipse><path d="M3.5 4.25v7.5c0 .97 2 1.75 4.5 1.75s4.5-.78 4.5-1.75v-7.5M3.5 8c0 .97 2 1.75 4.5 1.75S12.5 8.97 12.5 8"></path>'),
    variables: utilityIcon('<path d="M5.75 2.75c-1.1 0-1.6.55-1.6 1.5v1.6c0 .85-.45 1.4-1.4 1.4.95 0 1.4.55 1.4 1.4v1.6c0 .95.5 1.5 1.6 1.5M10.25 2.75c1.1 0 1.6.55 1.6 1.5v1.6c0 .85.45 1.4 1.4 1.4-.95 0-1.4.55-1.4 1.4v1.6c0 .95-.5 1.5-1.6 1.5"></path>'),
    formulas: utilityIcon('<path d="M12 3.25H4.25L8.5 8l-4.25 4.75H12"></path>'),
  };

  // Same outline as app_icon.py, so the window, tray and EXE share one logo.
  const brandLogo = `
    <svg class="brand-logo" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
      <rect x="3" y="3" width="58" height="58" rx="14"></rect>
      <path d="M17 47V17h8l14 18.5V17h8v30h-8L25 28.5V47Z"></path>
    </svg>
  `;

  function setUtilityIcon(element, icon) {
    if (!element || !icon) return;
    element.innerHTML = icon;
  }

  setUtilityIcon(document.getElementById('themeButton'), utilityIcons.theme);
  setUtilityIcon(document.getElementById('settingsButton'), utilityIcons.settings);
  setUtilityIcon(document.getElementById('helpButton'), utilityIcons.help);
  setUtilityIcon(document.getElementById('hideButton'), utilityIcons.hide);
  setUtilityIcon(document.getElementById('clearHistoryButton'), utilityIcons.clear);
  setUtilityIcon(document.getElementById('swapUnitsButton'), utilityIcons.swap);
  setUtilityIcon(document.getElementById('drawerClose'), utilityIcons.close);
  setUtilityIcon(document.getElementById('onboardingClose'), utilityIcons.close);
  document.querySelectorAll('.brand-mark').forEach(element => {
    element.innerHTML = brandLogo;
  });
  const aboutTitle = document.getElementById('aboutTitle');
  if (aboutTitle && !aboutTitle.querySelector('.brand-logo')) {
    aboutTitle.insertAdjacentHTML('afterbegin', brandLogo);
  }
  setUtilityIcon(document.querySelector('.about-close'), utilityIcons.close);
  setUtilityIcon(document.getElementById('paletteButton'), utilityIcons.functions);
  setUtilityIcon(document.getElementById('memoryButton'), utilityIcons.memory);
  setUtilityIcon(document.getElementById('variablesButton'), utilityIcons.variables);
  setUtilityIcon(document.getElementById('formulasButton'), utilityIcons.formulas);

  document.querySelectorAll('.search-field > span, .palette-search-wrap > span').forEach(element => {
    element.innerHTML = utilityIcons.search;
  });
