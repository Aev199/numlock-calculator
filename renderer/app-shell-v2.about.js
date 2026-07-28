
  const aboutOverlay = document.createElement('div');
  aboutOverlay.className = 'about-overlay hidden';
  aboutOverlay.setAttribute('aria-hidden', 'true');
  aboutOverlay.innerHTML = `
    <section class="about-card" role="dialog" aria-modal="true" aria-labelledby="aboutTitle">
      <button class="about-close" type="button" aria-label="Закрыть">×</button>
      <div class="about-mark" aria-hidden="true">N</div>
      <h2 id="aboutTitle">NumCalc 1.0.0</h2>
      <p class="about-description">Компактный keyboard-first калькулятор для Windows.</p>
      <p>
        Калькулятор — идеологическое продолжение
        <a class="about-link" href="https://nlcalc.narod.ru/" data-product-link>
          NumLock Calculator
        </a>
        от Владимира Потапова.
      </p>
      <a class="about-link about-repository" href="https://github.com/Aev199/numlock-calculator" data-product-link>
        Репозиторий NumCalc
      </a>
      <p class="about-license">Лицензия исходного кода: MIT</p>
    </section>
  `;
  document.body.appendChild(aboutOverlay);

  const aboutCard = aboutOverlay.querySelector('.about-card');
  const aboutClose = aboutOverlay.querySelector('.about-close');

  function closeAbout() {
    aboutOverlay.classList.add('hidden');
    aboutOverlay.setAttribute('aria-hidden', 'true');
    restoreEditorFocusSoon();
  }

  function showAbout() {
    closeTransientUi();
    aboutOverlay.classList.remove('hidden');
    aboutOverlay.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(() => aboutClose.focus());
    return true;
  }

  window.__nlcalcShowAbout = showAbout;

  aboutClose.addEventListener('click', closeAbout);
  aboutOverlay.addEventListener('pointerdown', event => {
    if (event.target === aboutOverlay) closeAbout();
  });
  aboutCard.addEventListener('pointerdown', event => event.stopPropagation());

  aboutOverlay.querySelectorAll('[data-product-link]').forEach(link => {
    link.addEventListener('click', async event => {
      event.preventDefault();
      const url = link.getAttribute('href');
      try {
        const opened = await state.api.open_product_link(url);
        if (!opened) showToast('Не удалось открыть ссылку');
      } catch (_) {
        showToast('Не удалось открыть ссылку');
      }
    });
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !aboutOverlay.classList.contains('hidden')) {
      event.preventDefault();
      event.stopImmediatePropagation();
      closeAbout();
    }
  }, { capture: true });
