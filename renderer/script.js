(function() {
  // Состояние
  let currentExpr = '';
  let currentResult = '0';
  let memory = 0;
  let isEngineerMode = true;
  let history = JSON.parse(localStorage.getItem('nlcalc_history') || '[]');
  let theme = localStorage.getItem('nlcalc_theme') || 'light';

  document.body.setAttribute('data-theme', theme);

  // DOM
  const exprLine = document.getElementById('exprLine');
  const resultLine = document.getElementById('resultLine');
  const keypad = document.getElementById('keypad');
  const btnMode = document.getElementById('btnMode');
  const btnClearHistory = document.getElementById('btnClearHistory');
  const historyScroll = document.getElementById('historyScroll');
  const converterWrap = document.getElementById('converterWrap');

  // Раскладки
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

  function buildKeypad(mode) {
    const buttons = mode === 'engineer' ? engineerButtons : standardButtons;
    keypad.innerHTML = '';
    keypad.className = 'keypad ' + (mode === 'engineer' ? 'engineer' : 'standard');

    buttons.forEach(row => {
      row.forEach(label => {
        if (!label) {
          const spacer = document.createElement('div');
          spacer.style.visibility = 'hidden';
          keypad.appendChild(spacer);
          return;
        }
        const btn = document.createElement('button');
        btn.textContent = label;
        btn.classList.add('btn');

        if (/^[0-9.]$/.test(label)) btn.classList.add('btn--number');
        else if (['+', '-', '*', '/', '%'].includes(label)) btn.classList.add('btn--operator');
        else if (label === '=') btn.classList.add('btn--equals');
        else if (['MC', 'MR', 'M+', 'M-'].includes(label)) btn.classList.add('btn--memory');
        else btn.classList.add('btn--func');

        btn.addEventListener('click', () => handleButton(label));
        keypad.appendChild(btn);
      });
    });
  }

  function handleButton(label) {
    switch (label) {
      case 'C':
        currentExpr = '';
        currentResult = '0';
        break;
      case '⌫':
        currentExpr = currentExpr.slice(0, -1);
        evaluateExpr();
        break;
      case '=':
        calculateFinal();
        return;
      case '±':
        toggleSign();
        break;
      case 'MC': memory = 0; return;
      case 'MR': appendToExpr(String(memory)); break;
      case 'M+': memory += parseFloat(currentResult) || 0; return;
      case 'M-': memory -= parseFloat(currentResult) || 0; return;
      case 'sin': applyUnary('sin'); return;
      case 'cos': applyUnary('cos'); return;
      case 'tan': applyUnary('tan'); return;
      case 'sin⁻¹': applyUnary('asin'); return;
      case 'cos⁻¹': applyUnary('acos'); return;
      case 'tan⁻¹': applyUnary('atan'); return;
      case 'log': applyUnary('log10'); return;
      case 'ln': applyUnary('ln'); return;
      case '10ˣ': applyUnary('10^'); return;
      case 'eˣ': applyUnary('exp'); return;
      case 'x²': applyUnary('sqr'); return;
      case 'x³': applyUnary('cube'); return;
      case '√': applyUnary('sqrt'); return;
      case '∛': applyUnary('cbrt'); return;
      case '1/x': applyUnary('inv'); return;
      case 'n!': applyUnary('fact'); return;
      case 'π': appendToExpr(String(Math.PI)); break;
      case 'EXP': appendToExpr('e'); break;
      case 'xⁿ': appendToExpr('^'); break;
      default:
        appendToExpr(label);
    }
    evaluateExpr();
    updateDisplay();
  }

  function appendToExpr(val) {
    if (currentResult === 'Error') { currentExpr = ''; currentResult = '0'; }
    currentExpr += val;
  }

  function toggleSign() {
    if (currentResult !== '0' && currentResult !== 'Error' && currentExpr === '') {
      currentExpr = String(-parseFloat(currentResult));
      currentResult = currentExpr;
    } else if (currentExpr) {
      const match = currentExpr.match(/(.*?)(-?\d+\.?\d*)(?![\d.])$/);
      if (match) {
        const num = parseFloat(match[2]);
        currentExpr = match[1] + String(-num);
      }
    }
    evaluateExpr();
  }

  function applyUnary(func) {
    try {
      let val = parseFloat(currentResult);
      if (isNaN(val)) val = 0;
      let res;
      const degToRad = (d) => d * Math.PI / 180;
      const radToDeg = (r) => r * 180 / Math.PI;
      switch (func) {
        case 'sin': res = Math.sin(degToRad(val)); break;
        case 'cos': res = Math.cos(degToRad(val)); break;
        case 'tan': res = Math.tan(degToRad(val)); break;
        case 'asin': res = radToDeg(Math.asin(Math.max(-1, Math.min(1, val)))); break;
        case 'acos': res = radToDeg(Math.acos(Math.max(-1, Math.min(1, val)))); break;
        case 'atan': res = radToDeg(Math.atan(val)); break;
        case 'log10': res = Math.log10(val); break;
        case 'ln': res = Math.log(val); break;
        case '10^': res = Math.pow(10, val); break;
        case 'exp': res = Math.exp(val); break;
        case 'sqr': res = val * val; break;
        case 'cube': res = val * val * val; break;
        case 'sqrt': res = Math.sqrt(val); break;
        case 'cbrt': res = Math.cbrt(val); break;
        case 'inv': res = val !== 0 ? 1 / val : NaN; break;
        case 'fact': {
          if (val < 0 || !Number.isInteger(val)) { res = NaN; break; }
          res = 1;
          for (let i = 2; i <= val; i++) res *= i;
          break;
        }
        default: res = val;
      }
      if (isNaN(res) || !isFinite(res)) {
        currentResult = 'Error';
        currentExpr = func + '(' + (parseFloat(currentResult)||val) + ')';
      } else {
        currentExpr = func + '(' + val + ')';
        currentResult = formatNumber(res);
      }
    } catch(e) {
      currentResult = 'Error';
    }
    updateDisplay();
  }

  function evaluateExpr() {
    if (!currentExpr) { currentResult = '0'; return; }
    try {
      let expr = currentExpr
        .replace(/\^/g, '**')
        .replace(/π/g, String(Math.PI))
        .replace(/(?<![0-9)])e(?![0-9+\-*/^(])/, String(Math.E));
      const sanitized = expr.replace(/[^0-9+\-*/().%eE\s]/g, '');
      if (!sanitized) { currentResult = '0'; return; }
      // eslint-disable-next-line no-new-func
      const result = new Function('return ' + sanitized)();
      if (isNaN(result) || !isFinite(result)) {
        currentResult = 'Error';
      } else {
        currentResult = formatNumber(result);
      }
    } catch(e) {
      currentResult = 'Error';
    }
  }

  function calculateFinal() {
    const expr = currentExpr;
    evaluateExpr();
    if (currentResult !== 'Error' && expr) {
      addToHistory(expr, currentResult);
    }
    currentExpr = currentResult !== 'Error' ? currentResult : '';
    updateDisplay();
  }

  function formatNumber(num) {
    if (typeof num !== 'number') return String(num);
    if (Number.isInteger(num) && Math.abs(num) < 1e15) return String(num);
    if (Math.abs(num) < 1e-10 && num !== 0) return num.toExponential(8);
    if (Math.abs(num) >= 1e15) return num.toExponential(8);
    return parseFloat(num.toPrecision(12)).toString();
  }

  function updateDisplay() {
    exprLine.textContent = currentExpr;
    resultLine.textContent = currentResult;
  }

  // История в основном окне
  function addToHistory(expr, res) {
    const entry = { expr, res, time: Date.now() };
    history.unshift(entry);
    if (history.length > 200) history = history.slice(0, 200);
    localStorage.setItem('nlcalc_history', JSON.stringify(history));
    renderHistoryPanel();
  }

  function renderHistoryPanel() {
    if (history.length === 0) {
      historyScroll.innerHTML = '<div class="history-empty">Нет истории</div>';
      return;
    }
    historyScroll.innerHTML = history.slice(0, 20).map((h, i) => `
      <div class="history-item" data-index="${i}">
        <span class="history-expr" title="${escapeHtml(h.expr)}">${escapeHtml(h.expr)}</span>
        <span class="history-res">${escapeHtml(h.res)}</span>
      </div>
    `).join('');

    historyScroll.querySelectorAll('.history-item').forEach(item => {
      item.addEventListener('click', () => {
        const idx = parseInt(item.dataset.index);
        const entry = history[idx];
        currentExpr = entry.expr;
        currentResult = entry.res;
        updateDisplay();
      });
    });
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function clearHistory() {
    if (confirm('Очистить всю историю вычислений?')) {
      history = [];
      localStorage.removeItem('nlcalc_history');
      renderHistoryPanel();
    }
  }

  // Конвертер единиц
  const unitCategories = {
    'Давление': {
      units: ['Па', 'кПа', 'МПа', 'бар', 'атм', 'мм рт.ст.', 'psi'],
      toBase: [1, 1000, 1e6, 1e5, 101325, 133.322, 6894.76],
    },
    'Площадь': {
      units: ['м²', 'км²', 'га', 'см²', 'мм²', 'дюйм²', 'фут²'],
      toBase: [1, 1e6, 10000, 0.0001, 1e-6, 0.00064516, 0.092903],
    },
    'Сила': {
      units: ['Н', 'кН', 'кгс', 'фунт-сила', 'дина'],
      toBase: [1, 1000, 9.80665, 4.44822, 1e-5],
    },
    'Объём': {
      units: ['м³', 'л', 'мл', 'см³', 'галлон (US)', 'фут³'],
      toBase: [1, 0.001, 1e-6, 1e-6, 0.00378541, 0.0283168],
    },
    'Длина': {
      units: ['м', 'км', 'см', 'мм', 'дюйм', 'фут', 'миля'],
      toBase: [1, 1000, 0.01, 0.001, 0.0254, 0.3048, 1609.34],
    },
    'Масса': {
      units: ['кг', 'г', 'т', 'фунт', 'унция'],
      toBase: [1, 0.001, 1000, 0.453592, 0.0283495],
    },
    'Температура': {
      units: ['°C', '°F', 'K'],
      toBase: null,
    },
  };

  function buildConverter() {
    const catSelect = document.createElement('select');
    Object.keys(unitCategories).forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat;
      opt.textContent = cat;
      catSelect.appendChild(opt);
    });

    const fromSelect = document.createElement('select');
    const toSelect = document.createElement('select');
    const fromInput = document.createElement('input');
    fromInput.type = 'number';
    fromInput.value = '1';
    const toInput = document.createElement('input');
    toInput.type = 'number';
    toInput.readOnly = true;

    function populateUnits(cat) {
      const data = unitCategories[cat];
      fromSelect.innerHTML = '';
      toSelect.innerHTML = '';
      data.units.forEach(u => {
        fromSelect.appendChild(new Option(u, u));
        toSelect.appendChild(new Option(u, u));
      });
      toSelect.selectedIndex = 1;
    }

    function convert() {
      const cat = catSelect.value;
      const data = unitCategories[cat];
      const fromUnit = fromSelect.value;
      const toUnit = toSelect.value;
      const fromVal = parseFloat(fromInput.value) || 0;

      if (cat === 'Температура') {
        let kelvin;
        if (fromUnit === '°C') kelvin = fromVal + 273.15;
        else if (fromUnit === '°F') kelvin = (fromVal - 32) * 5/9 + 273.15;
        else kelvin = fromVal;

        let result;
        if (toUnit === '°C') result = kelvin - 273.15;
        else if (toUnit === '°F') result = (kelvin - 273.15) * 9/5 + 32;
        else result = kelvin;
        toInput.value = parseFloat(result.toPrecision(10));
      } else {
        const fromIdx = data.units.indexOf(fromUnit);
        const toIdx = data.units.indexOf(toUnit);
        const baseVal = fromVal * data.toBase[fromIdx];
        const result = baseVal / data.toBase[toIdx];
        toInput.value = parseFloat(result.toPrecision(10));
      }
    }

    catSelect.addEventListener('change', () => { populateUnits(catSelect.value); convert(); });
    fromSelect.addEventListener('change', convert);
    toSelect.addEventListener('change', convert);
    fromInput.addEventListener('input', convert);

    const swapBtn = document.createElement('button');
    swapBtn.className = 'swap-btn';
    swapBtn.textContent = '⇄';
    swapBtn.addEventListener('click', () => {
      const tmpUnit = fromSelect.value;
      const tmpVal = fromInput.value;
      fromSelect.value = toSelect.value;
      fromInput.value = toInput.value;
      toSelect.value = tmpUnit;
      convert();
    });

    converterWrap.innerHTML = '';
    const catRow = document.createElement('div');
    catRow.className = 'conv-row';
    const catField = document.createElement('div');
    catField.className = 'conv-field';
    catField.innerHTML = '<label>Категория</label>';
    catField.appendChild(catSelect);
    catRow.appendChild(catField);
    converterWrap.appendChild(catRow);

    const fromRow = document.createElement('div');
    fromRow.className = 'conv-row';
    const fromField = document.createElement('div');
    fromField.className = 'conv-field';
    fromField.innerHTML = '<label>Из</label>';
    fromField.appendChild(fromInput);
    fromField.appendChild(fromSelect);
    fromRow.appendChild(fromField);
    fromRow.appendChild(swapBtn);
    const toField = document.createElement('div');
    toField.className = 'conv-field';
    toField.innerHTML = '<label>В</label>';
    toField.appendChild(toInput);
    toField.appendChild(toSelect);
    fromRow.appendChild(toField);
    converterWrap.appendChild(fromRow);

    populateUnits(catSelect.value);
    convert();
  }

  // Вкладки
  function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById('tab-' + tabName).classList.add('active');
  }

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Тема
  document.getElementById('btnTheme').addEventListener('click', function() {
    const newTheme = document.body.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    document.body.setAttribute('data-theme', newTheme);
    localStorage.setItem('nlcalc_theme', newTheme);
  });

  // Очистка истории
  btnClearHistory.addEventListener('click', clearHistory);

  // Переключение режима
  btnMode.addEventListener('click', () => {
    isEngineerMode = !isEngineerMode;
    btnMode.textContent = isEngineerMode ? 'Инженерный ▸ Стандартный' : 'Стандартный ▸ Инженерный';
    buildKeypad(isEngineerMode ? 'engineer' : 'standard');
  });

  // Горячие клавиши
  document.addEventListener('keydown', (e) => {
    const tab = document.querySelector('.tab-content.active');
    if (tab.id !== 'tab-calc') return;
    
    const key = e.key;
    if (/^[0-9.]$/.test(key)) { handleButton(key); return; }
    const keyMap = {
      '+': '+', '-': '-', '*': '*', '/': '/', '%': '%',
      'Enter': '=', 'Escape': 'C', 'Backspace': '⌫',
      '(': '(', ')': ')',
    };
    if (keyMap[key]) { handleButton(keyMap[key]); e.preventDefault(); }
  });

  // Старт
  buildKeypad('engineer');
  buildConverter();
  renderHistoryPanel();
  updateDisplay();
})();
