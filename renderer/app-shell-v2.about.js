
  const aboutOverlay = document.createElement('div');
  aboutOverlay.className = 'about-overlay hidden';
  aboutOverlay.setAttribute('aria-hidden', 'true');
  aboutOverlay.innerHTML = `
    <section class="about-card" role="dialog" aria-modal="true" aria-labelledby="aboutTitle">
      <button class="about-close" type="button" aria-label="Закрыть">×</button>
      <h2 id="aboutTitle">
        __NUMCALC_PRODUCT_NAME__
        <span class="about-version">__NUMCALC_PRODUCT_VERSION__</span>
      </h2>
      <p class="about-purpose">Калькулятор для Windows</p>
      <p class="about-license">MIT</p>
      <p class="about-origin">
        <a class="about-link" href="https://nlcalc.narod.ru/" data-product-link>NumLock Calculator</a>
        — Владимир Потапов
      </p>
      <div class="about-actions">
        <a class="about-link" href="https://github.com/Aev199/numlock-calculator" data-product-link>GitHub</a>
      </div>
    </section>
  `;
  document.body.appendChild(aboutOverlay);

  const aboutCard = aboutOverlay.querySelector('.about-card');
  const aboutClose = aboutOverlay.querySelector('.about-close');

  function closeAbout() {
    aboutOverlay.classList.add('hidden');
    aboutOverlay.setAttribute('aria-hidden', 'true');
    requestAnimationFrame(() => {
      try { dom.input.focus({ preventScroll: true }); } catch (_) {}
    });
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

