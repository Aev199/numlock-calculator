
  const utilityIcon = (paths, viewBox = '0 0 16 16') => `
    <svg class="ui-glyph" viewBox="${viewBox}" aria-hidden="true" focusable="false">
      ${paths}
    </svg>
  `;

  const utilityIcons = {
    theme: utilityIcon('<circle cx="8" cy="8" r="5.25"></circle><path d="M8 2.75a5.25 5.25 0 0 0 0 10.5V2.75Z"></path>'),
    settings: utilityIcon('<circle cx="8" cy="8" r="2.25"></circle><path d="M8 1.75v1.5M8 12.75v1.5M1.75 8h1.5M12.75 8h1.5M3.58 3.58l1.06 1.06M11.36 11.36l1.06 1.06M12.42 3.58l-1.06 1.06M4.64 11.36l-1.06 1.06"></path>'),
    help: utilityIcon('<circle cx="8" cy="8" r="5.5"></circle><path d="M6.65 6.1a1.65 1.65 0 1 1 2.48 1.43C8.36 8 8 8.43 8 9.2"></path><circle class="ui-glyph-dot" cx="8" cy="11.45" r=".65"></circle>'),
    hide: utilityIcon('<path d="M3 8h10"></path>'),
    search: utilityIcon('<circle cx="6.75" cy="6.75" r="3.75"></circle><path d="m9.6 9.6 3.15 3.15"></path>'),
    clear: utilityIcon('<path d="M4.25 5.25h7.5M6 5.25V3.5h4v1.75M5 5.25l.5 7.25h5l.5-7.25M7 7.25v3.5M9 7.25v3.5"></path>'),
    swap: utilityIcon('<path d="M3 5h8.5M9.5 3l2 2-2 2M13 11H4.5M6.5 9l-2 2 2 2"></path>'),
    close: utilityIcon('<path d="m4 4 8 8M12 4l-8 8"></path>'),
  };

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

  document.querySelectorAll('.search-field > span, .palette-search-wrap > span').forEach(element => {
    element.innerHTML = utilityIcons.search;
  });
