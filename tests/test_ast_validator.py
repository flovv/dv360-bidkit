"""Unit tests for AST validator, signal registry, and linter."""

import pytest
from dv360_bidkit.contracts.schemas import DiagnosticSeverity
from dv360_bidkit.linter.ast_validator import lint_script
from dv360_bidkit.linter.migrator import migrate_script


def test_valid_first_match_script():
    code = """
return first_match_aggregate([
    ([domain == "spiegel.de"], 10.0),
    ([device_type == 2], 5.0),
    ([True], 1.0)
])
"""
    report = lint_script(code)
    assert report.is_valid
    assert not report.has_errors


def test_valid_sum_aggregate_script():
    code = """
return sum_aggregate([
    ([country_code == "US"], 2.0),
    ([total_conversion_count(12345, 0) > 0], 50.0)
])
"""
    report = lint_script(code)
    assert report.is_valid
    assert not report.has_errors


def test_rejects_imports():
    code = """
import os
return sum_aggregate([([True], 1.0)])
"""
    report = lint_script(code)
    assert not report.is_valid
    assert any(d.code == "DISALLOWED_SYNTAX_NODE" for d in report.diagnostics)


def test_rejects_loops():
    code = """
for i in range(10):
    pass
return 1.0
"""
    report = lint_script(code)
    assert not report.is_valid
    assert any(d.code == "DISALLOWED_SYNTAX_NODE" for d in report.diagnostics)


def test_rejects_lambdas_and_classes():
    code = """
fn = lambda x: x + 1
return 1.0
"""
    report = lint_script(code)
    assert not report.is_valid
    assert any(d.code == "DISALLOWED_SYNTAX_NODE" for d in report.diagnostics)


def test_rejects_dynamic_calls():
    code = """
obj.method()
return 1.0
"""
    report = lint_script(code)
    assert not report.is_valid
    assert any(d.code == "DYNAMIC_CALL_DISALLOWED" for d in report.diagnostics)


def test_invalid_function_arity():
    code = """
# total_conversion_count requires 2 args (activity_id, model_id)
return sum_aggregate([([total_conversion_count(12345) > 0], 10.0)])
"""
    report = lint_script(code)
    assert not report.is_valid
    assert any(d.code == "INVALID_FUNCTION_ARITY" for d in report.diagnostics)


def test_deprecated_signal_warning():
    code = """
return sum_aggregate([([browser_id == 4], 2.0)])
"""
    report = lint_script(code)
    assert report.is_valid  # Warnings do not fail is_valid
    assert any(d.code == "DEPRECATED_SIGNAL" for d in report.diagnostics)


def test_ctv_domain_warning():
    code = """
if device_type == 4 and domain == "joyn.de":
    return 10.0
return 1.0
"""
    report = lint_script(code)
    assert any(d.code == "CTV_DOMAIN_MISMATCH" for d in report.diagnostics)


def test_negative_score_policy_violation():
    code = """
return sum_aggregate([
    ([domain == "bad.com"], -5.0)
])
"""
    report = lint_script(code)
    assert not report.is_valid
    assert any(d.code == "NEGATIVE_SCORE_POLICY" for d in report.diagnostics)


def test_missing_return():
    code = """
x = 10.0
"""
    report = lint_script(code)
    assert not report.is_valid
    assert any(d.code == "MISSING_RETURN" for d in report.diagnostics)


def test_migrator_detects_deprecations():
    old_script = """
if has_ga_goal(111, 222):
    return 10.0
tier = conversion_variable_str(333, 0)
"""
    plan = migrate_script(old_script)
    assert plan.has_deprecations
    assert len(plan.items) == 2
    assert any(item.old_signal == "has_ga_goal" for item in plan.items)
    assert any(item.old_signal == "conversion_variable_str" for item in plan.items)
    assert "conversion_custom_variable" in plan.proposed_code
