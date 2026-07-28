
  // Variable drawer actions are kept in a late renderer layer so deletion can
  // update the persisted backend state and the live suggestion catalog together.
  renderVariablesDrawer = function () {
    dom.drawerTitle.textContent = 'Переменные';
    dom.drawerSubtitle.textContent = 'Создание: имя := выражение';
    dom.drawerContent.replaceChildren();
    const entries = Object.entries(state.variables);
    if (!entries.length) {
      const empty = document.createElement('div');
      empty.className = 'history-empty';
      empty.innerHTML = '<div><strong>Переменных пока нет</strong>Пример: span := 6</div>';
      dom.drawerContent.appendChild(empty);
      return;
    }

    for (const [name, value] of entries) {
      const row = document.createElement('div');
      row.className = 'variable-row';

      const label = document.createElement('span');
      label.className = 'memory-slot';
      label.textContent = name;

      const display = document.createElement('span');
      display.className = 'variable-value';
      display.textContent = value;

      const actions = document.createElement('div');
      actions.className = 'variable-actions';

      const insert = document.createElement('button');
      insert.type = 'button';
      insert.className = 'row-button';
      insert.textContent = 'Вставить';
      insert.addEventListener('click', () => {
        insertAtSelection(name);
        closeDrawer();
      });

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'row-button variable-delete';
      remove.textContent = '×';
      remove.title = `Удалить переменную ${name}`;
      remove.setAttribute('aria-label', `Удалить переменную ${name}`);
      remove.addEventListener('click', async () => {
        remove.disabled = true;
        try {
          const response = await state.api.delete_variable(name);
          if (!response?.ok) {
            showToast(response?.error || 'Не удалось удалить переменную');
            remove.disabled = false;
            return;
          }
          state.variables = response.variables || {};
          if (Array.isArray(response.suggestions)) setCatalog(response.suggestions);
          hideCompletion();
          renderVariablesDrawer();
          scheduleCalculatorPreview(0);
          showToast(`Переменная ${name} удалена`);
        } catch (_) {
          remove.disabled = false;
          showToast('Не удалось удалить переменную');
        }
      });

      actions.append(insert, remove);
      row.append(label, display, actions);
      dom.drawerContent.appendChild(row);
    }
  };
