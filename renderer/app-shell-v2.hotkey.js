  const settingsButton = byId('settingsButton');
  dom.settingsButton = settingsButton;

  const HOTKEY_DISPLAY = {
    ctrl: 'Ctrl',
    alt: 'Alt',
    shift: 'Shift',
    meta: 'Win',
    Control: 'Ctrl',
    Alt: 'Alt',
    Shift: 'Shift',
    Meta: 'Win',
    ' ': 'Space',
    NumLock: 'NumLock',
    'num lock': 'NumLock',
    Escape: 'Esc',
    Enter: 'Enter',
    Tab: 'Tab',
    Backspace: 'Backspace',
    Delete: 'Delete',
    Insert: 'Insert',
    Home: 'Home',
    End: 'End',
    PageUp: 'PageUp',
    PageDown: 'PageDown',
    ArrowLeft: '←',
    ArrowRight: '→',
    ArrowUp: '↑',
    ArrowDown: '↓',
    CapsLock: 'CapsLock',
    ScrollLock: 'ScrollLock',
    PrintScreen: 'PrintScreen',
  };

  function browserHotkeyKey(event) {
    const key = String(event.key || '');
    if (['Control', 'Alt', 'Shift', 'Meta'].includes(key)) return '';
    if (key === ' ') return 'space';
    if (key === 'NumLock') return 'num lock';
    if (key === 'PageUp') return 'page up';
    if (key === 'PageDown') return 'page down';
    if (key === 'ArrowLeft') return 'left';
    if (key === 'ArrowRight') return 'right';
    if (key === 'ArrowUp') return 'up';
    if (key === 'ArrowDown') return 'down';
    if (key === 'Escape') return 'escape';
    if (key === 'Enter') return 'enter';
    if (key === 'Tab') return 'tab';
    if (key === 'CapsLock') return 'caps lock';
    if (key === 'ScrollLock') return 'scroll lock';
    if (key === 'PrintScreen') return 'print screen';
    if (/^F(?:[1-9]|1[0-9]|2[0-4])$/i.test(key)) return key.toLowerCase();
    if (key.length === 1) return key.toLowerCase();
    return key.toLowerCase().replace(/\s+/g, ' ');
  }

  function hotkeyFromEvent(event) {
    const key = browserHotkeyKey(event);
    if (!key) return null;
    const modifiers = [];
    if (event.ctrlKey) modifiers.push('ctrl');
    if (event.altKey) modifiers.push('alt');
    if (event.shiftKey) modifiers.push('shift');
    if (event.metaKey) modifiers.push('windows');
    return [...modifiers, key].join('+');
  }

  function hotkeyDisplay(value) {
    return String(value || '')
      .split('+')
      .map(part => HOTKEY_DISPLAY[part] || HOTKEY_DISPLAY[part.toLowerCase()] || (
        /^f\d+$/i.test(part) ? part.toUpperCase() : part.length === 1 ? part.toUpperCase() : part
      ))
      .join(' + ');
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function renderSettingsDrawer() {
    dom.drawerTitle.textContent = 'Настройки';
    dom.drawerSubtitle.textContent = 'Формат, Enter и горячая клавиша';
    dom.drawerContent.replaceChildren();

    const content = document.createElement('div');
    content.className = 'settings-content';
    content.innerHTML = `
      <section class="settings-section">
        <span class="settings-label">Формат результатов</span>
        <div class="format-settings-grid">
          <label class="format-setting">
            <span>Вид записи</span>
            <select id="numberFormatSelect" class="settings-select">
              <option value="auto">Автоматический</option>
              <option value="engineering">Инженерный (e кратно 3)</option>
            </select>
          </label>
          <label class="format-setting">
            <span>Значащих знаков</span>
            <input id="precisionInput" class="settings-number" type="number" min="3" max="17" step="1">
          </label>
          <label class="format-setting">
            <span>Разделитель</span>
            <select id="decimalSeparatorSelect" class="settings-select">
              <option value=".">Точка — 1.23</option>
              <option value=",">Запятая — 1,23</option>
            </select>
          </label>
        </div>
        <p class="settings-help">Настройки применяются к результату, истории, копированию и вкладке «Единицы».</p>
        <div class="hotkey-status" id="formatStatus" role="status"></div>
      </section>
      <section class="settings-section">
        <span class="settings-label">После Enter</span>
        <label class="settings-checkbox">
          <input id="selectResultOnEnter" type="checkbox">
          <span>Выделять результат в строке ввода</span>
        </label>
        <p class="settings-help">Включено по умолчанию. Выделение удобно для немедленной замены результата новым выражением.</p>
        <div class="hotkey-status" id="behaviorStatus" role="status"></div>
      </section>
      <div class="settings-divider" aria-hidden="true"></div>
      <section class="settings-section">
        <label class="settings-label" for="globalHotkeyCapture">Глобальная клавиша</label>
        <div class="hotkey-capture-row">
          <input class="hotkey-capture" id="globalHotkeyCapture" type="text" readonly
            aria-describedby="globalHotkeyHelp globalHotkeyStatus">
          <button class="hotkey-save" id="globalHotkeySave" type="button">Сохранить</button>
        </div>
        <p class="settings-help" id="globalHotkeyHelp">
          Нажмите поле и затем нужную комбинацию. Клавиша показывает, возвращает фокус или скрывает NumCalc.
        </p>
        <div class="hotkey-status" id="globalHotkeyStatus" role="status"></div>
      </section>
      <div class="settings-divider" aria-hidden="true"></div>
      <section class="settings-section">
        <span class="settings-label">Текущая комбинация</span>
    <p class="settings-help">${escapeHtml(hotkeyDisplay(state.ui.global_hotkey || 'num lock'))}</p>
      </section>
    `;
    dom.drawerContent.appendChild(content);

    const capture = content.querySelector('#globalHotkeyCapture');
    const save = content.querySelector('#globalHotkeySave');
    const status = content.querySelector('#globalHotkeyStatus');
    const formatSelect = content.querySelector('#numberFormatSelect');
    const precisionInput = content.querySelector('#precisionInput');
    const separatorSelect = content.querySelector('#decimalSeparatorSelect');
    const formatStatus = content.querySelector('#formatStatus');
    const selectResultOnEnter = content.querySelector('#selectResultOnEnter');
    const behaviorStatus = content.querySelector('#behaviorStatus');
    let pending = state.ui.global_hotkey || 'num lock';
    capture.value = hotkeyDisplay(pending);
    formatSelect.value = state.settings.number_format || 'auto';
    precisionInput.value = String(state.settings.precision || 12);
    separatorSelect.value = state.settings.decimal_separator || '.';
    selectResultOnEnter.checked = state.ui.select_result_on_enter !== false;

    const setStatus = (message, kind = '') => {
      status.textContent = message;
      status.className = `hotkey-status${kind ? ` ${kind}` : ''}`;
    };

    const setFormatStatus = (message, kind = '') => {
      formatStatus.textContent = message;
      formatStatus.className = `hotkey-status${kind ? ` ${kind}` : ''}`;
    };

    const setBehaviorStatus = (message, kind = '') => {
      behaviorStatus.textContent = message;
      behaviorStatus.className = `hotkey-status${kind ? ` ${kind}` : ''}`;
    };

    async function saveFormatSettings() {
      const precision = Math.max(
        3,
        Math.min(17, Number.parseInt(precisionInput.value, 10) || 12),
      );
      precisionInput.value = String(precision);
      setFormatStatus('Сохранение…');
      try {
        const response = await state.api.set_settings({
          number_format: formatSelect.value,
          precision,
          decimal_separator: separatorSelect.value,
        });
        if (!response?.precision) {
          setFormatStatus(response?.error || 'Не удалось сохранить формат', 'error');
          return;
        }
        applySettings(response);
        if (state.mode === 'calculator') {
          setInputValue(state.calculator.expression);
          scheduleCalculatorPreview(0);
        } else {
          setInputValue(state.units.expression);
          scheduleUnitsPreview(0);
        }
        setFormatStatus('Формат сохранён', 'success');
      } catch (_) {
        setFormatStatus('Не удалось сохранить формат', 'error');
      }
    }

    [formatSelect, precisionInput, separatorSelect].forEach(control => {
      control.addEventListener('change', saveFormatSettings);
    });

    selectResultOnEnter.addEventListener('change', async () => {
      const enabled = selectResultOnEnter.checked;
      selectResultOnEnter.disabled = true;
      setBehaviorStatus('Сохранение…');
      try {
        const response = await state.api.set_ui_settings({
          select_result_on_enter: enabled,
        });
        state.ui = { ...state.ui, ...(response || {}) };
        selectResultOnEnter.checked = state.ui.select_result_on_enter !== false;
        setBehaviorStatus('Настройка сохранена', 'success');
      } catch (_) {
        selectResultOnEnter.checked = state.ui.select_result_on_enter !== false;
        setBehaviorStatus('Не удалось сохранить настройку', 'error');
      } finally {
        selectResultOnEnter.disabled = false;
      }
    });

    capture.addEventListener('focus', () => {
      capture.classList.add('is-listening');
      capture.value = 'Нажмите комбинацию…';
      setStatus('Ожидание клавиш');
    });
    capture.addEventListener('blur', () => {
      capture.classList.remove('is-listening');
      capture.value = hotkeyDisplay(pending);
    });
    capture.addEventListener('keydown', event => {
      event.preventDefault();
      event.stopPropagation();
      if (event.key === 'Escape') {
        capture.blur();
        setStatus('Изменение отменено');
        return;
      }
      const next = hotkeyFromEvent(event);
      if (!next) {
        setStatus('Добавьте основную клавишу после Ctrl, Alt, Shift или Win', 'error');
        return;
      }
      pending = next;
      capture.value = hotkeyDisplay(next);
      setStatus('Нажмите «Сохранить» для применения');
      save.disabled = false;
    });
    save.addEventListener('click', async () => {
      save.disabled = true;
      setStatus('Проверка и регистрация…');
      try {
        const response = await state.api.set_global_hotkey(pending);
        if (!response?.ok) {
          setStatus(response?.error || 'Комбинация занята или недоступна', 'error');
          save.disabled = false;
          return;
        }
        state.ui.global_hotkey = response.hotkey;
        capture.value = response.display || hotkeyDisplay(response.hotkey);
        setStatus(`Сохранено: ${response.display || hotkeyDisplay(response.hotkey)}`, 'success');
        showToast('Глобальная клавиша изменена');
      } catch (_) {
        setStatus('Не удалось зарегистрировать комбинацию', 'error');
        save.disabled = false;
      }
    });
  }

  settingsButton?.addEventListener('click', () => openDrawer('settings'));
