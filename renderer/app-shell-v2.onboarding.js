
  const ONBOARDING_SHORTCUTS = [
    ['NumLock', 'показать или скрыть NumCalc'],
    ['Enter', 'вычислить и добавить в историю'],
    ['↑ / ↓', 'перейти по истории выражений'],
    ['Tab', 'открыть функции'],
    ['Alt+← / →', 'переключить рабочий режим'],
    ['Alt+↑ / ↓', 'компактный / полный интерфейс'],
    ['Ctrl+H', 'открыть историю'],
    ['Ctrl+C', 'скопировать выражение и результат'],
  ];

  function renderOnboardingSlide() {
    dom.onboardingKicker.textContent = '';
    dom.onboardingTitle.textContent = 'Клавиши NumCalc';
    dom.onboardingDescription.textContent = 'Основные команды. Полная настройка доступна через ⚙.';
    dom.onboardingItems.replaceChildren();
    for (const [key, description] of ONBOARDING_SHORTCUTS) {
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
    dom.onboardingProgress.textContent = '';
    dom.onboardingBack.disabled = true;
    dom.onboardingNext.textContent = 'Понятно';
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
    renderOnboardingSlide();
    dom.onboardingOverlay.classList.remove('hidden');
    dom.onboardingOverlay.setAttribute('aria-hidden', 'false');
    dom.onboardingNext.focus();
  }

  function bindOnboardingEvents() {
    dom.helpButton.addEventListener('click', showOnboarding);
    dom.onboardingClose.addEventListener('click', closeOnboarding);
    dom.onboardingSkip.addEventListener('click', closeOnboarding);
    dom.onboardingBack.addEventListener('click', closeOnboarding);
    dom.onboardingNext.addEventListener('click', closeOnboarding);
    dom.onboardingOverlay.addEventListener('mousedown', event => {
      if (event.target === dom.onboardingOverlay) closeOnboarding();
    });
    dom.onboardingOverlay.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeOnboarding();
      }
    });
  }
