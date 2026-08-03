  function applyHandoff(incoming) {
    if (!incoming) return;
    const currentRevision = Number(state.calculator.handoff.revision || 0);
    const incomingRevision = Number(incoming.revision || 0);
    if (incomingRevision < currentRevision) return;
    state.calculator.handoff = { ...incoming, optimistic: false };
  }

  async function refreshSessionData(refreshCatalog = false) {
    const data = await state.api.bootstrap();
    state.variables = data.variables || {};
    state.memories = data.memories || Array(10).fill('0');
    if (refreshCatalog) setCatalog(data.suggestions || []);
  }

  async function commitCalculator() {
    cancelCalculatorPreview();
    const expression = normalize(state.calculator.expression);
    if (!expression) return;
    hideCompletion();

    const commitId = ++state.calculator.commitSequence;
    const historyEpoch = state.calculator.historyEpoch;
    const preview = (
      state.calculator.previewExpression === state.calculator.expression
      && state.calculator.preview?.ok
    ) ? state.calculator.preview : null;
    const optimisticResult = preview ? normalize(preview.result) : '';
    const visibleCommittedValue = optimisticResult || expression;
    const previousHandoff = { ...state.calculator.handoff };
    const previousUnits = {
      expression: state.units.expression,
      imported_revision: state.units.imported_revision,
    };
    let optimisticRevision = null;
    let localId = null;
    let resultSelected = false;

    const rollbackOptimisticState = () => {
      if (
        optimisticRevision !== null
        && Number(state.calculator.handoff.revision || 0) === optimisticRevision
        && state.calculator.handoff.optimistic
      ) {
        state.calculator.handoff = previousHandoff;
        if (
          Number(state.units.imported_revision || 0) === optimisticRevision
          && state.units.expression === optimisticResult
        ) {
          state.units.expression = previousUnits.expression;
          state.units.imported_revision = previousUnits.imported_revision;
          persistUnitsSoon();
        }
      }
    };

    if (optimisticResult) {
      localId = optimisticHistoryEntry(expression, optimisticResult);
      state.calculator.expression = optimisticResult;
      setInputValue(optimisticResult);
      state.calculator.preview = {
        ...preview,
        expression: optimisticResult,
        result: optimisticResult,
      };
      state.calculator.previewExpression = optimisticResult;
      renderResult(state.calculator.preview);
      resultSelected = selectEditorResultAfterEnter();

      if (isPlainNumber(optimisticResult)) {
        optimisticRevision = Number(previousHandoff.revision || 0) + 1;
        state.calculator.handoff = {
          revision: optimisticRevision,
          value: optimisticResult,
          updated_at: new Date().toISOString(),
          optimistic: true,
        };
      }
    }

    ++state.calculator.pendingCommits;
    try {
      const response = await state.api.commit(expression);
      if (!response?.ok) {
        rollbackHistoryEntry(localId, historyEpoch);
        const stillCurrent = (
          state.calculator.commitSequence === commitId
          && state.calculator.expression === visibleCommittedValue
        );
        if (stillCurrent) {
          state.calculator.expression = expression;
          if (state.mode === 'calculator') setInputValue(expression);
          state.calculator.preview = response;
          state.calculator.previewExpression = expression;
          if (state.mode === 'calculator') renderResult(response);
        }
        rollbackOptimisticState();
        return;
      }

      if (localId && response.history_entry) {
        confirmHistoryEntry(localId, response.history_entry, historyEpoch);
      } else if (
        response.history_entry
        && historyEpoch === state.calculator.historyEpoch
        && !state.calculator.history.some(
          entry => entry.id === response.history_entry.id,
        )
      ) {
        state.calculator.history.unshift(response.history_entry);
        reconcileHistory({ animateId: response.history_entry.id });
      }

      const result = normalize(response.result) || expression;
      const stillCurrent = (
        state.calculator.commitSequence === commitId
        && state.calculator.expression === visibleCommittedValue
      );
      if (stillCurrent) {
        state.calculator.expression = result;
        state.calculator.preview = { ...response, expression: result, result };
        state.calculator.previewExpression = result;
        if (state.mode === 'calculator') {
          setInputValue(result);
          renderResult(state.calculator.preview);
          if (!resultSelected || result !== visibleCommittedValue) {
            resultSelected = selectEditorResultAfterEnter();
          }
        }
      }

      applyHandoff(response.calculator_handoff);
      state.calculator.historyCursor = -1;
      state.calculator.historyDraft = '';
      if (response.assigned_variable) await refreshSessionData(true);
    } catch (_) {
      rollbackHistoryEntry(localId, historyEpoch);
      const stillCurrent = (
        state.calculator.commitSequence === commitId
        && state.calculator.expression === visibleCommittedValue
      );
      if (stillCurrent) {
        state.calculator.expression = expression;
        state.calculator.preview = null;
        state.calculator.previewExpression = '';
        if (state.mode === 'calculator') {
          setInputValue(expression);
          scheduleCalculatorPreview(0);
        }
      }
      rollbackOptimisticState();
      showToast('Ошибка связи с приложением');
    } finally {
      state.calculator.pendingCommits = Math.max(
        0,
        state.calculator.pendingCommits - 1,
      );
    }
  }

  async function commitUnits() {
    cancelUnitsPreview();
    const expression = normalize(state.units.expression);
    if (!expression) return;

    const commitId = ++state.units.commitSequence;
    const context = unitContext();
    const preview = (
      state.units.previewExpression === state.units.expression
      && state.units.previewContext === context
      && state.units.preview?.ok
    ) ? state.units.preview : null;
    const optimisticValue = preview?.source_value
      ? String(preview.source_value)
      : expression;
    let resultSelected = false;

    if (preview?.source_value) {
      state.units.expression = optimisticValue;
      if (state.mode === 'units') {
        setInputValue(optimisticValue);
        renderResult(preview);
        resultSelected = selectEditorResultAfterEnter();
      }
    }

    try {
      const response = await state.api.convert_units(
        expression,
        context.split('|')[0],
        context.split('|')[1],
        context.split('|')[2],
        true,
        state.units.imported_revision,
      );
      const stillCurrent = (
        state.units.commitSequence === commitId
        && state.units.expression === optimisticValue
        && unitContext() === context
      );
      if (!response?.ok) {
        if (stillCurrent && state.mode === 'units') renderResult(response);
        return;
      }
