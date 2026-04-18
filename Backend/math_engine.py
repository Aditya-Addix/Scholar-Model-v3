from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    function_exponentiation,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


_TRANSFORMATIONS = standard_transformations + (
    convert_xor,
    implicit_multiplication_application,
    function_exponentiation,
)

_COMMON_SYMBOLS = {
    name: sp.symbols(name)
    for name in (
        "x",
        "y",
        "z",
        "t",
        "u",
        "v",
        "w",
        "a",
        "b",
        "c",
        "m",
        "n",
        "r",
        "s",
        "p",
        "q",
        "k",
        "theta",
        "phi",
        "alpha",
        "beta",
    )
}

_COMMON_LOCALS: dict[str, Any] = {
    **_COMMON_SYMBOLS,
    "E": sp.E,
    "e": sp.E,
    "I": sp.I,
    "pi": sp.pi,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "cot": sp.cot,
    "sec": sp.sec,
    "csc": sp.csc,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "log": sp.log,
    "ln": sp.log,
    "sqrt": sp.sqrt,
    "exp": sp.exp,
    "Abs": sp.Abs,
}


@dataclass(slots=True)
class SymbolicVerification:
    operation: str
    plain_result: str
    latex_result: str

    @property
    def context_note(self) -> str:
        return (
            "SymPy Verified Result: "
            + self.plain_result
            + "\nSymPy LaTeX: "
            + self.latex_result
        )


def looks_like_raw_math_expression(query: str) -> bool:
    text = re.sub(r"\s+", " ", str(query or "")).strip()
    if not text:
        return False

    lowered = text.lower()
    mathy_tokens = (
        "solve",
        "differentiate",
        "derivative",
        "integrate",
        "integral",
        "simplify",
        "equation",
        "factor",
        "expand",
    )
    if any(token in lowered for token in mathy_tokens):
        return True

    if re.search(r"[=^/*+\-()]", text):
        return True

    if re.search(r"\b(sin|cos|tan|log|ln|sqrt|exp)\b", lowered):
        return True

    return bool(re.fullmatch(r"[0-9a-zA-Z_\s+\-*/^=().,]+", text))


