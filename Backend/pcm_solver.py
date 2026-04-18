from __future__ import annotations

import os
import re
import urllib.parse
import urllib.request
from typing import Any

import sympy as sp

UNBOUNDED_SOLVER_RESPONSE: dict[str, Any] = {
    "result": "\\text{System requires more constrained variables to solve.}",
    "explanation": [
        "STEP 1 [SETUP]: Variables & SI Units",
        "STEP 2 [CONCEPT]: Core Physics/Math Law",
        "STEP 3 [EXECUTION]: Algebraic Steps",
        "STEP 4 [VERIFICATION]: Dimensional and boundary-condition checks could not certify a unique result.",
    ],
}

WOLFRAM_RESULT_ENDPOINT = "https://api.wolframalpha.com/v1/result"
WOLFRAM_APP_ID_ENV_NAME = "WOLFRAM_APP_ID"


def _is_indeterminate_expr(expr: sp.Expr) -> bool:
    return bool(
        expr.has(sp.nan)
        or expr.has(sp.zoo)
        or expr.has(sp.oo)
        or expr.has(-sp.oo)
        or expr in {sp.nan, sp.zoo, sp.oo, -sp.oo}
    )


def _query_wolfram_secondary(raw_equation: str) -> str | None:
    app_id = os.getenv(WOLFRAM_APP_ID_ENV_NAME)
    equation = (raw_equation or "").strip()
    if not app_id or not equation:
        return None

    params = urllib.parse.urlencode({"appid": app_id, "i": equation})
    request_url = f"{WOLFRAM_RESULT_ENDPOINT}?{params}"

    try:
        with urllib.request.urlopen(request_url, timeout=6.0) as response:
            text = response.read().decode("utf-8", errors="ignore").strip()
            if not text:
                return None
            lowered = text.lower()
            if "no short answer available" in lowered or "unable to interpret" in lowered:
                return None
            return text
    except Exception:
        return None


def _parse_wolfram_to_expr(wolfram_answer: str | None) -> sp.Expr | None:
    if not wolfram_answer:
        return None

    candidate = wolfram_answer.strip().replace("^", "**")
    candidate = re.sub(r"\s*(seconds?|meters?|metres?|kilograms?|joules?|newtons?)\b", "", candidate, flags=re.IGNORECASE)
    candidate = candidate.replace("∞", "oo")

    try:
        expr = sp.sympify(candidate, locals={"sp": sp})
        if _is_indeterminate_expr(expr):
            return None
        return expr.evalf(6)
    except Exception:
        return None


def sympy_simplify_fraction(expression_text: str) -> sp.Expr:
    """Simplify algebraic fractions with deterministic precision and Wolfram secondary-check fallback."""
    x = sp.Symbol("x")
    cleaned_expression = (expression_text or "").strip()

    try:
        expr = sp.sympify(cleaned_expression, locals={"x": x, "sp": sp})
        simplified = sp.simplify(sp.together(expr))
    except Exception as exc:
        # If SymPy parsing fails (including coupled/complex systems), route raw equation to Wolfram first.
        wolfram_expr = _parse_wolfram_to_expr(_query_wolfram_secondary(cleaned_expression))
        if wolfram_expr is not None:
            return wolfram_expr
        raise ValueError(f"SymPy parse failure and Wolfram secondary-check unavailable: {exc}") from exc

    numeric_probe = simplified.evalf(6)
    if _is_indeterminate_expr(simplified) or _is_indeterminate_expr(numeric_probe):
        wolfram_expr = _parse_wolfram_to_expr(_query_wolfram_secondary(cleaned_expression))
        if wolfram_expr is not None:
            return wolfram_expr
        raise ValueError("SymPy produced indeterminate form and Wolfram secondary-check returned no usable result.")

    is_complex = bool(simplified.has(sp.I)) or bool(getattr(numeric_probe, "is_real", None) is False)
    if is_complex:
        wolfram_expr = _parse_wolfram_to_expr(_query_wolfram_secondary(cleaned_expression))
        if wolfram_expr is not None:
            return wolfram_expr
        raise ValueError("Unexpected complex/imaginary result in real-domain solve.")

    return simplified


def wolfram_graceful_fallback() -> dict[str, Any]:
    return dict(UNBOUNDED_SOLVER_RESPONSE)
