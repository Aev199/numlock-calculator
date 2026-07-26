"""Separate calculator and unit-conversion modes for NumLock Calc."""

from __future__ import annotations

import ast
import math
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import calc_engine as core


UNIT_CATEGORIES: tuple[dict[str, Any], ...] = (
    {
        "id": "length",
        "label": "Длина",
        "units": (
            ("mm", "Миллиметр"),
            ("cm", "Сантиметр"),
            ("m", "Метр"),
            ("km", "Километр"),
            ("in", "Дюйм"),
            ("ft", "Фут"),
            ("mi", "Миля"),
        ),
    },
    {
        "id": "area",
        "label": "Площадь",
        "units": (
            ("mm2", "Квадратный миллиметр"),
            ("cm2", "Квадратный сантиметр"),
            ("m2", "Квадратный метр"),
            ("ha", "Гектар"),
            ("km2", "Квадратный километр"),
            ("in2", "Квадратный дюйм"),
            ("ft2", "Квадратный фут"),
        ),
    },
    {
        "id": "volume",
        "label": "Объём",
        "units": (
            ("mL", "Миллилитр"),
            ("cm3", "Кубический сантиметр"),
            ("L", "Литр"),
            ("m3", "Кубический метр"),
            ("gal", "Галлон США"),
            ("ft3", "Кубический фут"),
        ),
    },
    {
        "id": "mass",
        "label": "Масса",
        "units": (
            ("g", "Грамм"),
            ("kg", "Килограмм"),
            ("t", "Тонна"),
            ("oz", "Унция"),
            ("lb", "Фунт"),
        ),
    },
    {
        "id": "time",
        "label": "Время",
        "units": (
            ("s", "Секунда"),
            ("min", "Минута"),
            ("h", "Час"),
        ),
    },
    {
        "id": "temperature",
        "label": "Температура",
        "units": (
            ("degC", "Градус Цельсия"),
            ("K", "Кельвин"),
            ("degF", "Градус Фаренгейта"),
        ),
    },
    {
        "id": "force",
        "label": "Сила",
        "units": (
            ("N", "Ньютон"),
            ("kN", "Килоньютон"),
            ("kgf", "Килограмм-сила"),
            ("lbf", "Фунт-сила"),
        ),
    },
    {
        "id": "pressure",
        "label": "Давление",
        "units": (
            ("Pa", "Паскаль"),
            ("kPa", "Килопаскаль"),
            ("MPa", "Мегапаскаль"),
            ("GPa", "Гигапаскаль"),
            ("bar", "Бар"),
            ("atm", "Атмосфера"),
            ("mmHg", "Миллиметр ртутного столба"),
            ("psi", "Фунт на квадратный дюйм"),
        ),
    },
)

_CATEGORY_BY_ID = {item["id"]: item for item in UNIT_CATEGORIES}
_DEFAULT_STATE = {
    "category": "length",
    "from_unit": "m",
    "to_unit": "mm",
    "expression": "",
    "imported_revision": 0,
}
_PLAIN_NUMBER = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$",
    flags=re.IGNORECASE,
)
_ALLOWED_BINARY = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
    ast.Pow: lambda left, right: left**right,
}
_ALLOWED_UNARY = {
    ast.UAdd: lambda value: value,
    ast.USub: lambda value: -value,
}


def _unit_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": category["id"],
            "label": category["label"],
            "units": [
                {"symbol": symbol, "label": label}
                for symbol, label in category["units"]
            ],
        }
        for category in UNIT_CATEGORIES
    ]


def _category_symbols(category_id: str) -> tuple[str, ...]:
    category = _CATEGORY_BY_ID.get(category_id) or _CATEGORY_BY_ID[_DEFAULT_STATE["category"]]
    return tuple(symbol for symbol, _label in category["units"])


