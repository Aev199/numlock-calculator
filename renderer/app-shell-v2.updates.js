  // Updates: a title-bar badge when there is something to act on, a dialog for
  // checks the user asked for, and a section in Settings. The Python updater
  // pushes every phase change through window.__numcalcUpdates.
  const updateIcon = `
    <svg class="ui-glyph" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d="M8 2.75v7.5M5 7.5l3 3 3-3M3.5 13.25h9"></path>
    </svg>
  `;
  const updateBadge = document.createElement('button');
  updateBadge.type = 'button';
  updateBadge.className = 'update-badge hidden';
  updateBadge.id = 'updateBadge';
  dom.themeButton.before(updateBadge);

  const updateOverlay = document.createElement('div');
  updateOverlay.className = 'update-overlay hidden';
  updateOverlay.setAttribute('aria-hidden', 'true');
  updateOverlay.innerHTML = `
    <section class="update-card" role="dialog" aria-modal="true" aria-labelledby="updateTitle">
      <h2 id="updateTitle"></h2>
      <div class="update-body"></div>
      <div class="update-actions"></div>
    </section>
  `;
  document.body.appendChild(updateOverlay);
  const updateTitle = updateOverlay.querySelector('#updateTitle');
  const updateBody = updateOverlay.querySelector('.update-body');
  const updateActions = updateOverlay.querySelector('.update-actions');

  let updateState = null;
  let updateDialogOpen = false;
  // Set while a check the user asked for here is running: a fast failure can
  // answer before the "checking" phase ever reaches the renderer.
  let awaitingCheck = false;

  function formatSize(bytes) {
    const value = Number(bytes || 0);
    if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} МБ`;
    if (value >= 1024) return `${Math.round(value / 1024)} КБ`;
    return `${value} Б`;
  }

  function updateText(text, className = 'update-text') {
    const element = document.createElement('p');
    element.className = className;
    element.textContent = text;
    return element;
  }

  function updateButton(label, action, kind = '') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `update-button${kind ? ` ${kind}` : ''}`;
    button.textContent = label;
    button.addEventListener('click', action);
    return button;
  }

  async function callUpdates(method, ...args) {
    if (method === 'update_check') awaitingCheck = true;
    try {
      const result = await state.api?.[method]?.(...args);
      if (result && typeof result === 'object') applyUpdateState(result);
      return result;
    } catch (_) {
      showToast('Нет связи с приложением');
      return null;
    }
  }

  function openUpdateDialog() {
    updateDialogOpen = true;
    renderUpdateDialog();
  }

  function closeUpdateDialog() {
    updateDialogOpen = false;
    updateOverlay.classList.add('hidden');
    updateOverlay.setAttribute('aria-hidden', 'true');
    if (['blocked', 'failed'].includes(updateState?.phase)) void callUpdates('update_dismiss');
    restoreEditorFocus();
  }

  function renderUpdateBadge() {
    const current = updateState || {};
    const found = current.update;
    let label = '';
    if (current.phase === 'available' && found) label = found.version;
    else if (current.phase === 'downloading') {
      label = current.total ? `${Math.floor(current.done * 100 / current.total)}%` : '…';
    } else if (current.phase === 'ready' || current.phase === 'rolled_back') label = 'Перезапуск';
    updateBadge.classList.toggle('hidden', !label);
    if (!label) return;
    updateBadge.innerHTML = `${updateIcon}<span></span>`;
    updateBadge.querySelector('span').textContent = label;
    updateBadge.title = current.phase === 'available'
      ? `Доступна версия ${found.version}`
      : current.phase === 'downloading' ? 'Загрузка обновления' : 'Перезапустить NumCalc';
  }

  function renderUpdateDialog() {
    const current = updateState || {};
    const found = current.update;
    updateBody.replaceChildren();
    updateActions.replaceChildren();
    const later = updateButton('Позже', closeUpdateDialog);

    if (current.phase === 'available' && found) {
      updateTitle.textContent = `Доступна версия ${found.version}${found.prerelease ? ' (бета)' : ''}`;
      updateBody.append(updateText(`Установлена ${current.current}`, 'update-meta'));
      if (found.local) updateBody.append(updateText(`Файл: ${found.source}`, 'update-meta'));
      const notes = document.createElement('ul');
      notes.className = 'update-notes';
      (found.notes || []).slice(0, 40).forEach(note => {
        const item = document.createElement('li');
        item.textContent = note;
        notes.appendChild(item);
      });
      updateBody.append(notes.children.length ? notes : updateText('Список изменений не приложен.'));
      updateActions.append(
        updateButton('Пропустить версию', () => { closeUpdateDialog(); void callUpdates('update_skip'); }, 'quiet'),
        later,
        updateButton('Обновить', () => void callUpdates('update_download'), 'primary'),
      );
    } else if (current.phase === 'downloading' && found) {
      updateTitle.textContent = `Загрузка версии ${found.version}`;
      const fraction = current.total ? Math.min(1, current.done / current.total) : 0;
      const bar = document.createElement('div');
      bar.className = 'update-progress';
      bar.innerHTML = '<span></span>';
      bar.firstElementChild.style.width = `${(fraction * 100).toFixed(1)}%`;
      updateBody.append(
        bar,
        updateText(current.total
          ? `${formatSize(current.done)} из ${formatSize(current.total)}`
          : formatSize(current.done), 'update-meta'),
        updateText('Файл заменит программу только после проверки контрольной суммы.'),
      );
      updateActions.append(updateButton('Скрыть', closeUpdateDialog));
    } else if (current.phase === 'ready' && found) {
      updateTitle.textContent = `Версия ${found.version} установлена`;
      updateBody.append(updateText('Она запустится после перезапуска. Прежняя версия сохранена, её можно вернуть в настройках.'));
      if (current.note) updateBody.append(updateText(current.note, 'update-meta'));
      updateActions.append(later, updateButton('Перезапустить', () => void callUpdates('update_restart'), true));
    } else if (current.phase === 'rolled_back') {
      updateTitle.textContent = 'Предыдущая версия возвращена';
      updateBody.append(updateText('Она запустится после перезапуска.'));
      updateActions.append(later, updateButton('Перезапустить', () => void callUpdates('update_restart'), true));
    } else if (current.phase === 'blocked') {
      updateTitle.textContent = 'Нет доступа к GitHub';
      updateBody.append(
        updateText('Похоже, выход в интернет разрешён только браузеру. Скачайте NumCalc.exe в браузере: NumCalc найдёт файл в «Загрузках» и предложит установить его.'),
        updateText(current.message || '', 'update-meta'),
      );
      updateActions.append(
        updateButton('Закрыть', closeUpdateDialog),
        updateButton('Скачать в браузере', () => { updateDialogOpen = false; renderUpdates(); void callUpdates('update_open_browser'); }, 'primary'),
      );
    } else if (current.phase === 'failed') {
      updateTitle.textContent = 'Обновление не удалось';
      updateBody.append(updateText(current.message || '', 'update-text danger'));
      const page = found?.page || '';
      if (page.startsWith('https://')) {
        updateActions.append(updateButton('Страница выпуска', () => void state.api?.open_product_link?.(page)));
      }
      updateActions.append(
        updateButton('Закрыть', closeUpdateDialog),
        updateButton('Повторить', () => void callUpdates('update_download'), 'primary'),
      );
    } else {
      updateDialogOpen = false;
    }

    const visible = updateDialogOpen;
    updateOverlay.classList.toggle('hidden', !visible);
    updateOverlay.setAttribute('aria-hidden', String(!visible));
    if (visible && !updateOverlay.contains(document.activeElement)) {
      requestAnimationFrame(() => (
        updateActions.querySelector('.primary') || updateActions.querySelector('.update-button')
      )?.focus());
    }
  }

  function renderUpdateSettings() {
    const section = dom.drawerContent.querySelector('.settings-updates');
    if (!section || !updateState) return;
    const settings = updateState.settings || {};
    section.querySelector('#updateAuto').checked = settings.auto !== false;
    const channel = section.querySelector('#updateChannel');
    if (!channel.options.length) {
      (updateState.channels || []).forEach(item => channel.add(new Option(item.label, item.id)));
    }
    channel.value = settings.channel || 'stable';
    const folder = section.querySelector('#updateFolder');
    if (document.activeElement !== folder) folder.value = settings.folder || '';
    folder.placeholder = settings.side_folder || 'Не задана';
    section.querySelector('#updateShare').checked = settings.share === true;
    const checkButton = section.querySelector('#updateCheckNow');
    checkButton.disabled = ['checking', 'downloading'].includes(updateState.phase);
    checkButton.textContent = updateState.phase === 'checking' ? 'Проверка…' : 'Проверить сейчас';
    section.querySelector('#updateRollback').classList.toggle('hidden', !updateState.previous);
    section.querySelector('#updateStatus').textContent = updateState.note || '';
    section.querySelector('#updateVersion').textContent = `Установлена версия ${updateState.current}`;
  }

  function renderUpdates() {
    renderUpdateBadge();
    renderUpdateDialog();
    renderUpdateSettings();
  }

  function applyUpdateState(next) {
    const previous = updateState;
    updateState = next;
    const finishedCheck = next.phase !== 'checking'
      && (awaitingCheck || (next.manual && previous?.phase === 'checking'));
    if (next.phase !== 'checking') awaitingCheck = false;
    if (finishedCheck && ['available', 'blocked'].includes(next.phase)) {
      updateDialogOpen = true;
    }
    if (next.manual && previous?.phase === 'idle' && next.phase === 'available') {
      // A file found in Downloads after "Скачать в браузере".
      updateDialogOpen = true;
    }
    if (finishedCheck && next.phase === 'idle' && next.note
        && !dom.drawerContent.querySelector('.settings-updates')) {
      showToast(next.note);
    }
    renderUpdates();
  }

  window.__numcalcUpdates = next => {
    if (next && typeof next === 'object') applyUpdateState(next);
  };

  updateBadge.addEventListener('click', openUpdateDialog);
  document.querySelector('.about-check')?.addEventListener('click', () => {
    document.querySelector('.about-close')?.click();
    void callUpdates('update_check');
  });
  updateOverlay.addEventListener('pointerdown', event => {
    if (event.target === updateOverlay) closeUpdateDialog();
  });
  document.addEventListener('keydown', event => {
    if (!updateDialogOpen || event.key !== 'Escape') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    closeUpdateDialog();
  }, { capture: true });

  const renderSettingsDrawerWithoutUpdates = renderSettingsDrawer;
  renderSettingsDrawer = function renderSettingsDrawerWithUpdates() {
    renderSettingsDrawerWithoutUpdates();
    const content = dom.drawerContent.querySelector('.settings-content');
    if (!content || content.querySelector('.settings-updates')) return;
    const divider = document.createElement('div');
    divider.className = 'settings-divider';
    divider.setAttribute('aria-hidden', 'true');
    const section = document.createElement('section');
    section.className = 'settings-section settings-updates';
    section.innerHTML = `
      <span class="settings-label">Обновления</span>
      <p class="settings-help" id="updateVersion"></p>
      <label class="settings-checkbox">
        <input id="updateAuto" type="checkbox">
        <span>Проверять автоматически</span>
      </label>
      <label class="format-setting">
        <span>Канал</span>
        <select id="updateChannel" class="settings-select"></select>
      </label>
      <label class="format-setting">
        <span>Папка обновлений в сети</span>
        <input id="updateFolder" class="settings-text" type="text" spellcheck="false" autocomplete="off">
      </label>
      <label class="settings-checkbox">
        <input id="updateShare" type="checkbox">
        <span>Выкладывать установленную версию в эту папку</span>
      </label>
      <div class="update-settings-actions">
        <button class="row-button" id="updateCheckNow" type="button">Проверить сейчас</button>
        <button class="row-button hidden" id="updateRollback" type="button">Вернуть предыдущую версию</button>
      </div>
      <div class="hotkey-status" id="updateStatus" role="status"></div>
    `;
    content.append(divider, section);

    const save = () => callUpdates('update_set_preferences', {
      auto: section.querySelector('#updateAuto').checked,
      channel: section.querySelector('#updateChannel').value,
      folder: section.querySelector('#updateFolder').value,
      share: section.querySelector('#updateShare').checked,
    });
    section.querySelector('#updateAuto').addEventListener('change', save);
    section.querySelector('#updateChannel').addEventListener('change', save);
    section.querySelector('#updateShare').addEventListener('change', save);
    section.querySelector('#updateFolder').addEventListener('change', save);
    section.querySelector('#updateCheckNow').addEventListener('click', () => void callUpdates('update_check'));
    section.querySelector('#updateRollback').addEventListener('click', () => void callUpdates('update_rollback'));
    renderUpdateSettings();
  };

  waitForBridge()
    .then(api => api.update_state?.())
    .then(next => { if (next && typeof next === 'object') applyUpdateState(next); })
    .catch(() => {});
