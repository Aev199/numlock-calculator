
  const COMPACT_PALETTE_RESULTS_MAX_HEIGHT = 232;
  const COMPACT_PALETTE_VERTICAL_PADDING = 12;
  const COMPACT_PALETTE_BORDER_HEIGHT = 2;
  let compactPaletteFitFrame = null;

  function visibleElementHeight(element) {
    if (!element || window.getComputedStyle(element).display === 'none') return 0;
    return Math.ceil(element.getBoundingClientRect().height);
  }

  function compactPaletteContentHeight() {
    const palette = dom.paletteOverlay.querySelector('.palette');
    if (!palette) return COMPACT_OVERLAY_HEIGHT;

    const search = palette.querySelector('.palette-search-wrap');
    const groups = palette.querySelector('.palette-groups');
    const footer = palette.querySelector('.palette-footer');

    // Do not measure the palette box itself here. In compact mode its max-height
    // is constrained by the *current* 100vh, which creates a feedback loop: the
    // short calculator viewport makes the palette report the same short height.
    // scrollHeight gives us the natural result-list height even while its parent
    // is clipped, so the native window can grow first and only then display it.
    const resultsHeight = Math.min(
      COMPACT_PALETTE_RESULTS_MAX_HEIGHT,
      Math.ceil(dom.paletteResults.scrollHeight || 0),
    );
    return Math.ceil(
      visibleElementHeight(search)
      + visibleElementHeight(groups)
      + resultsHeight
      + visibleElementHeight(footer)
      + COMPACT_PALETTE_BORDER_HEIGHT
      + COMPACT_PALETTE_VERTICAL_PADDING,
    );
  }

  function scheduleCompactPaletteFit() {
    if (!compactModeEnabled() || !paletteIsOpen()) return;
    window.cancelAnimationFrame(compactPaletteFitFrame);
    compactPaletteFitFrame = window.requestAnimationFrame(() => {
      compactPaletteFitFrame = null;
      if (!compactModeEnabled() || !paletteIsOpen()) return;
      state.api?.set_compact_window?.(
        true,
        compactPaletteContentHeight(),
      ).catch?.(() => {});
    });
  }

  // The generic compact overlay height is intentionally large enough for
  // settings/history. The function palette instead computes its natural height
  // from search + groups + visible results, independently of the current compact
  // viewport. Long lists stop at the result-list ceiling and scroll internally.
  const openPaletteWithoutContentFit = openPalette;
  openPalette = function () {
    dom.paletteResults.style.maxHeight = compactModeEnabled()
      ? `${COMPACT_PALETTE_RESULTS_MAX_HEIGHT}px`
      : '';
    const result = openPaletteWithoutContentFit();
    if (compactModeEnabled()) scheduleCompactPaletteFit();
    return result;
  };

  const renderPaletteWithoutContentFit = renderPalette;
  renderPalette = function () {
    const result = renderPaletteWithoutContentFit();
    if (compactModeEnabled() && paletteIsOpen()) {
      scheduleCompactPaletteFit();
    }
    return result;
  };

  const closePaletteWithoutContentFit = closePalette;
  closePalette = function (focus = true) {
    window.cancelAnimationFrame(compactPaletteFitFrame);
    compactPaletteFitFrame = null;
    const result = closePaletteWithoutContentFit(focus);
    dom.paletteResults.style.maxHeight = '';
    return result;
  };
