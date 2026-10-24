"""Unit tests for AST interpreter safe evaluation."""

import pytest
from dv360_bidkit.contracts.exceptions import EvaluationError
from dv360_bidkit.evaluator.interpreter import create_interpreter


def test_interpreter_sum_aggregate():
    code = """
return sum_aggregate([
    ([domain == "spiegel.de"], 5.0),
    ([device_type == 2], 3.0),
    ([country_code == "US"], 2.0)
])
"""
    interp = create_interpreter(code)
    # Match domain and device_type, but not country_code
    ctx = {"domain": "spiegel.de", "device_type": 2, "country_code": "DE"}
    res = interp.evaluate(ctx)
    assert not res.is_excluded
    assert res.score == 8.0


def test_interpreter_first_match_aggregate():
    code = """
return first_match_aggregate([
    ([domain == "spiegel.de"], 10.0),
    ([device_type == 2], 5.0),
    ([True], 1.0)
])
"""
    interp = create_interpreter(code)
    # If domain matches, returns 10.0 even if device_type matches
    ctx = {"domain": "spiegel.de", "device_type": 2}
    res = interp.evaluate(ctx)
    assert res.score == 10.0

    # If domain doesn't match, falls through to device_type
    ctx2 = {"domain": "unknown.com", "device_type": 2}
    res2 = interp.evaluate(ctx2)
    assert res2.score == 5.0

    # Fallback
    ctx3 = {"domain": "unknown.com", "device_type": 1}
    res3 = interp.evaluate(ctx3)
    assert res3.score == 1.0


def test_interpreter_return_none_exclusion():
    code = """
if domain == "mfa-site.com":
    return None
return 1.0
"""
    interp = create_interpreter(code)
    res_mfa = interp.evaluate({"domain": "mfa-site.com"})
    assert res_mfa.is_excluded
    assert res_mfa.score is None

    res_good = interp.evaluate({"domain": "good-site.com"})
    assert not res_good.is_excluded
    assert res_good.score == 1.0


def test_interpreter_short_circuit_and_errors():
    # If first condition of 'and' is False, second condition is never evaluated
    code = """
if False and (1 / 0 == 0):
    return 10.0
return 2.0
"""
    interp = create_interpreter(code)
    res = interp.evaluate({})
    assert res.score == 2.0


def test_interpreter_division_by_zero():
    code = """
return 10.0 / device_type
"""
    interp = create_interpreter(code)
    res = interp.evaluate({"device_type": 0})
    assert res.error == "Division by zero"
    assert res.score is None


def test_interpreter_max_ops_limit():
    # Construct script that generates deep evaluation
    code = """
x = 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1
return x
"""
    interp = create_interpreter(code)
    interp.max_ops = 5
    res = interp.evaluate({})
    assert "budget of 5 operations" in (res.error or "")


def test_interpreter_operators_and_casts():
    code = """
score = float(10) * 2 - 5 // 2 + (8 % 3)
flag = bool(score > 0)
num = int(score)
return float(num) if flag else 0.0
"""
    interp = create_interpreter(code)
    res = interp.evaluate({})
    assert res.score == 20.0


def test_interpreter_max_aggregate():
    code = """
return max_aggregate([
    ([device_type == 1], 5.0),
    ([domain == "premium.com"], 15.0),
    ([country_code == "US"], 2.0)
])
"""
    interp = create_interpreter(code)
    res = interp.evaluate({"device_type": 1, "domain": "premium.com", "country_code": "US"})
    assert res.score == 15.0


def test_interpreter_comparisons_and_unary():
    code = """
if not (device_type <= 2 and environment >= 1 and country_code != "CA"):
    return 0.0
return +10.0
"""
    interp = create_interpreter(code)
    res = interp.evaluate({"device_type": 2, "environment": 1, "country_code": "US"})
    assert res.score == 10.0

