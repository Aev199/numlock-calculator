"""Lightweight persistent user-defined functions for the calculator line.

Definitions deliberately mirror variable assignments::

    c(d) := pi*d^2/4
    rect(a, b) = a*b

The function body is evaluated by NumCalc's existing safe AST engine. No Python
``eval`` or separate expression language is introduced.
"""

from __future__ import annotations

import ast
import re
from copy import deepcopy
from typing import Any

import calc_engine as core
import calc_engine_runtime as runtime


MAX_USER_FUNCTIONS = 100
MAX_PARAMETERS = 16
MAX_EXPRESSION = 1600
MAX_CALL_DEPTH = 16
_NAME_PATTERN = r"[A-Za-zА-Яа-я_][\wА-Яа-я]*"
_NAME_RE = re.compile(rf"^{_NAME_PATTERN}$")
_DEFINITION_RE = re.compile(
    rf"^\s*(?P<name>{_NAME_PATTERN})\s*\((?P<parameters>[^()]*)\)\s*"
    r"(?::=|=(?!=))\s*(?P<expression>.+?)\s*$",
    flags=re.DOTALL,
)


def _reserved_function_names() -> set[str]:
    return {
        *(name.lower() for name in core.FUNCTION_NAMES),
        *(name.lower() for name in core.UNIT_DEFS),
        "pi",
        "e",
        "tau",
        "ans",
    }


def _parse_parameters(value: str) -> tuple[list[str] | None, str | None]:
    text = str(value or "").strip()
    if not text:
        return [], None
    # Semicolon is an explicit separator when decimal commas are also used.
    raw_items = text.replace(";", ",").split(",")
    if len(raw_items) > MAX_PARAMETERS:
        return None, f"Допустимо не более {MAX_PARAMETERS} параметров"
    parameters: list[str] = []
    seen: set[str] = set()
    for raw in raw_items:
        name = raw.strip()
        if not _NAME_RE.fullmatch(name):
            return None, f"Некорректное имя параметра: {name or 'пусто'}"
        lowered = name.lower()
        if lowered in {"pi", "e", "tau", "ans"}:
            return None, f"Имя параметра зарезервировано: {name}"
        if lowered in seen:
            return None, f"Параметр повторяется: {name}"
        seen.add(lowered)
        parameters.append(lowered)
    return parameters, None


def _validate_body(expression: str) -> str | None:
    body = str(expression or "").strip()
    if not body:
        return "Введите выражение функции"
    if len(body) > MAX_EXPRESSION:
        return f"Выражение функции длиннее {MAX_EXPRESSION} символов"
    try:
        ast.parse(core.prepare_for_ast(body), mode="eval")
    except (SyntaxError, core.CalculationError, ValueError) as exc:
        message = getattr(exc, "message", None) or str(exc) or "Некорректное выражение"
        return f"Некорректное выражение функции: {message}"
    return None


