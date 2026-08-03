    if (data.storage_warning) showToast(data.storage_warning);
    reconcileHistory();
    bindEvents();
    setInputValue(state.calculator.expression);
    renderResult(null);
    renderInterpolation();
    if (state.ui.onboarding_seen !== true) showOnboarding();
    else restoreEditorFocus();

    function reportRendererDiagnostic(source, message, details = '') {
      try {
        const pending = state.api?.report_diagnostic(source, message, details);
        pending?.catch?.(() => {});
      } catch (_) {}
    }

    window.addEventListener('error', event => {
      reportRendererDiagnostic(
        'renderer',
        event.message || 'JavaScript error',
        event.error?.stack || `${event.filename || ''}:${event.lineno || 0}:${event.colno || 0}`,
      );
    });
    window.addEventListener('unhandledrejection', event => {
      const reason = event.reason;
      reportRendererDiagnostic(
        'renderer-promise',
        reason?.message || String(reason || 'Unhandled promise rejection'),
        reason?.stack || '',
      );
    });

    await state.api.window_focus_changed(document.hasFocus());
  }

  initialize().catch(error => {
    try {
      const pending = state.api?.report_diagnostic(
        'renderer-initialize',
        error?.message || String(error || 'Initialization failed'),
        error?.stack || '',
      );
      pending?.catch?.(() => {});
    } catch (_) {}
    dom.resultValue.textContent = '—';
    dom.resultValue.classList.add('muted');
    dom.resultError.textContent = 'Python API недоступен';
    dom.resultError.classList.remove('hidden');
  });
})();