def _sanitize_state(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    category = str(raw.get("category", _DEFAULT_STATE["category"]))
    if category not in _CATEGORY_BY_ID:
        category = _DEFAULT_STATE["category"]
    symbols = _category_symbols(category)
    source = str(raw.get("from_unit", symbols[0]))
    target = str(raw.get("to_unit", symbols[1] if len(symbols) > 1 else symbols[0]))
    if source not in symbols:
        source = symbols[0]
    if target not in symbols:
        target = symbols[1] if len(symbols) > 1 else symbols[0]
    if target == source and len(symbols) > 1:
        target = next(symbol for symbol in symbols if symbol != source)
    try:
        imported_revision = max(0, int(raw.get("imported_revision", 0)))
    except (TypeError, ValueError):
        imported_revision = 0
    return {
        "category": category,
        "from_unit": source,
        "to_unit": target,
        "expression": str(raw.get("expression", "")),
        "imported_revision": imported_revision,
    }


def _sanitize_handoff(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    try:
        revision = max(0, int(raw.get("revision", 0)))
    except (TypeError, ValueError):
        revision = 0
    result = str(raw.get("value", "")).strip()
    if result and not _PLAIN_NUMBER.fullmatch(result):
        result = ""
    return {
        "revision": revision,
        "value": result,
        "updated_at": str(raw.get("updated_at", "")),
    }


def _ensure_state(api: Any) -> None:
    if not hasattr(api, "_unit_converter_state"):
        api._unit_converter_state = _sanitize_state(
            api._storage.get("unit_converter_state", {})
        )
    if not hasattr(api, "_calculator_handoff"):
        api._calculator_handoff = _sanitize_handoff(
            api._storage.get("calculator_handoff", {})
        )


def _normalize_simple_expression(expression: str) -> str:
    value = str(expression or "").replace("\u00a0", " ")
    value = value.replace("×", "*").replace("·", "*").replace("÷", "/")
    value = value.replace("−", "-").replace("–", "-").replace("—", "-")
    value = re.sub(r"(?<=\d),(?=\d)", ".", value)
    value = value.replace("^", "**").strip()
    if len(value) > 256:
        raise ValueError("Выражение слишком длинное")
    return value


def _evaluate_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("Разрешены только числа и арифметические операции")
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
        return float(_ALLOWED_UNARY[type(node.op)](_evaluate_node(node.operand)))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINARY:
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise ValueError("Деление на ноль")
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("Слишком большой показатель степени")
        try:
            result = _ALLOWED_BINARY[type(node.op)](left, right)
        except (ArithmeticError, OverflowError) as exc:
            raise ValueError("Некорректная арифметическая операция") from exc
        if isinstance(result, complex) or not math.isfinite(float(result)):
            raise ValueError("Результат не является конечным числом")
        return float(result)
    raise ValueError("Разрешены только числа, скобки и операции + − × ÷ ^")


def evaluate_simple(expression: str) -> float:
    prepared = _normalize_simple_expression(expression)
    if not prepared:
        raise ValueError("Введите значение")
    try:
        tree = ast.parse(prepared, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Проверьте арифметическое выражение") from exc
    return _evaluate_node(tree)


def _format_number(value: float, precision: int = 12) -> str:
    if not math.isfinite(value):
        raise ValueError("Результат не является конечным числом")
    precision = max(3, min(17, int(precision)))
    if value == 0:
        return "0"
    if abs(value) >= 10 ** max(precision, 6) or abs(value) < 10 ** (-max(precision - 2, 6)):
        text = f"{value:.{precision - 1}e}"
        mantissa, exponent = text.split("e")
        return f"{mantissa.rstrip('0').rstrip('.')}e{int(exponent):+d}"
    return f"{value:.{precision}g}"


def _plain_result(response: dict[str, Any]) -> str:
    result = str(response.get("result", "")).strip()
    return result if _PLAIN_NUMBER.fullmatch(result) else ""


def _filter_suggestions(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [
        item
        for item in items
        if isinstance(item, dict)
        and item.get("kind") != "unit"
        and item.get("group") != "Единицы"
    ]


def install(app: Any) -> None:
    """Install unit mode API and inject its renderer shell."""

    if getattr(app, "_units_mode_installed", False):
        return
    app._units_mode_installed = True

    original_bootstrap = app.AppApi.bootstrap
    original_suggestions = app.AppApi.suggestions
    original_build_html: Callable[[], str] = app.build_html

    def bootstrap(self: Any) -> dict[str, Any]:
        _ensure_state(self)
        data = original_bootstrap(self)
        data["suggestions"] = _filter_suggestions(data.get("suggestions", []))
        data["unit_converter"] = {
            "categories": _unit_payload(),
            "state": deepcopy(self._unit_converter_state),
            "calculator_handoff": deepcopy(self._calculator_handoff),
        }
        return data

    def suggestions(self: Any, query: str = "") -> list[dict[str, Any]]:
        return _filter_suggestions(original_suggestions(self, query))

    def commit(self: Any, expression: str) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            evaluation = self._session.evaluate(expression, commit=True)
            response = evaluation.as_dict()
            if evaluation.ok and expression.strip():
                self._sequence += 1
                entry = app.make_history_entry(
                    evaluation, self._session.settings, self._sequence
                ).as_dict()
                self._history.insert(0, entry)
                self._history = self._history[: app.MAX_HISTORY]
                response["history_entry"] = entry

                plain = _plain_result(response)
                if plain:
                    self._calculator_handoff = {
                        "revision": int(self._calculator_handoff.get("revision", 0)) + 1,
                        "value": plain,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                response["calculator_handoff"] = deepcopy(self._calculator_handoff)
                self._storage.update(
                    {
                        "engine_state": self._session.export_state(),
                        "history": self._history[: app.MAX_HISTORY],
                        "calculator_handoff": self._calculator_handoff,
                    }
                )
            else:
                response["calculator_handoff"] = deepcopy(self._calculator_handoff)
            return response

    def units_bootstrap(self: Any) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            return {
                "categories": _unit_payload(),
                "state": deepcopy(self._unit_converter_state),
                "calculator_handoff": deepcopy(self._calculator_handoff),
            }

    def save_unit_converter_state(self: Any, state: dict[str, Any]) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            merged = dict(self._unit_converter_state)
            if isinstance(state, dict):
                merged.update(state)
            self._unit_converter_state = _sanitize_state(merged)
            self._storage.set("unit_converter_state", self._unit_converter_state)
            return deepcopy(self._unit_converter_state)

    def convert_units(
        self: Any,
        expression: str,
        category: str,
        from_unit: str,
        to_unit: str,
        commit: bool = False,
        imported_revision: int | None = None,
    ) -> dict[str, Any]:
        _ensure_state(self)
        with self._lock:
            category_id = str(category)
            if category_id not in _CATEGORY_BY_ID:
                return {"ok": False, "error": "Выберите категорию величины"}
            symbols = _category_symbols(category_id)
            source_symbol = str(from_unit)
            target_symbol = str(to_unit)
            if source_symbol not in symbols or target_symbol not in symbols:
                return {"ok": False, "error": "Единица не относится к выбранной категории"}
            try:
                source_value = evaluate_simple(expression)
                source = core.UNIT_DEFS[source_symbol.lower()]
                target = core.UNIT_DEFS[target_symbol.lower()]
                base_value = source.to_base(source_value)
                converted = target.from_base(base_value)
                precision = self._session.settings.precision
                source_text = _format_number(source_value, precision)
                result_text = _format_number(converted, precision)
            except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
                return {"ok": False, "error": str(exc) or "Ошибка преобразования"}

            response = {
                "ok": True,
                "expression": str(expression),
                "source_value": source_text,
                "result": result_text,
                "from_unit": source_symbol,
                "to_unit": target_symbol,
                "category": category_id,
            }
            if commit:
                merged = {
                    "category": category_id,
                    "from_unit": source_symbol,
                    "to_unit": target_symbol,
                    "expression": source_text,
                    "imported_revision": (
                        imported_revision
                        if imported_revision is not None
                        else self._unit_converter_state.get("imported_revision", 0)
                    ),
                }
                self._unit_converter_state = _sanitize_state(merged)
                self._storage.set("unit_converter_state", self._unit_converter_state)
                response["state"] = deepcopy(self._unit_converter_state)
            return response

    app.AppApi.bootstrap = bootstrap
    app.AppApi.suggestions = suggestions
    app.AppApi.commit = commit
    app.AppApi.units_bootstrap = units_bootstrap
    app.AppApi.save_unit_converter_state = save_unit_converter_state
    app.AppApi.convert_units = convert_units
    _ensure_state(app._api)

    def build_html() -> str:
        html = original_build_html()
        renderer = Path(app.RENDERER_DIR)
        units_css = (renderer / "units-mode.css").read_text(encoding="utf-8")
        units_js = (renderer / "units-mode.js").read_text(encoding="utf-8")

        html = html.replace("</style>", f"\n{units_css}\n</style>", 1)
        html = html.replace(
            "</header>",
            "</header>\n"
            '<nav class="app-mode-tabs" aria-label="Режим приложения">\n'
            '  <button class="app-mode-tab active" id="calculatorModeTab" type="button">Калькулятор</button>\n'
            '  <button class="app-mode-tab" id="unitsModeTab" type="button">Единицы</button>\n'
            "</nav>",
            1,
        )
        textarea = (
            '<textarea id="expressionInput" class="expression-input" rows="2" '
            'spellcheck="false" autocomplete="off" autocapitalize="off" '
            'placeholder="Например: (120 + 30) / 5" aria-label="Введите выражение"></textarea>'
        )
        shell = (
            '<div class="expression-field-shell">\n'
            f"  {textarea}\n"
            '  <span class="field-unit-badge hidden" id="sourceUnitBadge"></span>\n'
            "</div>"
        )
        html = re.sub(
            r'<textarea id="expressionInput"[^>]*></textarea>',
            shell,
            html,
            count=1,
        )
        html = html.replace(
            '<div class="result-actions">',
            '<span class="result-unit-badge hidden" id="targetUnitBadge"></span>\n'
            '<div class="result-actions">',
            1,
        )
        converter_panel = """
      <section class="history-card unit-converter-card hidden" id="unitConverterCard" aria-label="Преобразование единиц">
        <div class="section-header unit-converter-header">
          <div>
            <h2>Единицы</h2>
            <span class="converter-caption">простая арифметика</span>
          </div>
          <select class="converter-select category-select" id="unitCategory" aria-label="Категория величины"></select>
        </div>
        <div class="unit-converter-content">
          <div class="unit-route">
            <label class="unit-picker-card">
              <span>Исходная единица</span>
              <select class="converter-select" id="sourceUnitSelect"></select>
            </label>
            <button class="swap-units-button" id="swapUnitsButton" type="button" title="Поменять единицы местами" aria-label="Поменять единицы местами">⇄</button>
            <label class="unit-picker-card">
              <span>Целевая единица</span>
              <select class="converter-select" id="targetUnitSelect"></select>
            </label>
          </div>
          <p class="converter-help">Введите число или выражение с операциями + − × ÷ и скобками. Enter упрощает исходное выражение.</p>
        </div>
      </section>
"""
        html = html.replace("    </main>", f"{converter_panel}    </main>", 1)
        html = html.replace("Функции и единицы (Ctrl+K)", "Функции (Ctrl+K)")

        # Insert before the existing renderer layers. The unit-mode capture handler
        # then runs first and can isolate converter input from calculator listeners.
        main_script_marker = "<script>\n(function () {\n  'use strict';"
        html = html.replace(
            main_script_marker,
            f"<script>\n{units_js}\n</script>\n{main_script_marker}",
            1,
        )
        return html

    app.build_html = build_html
