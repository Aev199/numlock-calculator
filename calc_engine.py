"""Safe keyboard-first calculation engine for NumLock Calc.

The engine intentionally uses Python's AST only as a parser. It never calls
``eval`` and only supports an explicit allow-list of operations, functions,
variables, constants and units.
"""

from __future__ import annotations

import ast
import math
import operator
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from typing import Any, Callable, Iterable


class CalculationError(ValueError):
    """User-facing expression error."""

    def __init__(self, message: str, position: int | None = None):
        super().__init__(message)
        self.message = message
        self.position = position


Dim = tuple[Fraction, Fraction, Fraction, Fraction]
DIMENSIONLESS: Dim = (Fraction(0),) * 4
LENGTH: Dim = (Fraction(1), Fraction(0), Fraction(0), Fraction(0))
MASS: Dim = (Fraction(0), Fraction(1), Fraction(0), Fraction(0))
TIME: Dim = (Fraction(0), Fraction(0), Fraction(1), Fraction(0))
TEMPERATURE: Dim = (Fraction(0), Fraction(0), Fraction(0), Fraction(1))
FORCE: Dim = (Fraction(1), Fraction(1), Fraction(-2), Fraction(0))
PRESSURE: Dim = (Fraction(-1), Fraction(1), Fraction(-2), Fraction(0))


def _dim_add(a: Dim, b: Dim) -> Dim:
    return tuple(x + y for x, y in zip(a, b, strict=True))  # type: ignore[return-value]


def _dim_sub(a: Dim, b: Dim) -> Dim:
    return tuple(x - y for x, y in zip(a, b, strict=True))  # type: ignore[return-value]


def _dim_mul(a: Dim, factor: Fraction) -> Dim:
    return tuple(x * factor for x in a)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class UnitDef:
    symbol: str
    scale: float
    dimensions: Dim
    offset: float = 0.0

    def quantity(self) -> "Quantity":
        if self.offset:
            raise CalculationError(
                f"Температурную единицу {self.symbol} используйте только с преобразованием 'to'"
            )
        return Quantity(self.scale, self.dimensions, self.symbol)

    def to_base(self, value: float) -> float:
        return (value + self.offset) * self.scale

    def from_base(self, value: float) -> float:
        return value / self.scale - self.offset


@dataclass(frozen=True, slots=True)
class Quantity:
    value: float
    dimensions: Dim = DIMENSIONLESS
    display_unit: str | None = None

    @property
    def dimensionless(self) -> bool:
        return self.dimensions == DIMENSIONLESS

    def _coerce(self, other: Any) -> "Quantity":
        if isinstance(other, Quantity):
            return other
        if isinstance(other, (int, float)) and not isinstance(other, bool):
            return Quantity(float(other))
        raise CalculationError("Недопустимый тип значения")

    def __add__(self, other: Any) -> "Quantity":
        rhs = self._coerce(other)
        if self.dimensions != rhs.dimensions:
            raise CalculationError("Нельзя складывать величины разных размерностей")
        return Quantity(self.value + rhs.value, self.dimensions, self.display_unit or rhs.display_unit)

    __radd__ = __add__

    def __sub__(self, other: Any) -> "Quantity":
        rhs = self._coerce(other)
        if self.dimensions != rhs.dimensions:
            raise CalculationError("Нельзя вычитать величины разных размерностей")
        return Quantity(self.value - rhs.value, self.dimensions, self.display_unit or rhs.display_unit)

    def __rsub__(self, other: Any) -> "Quantity":
        return self._coerce(other).__sub__(self)

    def __mul__(self, other: Any) -> "Quantity":
        rhs = self._coerce(other)
        return Quantity(self.value * rhs.value, _dim_add(self.dimensions, rhs.dimensions))

    __rmul__ = __mul__

    def __truediv__(self, other: Any) -> "Quantity":
        rhs = self._coerce(other)
        if rhs.value == 0:
            raise CalculationError("Деление на ноль")
        return Quantity(self.value / rhs.value, _dim_sub(self.dimensions, rhs.dimensions))

    def __rtruediv__(self, other: Any) -> "Quantity":
        return self._coerce(other).__truediv__(self)

    def __pow__(self, other: Any) -> "Quantity":
        exponent = self._coerce(other)
        if not exponent.dimensionless:
            raise CalculationError("Показатель степени должен быть безразмерным")
        value = exponent.value
        if not math.isfinite(value):
            raise CalculationError("Некорректный показатель степени")
        fraction = Fraction(value).limit_denominator(64)
        result = self.value**value
        if isinstance(result, complex) or not math.isfinite(float(result)):
            raise CalculationError("Результат степени не является действительным числом")
        return Quantity(float(result), _dim_mul(self.dimensions, fraction))

    def __neg__(self) -> "Quantity":
        return Quantity(-self.value, self.dimensions, self.display_unit)

    def __pos__(self) -> "Quantity":
        return self

    def __abs__(self) -> "Quantity":
        return Quantity(abs(self.value), self.dimensions, self.display_unit)

    def _compare(self, other: Any, fn: Callable[[float, float], bool]) -> bool:
        rhs = self._coerce(other)
        if self.dimensions != rhs.dimensions:
            raise CalculationError("Нельзя сравнивать величины разных размерностей")
        return fn(self.value, rhs.value)


