(function () {
  'use strict';

  const {
    CalculatorEngine,
    formatNumber,
    normalizeExpression,
  } = window.NumLockCalcCore;

  const engine = new CalculatorEngine();
  let history = [];
  let isEngineerMode = true;
  let storage = null;

  const exprInput = document.getElementById('exprInput');
  const resultLine = document.getElementById('resultLine');
  const keypad = document.getElementById('keypad');
  const btnMode = document.getElementById('btnMode');
  const btnClearHistory = document.getElementById('btnClearHistory');
  const historyScroll = document.getElementById('historyScroll');
  const converterWrap = document.getElementById('converterWrap');
  const btnTheme = document.getElementById('btnTheme');
  const btnExit = document.getElementById('btnExit');

  const standardButtons = [
    ['MC', 'MR', 'M+', 'M-', 'C'],
    ['7', '8', '9', '/', '√'],
    ['4', '5', '6', '*', '%'],
    ['1', '2', '3', '-', '1/x'],
    ['0', '.', '±', '+', '='],
  ];

  const engineerButtons = [
    ['sin', 'cos', 'tan', 'log', 'ln', 'C'],
    ['sin⁻¹', 'cos⁻¹', 'tan⁻¹', '10ˣ', 'eˣ', '⌫'],
    ['x²', 'x³', 'xⁿ', '√', '∛', 'π'],
    ['(', ')', 'EXP', 'n!', 'MC', 'MR'],
    ['7', '8', '9', '/', 'M+', 'M-'],
    ['4', '5', '6', '*', '±', '%'],
    ['1', '2', '3', '-', '.', '1/x'],
    ['0', '=', '+', '', '', ''],
  ];

  const functionMap = {
    sin: 'sin', cos: 'cos', tan: 'tan',
    'sin⁻¹': 'asin', 'cos⁻¹': 'acos', 'tan⁻¹': 'atan',
    log: 'log10', ln: 'ln', '10ˣ': 'pow10', 'eˣ': 'exp',
    'x²': 'sqr', 'x³': 'cube', '√': 'sqrt', '∛': 'cbrt',
    '1/x': 'inv', 'n!': 'fact',
  };

  const selectedFunctionSyntax = {
    sin: value => `sin(${value})`,
    cos: value => `cos(${value})`,
    tan: value => `tan(${value})`,
    'sin⁻¹': value => `sin⁻¹(${value})`,
    'cos⁻¹': value => `cos⁻¹(${value})`,
    'tan⁻¹': value => `tan⁻¹(${value})`,
    log: value => `log(${value})`,
    ln: value => `ln(${value})`,
    '10ˣ': value => `10^(${value})`,
    'eˣ': value => `e^(${value})`,
    'x²': value => `sqr(${value})`,
    'x³': value => `cube(${value})`,
    '√': value => `√(${value})`,
    '∛': value => `∛(${value})`,
    '1/x': value => `1/(${value})`,
    'n!': value => `fact(${value})`,
  };

  function createStorageAdapter() {
    const pythonHost = Boolean(window.__NUMLOCK_PYWEBVIEW__);

    async function waitForBridge() {
      if (!pythonHost) return null;
      if (window.pywebview && window.pywebview.api) return window.pywebview.api;
      return new Promise(resolve => {
        const handler = () => resolve(window.pywebview.api);
        window.addEventListener('pywebviewready', handler, { once: true });
      });
    }

    return waitForBridge().then(api => {
      if (api) {
        return {
          get: key => api.storage_get(key),
          set: (key, value) => api.storage_set(key, value),
          remove: key => api.storage_remove(key),
          clear: () => api.storage_clear(),
          quit: () => api.quit_app(),
        };
      }
      return {
        get: async key => window.localStorage.getItem(key),
        set: async (key, value) => window.localStorage.setItem(key, value),
        remove: async key => window.localStorage.removeItem(key),
        clear: async () => window.localStorage.clear(),
        quit: async () => window.close(),
      };
    });
  }

  function safeParseHistory(value) {
    if (!value) return [];
    try {
      const parsed = JSON.parse(value);
      if (!Array.isArray(parsed)) return [];
      return parsed
        .filter(item => item && typeof item.expr === 'string' && typeof item.res === 'string')
        .slice(0, 200);
    } catch (_) {
      return [];
    }
  }

  function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = String(value);
    return div.innerHTML;
  }

  function updateResult() {
    const state = engine.snapshot();
    resultLine.textContent = state.result;
    resultLine.classList.toggle('is-error', state.error);
  }

  function updateDisplay(options = {}) {
    const state = engine.snapshot();
    exprInput.value = state.displayExpression;
    updateResult();

    if (options.focus) {
      requestAnimationFrame(() => {
        exprInput.focus();
        const cursor = options.cursor === 'start' ? 0 : exprInput.value.length;
        exprInput.setSelectionRange(cursor, cursor);
      });
    }
  }

  function syncEngineFromInput() {
    const normalized = normalizeExpression(exprInput.value);
    if (normalized !== exprInput.value) {
      const start = exprInput.selectionStart ?? normalized.length;
      const end = exprInput.selectionEnd ?? start;
      exprInput.value = normalized;
      exprInput.setSelectionRange(start, end);
    }
    engine.setExpression(exprInput.value);
    updateResult();
  }

  function selection() {
    const start = exprInput.selectionStart ?? exprInput.value.length;
    const end = exprInput.selectionEnd ?? start;
    return { start, end, text: exprInput.value.slice(start, end) };
  }

  function replaceSelection(text, selectInserted = false) {
    const { start, end } = selection();
    const before = exprInput.value.slice(0, start);
    const after = exprInput.value.slice(end);
    exprInput.value = `${before}${text}${after}`;
    engine.setExpression(exprInput.value);
    updateResult();

    requestAnimationFrame(() => {
      exprInput.focus();
      const nextStart = selectInserted ? start : start + text.length;
      const nextEnd = selectInserted ? start + text.length : nextStart;
      exprInput.setSelectionRange(nextStart, nextEnd);
    });
  }

  function deleteAtCursor() {
    const { start, end } = selection();
    if (start !== end) {
      replaceSelection('');
      return;
    }
    if (start <= 0) return;
    exprInput.setSelectionRange(start - 1, end);
    replaceSelection('');
  }

  function insertionForLabel(label) {
    if (/^[0-9]$/.test(label)) return label;
    if (['+', '-', '*', '/', '(', ')', '.'].includes(label)) return label;
    if (label === 'xⁿ') return '^';
    if (label === 'EXP') return 'e';
    if (label === 'π') return 'π';
    if (label === 'MR') return formatNumber(engine.snapshot().memory);
    return null;
  }

  function shouldStartFresh(label, state) {
    return state.justEvaluated && (/^[0-9.]$/.test(label) || label === '(' || label === 'π');
  }

  function applyFunctionToSelection(label) {
    const builder = selectedFunctionSyntax[label];
    const range = selection();
    if (!builder || !range.text) return false;
    replaceSelection(builder(range.text));
    return true;
  }

  function buildKeypad(mode) {
    const buttons = mode === 'engineer' ? engineerButtons : standardButtons;
    keypad.innerHTML = '';
    keypad.className = `keypad ${mode === 'engineer' ? 'engineer' : 'standard'}`;

    buttons.flat().forEach(label => {
      if (!label) {
        const spacer = document.createElement('div');
        spacer.className = 'key-spacer';
        keypad.appendChild(spacer);
        return;
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      button.classList.add('btn');
      if (/^[0-9.]$/.test(label)) button.classList.add('btn--number');
      else if (['+', '-', '*', '/', '%'].includes(label)) button.classList.add('btn--operator');
      else if (label === '=') button.classList.add('btn--equals');
      else if (['MC', 'MR', 'M+', 'M-'].includes(label)) button.classList.add('btn--memory');
      else button.classList.add('btn--func');
      button.addEventListener('click', () => handleButton(label));
      keypad.appendChild(button);
    });
  }

  function handleButton(label) {
    const stateBefore = engine.snapshot();

    if (label === 'C') {
      engine.clear();
      updateDisplay({ focus: true });
      return;
    }

    if (label === '⌫') {
      deleteAtCursor();
      return;
    }

    if (applyFunctionToSelection(label)) return;

    if (label === '±' && selection().text) {
      replaceSelection(`-(${selection().text})`);
      return;
    }

    const insertion = insertionForLabel(label);
    if (insertion !== null) {
      if (shouldStartFresh(label, stateBefore)) {
        exprInput.value = '';
        exprInput.setSelectionRange(0, 0);
      }
      replaceSelection(insertion);
      return;
    }

    syncEngineFromInput();
    const coreLabel = functionMap[label] || label;
    const outcome = engine.press(coreLabel);
    if (outcome.historyEntry) addToHistory(outcome.historyEntry.expr, outcome.historyEntry.res);
    updateDisplay({ focus: label !== 'MC' && label !== 'M+' && label !== 'M-' });
  }

  async function addToHistory(expr, res) {
    history.unshift({ expr, res, time: Date.now() });
    history = history.slice(0, 200);
    renderHistoryPanel();
    try {
      await storage.set('nlcalc_history', JSON.stringify(history));
    } catch (_) {}
  }

  function renderHistoryPanel() {
    if (!history.length) {
      historyScroll.innerHTML = '<div class="history-empty">Нет истории</div>';
      return;
    }
    historyScroll.innerHTML = history.slice(0, 20).map((item, index) => `
      <button type="button" class="history-item" data-index="${index}" title="Загрузить выражение для редактирования">
        <span class="history-expr" title="${escapeHtml(item.expr)}">${escapeHtml(item.expr)}</span>
        <span class="history-res">${escapeHtml(item.res)}</span>
      </button>
    `).join('');

    historyScroll.querySelectorAll('.history-item').forEach(item => {
      item.addEventListener('click', () => {
        const entry = history[Number(item.dataset.index)];
        engine.loadExpression(entry.expr, entry.res);
        updateDisplay({ focus: true });
      });
    });
  }

  async function clearHistory() {
    if (!window.confirm('Очистить всю историю вычислений?')) return;
    history = [];
    renderHistoryPanel();
    try {
      await storage.remove('nlcalc_history');
    } catch (_) {}
  }

  function buildConverter() {
    const categories = {
      Давление: {
        units: ['Па', 'кПа', 'МПа', 'бар', 'атм', 'мм рт.ст.', 'psi'],
        toBase: [1, 1000, 1e6, 1e5, 101325, 133.3223684211, 6894.757293168],
      },
      Площадь: {
        units: ['м²', 'км²', 'га', 'см²', 'мм²', 'дюйм²', 'фут²'],
        toBase: [1, 1e6, 10000, 1e-4, 1e-6, 0.00064516, 0.09290304],
      },
      Сила: {
        units: ['Н', 'кН', 'кгс', 'фунт-сила', 'дина'],
        toBase: [1, 1000, 9.80665, 4.4482216153, 1e-5],
      },
      Объём: {
        units: ['м³', 'л', 'мл', 'см³', 'галлон (US)', 'фут³'],
        toBase: [1, 0.001, 1e-6, 1e-6, 0.003785411784, 0.028316846592],
      },
      Длина: {
        units: ['м', 'км', 'см', 'мм', 'дюйм', 'фут', 'миля'],
        toBase: [1, 1000, 0.01, 0.001, 0.0254, 0.3048, 1609.344],
      },
      Масса: {
        units: ['кг', 'г', 'т', 'фунт', 'унция'],
        toBase: [1, 0.001, 1000, 0.45359237, 0.028349523125],
      },
      Температура: {
        units: ['°C', '°F', 'K'],
        toBase: null,
      },
    };

    const category = document.createElement('select');
    const fromUnit = document.createElement('select');
    const toUnit = document.createElement('select');
    const fromInput = document.createElement('input');
    const toInput = document.createElement('input');
    fromInput.type = 'number';
    fromInput.step = 'any';
    fromInput.value = '1';
    toInput.type = 'text';
    toInput.readOnly = true;

    Object.keys(categories).forEach(name => category.appendChild(new Option(name, name)));

    function populateUnits() {
      const data = categories[category.value];
      fromUnit.innerHTML = '';
      toUnit.innerHTML = '';
      data.units.forEach(unit => {
        fromUnit.appendChild(new Option(unit, unit));
        toUnit.appendChild(new Option(unit, unit));
      });
      toUnit.selectedIndex = Math.min(1, data.units.length - 1);
    }

    function formatConverted(value) {
      if (!Number.isFinite(value)) return 'Error';
      if (value === 0) return '0';
      if (Math.abs(value) >= 1e12 || Math.abs(value) < 1e-9) return value.toExponential(8);
      return Number(value.toPrecision(12)).toString();
    }

    function convert() {
      const input = Number(fromInput.value);
      if (!Number.isFinite(input)) {
        toInput.value = '';
        return;
      }
      const data = categories[category.value];
      let result;
      if (category.value === 'Температура') {
        let kelvin;
        if (fromUnit.value === '°C') kelvin = input + 273.15;
        else if (fromUnit.value === '°F') kelvin = (input - 32) * 5 / 9 + 273.15;
        else kelvin = input;
        if (kelvin < 0) {
          toInput.value = 'Ниже абсолютного нуля';
          return;
        }
        if (toUnit.value === '°C') result = kelvin - 273.15;
        else if (toUnit.value === '°F') result = (kelvin - 273.15) * 9 / 5 + 32;
        else result = kelvin;
      } else {
        const fromIndex = data.units.indexOf(fromUnit.value);
        const toIndex = data.units.indexOf(toUnit.value);
        result = input * data.toBase[fromIndex] / data.toBase[toIndex];
      }
      toInput.value = formatConverted(result);
    }

    category.addEventListener('change', () => { populateUnits(); convert(); });
    fromUnit.addEventListener('change', convert);
    toUnit.addEventListener('change', convert);
    fromInput.addEventListener('input', convert);

    const swap = document.createElement('button');
    swap.type = 'button';
    swap.className = 'swap-btn';
    swap.textContent = '⇄';
    swap.title = 'Поменять единицы местами';
    swap.addEventListener('click', () => {
      const oldFrom = fromUnit.value;
      fromUnit.value = toUnit.value;
      toUnit.value = oldFrom;
      const converted = Number(toInput.value);
      if (Number.isFinite(converted)) fromInput.value = String(converted);
      convert();
    });

    function field(label, input, select) {
      const wrapper = document.createElement('div');
      wrapper.className = 'conv-field';
      const caption = document.createElement('label');
      caption.textContent = label;
      wrapper.append(caption, input, select);
      return wrapper;
    }

    const categoryRow = document.createElement('div');
    categoryRow.className = 'conv-row';
    const categoryField = document.createElement('div');
    categoryField.className = 'conv-field';
    const categoryLabel = document.createElement('label');
    categoryLabel.textContent = 'Категория';
    categoryField.append(categoryLabel, category);
    categoryRow.appendChild(categoryField);

    const valuesRow = document.createElement('div');
    valuesRow.className = 'conv-row';
    valuesRow.append(field('Из', fromInput, fromUnit), swap, field('В', toInput, toUnit));

    converterWrap.innerHTML = '';
    converterWrap.append(categoryRow, valuesRow);
    populateUnits();
    convert();
  }

  function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(button => {
      button.classList.toggle('active', button.dataset.tab === name);
    });
    document.querySelectorAll('.tab-content').forEach(content => {
      content.classList.toggle('active', content.id === `tab-${name}`);
    });
  }

  async function setTheme(theme) {
    const value = theme === 'dark' ? 'dark' : 'light';
    document.body.setAttribute('data-theme', value);
    try { await storage.set('nlcalc_theme', value); } catch (_) {}
  }

  async function initialize() {
    storage = await createStorageAdapter();
    let savedHistory = null;
    let savedTheme = null;
    let savedMode = null;
    try {
      [savedHistory, savedTheme, savedMode] = await Promise.all([
        storage.get('nlcalc_history'),
        storage.get('nlcalc_theme'),
        storage.get('nlcalc_mode'),
      ]);
    } catch (_) {}

    history = safeParseHistory(savedHistory);
    isEngineerMode = savedMode !== 'standard';
    document.body.setAttribute('data-theme', savedTheme === 'dark' ? 'dark' : 'light');
    btnMode.textContent = isEngineerMode ? 'Режим: инженерный' : 'Режим: стандартный';
    buildKeypad(isEngineerMode ? 'engineer' : 'standard');
    buildConverter();
    renderHistoryPanel();
    updateDisplay();
  }

  document.querySelectorAll('.tab-btn').forEach(button => {
    button.addEventListener('click', () => switchTab(button.dataset.tab));
  });

  btnTheme.addEventListener('click', () => {
    const next = document.body.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    setTheme(next);
  });

  btnExit.addEventListener('click', async () => {
    if (storage) await storage.quit();
  });

  btnClearHistory.addEventListener('click', clearHistory);

  btnMode.addEventListener('click', async () => {
    isEngineerMode = !isEngineerMode;
    btnMode.textContent = isEngineerMode ? 'Режим: инженерный' : 'Режим: стандартный';
    buildKeypad(isEngineerMode ? 'engineer' : 'standard');
    try { await storage.set('nlcalc_mode', isEngineerMode ? 'engineer' : 'standard'); } catch (_) {}
  });

  exprInput.addEventListener('input', syncEngineFromInput);
  exprInput.addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleButton('=');
    } else if (event.key === 'Escape') {
      event.preventDefault();
      handleButton('C');
    }
  });

  document.addEventListener('keydown', event => {
    const activeTab = document.querySelector('.tab-content.active');
    if (!activeTab || activeTab.id !== 'tab-calc') return;
    if (event.target === exprInput || event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return;

    const key = event.key === ',' ? '.' : event.key;
    if (/^[0-9.]$/.test(key)) handleButton(key);
    else {
      const map = {
        '+': '+', '-': '-', '*': '*', '/': '/', '%': '%', '^': 'xⁿ',
        Enter: '=', Escape: 'C', Backspace: '⌫', Delete: 'C',
        '(': '(', ')': ')',
      };
      if (!map[key]) return;
      handleButton(map[key]);
    }
    event.preventDefault();
  });

  initialize();
})();
