    reconcileHistory();
    bindEvents();
    setInputValue(state.calculator.expression);
    renderResult(null);
    restoreEditorFocus();
    await state.api.window_focus_changed(document.hasFocus());
  }

  initialize().catch(() => {
    dom.resultValue.textContent = '—';
    dom.resultValue.classList.add('muted');
    dom.resultError.textContent = 'Python API недоступен';
    dom.resultError.classList.remove('hidden');
  });
})();
