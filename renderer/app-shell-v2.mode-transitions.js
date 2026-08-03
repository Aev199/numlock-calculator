  const switchModeWithoutExplicitMotion = switchMode;
  const MODE_MOTION_ORDER = ['calculator', 'units', 'interpolation'];
  const MODE_MOTION_EASING = 'cubic-bezier(.22, 1, .36, 1)';
  let modeMotionEpoch = 0;
  let modeMotionAnimations = [];

  function clearModeMotionInlineStyles() {
    dom.modeStage?.querySelectorAll('.mode-panel').forEach(panel => {
      panel.style.removeProperty('visibility');
      panel.style.removeProperty('opacity');
      panel.style.removeProperty('pointer-events');
    });
  }

  function cancelModeMotion() {
    ++modeMotionEpoch;
    for (const animation of modeMotionAnimations) animation.cancel();
    modeMotionAnimations = [];
    clearModeMotionInlineStyles();
  }

  function runExplicitModeMotion(previousMode, nextMode) {
    if (reducedMotion()) return;
    const previousIndex = MODE_MOTION_ORDER.indexOf(previousMode);
    const nextIndex = MODE_MOTION_ORDER.indexOf(nextMode);
    const previousPanel = dom.modeStage?.querySelector(
      `[data-mode-panel="${previousMode}"]`,
    );
    const nextPanel = dom.modeStage?.querySelector(
      `[data-mode-panel="${nextMode}"]`,
    );
    const indicator = byId('modeIndicator');
    if (
      previousIndex < 0
      || nextIndex < 0
      || previousIndex === nextIndex
      || !previousPanel
      || !nextPanel
      || typeof nextPanel.animate !== 'function'
    ) return;

    const epoch = ++modeMotionEpoch;
    previousPanel.style.visibility = 'visible';
    previousPanel.style.opacity = '1';
    previousPanel.style.pointerEvents = 'none';
    nextPanel.style.visibility = 'visible';
    nextPanel.style.opacity = '0';
    nextPanel.style.pointerEvents = 'none';

    const animations = [];
    if (indicator && typeof indicator.animate === 'function') {
      animations.push(indicator.animate(
        [
          { transform: `translate3d(${previousIndex * 100}%, 0, 0)` },
          { transform: `translate3d(${nextIndex * 100}%, 0, 0)` },
        ],
        {
          duration: 300,
          easing: MODE_MOTION_EASING,
          fill: 'none',
        },
      ));
    }

    animations.push(previousPanel.animate(
      [
        { opacity: 1 },
        { opacity: 0 },
      ],
      {
        duration: 170,
        easing: 'ease-out',
        fill: 'both',
      },
    ));
    animations.push(nextPanel.animate(
      [
        { opacity: 0 },
        { opacity: 1 },
      ],
      {
        duration: 230,
        delay: 45,
        easing: MODE_MOTION_EASING,
        fill: 'both',
      },
    ));

    modeMotionAnimations = animations;
    Promise.allSettled(animations.map(animation => animation.finished)).then(() => {
      if (epoch !== modeMotionEpoch) return;
      modeMotionAnimations = [];
      clearModeMotionInlineStyles();
    });
  }

  switchMode = function switchModeWithExplicitMotion(mode) {
    const previousMode = state.mode;
    if (!MODE_MOTION_ORDER.includes(mode) || mode === previousMode) {
      switchModeWithoutExplicitMotion(mode);
      return;
    }

    cancelModeMotion();
    switchModeWithoutExplicitMotion(mode);
    runExplicitModeMotion(previousMode, mode);
  };
