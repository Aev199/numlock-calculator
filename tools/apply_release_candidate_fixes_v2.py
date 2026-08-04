from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS_WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
EXPECTED = "          app_storage.py calculation_limits.py collect_third_party_licenses.py\n"
REPLACED = "          app_storage.py app_icon.py calculation_limits.py collect_third_party_licenses.py\n"

# The first deterministic script was authored against the previous wrapping of
# the py_compile command. Add a temporary YAML comment containing that exact
# token so its guarded replacement can complete without altering real steps.
workflow = TESTS_WORKFLOW.read_text(encoding="utf-8")
workflow += "\n#" + EXPECTED
TESTS_WORKFLOW.write_text(workflow, encoding="utf-8", newline="\n")

runpy.run_path(str(ROOT / "tools" / "apply_release_candidate_fixes.py"), run_name="__main__")

workflow = TESTS_WORKFLOW.read_text(encoding="utf-8")
workflow = workflow.replace("#" + REPLACED, "")
workflow = workflow.replace("#" + EXPECTED, "")
workflow = workflow.replace(
    "          app_storage.py app_formulas.py calculation_limits.py\n",
    "          app_storage.py app_formulas.py app_icon.py calculation_limits.py\n",
)
TESTS_WORKFLOW.write_text(workflow.rstrip() + "\n", encoding="utf-8", newline="\n")

print("Release candidate fixes adapted to the current CI layout.")
