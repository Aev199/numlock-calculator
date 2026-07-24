(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.NumLockCalcCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  class CalcError extends Error {}

  function normalizeExpression(expression) {
    return String(expression || '')
      .replace(/,/g, '.')
      .replace(/[−–—]/g, '-')
      .replace(/[×·]/g, '*')
      .replace(/÷/g, '/');
  }

  function factorial(value) {
    if (value < 0 || !Number.isInteger(value) || value > 170) {
      throw new CalcError('Invalid factorial argument');
    }
    let result = 1;
    for (let i = 2; i <= value; i += 1) result *= i;
    return result;
  }

  function applyNamedFunction(name, value) {
    const degToRad = degrees => degrees * Math.PI / 180;
    const radToDeg = radians => radians * 180 / Math.PI;
    let result;

    switch (name) {
      case 'sin': result = Math.sin(degToRad(value)); break;
      case 'cos': result = Math.cos(degToRad(value)); break;
      case 'tan': result = Math.tan(degToRad(value)); break;
      case 'sin⁻¹': case 'asin': result = radToDeg(Math.asin(value)); break;
      case 'cos⁻¹': case 'acos': result = radToDeg(Math.acos(value)); break;
      case 'tan⁻¹': case 'atan': result = radToDeg(Math.atan(value)); break;
      case 'log': case 'log10': result = Math.log10(value); break;
      case 'ln': result = Math.log(value); break;
      case 'sqr': result = value * value; break;
      case 'cube': result = value * value * value; break;
      case '√': case 'sqrt': result = Math.sqrt(value); break;
      case '∛': case 'cbrt': result = Math.cbrt(value); break;
      case 'fact': result = factorial(value); break;
      default: throw new CalcError(`Unknown function ${name}`);
    }

    if (!Number.isFinite(result)) throw new CalcError('Non-finite result');
    return result;
  }

  class Parser {
    constructor(text) {
      this.text = normalizeExpression(text);
      this.pos = 0;
    }

    parse() {
      const value = this.parseExpression();
      this.skipSpaces();
      if (this.pos !== this.text.length) {
        throw new CalcError(`Unexpected token at ${this.pos}`);
      }
      if (!Number.isFinite(value)) throw new CalcError('Non-finite result');
      return value;
    }

    skipSpaces() {
      while (this.pos < this.text.length && /\s/.test(this.text[this.pos])) this.pos += 1;
    }

    match(char) {
      this.skipSpaces();
      if (this.text.startsWith(char, this.pos)) {
        this.pos += char.length;
        return true;
      }
      return false;
    }

    parseExpression() {
      let value = this.parseTerm();
      while (true) {
        if (this.match('+')) value += this.parseTerm();
        else if (this.match('-')) value -= this.parseTerm();
        else break;
      }
      return value;
    }

    parseTerm() {
      let value = this.parseSignedPower();
      while (true) {
        if (this.match('*')) value *= this.parseSignedPower();
        else if (this.match('/')) {
          const divisor = this.parseSignedPower();
          if (divisor === 0) throw new CalcError('Division by zero');
          value /= divisor;
        } else break;
      }
      return value;
    }

    parseSignedPower() {
      this.skipSpaces();
      if (this.match('+')) return this.parseSignedPower();
      if (this.match('-')) return -this.parseSignedPower();
      return this.parsePower();
    }

    parsePower() {
      let value = this.parsePrimary();
      if (this.match('^')) {
        const exponent = this.parseSignedPower();
        value = Math.pow(value, exponent);
      }
      if (!Number.isFinite(value)) throw new CalcError('Non-finite result');
      return value;
    }

    parseFunctionArgument(name) {
      if (!this.match('(')) throw new CalcError(`Missing opening parenthesis after ${name}`);
      const value = this.parseExpression();
      if (!this.match(')')) throw new CalcError('Missing closing parenthesis');
      return value;
    }

    parsePrimary() {
      this.skipSpaces();

      if (this.match('(')) {
        const value = this.parseExpression();
        if (!this.match(')')) throw new CalcError('Missing closing parenthesis');
        return value;
      }

      if (this.match('π')) return Math.PI;

      const constantRest = this.text.slice(this.pos);
      if (/^e(?![\w⁻¹])/.test(constantRest)) {
        this.pos += 1;
        return Math.E;
      }

      const functionNames = [
        'sin⁻¹', 'cos⁻¹', 'tan⁻¹',
        'asin', 'acos', 'atan',
        'log10', 'sqrt', 'cbrt',
        'sin', 'cos', 'tan', 'log', 'ln',
        'sqr', 'cube', 'fact', '√', '∛',
      ];
      for (const name of functionNames) {
        if (this.text.startsWith(name, this.pos)) {
          this.pos += name.length;
          return applyNamedFunction(name, this.parseFunctionArgument(name));
        }
      }

      const rest = this.text.slice(this.pos);
      const match = rest.match(/^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?/);
      if (!match) throw new CalcError(`Number expected at ${this.pos}`);
      this.pos += match[0].length;
      const value = Number(match[0]);
      if (!Number.isFinite(value)) throw new CalcError('Invalid number');
      return value;
    }
  }

  function evaluateRawExpression(expression) {
    return new Parser(expression).parse();
  }

  function isOperator(char) {
    return ['+', '-', '*', '/', '^'].includes(char);
  }

  function splitLastBinary(expression) {
    let depth = 0;
    let index = -1;
    for (let i = 0; i < expression.length; i += 1) {
      const char = expression[i];
      if (char === '(') depth += 1;
      else if (char === ')') depth -= 1;
      else if (depth === 0 && ['+', '-', '*', '/'].includes(char)) {
        const prev = expression[i - 1];
        const unary = i === 0 || isOperator(prev) || prev === '(' || prev === 'e' || prev === 'E';
        if (!unary) index = i;
      }
    }
    if (index < 0) return null;
    return {
      left: expression.slice(0, index),
      operator: expression[index],
      right: expression.slice(index + 1),
    };
  }

  function evaluatePercentExpression(source) {
    const parts = splitLastBinary(source);
    if (!parts) return evaluateRawExpression(source) / 100;

    const left = evaluateRawExpression(parts.left);
    const right = evaluateRawExpression(parts.right);
    const percent = right / 100;
    if (parts.operator === '+') return left + left * percent;
    if (parts.operator === '-') return left - left * percent;
    if (parts.operator === '*') return left * percent;
    if (percent === 0) throw new CalcError('Division by zero');
    return left / percent;
  }

  function evaluateExpression(expression) {
    const normalized = normalizeExpression(expression).trim();
    if (!normalized) throw new CalcError('Empty expression');
    if (normalized.endsWith('%')) {
      const source = normalized.slice(0, -1).trim();
      if (!source) throw new CalcError('Percent operand expected');
      const value = evaluatePercentExpression(source);
      if (!Number.isFinite(value)) throw new CalcError('Non-finite result');
      return value;
    }
    return evaluateRawExpression(normalized);
  }

  function formatNumber(value) {
    if (!Number.isFinite(value)) throw new CalcError('Non-finite result');
    if (Object.is(value, -0)) value = 0;
    if (Number.isInteger(value) && Math.abs(value) < 1e15) return String(value);
    if ((Math.abs(value) < 1e-10 && value !== 0) || Math.abs(value) >= 1e15) {
      return value.toExponential(10).replace(/\.?0+e/, 'e');
    }
    return Number(value.toPrecision(12)).toString();
  }

  function currentNumberFragment(expression) {
    const match = String(expression).match(/(?:^|[+\-*/^(])((?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d*)?)$/);
    return match ? match[1] : '';
  }

  class CalculatorEngine {
    constructor() {
      this.clear();
      this.memory = 0;
    }

    clear() {
      this.expression = '';
      this.displayExpression = '';
      this.result = '0';
      this.justEvaluated = false;
      this.error = false;
    }

    setExpression(value, fallbackResult = null) {
      const expression = normalizeExpression(value);
      this.expression = expression;
      this.displayExpression = expression;
      this.justEvaluated = false;
      this.error = false;

      if (!expression.trim()) {
        this.result = '0';
        return true;
      }

      if (fallbackResult !== null && Number.isFinite(Number(fallbackResult))) {
        this.result = formatNumber(Number(fallbackResult));
      }
      this.refreshPreview();
      return true;
    }

    loadExpression(expression, result = null) {
      return this.setExpression(expression, result);
    }

    loadValue(value) {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) return false;
      const formatted = formatNumber(numeric);
      this.expression = formatted;
      this.displayExpression = formatted;
      this.result = formatted;
      this.justEvaluated = true;
      this.error = false;
      return true;
    }

    snapshot() {
      return {
        expression: this.expression,
        displayExpression: this.displayExpression,
        result: this.result,
        memory: this.memory,
        justEvaluated: this.justEvaluated,
        error: this.error,
      };
    }

    press(label) {
      let historyEntry = null;
      switch (label) {
        case 'C': this.clear(); break;
        case '⌫': this.backspace(); break;
        case '=': historyEntry = this.finalize(); break;
        case '±': this.toggleSign(); break;
        case '%': this.applyPercent(); break;
        case 'MC': this.memory = 0; break;
        case 'MR': this.appendLiteral(formatNumber(this.memory)); break;
        case 'M+': this.memory += this.currentValue(); break;
        case 'M-': this.memory -= this.currentValue(); break;
        case 'sin': case 'cos': case 'tan':
        case 'asin': case 'acos': case 'atan':
        case 'log10': case 'ln': case 'pow10': case 'exp':
        case 'sqr': case 'cube': case 'sqrt': case 'cbrt':
        case 'inv': case 'fact':
          this.applyUnary(label);
          break;
        case 'π': this.appendLiteral(formatNumber(Math.PI)); break;
        case 'EXP': this.appendExponentMarker(); break;
        case 'xⁿ': this.appendOperator('^'); break;
        case '(': case ')': this.appendParenthesis(label); break;
        case '+': case '-': case '*': case '/': case '^': this.appendOperator(label); break;
        case '.': this.appendDecimal(); break;
        default:
          if (/^\d$/.test(label)) this.appendDigit(label);
      }
      return { state: this.snapshot(), historyEntry };
    }

    resetAfterError() {
      if (this.error) this.clear();
    }

    prepareForValue() {
      this.resetAfterError();
      if (this.justEvaluated) {
        this.expression = '';
        this.displayExpression = '';
        this.result = '0';
        this.justEvaluated = false;
      }
    }

    syncDisplay() {
      this.displayExpression = this.expression;
      this.error = false;
    }

    appendDigit(digit) {
      this.prepareForValue();
      if (this.expression.endsWith(')')) this.expression += '*';
      this.expression += digit;
      this.syncDisplay();
      this.refreshPreview();
    }

    appendDecimal() {
      this.prepareForValue();
      if (this.expression.endsWith(')')) this.expression += '*0.';
      else {
        const fragment = currentNumberFragment(this.expression);
        if (fragment.includes('.') || /[eE]/.test(fragment)) return;
        if (!fragment) this.expression += '0.';
        else this.expression += '.';
      }
      this.syncDisplay();
      this.refreshPreview();
    }

    appendLiteral(literal) {
      this.prepareForValue();
      if (/[\d.)]$/.test(this.expression)) this.expression += '*';
      this.expression += literal;
      this.syncDisplay();
      this.refreshPreview();
    }

    appendExponentMarker() {
      this.resetAfterError();
      if (this.justEvaluated) this.justEvaluated = false;
      const fragment = currentNumberFragment(this.expression);
      if (!fragment || /[eE]/.test(fragment) || !/\d$/.test(fragment)) return;
      this.expression += 'e';
      this.syncDisplay();
    }

    appendOperator(operator) {
      this.resetAfterError();
      if (this.justEvaluated) {
        this.displayExpression = this.expression;
        this.justEvaluated = false;
      }

      if (/[eE]$/.test(this.expression) && (operator === '+' || operator === '-')) {
        this.expression += operator;
        this.syncDisplay();
        return;
      }

      if (!this.expression) {
        if (operator === '-') {
          this.expression = '-';
          this.syncDisplay();
        }
        return;
      }

      if (this.expression.endsWith('(')) {
        if (operator === '-') {
          this.expression += '-';
          this.syncDisplay();
        }
        return;
      }

      if (isOperator(this.expression.slice(-1))) {
        const previous = this.expression.slice(-1);
        if (operator === '-' && ['*', '/', '^', '+'].includes(previous)) {
          this.expression += '-';
        } else {
          while (this.expression.length > 1 && isOperator(this.expression.slice(-1))) {
            this.expression = this.expression.slice(0, -1);
          }
          this.expression += operator;
        }
      } else {
        this.expression += operator;
      }
      this.syncDisplay();
    }

    appendParenthesis(paren) {
      this.prepareForValue();
      if (paren === '(') {
        if (/[\d.)]$/.test(this.expression)) this.expression += '*';
        this.expression += '(';
      } else {
        const balance = (this.expression.match(/\(/g) || []).length - (this.expression.match(/\)/g) || []).length;
        if (balance <= 0 || !this.expression || /[+\-*/^(eE]$/.test(this.expression)) return;
        this.expression += ')';
      }
      this.syncDisplay();
      this.refreshPreview();
    }

    backspace() {
      if (this.error || this.justEvaluated) {
        this.clear();
        return;
      }
      this.expression = this.expression.slice(0, -1);
      this.syncDisplay();
      if (!this.expression) this.result = '0';
      else this.refreshPreview();
    }

    currentValue() {
      try {
        if (this.expression) return evaluateExpression(this.expression);
      } catch (_) {}
      const fallback = Number(this.result);
      return Number.isFinite(fallback) ? fallback : 0;
    }

    refreshPreview() {
      try {
        this.result = formatNumber(evaluateExpression(this.expression));
        this.error = false;
      } catch (_) {
        // An incomplete edited expression is not fatal. Keep the last valid preview.
      }
    }

    finalize() {
      if (!this.expression || this.error) return null;
      try {
        const value = evaluateExpression(this.expression);
        const formatted = formatNumber(value);
        const label = this.displayExpression || this.expression;
        const shouldStore = !(this.justEvaluated && label === formatted);
        this.expression = formatted;
        this.displayExpression = formatted;
        this.result = formatted;
        this.justEvaluated = true;
        this.error = false;
        return shouldStore ? { expr: label, res: formatted } : null;
      } catch (_) {
        this.setError(this.displayExpression || this.expression);
        return null;
      }
    }

    setError(displayExpression) {
      if (displayExpression) this.displayExpression = displayExpression;
      this.result = 'Error';
      this.error = true;
      this.justEvaluated = false;
    }

    applyUnary(name) {
      const source = this.displayExpression || this.expression || this.result;
      const value = this.currentValue();
      let result;
      let label = name;

      try {
        switch (name) {
          case 'sin': result = applyNamedFunction('sin', value); label = 'sin'; break;
          case 'cos': result = applyNamedFunction('cos', value); label = 'cos'; break;
          case 'tan': result = applyNamedFunction('tan', value); label = 'tan'; break;
          case 'asin': result = applyNamedFunction('asin', value); label = 'sin⁻¹'; break;
          case 'acos': result = applyNamedFunction('acos', value); label = 'cos⁻¹'; break;
          case 'atan': result = applyNamedFunction('atan', value); label = 'tan⁻¹'; break;
          case 'log10': result = applyNamedFunction('log10', value); label = 'log'; break;
          case 'ln': result = applyNamedFunction('ln', value); label = 'ln'; break;
          case 'pow10': result = Math.pow(10, value); label = '10^'; break;
          case 'exp': result = Math.exp(value); label = 'e^'; break;
          case 'sqr': result = applyNamedFunction('sqr', value); label = 'sqr'; break;
          case 'cube': result = applyNamedFunction('cube', value); label = 'cube'; break;
          case 'sqrt': result = applyNamedFunction('sqrt', value); label = '√'; break;
          case 'cbrt': result = applyNamedFunction('cbrt', value); label = '∛'; break;
          case 'inv': result = value === 0 ? NaN : 1 / value; label = '1/'; break;
          case 'fact': result = applyNamedFunction('fact', value); label = 'fact'; break;
          default: result = NaN;
        }
      } catch (_) {
        result = NaN;
      }

      const shown = `${label}(${source})`;
      if (!Number.isFinite(result)) {
        this.setError(shown);
        return;
      }
      const formatted = formatNumber(result);
      this.expression = formatted;
      this.displayExpression = shown;
      this.result = formatted;
      this.justEvaluated = true;
      this.error = false;
    }

    toggleSign() {
      const source = this.displayExpression || this.expression || this.result;
      const value = -this.currentValue();
      const formatted = formatNumber(value);
      this.expression = formatted;
      this.displayExpression = `−(${source})`;
      this.result = formatted;
      this.justEvaluated = true;
      this.error = false;
    }

    applyPercent() {
      if (!this.expression || this.error) return;
      const source = this.displayExpression || this.expression;
      try {
        const value = evaluatePercentExpression(this.expression);
        const formatted = formatNumber(value);
        this.expression = formatted;
        this.displayExpression = `${source}%`;
        this.result = formatted;
        this.justEvaluated = true;
        this.error = false;
      } catch (_) {
        this.setError(`${source}%`);
      }
    }
  }

  return {
    CalcError,
    CalculatorEngine,
    evaluateExpression,
    formatNumber,
    normalizeExpression,
  };
});
