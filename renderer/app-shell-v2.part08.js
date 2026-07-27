    if (data.storage_warning) showToast(data.storage_warning);
    reconcileHistory();
    bindEvents();
    setInputValue(state.calculator.expression);
    renderResult(null);
    restoreEditorFocus();

    window.addEventListener('error', event => {
      state.api?.report_diagnostic(
        'renderer',
        event.message || 'JavaScript error',
        event.error?.stack || `${event.filename || ''}:${event.lineno || 0}:${event.colno || 0}`,
      ).catch(() => {});
    });
    window.addEventListener('unhandledrejection', event => {
      const reason = event.reason;
      state.api?.report_diagnostic(
        'renderer-promise',
        reason?.message || String(reason || 'Unhandled promise rejection'),
        reason?.stack || '',
      ).catch(() => {});
    });

    await state.api.window_focus_changed(document.hasFocus());
  }

  initialize().catch(error => {
    state.api?.report_diagnostic(
      'renderer-initialize',
      error?.message || String(error || 'Initialization failed'),
      error?.stack || '',
    ).catch(() => {});
    dom.resultValue.textContent = '—';
    dom.resultValue.classList.add('muted');
    dom.resultError.textContent = 'Python API недоступен';
    dom.resultError.classList.remove('hidden');
  });
})();
