
  function currentFlexibleUnitCategory() {
    const category = currentUnitCategory();
    return category?.picker?.kind === 'compound' ? category : null;
  }

  function unitPayloadBySymbol(category, symbol) {
    return (category?.units || []).find(item => item.symbol === symbol) || null;
  }

  function appendUnitOptions(select, items, selected, prefix = '') {
    const fragment = document.createDocumentFragment();
    for (const item of items || []) {
      const option = document.createElement('option');
      option.value = `${prefix}${item.symbol}`;
      option.textContent = item.label || item.symbol;
      option.selected = option.value === selected;
      fragment.appendChild(option);
    }
    select.appendChild(fragment);
  }

  function compoundParts(category, symbol) {
    const picker = category?.picker;
    if (!picker) return null;
    const preset = (picker.presets || []).find(item => item.symbol === symbol);
    if (preset) {
      return {
        preset: true,
        left: `preset:${preset.symbol}`,
        right: '',
      };
    }
    const separator = picker.operator;
    const position = String(symbol || '').indexOf(separator);
    if (position <= 0) return null;
    const left = String(symbol).slice(0, position);
    const right = String(symbol).slice(position + separator.length);
    if (!(picker.left || []).some(item => item.symbol === left)) return null;
    if (!(picker.right || []).some(item => item.symbol === right)) return null;
    return { preset: false, left: `component:${left}`, right };
  }

  function defaultCompoundParts(category) {
    const picker = category?.picker || {};
    return {
      preset: false,
      left: `component:${picker.left?.[0]?.symbol || ''}`,
      right: picker.right?.[0]?.symbol || '',
    };
  }

  function composePickerSymbol(category, leftValue, rightValue) {
    const picker = category?.picker;
    if (!picker) return '';
    if (String(leftValue).startsWith('preset:')) {
      return String(leftValue).slice('preset:'.length);
    }
    const left = String(leftValue).replace(/^component:/, '');
    return left && rightValue
      ? `${left}${picker.operator}${rightValue}`
      : '';
  }

  function buildCompoundPicker(category, hiddenSelect, selectedSymbol) {
    const picker = category.picker;
    const parsed = compoundParts(category, selectedSymbol) || defaultCompoundParts(category);
    const wrapper = document.createElement('div');
    wrapper.className = 'compound-unit-picker';
    wrapper.dataset.unitSide = hiddenSelect === dom.sourceUnit ? 'source' : 'target';

    const left = document.createElement('select');
    left.className = 'converter-select compound-unit-select compound-unit-left';
    left.setAttribute('aria-label', picker.left_label || 'Числитель единицы');

    const components = document.createElement('optgroup');
    components.label = picker.operator === '*' ? 'Составная единица' : 'Числитель';
    for (const item of picker.left || []) {
      const option = document.createElement('option');
      option.value = `component:${item.symbol}`;
      option.textContent = item.label || item.symbol;
      components.appendChild(option);
    }
    left.appendChild(components);

    if ((picker.presets || []).length) {
      const presets = document.createElement('optgroup');
      presets.label = 'Готовые единицы';
      for (const item of picker.presets) {
        const option = document.createElement('option');
        option.value = `preset:${item.symbol}`;
        option.textContent = item.label || item.symbol;
        presets.appendChild(option);
      }
      left.appendChild(presets);
    }

    const operator = document.createElement('span');
    operator.className = 'compound-unit-operator';
    operator.textContent = picker.operator === '*' ? '·' : '/';
    operator.setAttribute('aria-hidden', 'true');

    const right = document.createElement('select');
    right.className = 'converter-select compound-unit-select compound-unit-right';
    right.setAttribute('aria-label', picker.right_label || 'Знаменатель единицы');
    appendUnitOptions(right, picker.right || [], parsed.right);

    left.value = parsed.left;
    right.value = parsed.right;

    const updatePresetState = () => {
      const preset = left.value.startsWith('preset:');
      wrapper.classList.toggle('is-preset', preset);
      right.disabled = preset;
      right.setAttribute('aria-hidden', preset ? 'true' : 'false');
    };

    const commit = () => {
      const symbol = composePickerSymbol(category, left.value, right.value);
      if (!symbol || !unitPayloadBySymbol(category, symbol)) return;
      if (hiddenSelect.value === symbol) {
        updatePresetState();
        const payload = unitPayloadBySymbol(category, symbol);
        const badge = hiddenSelect === dom.sourceUnit ? dom.sourceBadge : dom.targetBadge;
        badge.textContent = payload?.display || payload?.label || symbol;
        return;
      }
      hiddenSelect.value = symbol;
      updatePresetState();
      hiddenSelect.dispatchEvent(new Event('change', { bubbles: true }));
    };

    left.addEventListener('change', commit);
    right.addEventListener('change', commit);
    wrapper.append(left, operator, right);
    updatePresetState();
    return wrapper;
  }

  function renderFlexibleUnitPickers() {
    const category = currentFlexibleUnitCategory();
    const pairs = [
      [dom.sourceUnit, state.units.from_unit, dom.sourceBadge],
      [dom.targetUnit, state.units.to_unit, dom.targetBadge],
    ];

    for (const [select, selected, badge] of pairs) {
      const card = select.closest('.unit-picker-card');
      card?.querySelector('.compound-unit-picker')?.remove();
      select.classList.toggle('compound-unit-hidden', Boolean(category));
      if (!category || !card) {
        badge.textContent = selected;
        continue;
      }
      const builder = buildCompoundPicker(category, select, selected);
      card.appendChild(builder);
      const payload = unitPayloadBySymbol(category, selected);
      badge.textContent = payload?.display || payload?.label || selected;
    }
  }

  const renderUnitControlsWithoutFlexiblePickers = renderUnitControls;
  renderUnitControls = function (preferProfile = false) {
    const result = renderUnitControlsWithoutFlexiblePickers(preferProfile);
    renderFlexibleUnitPickers();
    return result;
  };
