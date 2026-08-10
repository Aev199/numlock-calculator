
  function formulaGuidanceParagraph(text) {
    const paragraph = document.createElement('p');
    paragraph.className = 'formula-help formula-guide';
    paragraph.textContent = text;
    return paragraph;
  }

  function insertFormulaGuidance(text) {
    const content = dom.drawerContent.querySelector('.formula-content');
    if (!content) return;
    const tabs = content.querySelector('.formula-tabs');
    if (tabs) {
      tabs.insertAdjacentElement('afterend', formulaGuidanceParagraph(text));
      return;
    }
    content.insertBefore(
      formulaGuidanceParagraph(text),
      content.children[1] || null,
    );
  }

  const renderFormulasDrawerWithoutGuidance = renderFormulasDrawer;
  renderFormulasDrawer = function renderFormulasDrawerWithGuidance() {
    renderFormulasDrawerWithoutGuidance();

    if (runningFormulaId) return;
    if (editingFormulaId !== null) {
      insertFormulaGuidance(
        'В выражении используйте имена параметров. Например: N / A; в поле «Параметры» — N = 1200 кН и A = 10 м2. Значения после «=» используются как значения по умолчанию.',
      );
      return;
    }
    if (editingProfileId !== null) {
      insertFormulaGuidance(
        'Константы активного профиля доступны его формулам автоматически. Выберите нужные формулы, задайте постоянные величины, предпочтительные единицы и формат — они применятся после активации профиля.',
      );
      return;
    }

    if (formulaDrawerTab === 'profiles') {
      insertFormulaGuidance(
        'Профиль — набор для конкретного типа задач. Он объединяет нужные формулы, общие константы, предпочтительные единицы и формат. Активный профиль фильтрует список формул, автоматически подставляет свои константы при их запуске и временно применяет единицы и формат; после отключения прежние настройки возвращаются.',
      );
      return;
    }

    insertFormulaGuidance(
      'Формула — шаблон повторяемого расчёта. Один раз сохраните выражение и параметры, например N / A с параметрами N и A. «Запуск» попросит новые значения, рассчитает результат и добавит его в историю; «Вставить» только переносит выражение в калькулятор.',
    );
  };