def _definition_from_parts(
    name: Any,
    parameters: Any,
    expression: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    function_name = str(name or "").strip()
    if not _NAME_RE.fullmatch(function_name):
        return None, f"Некорректное имя функции: {function_name or 'пусто'}"
    key = function_name.lower()
    if key in _reserved_function_names():
        return None, f"Имя функции зарезервировано: {function_name}"

    if isinstance(parameters, str):
        parsed_parameters, error = _parse_parameters(parameters)
    elif isinstance(parameters, (list, tuple)):
        parsed_parameters, error = _parse_parameters(",".join(str(item) for item in parameters))
    else:
        return None, "Параметры функции должны быть списком имён"
    if error:
        return None, error
    assert parsed_parameters is not None

    body = str(expression or "").strip()
    error = _validate_body(body)
    if error:
        return None, error
    return {
        "name": key,
        "parameters": parsed_parameters,
        "expression": body,
    }, None


def _parse_definition(expression: Any) -> tuple[dict[str, Any] | None, str | None, bool]:
    match = _DEFINITION_RE.fullmatch(str(expression or ""))
    if match is None:
        return None, None, False
    definition, error = _definition_from_parts(
        match.group("name"),
        match.group("parameters"),
        match.group("expression"),
    )
    return definition, error, True


def _public_functions(session: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key, definition in sorted(getattr(session, "user_functions", {}).items()):
        parameters = list(definition.get("parameters", []))
        name = str(definition.get("name", key) or key)
        result[key] = {
            "name": name,
            "parameters": parameters,
            "expression": str(definition.get("expression", "")),
            "signature": f"{name}({', '.join(parameters)})",
        }
    return result


def _load_functions(session: Any, value: Any) -> None:
    session.user_functions = {}
    if not isinstance(value, dict):
        return
    for raw_name, raw_definition in list(value.items())[:MAX_USER_FUNCTIONS]:
        if not isinstance(raw_definition, dict):
            continue
        definition, error = _definition_from_parts(
            raw_definition.get("name", raw_name),
            raw_definition.get("parameters", []),
            raw_definition.get("expression", ""),
        )
        if definition is not None and error is None:
            session.user_functions[definition["name"]] = definition


def _matching_paren(text: str, opening: int) -> int | None:
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _top_level_separators(text: str, start: int, end: int) -> tuple[list[int], list[int]]:
    commas: list[int] = []
    semicolons: list[int] = []
    depth = 0
    for index in range(start, end):
        char = text[index]
        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        elif depth == 0 and char == ",":
            commas.append(index)
        elif depth == 0 and char == ";":
            semicolons.append(index)
    return commas, semicolons


def _protect_user_function_separators(session: Any, expression: Any) -> str:
    """Disambiguate argument separators from decimal commas by known arity.

    ``r(2,3)`` is two arguments when ``r`` has two parameters; ``c(2,5)``
    remains decimal 2.5 when ``c`` has one. Semicolon is accepted explicitly,
    so ``r(2,5;3,5)`` means two decimal-comma arguments.
    """

    text = str(expression or "")
    definitions = getattr(session, "user_functions", {})
    if not text or not definitions:
        return text

    comma_positions: set[int] = set()
    semicolon_positions: set[int] = set()
    for match in re.finditer(_NAME_PATTERN, text):
        definition = definitions.get(match.group(0).lower())
        if definition is None:
            continue
        cursor = match.end()
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor >= len(text) or text[cursor] != "(":
            continue
        closing = _matching_paren(text, cursor)
        if closing is None:
            continue
        expected = max(0, len(definition.get("parameters", [])) - 1)
        if expected == 0:
            continue
        commas, semicolons = _top_level_separators(text, cursor + 1, closing)
        if len(semicolons) == expected:
            semicolon_positions.update(semicolons)
        elif not semicolons and len(commas) == expected:
            comma_positions.update(commas)

    if not comma_positions and not semicolon_positions:
        return text
    pieces: list[str] = []
    for index, char in enumerate(text):
        if index in semicolon_positions or index in comma_positions:
            pieces.append(", ")
        else:
            pieces.append(char)
    return "".join(pieces)


def install(app: Any) -> None:
    """Install quick user functions into the calculator session and AppApi."""

    if getattr(app, "_user_functions_installed", False):
        return
    app._user_functions_installed = True

    session_cls = app.CalculatorSession
    original_session_init = session_cls.__init__
    original_call_function = session_cls.call_function
    original_evaluate = session_cls.evaluate
    original_export_state = session_cls.export_state
    original_suggestions = session_cls.suggestions

    def session_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_session_init(self, *args, **kwargs)
        self.user_functions: dict[str, dict[str, Any]] = {}
        self._user_function_stack: list[str] = []

    def call_function(self: Any, name: str, args: list[Any]) -> Any:
        key = str(name or "").lower()
        definition = self.user_functions.get(key)
        if definition is None:
            return original_call_function(self, name, args)

        parameters = list(definition.get("parameters", []))
        if len(args) != len(parameters):
            raise core.CalculationError(
                f"Функция {key} ожидает аргументов: {len(parameters)}"
            )
        if key in self._user_function_stack or len(self._user_function_stack) >= MAX_CALL_DEPTH:
            raise core.CalculationError(f"Рекурсивный вызов функции: {key}")

        values = [core._as_quantity(value) for value in args]
        previous: dict[str, Any] = {}
        missing: set[str] = set()
        for parameter, value in zip(parameters, values, strict=True):
            if parameter in self.variables:
                previous[parameter] = self.variables[parameter]
            else:
                missing.add(parameter)
            self.variables[parameter] = value

        self._user_function_stack.append(key)
        try:
            body = _protect_user_function_separators(
                self,
                definition.get("expression", ""),
            )
            return self._evaluate_source(body)
        finally:
            self._user_function_stack.pop()
            for parameter in parameters:
                if parameter in previous:
                    self.variables[parameter] = previous[parameter]
                elif parameter in missing:
                    self.variables.pop(parameter, None)

    def evaluate(self: Any, expression: str, *, commit: bool = False) -> runtime.Evaluation:
        original = str(expression or "")
        definition, error, matched = _parse_definition(original)
        if matched:
            normalized = core.normalize_expression(original)
            if error:
                return runtime.Evaluation(
                    expression=original,
                    normalized=normalized,
                    ok=False,
                    error=error,
                )
            assert definition is not None
            key = definition["name"]
            if commit and key not in self.user_functions and len(self.user_functions) >= MAX_USER_FUNCTIONS:
                return runtime.Evaluation(
                    expression=original,
                    normalized=normalized,
                    ok=False,
                    error=f"Допустимо не более {MAX_USER_FUNCTIONS} пользовательских функций",
                )
            if commit:
                self.user_functions[key] = deepcopy(definition)
            signature = f"{key}({', '.join(definition['parameters'])})"
            return runtime.Evaluation(
                expression=original,
                normalized=normalized,
                result=f"{signature} := {definition['expression']}",
            )

        prepared = _protect_user_function_separators(self, original)
        result = original_evaluate(self, prepared, commit=commit)
        result.expression = original
        return result

    def export_state(self: Any) -> dict[str, Any]:
        state = original_export_state(self)
        state["user_functions"] = deepcopy(self.user_functions)
        return state

    def suggestions(self: Any, query: str = "") -> list[dict[str, Any]]:
        needle = str(query or "").strip().lower()
        custom: list[dict[str, Any]] = []
        for key, definition in sorted(self.user_functions.items()):
            parameters = list(definition.get("parameters", []))
            signature = f"{key}({', '.join(parameters)})"
            body = str(definition.get("expression", ""))
            if needle and not any(
                needle in value.lower()
                for value in (key, signature, body, "Пользовательские функции")
            ):
                continue
            custom.append(
                {
                    "kind": "function",
                    "group": "Пользовательские функции",
                    "label": key,
                    "insert": f"{key}()",
                    "description": f"{signature} = {body}",
                    "user_function": True,
                }
            )
        return (custom + list(original_suggestions(self, query)))[:120]

    session_cls.__init__ = session_init
    session_cls.call_function = call_function
    session_cls.evaluate = evaluate
    session_cls.export_state = export_state
    session_cls.suggestions = suggestions
    session_cls.load_user_functions = _load_functions

    original_api_init = app.AppApi.__init__
    original_bootstrap = app.AppApi.bootstrap

    def api_init(self: Any, storage: Any) -> None:
        original_api_init(self, storage)
        state = storage.get("engine_state", {})
        raw_functions = state.get("user_functions", {}) if isinstance(state, dict) else {}
        _load_functions(self._session, raw_functions)

    def bootstrap(self: Any) -> dict[str, Any]:
        data = original_bootstrap(self)
        data["user_functions"] = _public_functions(self._session)
        data["suggestions"] = self._session.suggestions()
        return data

    def delete_user_function(self: Any, name: str) -> dict[str, Any]:
        key = str(name or "").strip().lower()
        with self._lock:
            if not key or key not in self._session.user_functions:
                return {"ok": False, "error": "Пользовательская функция не найдена"}
            del self._session.user_functions[key]
            self._persist()
            return {
                "ok": True,
                "deleted": key,
                "user_functions": _public_functions(self._session),
                "suggestions": self._session.suggestions(),
            }

    app.AppApi.__init__ = api_init
    app.AppApi.bootstrap = bootstrap
    app.AppApi.delete_user_function = delete_user_function
