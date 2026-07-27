
  // Keyboard UX: Tab opens functions, opening brackets are paired, and a mirror
  // layer colors nested parentheses without replacing the native textarea.
  const TRIG_ORDER = ['sin', 'cos', 'tan', 'atan', 'asin', 'acos'];
  const POWER_ORDER = ['sqrt', 'exp', 'log', 'ln', 'log10', 'fact', 'cbrt'];
  const FUNCTION_GROUP_ORDER = ['Тригонометрия', 'Степени и логарифмы', 'Прочие функции'];
  const FUNCTION_RANK = new Map(
    [...TRIG_ORDER, ...POWER_ORDER].map((name, index) => [name, index]),
  );

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

  const bracketOverlay = document.createElement('div');
  bracketOverlay.className = 'bracket-color-overlay';
  bracketOverlay.setAttribute('aria-hidden', 'true');
  dom.input.parentElement.insertBefore(bracketOverlay, dom.input.nextSibling);

  function appendOverlayText(text) {
    if (!text) return;
    bracketOverlay.appendChild(document.createTextNode(text));
  }

  function renderBracketColors() {
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
    baseSetInputValueUx(value, selection);
    renderBracketColors();
  };

  dom.input.addEventListener('input', renderBracketColors);
  dom.input.addEventListener('scroll', renderBracketColors, { passive: true });
  window.addEventListener('resize', renderBracketColors, { passive: true });

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