@dataclass(slots=True)
class EngineSettings:
    angle_mode: str = "DEG"
    number_base: str = "DEC"
    precision: int = 12

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "EngineSettings":
        data = data or {}
        angle = str(data.get("angle_mode", "DEG")).upper()
        base = str(data.get("number_base", "DEC")).upper()
        precision = int(data.get("precision", 12))
        return cls(
            angle_mode=angle if angle in {"DEG", "RAD", "GRAD"} else "DEG",
            number_base=base if base in {"DEC", "HEX", "OCT", "BIN"} else "DEC",
            precision=max(3, min(17, precision)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "angle_mode": self.angle_mode,
            "number_base": self.number_base,
            "precision": self.precision,
        }


@dataclass(slots=True)
class Evaluation:
    expression: str
    normalized: str
    result: str = ""
    raw_value: float | None = None
    unit: str | None = None
    ok: bool = True
    error: str | None = None
    position: int | None = None
    assigned_variable: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "expression": self.expression,
            "normalized": self.normalized,
            "result": self.result,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "ok": self.ok,
            "error": self.error,
            "position": self.position,
            "assigned_variable": self.assigned_variable,
        }


@dataclass(slots=True)
class HistoryEntry:
    id: str
    expression: str
    result: str
    raw_value: float | None
    unit: str | None
    angle_mode: str
    number_base: str
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "expression": self.expression,
            "result": self.result,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "angle_mode": self.angle_mode,
            "number_base": self.number_base,
            "created_at": self.created_at,
        }


UNIT_DEFS: dict[str, UnitDef] = {}


def _register_unit(
    symbol: str,
    scale: float,
    dimensions: Dim,
    *aliases: str,
    offset: float = 0.0,
) -> None:
    unit = UnitDef(symbol=symbol, scale=scale, dimensions=dimensions, offset=offset)
    for name in (symbol, *aliases):
        UNIT_DEFS[name.lower()] = unit


