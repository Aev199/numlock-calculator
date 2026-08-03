
  const ONBOARDING_SLIDES = [
    {
      kicker: 'Быстрый старт',
      title: 'Результат всегда под рукой',
      description: 'Введите выражение и работайте с результатом прямо в компактном окне.',
      items: [
        ['Enter', 'посчитать и добавить запись в историю'],
        ['Ctrl+C', 'скопировать выражение вместе с ответом'],
      ],
    },
    {
      kicker: 'Навигация',
      title: 'Три режима в одной вкладке',
      description: 'Переключайтесь между обычным расчётом, единицами и интерполяцией без мыши.',
      items: [
        ['Alt+← / →', 'перейти к соседней вкладке'],
        ['Tab', 'открыть палитру функций в калькуляторе'],
        ['↑ / ↓', 'подсказки и предыдущие выражения'],
      ],
    },
    {
      kicker: 'Единицы',
      title: 'Преобразуйте инженерные величины',
      description: 'Выберите категорию, исходную и целевую единицы. Формат результата берётся из настроек калькулятора.',
      items: [
        ['Единицы', 'простая арифметика и преобразование величин'],
        ['⇄', 'быстро поменять направление преобразования'],
        ['Enter', 'зафиксировать исходное значение'],
      ],
    },
    {
      kicker: 'Новая возможность',
      title: 'Линейная интерполяция',
      description: 'Во вкладке «Интерполяция» можно найти значение функции между двумя опорными точками.',
      items: [
        ['1D', 'найти y по двум опорным точкам'],
      ],
    },
    {
      kicker: 'Настройки',
      title: 'Настройте NumCalc под себя',
      description: 'В шестерёнке доступны формат чисел, выделение результата после Enter и глобальная клавиша показа окна.',
      items: [
        ['NumLock', 'показать окно, вернуть фокус или скрыть его'],
        ['⚙', 'формат, точность и глобальная клавиша'],
        ['?', 'открыть этот помощник снова'],
      ],
    },
  ];

  let onboardingIndex = 0;

  function renderOnboardingSlide() {
    const slide = ONBOARDING_SLIDES[onboardingIndex];
    dom.onboardingKicker.textContent = slide.kicker;
    dom.onboardingTitle.textContent = slide.title;
    dom.onboardingDescription.textContent = slide.description;
    dom.onboardingItems.replaceChildren();
    for (const [key, description] of slide.items) {
      const row = document.createElement('div');
      row.className = 'onboarding-item';
      const keyElement = document.createElement('kbd');
      keyElement.textContent = key;
      const textElement = document.createElement('span');
      textElement.className = 'onboarding-item-text';
      textElement.textContent = description;
      row.append(keyElement, textElement);
      dom.onboardingItems.appendChild(row);
    }
    dom.onboardingProgress.textContent = `${onboardingIndex + 1} / ${ONBOARDING_SLIDES.length}`;
    dom.onboardingBack.disabled = onboardingIndex === 0;
    dom.onboardingNext.textContent = onboardingIndex === ONBOARDING_SLIDES.length - 1
      ? 'Начать работу'
      : 'Далее';
  }

  function markOnboardingSeen() {
    if (state.ui.onboarding_seen === true) return;
    state.ui.onboarding_seen = true;
    state.api?.set_ui_settings?.({ onboarding_seen: true }).catch?.(() => {});
  }

  function closeOnboarding() {
    markOnboardingSeen();
    dom.onboardingOverlay.classList.add('hidden');
    dom.onboardingOverlay.setAttribute('aria-hidden', 'true');
    if (state.mode === 'interpolation') {
      interpolationField(INTERPOLATION_FIELDS[0])?.focus();
    } else {
      restoreEditorFocus();
    }
  }

  function showOnboarding() {
    closeTransientUi();
    onboardingIndex = 0;
    renderOnboardingSlide();
    dom.onboardingOverlay.classList.remove('hidden');
    dom.onboardingOverlay.setAttribute('aria-hidden', 'false');
    dom.onboardingNext.focus();
  }

  function advanceOnboarding() {
    if (onboardingIndex >= ONBOARDING_SLIDES.length - 1) {
      closeOnboarding();
      return;
    }
    onboardingIndex += 1;
    renderOnboardingSlide();
  }

  function bindOnboardingEvents() {
    dom.helpButton.addEventListener('click', showOnboarding);
    dom.onboardingClose.addEventListener('click', closeOnboarding);
    dom.onboardingSkip.addEventListener('click', closeOnboarding);
    dom.onboardingBack.addEventListener('click', () => {
      if (onboardingIndex === 0) return;
      onboardingIndex -= 1;
      renderOnboardingSlide();
    });
    dom.onboardingNext.addEventListener('click', advanceOnboarding);
    dom.onboardingOverlay.addEventListener('mousedown', event => {
      if (event.target === dom.onboardingOverlay) closeOnboarding();
    });
    dom.onboardingOverlay.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeOnboarding();
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        advanceOnboarding();
      } else if (event.key === 'ArrowLeft' && onboardingIndex > 0) {
        event.preventDefault();
        onboardingIndex -= 1;
        renderOnboardingSlide();
      }
    });
  }