def _strip_instruction_prefix(query: str) -> str:
    text = re.sub(r"^\s*(please\s+)?", "", str(query or ""), flags=re.IGNORECASE).strip()
    text = re.sub(
        r"^\s*(solve|differentiate|differentiate\s+the|integrate|integrate\s+the|simplify|evaluate)\b[:\s]*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return text


def _build_local_dict() -> dict[str, Any]:
    return dict(_COMMON_LOCALS)


def _parse_expression(expression_text: str) -> sp.Expr:
    global_dict = dict(sp.__dict__)
    global_dict["__builtins__"] = {}
    return parse_expr(
        expression_text,
        local_dict=_build_local_dict(),
        global_dict=global_dict,
        transformations=_TRANSFORMATIONS,
        evaluate=True,
    )


def _normalize_plain(expr: Any) -> str:
    return re.sub(r"\s+", " ", sp.sstr(expr)).strip()


def _clean_latex(expr: Any) -> str:
    return re.sub(r"\s+", " ", sp.latex(expr)).strip()


_NUMERIC_ASSIGNMENT_PATTERN = re.compile(
    r"\b(?P<name>force|mass|acceleration|velocity|distance|time)\b\s*(?:=|is|of|are)?\s*(?P<value>[-+]?\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Zμµ/\^²³0-9]*)",
    flags=re.IGNORECASE,
)


def _canonical_measurement_name(raw_name: str) -> str | None:
    name = re.sub(r"\s+", " ", str(raw_name or "")).strip().lower()
    aliases = {
        "force": "force",
        "mass": "mass",
        "acceleration": "acceleration",
        "velocity": "velocity",
        "distance": "distance",
        "time": "time",
    }
    return aliases.get(name)


def _parse_numeric_measurement(raw_value: str) -> sp.Expr | None:
    text = re.sub(r"\s+", " ", str(raw_value or "")).strip()
    if not text:
        return None

    try:
        return sp.nsimplify(text, rational=True)
    except Exception:
        try:
            return sp.Float(text)
        except Exception:
            return None


def _format_measurement(value: sp.Expr, unit: str | None = None) -> str:
    rendered = sp.sstr(sp.simplify(value))
    unit_text = re.sub(r"\s+", "", str(unit or "")).strip()
    if unit_text:
        unit_text = unit_text.replace("²", "^2").replace("³", "^3")
        return f"{rendered} {unit_text}"
    return rendered


def build_numeric_ground_truth_context(query_text: str) -> str | None:
    text = re.sub(r"\s+", " ", str(query_text or "")).strip()
    if not text:
        return None

    measurements: dict[str, tuple[sp.Expr, str | None]] = {}
    for match in _NUMERIC_ASSIGNMENT_PATTERN.finditer(text):
        canonical_name = _canonical_measurement_name(match.group("name"))
        numeric_value = _parse_numeric_measurement(match.group("value"))
        if not canonical_name or numeric_value is None:
            continue
        unit = re.sub(r"\s+", "", str(match.group("unit") or "")).strip() or None
        measurements[canonical_name] = (numeric_value, unit)

    if not measurements:
        return None

    if {"force", "mass"}.issubset(measurements):
        force_value, force_unit = measurements["force"]
        mass_value, mass_unit = measurements["mass"]
        acceleration_value = sp.simplify(force_value / mass_value)
        return (
            "CRITICAL: The mathematically verified result is acceleration = "
            + _format_measurement(acceleration_value, "m/s²")
            + ". Ensure your explanation aligns with this. Parsed inputs: Force = "
            + _format_measurement(force_value, force_unit)
            + ", Mass = "
            + _format_measurement(mass_value, mass_unit)
            + "."
        )

    if {"mass", "acceleration"}.issubset(measurements):
        mass_value, mass_unit = measurements["mass"]
        acceleration_value, acceleration_unit = measurements["acceleration"]
        force_value = sp.simplify(mass_value * acceleration_value)
        return (
            "CRITICAL: The mathematically verified result is force = "
            + _format_measurement(force_value, "N")
            + ". Ensure your explanation aligns with this. Parsed inputs: Mass = "
            + _format_measurement(mass_value, mass_unit)
            + ", Acceleration = "
            + _format_measurement(acceleration_value, acceleration_unit)
            + "."
        )

    if {"force", "acceleration"}.issubset(measurements):
        force_value, force_unit = measurements["force"]
        acceleration_value, acceleration_unit = measurements["acceleration"]
        mass_value = sp.simplify(force_value / acceleration_value)
        return (
            "CRITICAL: The mathematically verified result is mass = "
            + _format_measurement(mass_value, "kg")
            + ". Ensure your explanation aligns with this. Parsed inputs: Force = "
            + _format_measurement(force_value, force_unit)
            + ", Acceleration = "
            + _format_measurement(acceleration_value, acceleration_unit)
            + "."
        )

    if {"distance", "time"}.issubset(measurements):
        distance_value, distance_unit = measurements["distance"]
        time_value, time_unit = measurements["time"]
        velocity_value = sp.simplify(distance_value / time_value)
        return (
            "CRITICAL: The mathematically verified result is velocity = "
            + _format_measurement(velocity_value, "m/s")
            + ". Ensure your explanation aligns with this. Parsed inputs: Distance = "
            + _format_measurement(distance_value, distance_unit)
            + ", Time = "
            + _format_measurement(time_value, time_unit)
            + "."
        )

    if {"velocity", "time"}.issubset(measurements):
        velocity_value, velocity_unit = measurements["velocity"]
        time_value, time_unit = measurements["time"]
        distance_value = sp.simplify(velocity_value * time_value)
        return (
            "CRITICAL: The mathematically verified result is distance = "
            + _format_measurement(distance_value, "m")
            + ". Ensure your explanation aligns with this. Parsed inputs: Velocity = "
            + _format_measurement(velocity_value, velocity_unit)
            + ", Time = "
            + _format_measurement(time_value, time_unit)
            + "."
        )

    if {"distance", "velocity"}.issubset(measurements):
        distance_value, distance_unit = measurements["distance"]
        velocity_value, velocity_unit = measurements["velocity"]
        time_value = sp.simplify(distance_value / velocity_value)
        return (
            "CRITICAL: The mathematically verified result is time = "
            + _format_measurement(time_value, "s")
            + ". Ensure your explanation aligns with this. Parsed inputs: Distance = "
            + _format_measurement(distance_value, distance_unit)
            + ", Velocity = "
            + _format_measurement(velocity_value, velocity_unit)
            + "."
        )

    rendered_inputs = "; ".join(
        f"{name} = {_format_measurement(value, unit)}"
        for name, (value, unit) in measurements.items()
    )
    return (
        "CRITICAL: Parsed numeric measurements were detected, but no direct SymPy derivation was available. "
        "Ensure your explanation aligns with the verified inputs: "
        + rendered_inputs
        + "."
    )


def _format_sympy_ground_truth(symbols: list[sp.Symbol], solutions: Any) -> str | None:
    if isinstance(solutions, dict):
        rendered_parts: list[str] = []
        for key, value in solutions.items():
            rendered_parts.append(f"{sp.sstr(key)} = {sp.sstr(sp.simplify(value))}")
        return "; ".join(rendered_parts) if rendered_parts else None

    if isinstance(solutions, (set, sp.FiniteSet)):
        ordered_solutions = sorted(list(solutions), key=sp.default_sort_key)
    elif isinstance(solutions, (list, tuple)):
        ordered_solutions = list(solutions)
    else:
        ordered_solutions = [solutions]

    if not ordered_solutions:
        return None

    if len(symbols) == 1:
        return "; ".join(f"{sp.sstr(symbols[0])} = {sp.sstr(sp.simplify(solution))}" for solution in ordered_solutions)

    rendered_parts: list[str] = []
    for solution in ordered_solutions:
        if isinstance(solution, dict):
            rendered_parts.append(
                ", ".join(f"{sp.sstr(key)} = {sp.sstr(sp.simplify(value))}" for key, value in solution.items())
            )
        elif len(symbols) == 1:
            rendered_parts.append(f"{sp.sstr(symbols[0])} = {sp.sstr(sp.simplify(solution))}")
        else:
            rendered_parts.append(sp.sstr(solution))

    if not rendered_parts:
        return None
    return "; ".join(rendered_parts)


def build_sympy_ground_truth_context(query_text: str) -> str | None:
    text = str(query_text or "").strip()
    if not text:
        return None

    lowered = text.lower()
    if "=" not in text and not re.search(r"\b(solve|root|roots|zero|zeros|solution|equation)\b", lowered):
        return None

    candidate = text
    solve_match = re.search(r"(?:solve|find|determine|calculate|evaluate)\s+(.*)", candidate, flags=re.IGNORECASE)
    if solve_match:
        candidate = solve_match.group(1).strip()

    candidate = candidate.replace("^", "**")
    candidate = re.sub(r"(?<=\d)(?=[a-zA-Z(])", "*", candidate)
    candidate = re.sub(r"(?<=[a-zA-Z)])(?=\d)", "*", candidate)
    candidate = candidate.strip(" .;")

    if "=" not in candidate:
        if re.search(r"\b(root|roots|zero|zeros|solution)\b", lowered):
            candidate = candidate + " = 0"
        else:
            return None

    lhs_text, rhs_text = candidate.split("=", 1)
    lhs_text = lhs_text.strip()
    rhs_text = rhs_text.strip()
    if not lhs_text or not rhs_text:
        return None

    try:
        parsed_lhs = parse_expr(lhs_text, local_dict={**_COMMON_LOCALS, "sp": sp}, transformations=_TRANSFORMATIONS)
        parsed_rhs = parse_expr(rhs_text, local_dict={**_COMMON_LOCALS, "sp": sp}, transformations=_TRANSFORMATIONS)
        equation = sp.Eq(parsed_lhs, parsed_rhs)
        symbols = sorted(list(equation.free_symbols), key=lambda symbol: symbol.sort_key())

        if not symbols:
            delta = sp.simplify(parsed_lhs - parsed_rhs)
            return f"Ground Truth (SymPy): {sp.sstr(delta)} = 0"

        if len(symbols) == 1:
            solved = sp.solve(equation, symbols[0])
            if solved is None:
                return None
            if isinstance(solved, list) and not solved:
                return "Ground Truth (SymPy): no solution"
            rendered = _format_sympy_ground_truth([symbols[0]], solved)
        else:
            solved = sp.solve(equation, symbols, dict=True)
            if solved is None:
                return None
            if isinstance(solved, list) and not solved:
                return "Ground Truth (SymPy): no solution"
            rendered = _format_sympy_ground_truth(symbols, solved)

        if not rendered:
            return None
        return "Ground Truth (SymPy): " + rendered
    except Exception:
        return None


def _select_target_symbol(expr: sp.Expr, query: str) -> sp.Symbol:
    symbol_name_match = re.search(
        r"\b(?:solve\s+for|differentiate\s+with\s+respect\s+to|integrate\s+with\s+respect\s+to)\s+([A-Za-z][A-Za-z0-9_]*)",
        query,
        flags=re.IGNORECASE,
    )
    if symbol_name_match:
        explicit_name = symbol_name_match.group(1).strip()
        if explicit_name in _COMMON_SYMBOLS:
            return _COMMON_SYMBOLS[explicit_name]
        return sp.symbols(explicit_name)

    ordered_symbols = sorted(expr.free_symbols, key=lambda symbol: symbol.name)
    if ordered_symbols:
        return ordered_symbols[0]
    return _COMMON_SYMBOLS["x"]


def _format_equation_solutions(symbol: sp.Symbol, solutions: Any) -> tuple[str, str]:
    if isinstance(solutions, dict):
        items = list(solutions.items())
        plain_parts = [f"{sp.sstr(key)} = {sp.sstr(value)}" for key, value in items]
        latex_parts = [sp.latex(sp.Eq(key, value)) for key, value in items]
        return "; ".join(plain_parts), "; ".join(latex_parts)

    if isinstance(solutions, (set, sp.FiniteSet)):
        ordered = sorted(list(solutions), key=sp.default_sort_key)
    elif isinstance(solutions, (list, tuple)):
        ordered = list(solutions)
    else:
        ordered = [solutions]

    if not ordered:
        return "No symbolic solution found.", r"\varnothing"

    plain_values = [_normalize_plain(item) for item in ordered]
    if len(ordered) == 1:
        plain = f"{sp.sstr(symbol)} = {plain_values[0]}"
        latex = sp.latex(sp.Eq(symbol, ordered[0]))
    else:
        plain = f"{sp.sstr(symbol)} = " + ", ".join(plain_values)
        latex = sp.latex(sp.FiniteSet(*ordered))
    return plain, latex


def _solve_equation(query: str) -> SymbolicVerification | None:
    body = _strip_instruction_prefix(query)
    if "=" not in body:
        return None

    left_text, right_text = body.split("=", 1)
    left_expr = _parse_expression(left_text.strip())
    right_expr = _parse_expression(right_text.strip())
    equation = sp.Eq(left_expr, right_expr)
    symbol = _select_target_symbol(left_expr - right_expr, query)

    try:
        solutions = sp.solve(equation, symbol, dict=False)
    except Exception:
        solutions = sp.solve(equation, dict=True)

    plain, latex = _format_equation_solutions(symbol, solutions)
    return SymbolicVerification(operation="solve", plain_result=plain, latex_result=latex)


def _differentiate_expression(query: str) -> SymbolicVerification | None:
    body = _strip_instruction_prefix(query)
    match = re.search(
        r"\b(?:d/d([A-Za-z][A-Za-z0-9_]*)|differentiate\s+with\s+respect\s+to\s+([A-Za-z][A-Za-z0-9_]*))\b",
        query,
        flags=re.IGNORECASE,
    )
    variable_name = None
    if match:
        variable_name = match.group(1) or match.group(2)

    expression_text = re.sub(
        r"\b(?:d/d[A-Za-z][A-Za-z0-9_]*|differentiate\s+with\s+respect\s+to\s+[A-Za-z][A-Za-z0-9_]*)\b",
        "",
        body,
        flags=re.IGNORECASE,
    ).strip()
    if not expression_text:
        return None

    expression = _parse_expression(expression_text)
    symbol = _COMMON_SYMBOLS.get(variable_name or "", None)
    if symbol is None:
        symbol = _select_target_symbol(expression, query)

    differentiated = sp.simplify(sp.diff(expression, symbol))
    return SymbolicVerification(
        operation="differentiate",
        plain_result=_normalize_plain(differentiated),
        latex_result=_clean_latex(differentiated),
    )


def _integrate_expression(query: str) -> SymbolicVerification | None:
    body = _strip_instruction_prefix(query)
    variable_match = re.search(r"\b(?:d|d/d)([A-Za-z][A-Za-z0-9_]*)\b", query, flags=re.IGNORECASE)
    variable_name = variable_match.group(1) if variable_match else None

    expression_text = re.sub(r"\b(?:integrate|integral\s+of|antiderivative\s+of)\b", "", body, flags=re.IGNORECASE).strip()
    expression_text = re.sub(r"\b(?:dx|dy|dz|dt|du|dv|dw)\b\s*$", "", expression_text, flags=re.IGNORECASE).strip()
    if not expression_text:
        return None

    expression = _parse_expression(expression_text)
    symbol = _COMMON_SYMBOLS.get(variable_name or "", None)
    if symbol is None:
        symbol = _select_target_symbol(expression, query)

    integrated = sp.simplify(sp.integrate(expression, symbol))
    plain = f"{_normalize_plain(integrated)} + C"
    latex = _clean_latex(integrated) + r" + C"
    return SymbolicVerification(operation="integrate", plain_result=plain, latex_result=latex)


def _simplify_expression(query: str) -> SymbolicVerification | None:
    body = _strip_instruction_prefix(query)
    if not body:
        return None

    expression = _parse_expression(body)
    simplified = sp.simplify(expression)
    simplified = sp.trigsimp(simplified)
    simplified = sp.logcombine(simplified, force=True)
    return SymbolicVerification(
        operation="simplify",
        plain_result=_normalize_plain(simplified),
        latex_result=_clean_latex(simplified),
    )


def evaluate_symbolic_query(query: str) -> SymbolicVerification | None:
    text = re.sub(r"\s+", " ", str(query or "")).strip()
    if not text or not looks_like_raw_math_expression(text):
        return None

    lowered = text.lower()
    evaluators = []
    if any(token in lowered for token in ("solve", "equation")) or "=" in text:
        evaluators.append(_solve_equation)
    if any(token in lowered for token in ("differentiate", "derivative", "differentiate with respect to", "d/d")):
        evaluators.append(_differentiate_expression)
    if any(token in lowered for token in ("integrate", "integral", "antiderivative")):
        evaluators.append(_integrate_expression)
    if any(token in lowered for token in ("simplify", "factor", "expand")):
        evaluators.append(_simplify_expression)

    if evaluators == [_solve_equation] and "=" not in text:
        evaluators.append(_simplify_expression)

    if not evaluators:
        evaluators = [_simplify_expression]

    for evaluator in evaluators:
        try:
            result = evaluator(text)
        except Exception:
            continue
        if result is not None:
            return result

    return None