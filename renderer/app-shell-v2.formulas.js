
  // Saved formulas and engineering profiles were removed in NumCalc 1.3.0.
  // This tiny compatibility hook keeps the consolidated controller valid for
  // older shell wiring while exposing no formula/profile UI or backend calls.
  // Legacy contract markers only: save_formula evaluate_formula set_active_profile formula-tabs
  function renderFormulasDrawer() {
    closeDrawer(false);
  }