_register_unit("m", 1.0, LENGTH, "meter", "metre", "м")
_register_unit("km", 1000.0, LENGTH, "км")
_register_unit("cm", 0.01, LENGTH, "см")
_register_unit("mm", 0.001, LENGTH, "мм")
_register_unit("in", 0.0254, LENGTH, "inch", "дюйм")
_register_unit("ft", 0.3048, LENGTH, "foot", "фут")
_register_unit("mi", 1609.344, LENGTH, "mile", "миля")
_register_unit("m2", 1.0, _dim_mul(LENGTH, Fraction(2)), "m^2", "м2", "м²")
_register_unit("km2", 1e6, _dim_mul(LENGTH, Fraction(2)), "km^2", "км2", "км²")
_register_unit("cm2", 1e-4, _dim_mul(LENGTH, Fraction(2)), "cm^2", "см2", "см²")
_register_unit("mm2", 1e-6, _dim_mul(LENGTH, Fraction(2)), "mm^2", "мм2", "мм²")
_register_unit("ha", 10000.0, _dim_mul(LENGTH, Fraction(2)), "гa", "га")
_register_unit("in2", 0.00064516, _dim_mul(LENGTH, Fraction(2)), "in^2")
_register_unit("ft2", 0.09290304, _dim_mul(LENGTH, Fraction(2)), "ft^2")
_register_unit("m3", 1.0, _dim_mul(LENGTH, Fraction(3)), "m^3", "м3", "м³")
_register_unit("L", 0.001, _dim_mul(LENGTH, Fraction(3)), "l", "liter", "litre", "л")
_register_unit("mL", 1e-6, _dim_mul(LENGTH, Fraction(3)), "ml", "мл")
_register_unit("cm3", 1e-6, _dim_mul(LENGTH, Fraction(3)), "cm^3", "см3", "см³")
_register_unit("gal", 0.003785411784, _dim_mul(LENGTH, Fraction(3)), "gallon")
_register_unit("ft3", 0.028316846592, _dim_mul(LENGTH, Fraction(3)), "ft^3")
_register_unit("kg", 1.0, MASS, "кг")
_register_unit("g", 0.001, MASS, "г")
_register_unit("t", 1000.0, MASS, "tonne", "т")
_register_unit("lb", 0.45359237, MASS, "pound", "фунт")
_register_unit("oz", 0.028349523125, MASS, "ounce", "унция")
_register_unit("s", 1.0, TIME, "sec", "second", "с")
_register_unit("min", 60.0, TIME, "minute", "мин")
_register_unit("h", 3600.0, TIME, "hr", "hour", "ч")
_register_unit("N", 1.0, FORCE, "newton", "н")
_register_unit("kN", 1000.0, FORCE, "кн")
_register_unit("kgf", 9.80665, FORCE, "кгс")
_register_unit("lbf", 4.4482216152605, FORCE)
_register_unit("Pa", 1.0, PRESSURE, "па")
_register_unit("kPa", 1000.0, PRESSURE, "кпа")
_register_unit("MPa", 1e6, PRESSURE, "мпа")
_register_unit("GPa", 1e9, PRESSURE, "гпа")
_register_unit("bar", 1e5, PRESSURE, "бар")
_register_unit("atm", 101325.0, PRESSURE, "атм")
_register_unit("mmHg", 133.3223684211, PRESSURE, "ммртст", "мм_рт_ст")
_register_unit("psi", 6894.757293168, PRESSURE)
_register_unit("K", 1.0, TEMPERATURE, "kelvin", "к")
_register_unit("degC", 1.0, TEMPERATURE, "celsius", "°c", offset=273.15)
_register_unit("degF", 5 / 9, TEMPERATURE, "fahrenheit", "°f", offset=459.67)
_register_unit("rad", 1.0, DIMENSIONLESS, "radian", "рад")
_register_unit("deg", math.pi / 180.0, DIMENSIONLESS, "degree", "град")
_register_unit("grad", math.pi / 200.0, DIMENSIONLESS, "gon", "градус")

CANONICAL_UNITS: dict[Dim, str] = {
    LENGTH: "m",
    _dim_mul(LENGTH, Fraction(2)): "m2",
    _dim_mul(LENGTH, Fraction(3)): "m3",
    MASS: "kg",
    TIME: "s",
    FORCE: "N",
    PRESSURE: "Pa",
    TEMPERATURE: "K",
}

FUNCTION_NAMES = (
    "sin", "cos", "tan", "asin", "acos", "atan", "sqrt", "cbrt", "ln",
    "log", "log10", "exp", "abs", "floor", "ceil", "round", "fact",
    "factorial", "min", "max", "mean", "sum",
)


def normalize_expression(expression: str) -> str:
    value = str(expression or "")
    value = value.replace("\u00a0", " ")
    value = value.replace("×", "*").replace("·", "*").replace("÷", "/")
    value = value.replace("−", "-").replace("–", "-").replace("—", "-")
    value = value.replace("²", "2").replace("³", "3")
    value = re.sub(r"(?<=\d),(?=\d)", ".", value)
    value = value.replace("^", "**")
    value = re.sub(r"\bм\s*рт\.?\s*ст\.?\b", "mmHg", value, flags=re.IGNORECASE)
    return value.strip()


