
  // Variables and lightweight user functions share one compact drawer. Both
  // are created directly in the calculator line, so management stays close to
  // the keyboard-first workflow instead of the heavier formula/profile UI.
  renderVariablesDrawer = async function () {
    dom.drawerTitle.textContent = 'Переменные и функции';
    dom.drawerSubtitle.textContent = 'x := выражение · c(d) := pi*d^2/4';
    dom.drawerContent.replaceChildren();

    let userFunctions = {};
    try {
      const data = await state.api.bootstrap();
      state.variables = data.variables || state.variables || {};
      userFunctions = data.user_functions || {};
      if (Array.isArray(data.suggestions)) setCatalog(data.suggestions);
    } catch (_) {
      userFunctions = {};
    }

    const variableEntries = Object.entries(state.variables);
    const functionEntries = Object.entries(userFunctions);
    if (!variableEntries.length && !functionEntries.length) {
      const empty = document.createElement('div');
      empty.className = 'history-empty';
      empty.innerHTML = '<div><strong>Переменных и функций пока нет</strong>Примеры: span := 6 · c(d) := pi*d^2/4</div>';
      dom.drawerContent.appendChild(empty);
      return;
    }

    const appendRow = ({ labelText, valueText, insertText, deleteTitle, onDelete, functionCall = false }) => {
      const row = document.createElement('div');
      row.className = 'variable-row';

      const label = document.createElement('span');
      label.className = 'memory-slot';
      label.textContent = labelText;

      const display = document.createElement('span');
      display.className = 'variable-value';
      display.textContent = valueText;

      const actions = document.createElement('div');
      actions.className = 'variable-actions';

      const insert = document.createElement('button');
      insert.type = 'button';
      insert.className = 'row-button';
      insert.textContent = 'Вставить';
      insert.addEventListener('click', () => {
        insertAtSelection(insertText);
        if (functionCall) {
          const cursor = dom.input.selectionStart ?? dom.input.value.length;
          setSelection(Math.max(0, cursor - 1));
        }
        closeDrawer();
      });

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'row-button variable-delete';
      remove.textContent = '×';
      remove.title = deleteTitle;
      remove.setAttribute('aria-label', deleteTitle);
      remove.addEventListener('click', async () => {
        remove.disabled = true;
        try {
          const response = await onDelete();
          if (!response?.ok) {
            showToast(response?.error || 'Не удалось удалить запись');
            remove.disabled = false;
            return;
          }
          if (response.variables) state.variables = response.variables;
          if (Array.isArray(response.suggestions)) setCatalog(response.suggestions);
          hideCompletion();
          await renderVariablesDrawer();
          scheduleCalculatorPreview(0);
        } catch (_) {
          remove.disabled = false;
          showToast('Не удалось удалить запись');
        }
      });

      actions.append(insert, remove);
      row.append(label, display, actions);
      dom.drawerContent.appendChild(row);
    };

    for (const [name, value] of variableEntries) {
      appendRow({
        labelText: name,
        valueText: value,
        insertText: name,
        deleteTitle: `Удалить переменную ${name}`,
        onDelete: async () => {
          const response = await state.api.delete_variable(name);
          if (response?.ok) showToast(`Переменная ${name} удалена`);
          return response;
        },
      });
    }

    for (const [name, definition] of functionEntries) {
      const parameters = Array.isArray(definition?.parameters)
        ? definition.parameters
        : [];
      const signature = definition?.signature || `${name}(${parameters.join(', ')})`;
      const expression = String(definition?.expression || '');
      appendRow({
        labelText: signature,
        valueText: `= ${expression}`,
        insertText: `${name}()`,
        functionCall: true,
        deleteTitle: `Удалить функцию ${signature}`,
        onDelete: async () => {
          const response = await state.api.delete_user_function(name);
          if (response?.ok) showToast(`Функция ${signature} удалена`);
          return response;
        },
      });
    }
  };
