
  // The existing commit path passes only the optimistic result. Recover the
  // outgoing expression from the pending keyed history entry so the roll always
  // has both sides visible.
  const animateCommitRoll = animateCommit;
  animateCommit = function (result) {
    const pending = state.calculator.history.find(entry => entry.pending);
    const outgoing = pending?.expression || state.calculator.historyDraft || '';
    return animateCommitRoll(outgoing, result);
  };