def _split_conversion(expression: str) -> tuple[str, str | None]:
    depth = 0
    lowered = expression.lower()
    for index, char in enumerate(expression):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and lowered.startswith(" to ", index):
            return expression[:index].strip(), expression[index + 4 :].strip()
    return expression, None


def _split_assignment(expression: str) -> tuple[str | None, str]:
    match = re.match(r"^\s*([A-Za-zА-Яа-я_][\wА-Яа-я]*)\s*(?::=|=(?!=))\s*(.+)$", expression)
    if not match:
        return None, expression
    return match.group(1), match.group(2)


def _rewrite_postfix_factorials(expression: str) -> str:
    text = expression
    while "!" in text:
        index = text.find("!")
        if index == 0:
            raise CalculationError("Перед ! ожидается значение", index)
        end = index
        cursor = index - 1
        if text[cursor] == ")":
            depth = 1
            cursor -= 1
            while cursor >= 0 and depth:
                if text[cursor] == ")":
                    depth += 1
                elif text[cursor] == "(":
                    depth -= 1
                cursor -= 1
            if depth:
                raise CalculationError("Несогласованные скобки", index)
            start = cursor + 1
            while start > 0 and (text[start - 1].isalnum() or text[start - 1] in "_⁻¹"):
                start -= 1
        else:
            while cursor >= 0 and (text[cursor].isalnum() or text[cursor] in "._"):
                cursor -= 1
            start = cursor + 1
        operand = text[start:end]
        if not operand:
            raise CalculationError("Перед ! ожидается значение", index)
        text = f"{text[:start]}factorial({operand}){text[index + 1:]}"
    return text


def _insert_implicit_multiplication(expression: str) -> str:
    expression = re.sub(
        r"/\s*((?:\d+(?:\.\d*)?|\.\d+))\s+([A-Za-zА-Яа-я_][\wА-Яа-я]*)",
        r"/(\1*\2)",
        expression,
    )
    expression = re.sub(r"(?<=[\d)])\s+(?=[A-Za-zА-Яа-я_π])", "*", expression)
    expression = re.sub(r"(?<=[A-Za-zА-Яа-я_π])\s+(?=\d)", "*", expression)
    expression = re.sub(r"(?<=\))\s*(?=\()", "*", expression)
    expression = re.sub(r"(?<=\d)\s*(?=\()", "*", expression)
    expression = re.sub(r"(?<=\))\s*(?=[A-Za-zА-Яа-я_π])", "*", expression)
    expression = re.sub(r"(?<=\d)(?=[A-DF-Za-df-zА-Яа-я_π])", "*", expression)
    expression = re.sub(r"(?<=\d)(?=pi\b|tau\b|π)", "*", expression, flags=re.IGNORECASE)
    return expression


def prepare_for_ast(expression: str) -> str:
    return _insert_implicit_multiplication(_rewrite_postfix_factorials(normalize_expression(expression)))


