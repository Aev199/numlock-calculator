import types
import unittest
from pathlib import Path

import app_product
import app_renderer


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "renderer"


class FormulaGuidanceTests(unittest.TestCase):
    def test_guidance_layer_is_bundled_after_formulas_before_event_binding(self):
        guidance = "app-shell-v2.formula-guidance.js"
        self.assertIn(guidance, app_renderer.SCRIPT_PARTS)
        self.assertLess(
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.formulas.js"),
            app_renderer.SCRIPT_PARTS.index(guidance),
        )
        self.assertLess(
            app_renderer.SCRIPT_PARTS.index(guidance),
            app_renderer.SCRIPT_PARTS.index("app-shell-v2.part06.js"),
        )

    def test_contextual_guidance_explains_formulas_and_profiles(self):
        source = (RENDERER / "app-shell-v2.formula-guidance.js").read_text(
            encoding="utf-8"
        )
        for marker in (
            "Формула — шаблон повторяемого расчёта",
            "N / A",
            "«Запуск» попросит новые значения",
            "«Вставить» только переносит выражение",
            "Профиль — набор для конкретного типа задач",
            "автоматически подставляет свои константы",
            "после отключения прежние настройки возвращаются",
            "Значения после «=» используются как значения по умолчанию",
        ):
            self.assertIn(marker, source)

    def test_general_help_contains_formula_and_profile_workflow(self):
        app = types.SimpleNamespace()
        tray = types.SimpleNamespace()
        app_product.install(app, tray)

        self.assertIn("Формулы и профили", tray.HELP_TEXT)
        self.assertIn("Σ — библиотека повторяемых расчётов", tray.HELP_TEXT)
        self.assertIn("N / A", tray.HELP_TEXT)
        self.assertIn("Активный профиль", tray.HELP_TEXT)
        self.assertIn("прежние настройки возвращаются", tray.HELP_TEXT)


if __name__ == "__main__":
    unittest.main()
