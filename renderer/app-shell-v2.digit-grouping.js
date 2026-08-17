
  const DIGIT_GROUP_SEPARATOR = ' ';
  const DIGIT_GROUP_SPACES = new Set([' ', '\u00a0', '\u202f']);
  const DECIMAL_LITERAL = /(^|[^0-9A-Za-zА-Яа-я_.])(\d+(?:[.,]\d*)?(?:[eE][+-]?\d+)?)/g;

  function asciiDigit(char) {
    return char >= '0' && char <= '9';
  }

  function groupingSpaceMask(value) {
    const text = String(value ?? '');
    const masked = new Set();
    let index = 0;
    while (index < text.length) {
      if (!DIGIT_GROUP_SPACES.has(text[index])) {
        index += 1;
        continue;
      }
      const start = index;
      while (index < text.length && DIGIT_GROUP_SPACES.has(text[index])) {
        index += 1;
      }
      if (
        start > 0
        && index < text.length
        && asciiDigit(text[start - 1])
        && asciiDigit(text[index])
      ) {
        for (let cursor = start; cursor < index; cursor += 1) {
          masked.add(cursor);
        }
      }
    }
    return masked;
  }

  function stripDigitGrouping(value) {
    const text = String(value ?? '');
    const masked = groupingSpaceMask(text);
    if (!masked.size) return text;
    let result = '';
    for (let index = 0; index < text.length; index += 1) {
      if (!masked.has(index)) result += text[index];
    }
    return result;
  }

  function groupIntegerDigits(value) {
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, DIGIT_GROUP_SEPARATOR);
  }

  function groupDecimalLiteral(literal) {
    const exponentIndex = literal.search(/[eE]/);
    const mantissa = exponentIndex >= 0 ? literal.slice(0, exponentIndex) : literal;
    const exponent = exponentIndex >= 0 ? literal.slice(exponentIndex) : '';
    const decimalIndex = Math.max(mantissa.indexOf('.'), mantissa.indexOf(','));
    const integerPart = decimalIndex >= 0 ? mantissa.slice(0, decimalIndex) : mantissa;
    const fractionPart = decimalIndex >= 0 ? mantissa.slice(decimalIndex) : '';
    return `${groupIntegerDigits(integerPart)}${fractionPart}${exponent}`;
  }

  function shouldGroupEditorDigits() {
    return state.mode === 'units' || state.settings.number_base === 'DEC';
  }

  function groupExpressionDigits(value) {
    const canonical = stripDigitGrouping(value);
    if (!shouldGroupEditorDigits()) return canonical;
    return canonical.replace(
      DECIMAL_LITERAL,
      (_match, prefix, literal) => `${prefix}${groupDecimalLiteral(literal)}`,
    );
  }

  function clipboardDigitText(value) {
    return state.ui.group_copied_digits === false
      ? stripDigitGrouping(value)
      : groupExpressionDigits(value);
  }

  function logicalCaretOffset(value, domOffset) {
    const text = String(value ?? '');
    const masked = groupingSpaceMask(text);
    let logical = 0;
    const limit = Math.max(0, Math.min(text.length, Number(domOffset) || 0));
    for (let index = 0; index < limit; index += 1) {
      if (!masked.has(index)) logical += 1;
    }
    return logical;
  }

  function domCaretOffset(value, logicalOffset) {
    const text = String(value ?? '');
    const masked = groupingSpaceMask(text);
    const target = Math.max(0, Number(logicalOffset) || 0);
    let logical = 0;
    for (let index = 0; index < text.length; index += 1) {
      if (logical >= target) return index;
      if (!masked.has(index)) logical += 1;
    }
    return text.length;
  }

  function applyVisualDigitGroupingToEditor() {
    if (!shouldGroupEditorDigits()) return;
    const current = dom.input.value;
    const grouped = groupExpressionDigits(current);
    if (grouped === current) return;

    const startLogical = logicalCaretOffset(current, dom.input.selectionStart);
    const endLogical = logicalCaretOffset(current, dom.input.selectionEnd);
    dom.input.value = grouped;
    const start = domCaretOffset(grouped, startLogical);
    const end = domCaretOffset(grouped, endLogical);
    dom.input.setSelectionRange(start, end);
    state.selection.start = start;
    state.selection.end = end;
  }

  // Register before bindEvents() adds the main input handler. The visible value
  // is grouped first, while the backend receives an expression whose grouping
  // spaces are explicitly normalized away by the calculation layers.
  dom.input.addEventListener('input', applyVisualDigitGroupingToEditor);

  const setInputValueWithoutDigitGrouping = setInputValue;
  setInputValue = function setInputValueWithDigitGrouping(value, selectEnd = true) {
    return setInputValueWithoutDigitGrouping(groupExpressionDigits(value), selectEnd);
  };

  const renderResultWithoutDigitGrouping = renderResult;
  renderResult = function renderResultWithDigitGrouping(evaluation) {
    renderResultWithoutDigitGrouping(evaluation);
    if (dom.resultValue.classList.contains('muted')) return;
    dom.resultValue.textContent = groupExpressionDigits(dom.resultValue.textContent);
  };

  const updateHistoryNodeWithoutDigitGrouping = updateHistoryNode;
  updateHistoryNode = function updateHistoryNodeWithDigitGrouping(slot, entry) {
    updateHistoryNodeWithoutDigitGrouping(slot, entry);
    const expression = slot.querySelector('.history-expression');
    const result = slot.querySelector('.history-result');
    if (expression) expression.textContent = groupExpressionDigits(expression.textContent);
    if (result) result.textContent = groupExpressionDigits(result.textContent);
  };

  // Clipboard formatting is independent from the visible editor/result format.
  // The screen always groups decimal digits, while this preference controls
  // whether digit separators survive copy operations.
  const copyTextWithoutDigitGrouping = copyText;
  copyText = async function copyTextWithDigitGroupingPreference(
    text,
    successMessage = 'Результат скопирован',
  ) {
    return copyTextWithoutDigitGrouping(
      clipboardDigitText(text),
      successMessage,
    );
  };

  // Replace the earlier clipboard wrapper so both sides of "expression = result"
  // use the same grouping rules. This also preserves the concise copy behavior
  // for a standalone calculator number.
  copyCurrentCalculation = async function copyCurrentCalculationWithDigitGrouping() {
    if (state.mode === 'interpolation') {
      await copyInterpolationResult();
      return;
    }

    const expression = normalize(dom.input.value);
    if (!expression) {
      showToast('Нет выражения для копирования');
      return;
    }

    try {
      if (
        state.mode === 'calculator'
        && isStandaloneClipboardNumber(expression)
      ) {
        await copyText(
          displayExpression(expression),
          'Значение скопировано',
        );
        return;
      }

      let response;
      let text;
      if (state.mode === 'calculator') {
        response = (
          state.calculator.previewExpression === state.calculator.expression
          && state.calculator.preview?.ok
        ) ? state.calculator.preview : await state.api.preview(expression);
        if (!response?.ok) {
          showToast(response?.error || 'Нет результата для копирования');
          return;
        }
        text = `${copyExpression(expression)} = ${response.result}`;
      } else {
        response = (
          state.units.previewExpression === state.units.expression
          && state.units.previewContext === unitContext()
          && state.units.preview?.ok
        ) ? state.units.preview : await state.api.convert_units(
          expression,
          state.units.category,
          state.units.from_unit,
          state.units.to_unit,
          false,
          state.units.imported_revision,
        );
        if (!response?.ok) {
          showToast(response?.error || 'Нет результата для копирования');
          return;
        }
        text = `${copyExpression(expression)} ${state.units.from_unit} = ${response.result} ${state.units.to_unit}`;
      }

      await copyText(text, 'Вычисление скопировано');
    } catch (_) {
      showToast('Не удалось скопировать вычисление');
    }
  };

  const renderSettingsDrawerWithoutClipboardGrouping = renderSettingsDrawer;
  renderSettingsDrawer = function renderSettingsDrawerWithClipboardGrouping() {
    renderSettingsDrawerWithoutClipboardGrouping();
    const formatSection = dom.drawerContent.querySelector(
      '.settings-content .settings-section',
    );
    const formatStatus = formatSection?.querySelector('#formatStatus');
    if (!formatSection || !formatStatus) return;

    const row = document.createElement('label');
    row.className = 'settings-checkbox';
    row.innerHTML = `
      <input id="groupCopiedDigits" type="checkbox">
      <span>Группировать разряды при копировании</span>
    `;
    const help = document.createElement('p');
    help.className = 'settings-help';
    help.textContent = 'Включено: 150 000 000. Выключено: 150000000.';
    formatSection.insertBefore(row, formatStatus);
    formatSection.insertBefore(help, formatStatus);

    const input = row.querySelector('#groupCopiedDigits');
    input.checked = state.ui.group_copied_digits !== false;
    input.addEventListener('change', async () => {
      const enabled = input.checked;
      input.disabled = true;
      formatStatus.textContent = 'Сохранение…';
      formatStatus.className = 'hotkey-status';
      try {
        const response = await state.api.set_ui_settings({
          group_copied_digits: enabled,
        });
        state.ui = { ...state.ui, ...(response || {}) };
        input.checked = state.ui.group_copied_digits !== false;
        formatStatus.textContent = 'Настройка сохранена';
        formatStatus.className = 'hotkey-status success';
      } catch (_) {
        input.checked = state.ui.group_copied_digits !== false;
        formatStatus.textContent = 'Не удалось сохранить настройку';
        formatStatus.className = 'hotkey-status error';
      } finally {
        input.disabled = false;
      }
    });
  };
