
  // A lone numeric value is already its own result. Keep Ctrl+C concise for
  // values produced by Enter as well as numbers typed directly in the editor.
  const STANDALONE_CLIPBOARD_NUMBER = /^[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:e[+-]?\d+)?$/i;
  const CLIPBOARD_DIGIT_GROUPING = /(?<=\d)[ \u00a0\u202f]+(?=\d)/g;

  function isStandaloneClipboardNumber(value) {
    return STANDALONE_CLIPBOARD_NUMBER.test(
      String(value ?? '')
        .trim()
        .replace(CLIPBOARD_DIGIT_GROUPING, '')
        .replace(',', '.'),
    );
  }

  const copyCalculationWithResult = copyCurrentCalculation;
  copyCurrentCalculation = async function () {
    const expression = normalize(dom.input.value);
    if (state.mode !== 'calculator' || !isStandaloneClipboardNumber(expression)) {
      return copyCalculationWithResult();
    }

    try {
      const copied = await state.api.copy_text(displayExpression(expression));
      showToast(copied ? 'Скопировано' : 'Не удалось открыть буфер обмена');
    } catch (_) {
      showToast('Не удалось скопировать значение');
    }
  };

