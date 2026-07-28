
  // Keyboard UX: Tab opens functions, opening brackets are paired, and a mirror
  // layer colors nested parentheses without replacing the native textarea.
  const TRIG_ORDER = ['sin', 'cos', 'tan', 'atan', 'asin', 'acos'];
  const POWER_ORDER = ['sqrt', 'exp', 'log', 'ln', 'log10', 'fact', 'cbrt'];
  const FUNCTION_GROUP_ORDER = ['Тригонометрия', 'Степени и логарифмы', 'Прочие функции'];
  const FUNCTION_RANK = new Map(
    [...TRIG_ORDER, ...POWER_ORDER].map((name, index) => [name, index]),
  );
  const DISPLAY_MULTIPLY = '⋅';

  function displayExpression(value) {
    let visual = String(value ?? '');
    // Repair the same keypad separator sequences as the Python backend, so the
    // field, history and clipboard show the expression that is actually used.
    visual = visual.replace(
      /(^|[^\d])[.,]{1,2}(?=\d)/g,
      (_match, prefix) => `${prefix}0.`,
    );
    visual = visual.replace(/(\d)[.,]{1,2}(?=\d)/g, '$1.');
    return visual.replace(/\*/g, DISPLAY_MULTIPLY);
  }

  // Ctrl+K is intentionally retired. Tab from the expression field is the only
  // keyboard entry point; the toolbar button remains available for mouse users.
  isPaletteShortcut = function () { return false; };

  function prepareCatalog(items) {
    return (Array.isArray(items) ? items : []).map(item => {
      if (item?.kind !== 'function') return item;
      const name = String(item.label || '').toLowerCase();
      if (TRIG_ORDER.includes(name)) return { ...item, group: 'Тригонометрия' };
      if (POWER_ORDER.includes(name)) return { ...item, group: 'Степени и логарифмы' };
      return { ...item, group: 'Прочие функции' };
    });
  }

  function compareCatalogItems(left, right) {
    const leftGroup = left?.group || left?.kind || 'Команды';
    const rightGroup = right?.group || right?.kind || 'Команды';
    const leftGroupIndex = FUNCTION_GROUP_ORDER.indexOf(leftGroup);
    const rightGroupIndex = FUNCTION_GROUP_ORDER.indexOf(rightGroup);
    const groupA = leftGroupIndex >= 0 ? leftGroupIndex : 100;
    const groupB = rightGroupIndex >= 0 ? rightGroupIndex : 100;
    if (groupA !== groupB) return groupA - groupB;

    const nameA = String(left?.label || '').toLowerCase();
    const nameB = String(right?.label || '').toLowerCase();
    if (left?.kind === 'function' || right?.kind === 'function') {
      const rankA = FUNCTION_RANK.has(nameA) ? FUNCTION_RANK.get(nameA) : 1000;
      const rankB = FUNCTION_RANK.has(nameB) ? FUNCTION_RANK.get(nameB) : 1000;
      if (rankA !== rankB) return rankA - rankB;
    }
    return nameA.localeCompare(nameB, 'ru');
  }

  const baseSetCatalog = setCatalog;
  setCatalog = function (items) {
    const prepared = prepareCatalog(items).sort(compareCatalogItems);
    baseSetCatalog(prepared);
  };

  // Enforce the requested order again at render time. This prevents any backend
  // or search-result sorting from changing the visible sequence in the palette.
  activePaletteItems = function () {
    const group = state.palette.groups[state.palette.groupIndex];
    return state.palette.items
      .filter(item => (item.group || item.kind || 'Команды') === group)
      .slice()
      .sort(compareCatalogItems);
  };

  // Unit labels supplied by the backend are already Russian and user-facing.
  // Do not append the internal Latin conversion key a second time.
  fillSelect = function (select, items, selected, isCategory = false) {
    const fragment = document.createDocumentFragment();
    for (const item of items) {
      const option = document.createElement('option');
      option.value = isCategory ? item.id : item.symbol;
      option.textContent = item.label;
      option.selected = option.value === selected;
      fragment.appendChild(option);
    }
    select.replaceChildren(fragment);
  };

  // Expressions are stored exactly as typed, but multiplication and repaired
  // decimal separators are presented consistently in the editor and history.
  const baseUpdateHistoryNodeUx = updateHistoryNode;
  updateHistoryNode = function (slot, entry) {
    baseUpdateHistoryNodeUx(slot, entry);
    slot.querySelector('.history-expression').textContent = displayExpression(entry.expression);
  };

  const bracketOverlay = document.createElement('div');
  bracketOverlay.className = 'bracket-color-overlay';
  bracketOverlay.setAttribute('aria-hidden', 'true');
  dom.input.parentElement.insertBefore(bracketOverlay, dom.input.nextSibling);

  function appendOverlayText(text) {
    if (!text) return;
    bracketOverlay.appendChild(document.createTextNode(text));
  }

  // The compact product stylesheet changes the textarea padding, font size and
  // line height. Copy the actual computed metrics instead of duplicating those
  // values in CSS; otherwise the colored glyph and the native bracket diverge.
  const BRACKET_OVERLAY_METRICS = [
    'paddingTop',
    'paddingRight',
    'paddingBottom',
    'paddingLeft',
    'fontFamily',
    'fontSize',
    'fontWeight',
    'fontStyle',
    'fontStretch',
    'lineHeight',
    'letterSpacing',
    'wordSpacing',
    'textAlign',
    'textIndent',
    'textTransform',
    'direction',
    'tabSize',
    'whiteSpace',
    'overflowWrap',
    'wordBreak',
    'borderRadius',
  ];

  function syncBracketOverlayMetrics() {
    const style = window.getComputedStyle(dom.input);
    for (const property of BRACKET_OVERLAY_METRICS) {
      bracketOverlay.style[property] = style[property];
    }
    bracketOverlay.style.width = `${dom.input.offsetWidth}px`;
    bracketOverlay.style.height = `${dom.input.offsetHeight}px`;
  }

  function renderBracketColors() {
    syncBracketOverlayMetrics();
    bracketOverlay.replaceChildren();
    const text = dom.input.value;
    let plainStart = 0;
    let depth = 0;
    const stack = [];

    for (let index = 0; index < text.length; index += 1) {
      const char = text[index];
      if (char !== '(' && char !== ')') continue;
      appendOverlayText(text.slice(plainStart, index));

      let bracketDepth;
      if (char === '(') {
        bracketDepth = depth;
        stack.push(depth);
        depth += 1;
      } else {
        depth = Math.max(0, depth - 1);
        bracketDepth = stack.length ? stack.pop() : depth;
      }

      const span = document.createElement('span');
      span.className = `bracket depth-${Math.abs(bracketDepth) % 6}`;
      span.textContent = char;
      bracketOverlay.appendChild(span);
      plainStart = index + 1;
    }
    appendOverlayText(text.slice(plainStart));
    bracketOverlay.scrollTop = dom.input.scrollTop;
    bracketOverlay.scrollLeft = dom.input.scrollLeft;
  }

  const baseSetInputValueUx = setInputValue;
  setInputValue = function (value, selection = null) {
    baseSetInputValueUx(displayExpression(value), selection);
    renderBracketColors();
  };

  const baseOnInputUx = onInput;
  onInput = function (event) {
    const raw = dom.input.value;
    const start = dom.input.selectionStart ?? raw.length;
    const end = dom.input.selectionEnd ?? start;
    const visual = displayExpression(raw);
    if (visual !== raw) {
      const visualStart = start === raw.length
        ? visual.length
        : displayExpression(raw.slice(0, start)).length;
      const visualEnd = end === raw.length
        ? visual.length
        : displayExpression(raw.slice(0, end)).length;
      dom.input.value = visual;
      setSelection(visualStart, visualEnd);
    }
    baseOnInputUx(event);
    renderBracketColors();
  };

  async function copyCurrentCalculation() {
    const expression = normalize(dom.input.value);
    if (!expression) {
      showToast('Нет выражения для копирования');
      return;
    }

    let response;
    let text;
    try {
      if (state.mode === 'calculator') {
        response = (
          state.calculator.previewExpression === state.calculator.expression
          && state.calculator.preview?.ok
        ) ? state.calculator.preview : await state.api.preview(expression);
        if (!response?.ok) {
          showToast(response?.error || 'Нет результата для копирования');
          return;
        }
        text = `${displayExpression(expression)} = ${response.result}`;
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
        text = `${displayExpression(expression)} ${state.units.from_unit} = ${response.result} ${state.units.to_unit}`;
      }

      const copied = await state.api.copy_text(text);
      showToast(copied ? 'Вычисление скопировано' : 'Не удалось открыть буфер обмена');
    } catch (_) {
      showToast('Не удалось скопировать вычисление');
    }
  }

  // Global shortcuts work from the editor, selects, history and popovers.
  // Capture prevents WebView navigation on Alt+Left/Right.
  document.addEventListener('keydown', event => {
    if (
      event.altKey
      && !event.ctrlKey
      && !event.metaKey
      && !event.shiftKey
      && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')
    ) {
      event.preventDefault();
      event.stopImmediatePropagation();
      closeTransientUi();
      switchMode(event.key === 'ArrowLeft' ? 'calculator' : 'units');
      return;
    }

    if (
      (event.ctrlKey || event.metaKey)
      && !event.altKey
      && !event.shiftKey
      && event.code === 'KeyC'
    ) {
      event.preventDefault();
      event.stopImmediatePropagation();
      void copyCurrentCalculation();
    }
  }, { capture: true });

  dom.input.addEventListener('input', renderBracketColors);
  dom.input.addEventListener('scroll', renderBracketColors, { passive: true });
  window.addEventListener('resize', renderBracketColors, { passive: true });

  if (typeof ResizeObserver === 'function') {
    const bracketOverlayObserver = new ResizeObserver(renderBracketColors);
    bracketOverlayObserver.observe(dom.input);
  }

  dom.input.addEventListener('keydown', event => {
    if (event.target !== dom.input || event.defaultPrevented) return;

    if (event.key === 'Tab' && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (state.mode === 'calculator') openPalette();
      return;
    }

    if (event.key === '(' && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      event.stopImmediatePropagation();
      const start = dom.input.selectionStart ?? dom.input.value.length;
      const end = dom.input.selectionEnd ?? start;
      const selected = dom.input.value.slice(start, end);
      dom.input.setRangeText(`(${selected})`, start, end, 'end');
      setSelection(start + 1);
      onInput({
        isTrusted: false,
        isComposing: false,
        inputType: 'insertText',
        data: '(',
      });
      renderBracketColors();
    }
  }, { capture: true });

  renderBracketColors();
