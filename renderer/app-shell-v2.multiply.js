
  // Present implicit multiplication explicitly without changing the backend
  // expression grammar. This function is also used for history and clipboard.
  const displayExpressionWithoutImplicitMultiply = displayExpression;
  displayExpression = function (value) {
    const visual = displayExpressionWithoutImplicitMultiply(value);
    return visual.replace(/([0-9)])\s*(?=\()/g, `$1${DISPLAY_MULTIPLY}`);
  };

