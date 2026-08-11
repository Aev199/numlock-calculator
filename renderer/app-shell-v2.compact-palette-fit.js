
  const COMPACT_PALETTE_RESULTS_MAX_HEIGHT = 232;
  const COMPACT_PALETTE_VERTICAL_PADDING = 12;
  let compactPaletteFitFrame = null;

  function compactPaletteContentHeight() {
    const palette = dom.paletteOverlay.querySelector('.palette');
    if (!palette) return COMPACT_OVERLAY_HEIGHT;
    return Math.ceil(
      palette.getBoundingClientRect().height
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
  // settings/history. The function palette is usually much shorter, so give its
  // results a stable internal scroll ceiling and fit the native window around
  // the actual rendered palette instead of leaving a blank strip underneath.
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