class SafeAstEvaluator(ast.NodeVisitor):
    _binary_ops: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv,
    }
    _comparisons: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }

    def __init__(self, session: "CalculatorSession"):
        self.session = session

    def evaluate(self, expression: str) -> Any:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise CalculationError(exc.msg or "Некорректное выражение", (exc.offset - 1) if exc.offset else None) from exc
        return self.visit(tree.body)

    def generic_visit(self, node: ast.AST) -> Any:
        raise CalculationError(f"Конструкция {type(node).__name__} не поддерживается")

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, bool):
            return node.value
        if isinstance(node.value, (int, float)):
            return Quantity(float(node.value))
        raise CalculationError("Допустимы только числа")

    def visit_Name(self, node: ast.Name) -> Any:
        name = node.id
        lowered = name.lower()
        if lowered == "pi" or name == "π":
            return Quantity(math.pi)
        if lowered == "e":
            return Quantity(math.e)
        if lowered == "tau":
            return Quantity(math.tau)
        if lowered == "ans":
            return self.session.ans
        if lowered in self.session.variables:
            return self.session.variables[lowered]
        if lowered in UNIT_DEFS:
            return UNIT_DEFS[lowered].quantity()
        raise CalculationError(f"Неизвестное имя: {name}", getattr(node, "col_offset", None))

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        fn = self._binary_ops.get(type(node.op))
        if not fn:
            raise CalculationError("Операция не поддерживается")
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, (ast.Mod, ast.FloorDiv)):
            left_q = _as_quantity(left)
            right_q = _as_quantity(right)
            if not left_q.dimensionless or not right_q.dimensionless:
                raise CalculationError("Операция допустима только для безразмерных чисел")
            if right_q.value == 0:
                raise CalculationError("Деление на ноль")
            return Quantity(float(fn(left_q.value, right_q.value)))
        try:
            return fn(left, right)
        except ZeroDivisionError as exc:
            raise CalculationError("Деление на ноль") from exc
        except OverflowError as exc:
            raise CalculationError("Число слишком велико") from exc

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        value = self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            return -_as_quantity(value)
        if isinstance(node.op, ast.UAdd):
            return +_as_quantity(value)
        if isinstance(node.op, ast.Not):
            return not _truthy(value)
        raise CalculationError("Унарная операция не поддерживается")

    def visit_BoolOp(self, node: ast.BoolOp) -> bool:
        values = [_truthy(self.visit(item)) for item in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise CalculationError("Логическая операция не поддерживается")

    def visit_Compare(self, node: ast.Compare) -> bool:
        left = self.visit(node.left)
        for op_node, comparator in zip(node.ops, node.comparators, strict=True):
            right = self.visit(comparator)
            fn = self._comparisons.get(type(op_node))
            if not fn:
                raise CalculationError("Сравнение не поддерживается")
            if not _as_quantity(left)._compare(_as_quantity(right), fn):
                return False
            left = right
        return True

    def visit_IfExp(self, node: ast.IfExp) -> Any:
        return self.visit(node.body if _truthy(self.visit(node.test)) else node.orelse)

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise CalculationError("Разрешены только вызовы функций по имени")
        if node.keywords:
            raise CalculationError("Именованные аргументы не поддерживаются")
        return self.session.call_function(node.func.id.lower(), [self.visit(arg) for arg in node.args])

    def visit_List(self, node: ast.List) -> list[Any]:
        return [self.visit(item) for item in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> tuple[Any, ...]:
        return tuple(self.visit(item) for item in node.elts)


def _as_quantity(value: Any) -> Quantity:
    if isinstance(value, Quantity):
        return value
    if isinstance(value, bool):
        return Quantity(float(value))
    if isinstance(value, (int, float)):
        return Quantity(float(value))
    raise CalculationError("Ожидалось число")


def _truthy(value: Any) -> bool:
    quantity = _as_quantity(value)
    if not quantity.dimensionless:
        raise CalculationError("Логическое условие должно быть безразмерным")
    return bool(quantity.value)


def _flatten_quantities(args: Iterable[Any]) -> list[Quantity]:
    result: list[Quantity] = []
    for arg in args:
        if isinstance(arg, (list, tuple)):
            result.extend(_flatten_quantities(arg))
        else:
            result.append(_as_quantity(arg))
    return result


class CalculatorSession:
    """Stateful calculator session with variables, memories and formatting."""

    def __init__(self, settings: EngineSettings | None = None, variables: dict[str, Any] | None = None, memories: list[Any] | None = None):
        self.settings = settings or EngineSettings()
        self.variables: dict[str, Quantity] = {}
        for key, value in (variables or {}).items():
            restored = self.deserialize_quantity(value)
            if restored is not None:
                self.variables[str(key).lower()] = restored
        self.memories: list[Quantity] = [Quantity(0.0) for _ in range(10)]
        for index, value in enumerate((memories or [])[:10]):
            restored = self.deserialize_quantity(value)
            if restored is not None:
                self.memories[index] = restored
        self.ans = Quantity(0.0)
        self._evaluator = SafeAstEvaluator(self)

    def set_settings(self, data: dict[str, Any]) -> EngineSettings:
        self.settings = EngineSettings.from_mapping(self.settings.as_dict() | data)
        return self.settings

    def _angle_to_radians(self, quantity: Quantity) -> float:
        if not quantity.dimensionless:
            raise CalculationError("Тригонометрическая функция ожидает угол")
        if self.settings.angle_mode == "DEG":
            return math.radians(quantity.value)
        if self.settings.angle_mode == "GRAD":
            return quantity.value * math.pi / 200.0
        return quantity.value

    def _radians_to_angle(self, value: float) -> Quantity:
        if self.settings.angle_mode == "DEG":
            value = math.degrees(value)
        elif self.settings.angle_mode == "GRAD":
            value = value * 200.0 / math.pi
        return Quantity(value)

    def call_function(self, name: str, args: list[Any]) -> Any:
        values = _flatten_quantities(args)

        def exactly(count: int) -> None:
            if len(values) != count:
                raise CalculationError(f"Функция {name} ожидает аргументов: {count}")

        if name in {"sin", "cos", "tan"}:
            exactly(1)
            return Quantity(getattr(math, name)(self._angle_to_radians(values[0])))
        if name in {"asin", "acos", "atan"}:
            exactly(1)
            if not values[0].dimensionless:
                raise CalculationError(f"Функция {name} ожидает безразмерное число")
            return self._radians_to_angle(getattr(math, name)(values[0].value))
        if name in {"sqrt", "cbrt"}:
            exactly(1)
            power = Fraction(1, 2) if name == "sqrt" else Fraction(1, 3)
            return values[0] ** Quantity(float(power))
        if name in {"ln", "log", "log10", "exp"}:
            exactly(1)
            if not values[0].dimensionless:
                raise CalculationError(f"Функция {name} ожидает безразмерное число")
            fn = math.log if name in {"ln", "log"} else math.log10 if name == "log10" else math.exp
            return Quantity(fn(values[0].value))
        if name in {"fact", "factorial"}:
            exactly(1)
            value = values[0]
            if not value.dimensionless or value.value < 0 or not value.value.is_integer() or value.value > 170:
                raise CalculationError("Факториал определён для целых чисел от 0 до 170")
            return Quantity(float(math.factorial(int(value.value))))
        if name == "abs":
            exactly(1)
            return abs(values[0])
        if name in {"floor", "ceil", "round"}:
            exactly(1)
            if not values[0].dimensionless:
                raise CalculationError(f"Функция {name} ожидает безразмерное число")
            fn = math.floor if name == "floor" else math.ceil if name == "ceil" else round
            return Quantity(float(fn(values[0].value)))
        if name in {"min", "max"}:
            if not values:
                raise CalculationError(f"Функция {name} ожидает хотя бы один аргумент")
            dims = values[0].dimensions
            if any(value.dimensions != dims for value in values):
                raise CalculationError("Все аргументы должны иметь одну размерность")
            return (min if name == "min" else max)(values, key=lambda item: item.value)
        if name in {"mean", "sum"}:
            if not values:
                raise CalculationError(f"Функция {name} ожидает хотя бы один аргумент")
            total = Quantity(0.0, values[0].dimensions)
            for value in values:
                total = total + value
            return total / len(values) if name == "mean" else total
        raise CalculationError(f"Неизвестная функция: {name}")

    def _evaluate_quantity(self, expression: str) -> Quantity:
        prepared = prepare_for_ast(expression)
        if not prepared:
            raise CalculationError("Введите выражение")
        return _as_quantity(self._evaluator.evaluate(prepared))

    def _evaluate_percent(self, expression: str) -> Quantity:
        source = expression[:-1].strip()
        if not source:
            raise CalculationError("Перед % ожидается значение")
        depth = 0
        split_at = -1
        split_op = ""
        prepared = normalize_expression(source)
        for index, char in enumerate(prepared):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif depth == 0 and char in "+-*/":
                previous = prepared[index - 1] if index else ""
                following = prepared[index + 1] if index + 1 < len(prepared) else ""
                if char == "*" and (previous == "*" or following == "*"):
                    continue
                if index == 0 or previous in "+-*/(eE":
                    continue
                split_at = index
                split_op = char
        if split_at < 0:
            return self._evaluate_quantity(source) / 100
        left = self._evaluate_quantity(prepared[:split_at])
        right = self._evaluate_quantity(prepared[split_at + 1 :]) / 100
        if split_op == "+":
            return left + left * right
        if split_op == "-":
            return left - left * right
        if split_op == "*":
            return left * right
        return left / right

    def _evaluate_source(self, expression: str) -> Quantity:
        stripped = expression.strip()
        if stripped.endswith("%"):
            return self._evaluate_percent(stripped)
        temperature = re.fullmatch(
            r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(degC|degF|°C|°F|celsius|fahrenheit)",
            stripped,
            flags=re.IGNORECASE,
        )
        if temperature:
            unit = UNIT_DEFS[temperature.group(2).lower()]
            return Quantity(unit.to_base(float(temperature.group(1))), TEMPERATURE)
        return self._evaluate_quantity(stripped)

    def _convert(self, quantity: Quantity, target: str) -> tuple[Quantity, str]:
        target_text = normalize_expression(target).strip()
        unit = UNIT_DEFS.get(target_text.lower())
        if unit:
            if quantity.dimensions != unit.dimensions:
                raise CalculationError(f"Нельзя преобразовать в {unit.symbol}: другая размерность")
            return Quantity(unit.from_base(quantity.value), DIMENSIONLESS, unit.symbol), unit.symbol
        target_quantity = self._evaluate_quantity(target_text)
        if target_quantity.value == 0:
            raise CalculationError("Некорректная целевая единица")
        if quantity.dimensions != target_quantity.dimensions:
            raise CalculationError("Целевая единица имеет другую размерность")
        return Quantity(quantity.value / target_quantity.value), target_text

    def evaluate(self, expression: str, *, commit: bool = False) -> Evaluation:
        original = str(expression or "")
        normalized = normalize_expression(original)
        try:
            variable, body = _split_assignment(normalized)
            source, target = _split_conversion(body)
            quantity = self._evaluate_source(source)
            unit_symbol = None
            output_quantity = quantity
            if target:
                output_quantity, unit_symbol = self._convert(quantity, target)
            if variable:
                lowered = variable.lower()
                if lowered in {"pi", "e", "tau", "ans"} or lowered in UNIT_DEFS:
                    raise CalculationError(f"Имя {variable} зарезервировано")
                self.variables[lowered] = quantity
            if commit:
                self.ans = quantity
            return Evaluation(
                expression=original,
                normalized=normalized,
                result=self.format_quantity(output_quantity, unit_symbol),
                raw_value=output_quantity.value,
                unit=unit_symbol,
                assigned_variable=variable,
            )
        except CalculationError as exc:
            return Evaluation(expression=original, normalized=normalized, ok=False, error=exc.message, position=exc.position)
        except (ArithmeticError, ValueError, TypeError) as exc:
            return Evaluation(expression=original, normalized=normalized, ok=False, error=str(exc) or "Ошибка вычисления")

    def format_quantity(self, quantity: Quantity, explicit_unit: str | None = None) -> str:
        value = quantity.value
        if not math.isfinite(value):
            raise CalculationError("Результат не является конечным числом")
        if explicit_unit is None and not quantity.dimensionless:
            explicit_unit = CANONICAL_UNITS.get(quantity.dimensions)
        if quantity.dimensionless and explicit_unit is None and self.settings.number_base != "DEC":
            rounded = round(value)
            if not math.isclose(value, rounded, rel_tol=0, abs_tol=1e-12):
                raise CalculationError("Системы счисления применимы только к целым числам")
            integer = int(rounded)
            if self.settings.number_base == "HEX":
                return f"-0x{abs(integer):X}" if integer < 0 else f"0x{integer:X}"
            if self.settings.number_base == "OCT":
                return f"-0o{abs(integer):o}" if integer < 0 else f"0o{integer:o}"
            return f"-0b{abs(integer):b}" if integer < 0 else f"0b{integer:b}"
        precision = self.settings.precision
        if value == 0:
            text = "0"
        elif abs(value) >= 10 ** max(precision, 6) or abs(value) < 10 ** (-max(precision - 2, 6)):
            text = f"{value:.{precision - 1}e}"
            mantissa, exponent = text.split("e")
            text = f"{mantissa.rstrip('0').rstrip('.')}e{int(exponent):+d}"
        else:
            text = f"{value:.{precision}g}"
        return f"{text} {explicit_unit}" if explicit_unit else text

    def serialize_quantity(self, value: Quantity) -> dict[str, Any]:
        return {
            "value": value.value,
            "dimensions": [f"{item.numerator}/{item.denominator}" for item in value.dimensions],
            "display_unit": value.display_unit,
        }

    @staticmethod
    def deserialize_quantity(value: Any) -> Quantity | None:
        if isinstance(value, (int, float)):
            return Quantity(float(value))
        if not isinstance(value, dict):
            return None
        try:
            dimensions = tuple(Fraction(item) for item in value.get("dimensions", []))
            if len(dimensions) != 4:
                dimensions = DIMENSIONLESS
            return Quantity(float(value["value"]), dimensions, value.get("display_unit"))  # type: ignore[arg-type]
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            return None

    def export_state(self) -> dict[str, Any]:
        return {
            "settings": self.settings.as_dict(),
            "variables": {key: self.serialize_quantity(value) for key, value in self.variables.items()},
            "memories": [self.serialize_quantity(value) for value in self.memories],
            "ans": self.serialize_quantity(self.ans),
        }

    def restore_ans(self, value: Any) -> None:
        restored = self.deserialize_quantity(value)
        if restored is not None:
            self.ans = restored

    def set_memory(self, slot: int, expression: str) -> Evaluation:
        if slot < 0 or slot >= 10:
            return Evaluation(expression, normalize_expression(expression), ok=False, error="Ячейка памяти должна быть от 0 до 9")
        result = self.evaluate(expression, commit=False)
        if result.ok:
            source, _ = _split_conversion(_split_assignment(normalize_expression(expression))[1])
            self.memories[slot] = self._evaluate_source(source)
        return result

    def memory_expression(self, slot: int) -> str:
        if slot < 0 or slot >= 10:
            raise CalculationError("Ячейка памяти должна быть от 0 до 9")
        return self.format_quantity(self.memories[slot])

    def suggestions(self, query: str = "") -> list[dict[str, str]]:
        needle = query.strip().lower()
        items: list[dict[str, str]] = []
        descriptions = {
            "sin": "Синус", "cos": "Косинус", "tan": "Тангенс",
            "asin": "Арксинус", "acos": "Арккосинус", "atan": "Арктангенс",
            "sqrt": "Квадратный корень", "cbrt": "Кубический корень",
            "ln": "Натуральный логарифм", "log10": "Десятичный логарифм",
            "fact": "Факториал", "mean": "Среднее", "sum": "Сумма",
        }
        for name in FUNCTION_NAMES:
            if not needle or needle in name:
                items.append({"kind": "function", "label": name, "insert": f"{name}()", "description": descriptions.get(name, "Функция")})
        seen_units: set[str] = set()
        for unit in UNIT_DEFS.values():
            if unit.symbol in seen_units:
                continue
            seen_units.add(unit.symbol)
            if not needle or needle in unit.symbol.lower():
                items.append({"kind": "unit", "label": unit.symbol, "insert": unit.symbol, "description": "Единица измерения"})
        for name in sorted(self.variables):
            if not needle or needle in name:
                items.append({"kind": "variable", "label": name, "insert": name, "description": self.format_quantity(self.variables[name])})
        return items[:80]


def make_history_entry(evaluation: Evaluation, settings: EngineSettings, sequence: int) -> HistoryEntry:
    timestamp = datetime.now(timezone.utc)
    return HistoryEntry(
        id=f"{int(timestamp.timestamp() * 1000)}-{sequence}",
        expression=evaluation.expression.strip(),
        result=evaluation.result,
        raw_value=evaluation.raw_value,
        unit=evaluation.unit,
        angle_mode=settings.angle_mode,
        number_base=settings.number_base,
        created_at=timestamp.isoformat(),
    )
