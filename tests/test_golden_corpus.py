"""Golden Scripts Corpus Validation & Interpretation Tests.

Verifies canonical DV360 Custom Bidding scripts (01-07) lint cleanly and evaluate
correctly under ASTInterpreter, and verifies negative test fixtures (08-11)
raise exact expected validation errors.
"""

from pathlib import Path
import pytest

from dv360_bidkit.evaluator.interpreter import create_interpreter
from dv360_bidkit.linter.ast_validator import lint_script

GOLDEN_DIR = Path(__file__).parent / "golden"


POSITIVE_SCRIPTS = [
    "01_display_viewability_proxy.py",
    "02_floodlight_multi_objective.py",
    "03_capped_revenue_ternary.py",
    "04_ga4_key_events.py",
    "05_inventory_policy_exclusions.py",
    "06_inventory_site_id_overrides.py",
    "07_allowlist_only_fallback.py",
]


@pytest.mark.parametrize("filename", POSITIVE_SCRIPTS)
def test_positive_golden_scripts_lint_cleanly(filename: str):
    script_path = GOLDEN_DIR / filename
    assert script_path.exists(), f"Golden script missing: {filename}"
    code = script_path.read_text(encoding="utf-8")

    report = lint_script(code)
    errors = [d for d in report.diagnostics if d.severity.value == "error"]
    assert report.is_valid, f"{filename} failed validation with errors: {errors}"
    assert len(errors) == 0


def test_positive_script_01_viewability_proxy_eval():
    code = (GOLDEN_DIR / "01_display_viewability_proxy.py").read_text(encoding="utf-8")
    interpreter = create_interpreter(code)

    res_tier1 = interpreter.evaluate({"domain": "wsj.com"})
    assert res_tier1.score == 1.5

    res_tier2 = interpreter.evaluate({"domain": "techcrunch.com"})
    assert res_tier2.score == 1.2

    res_fallback = interpreter.evaluate({"domain": "unknown-local-site.com"})
    assert res_fallback.score == 0.8


def test_positive_script_02_floodlight_multi_objective_eval():
    code = (GOLDEN_DIR / "02_floodlight_multi_objective.py").read_text(encoding="utf-8")
    interpreter = create_interpreter(code)

    context = {
        "total_conversion_count:101:0": 1,
        "total_conversion_count:102:0": 0,
        "total_conversion_count:103:0": 2,
        "domain": "trustedpartner.com",
    }
    res = interpreter.evaluate(context)
    # 50.0 (conv 101) + 5.0 (conv 103) + 2.0 (domain) = 57.0
    assert res.score == 57.0


def test_positive_script_03_capped_revenue_eval():
    code = (GOLDEN_DIR / "03_capped_revenue_ternary.py").read_text(encoding="utf-8")
    interpreter = create_interpreter(code)

    res_uncapped = interpreter.evaluate({"total_conversion_value:201:0": 100.0})
    assert res_uncapped.score == 150.0

    res_capped = interpreter.evaluate({"total_conversion_value:201:0": 500.0})
    assert res_capped.score == 375.0  # 250.0 * 1.5


def test_positive_script_04_ga4_key_events_eval():
    code = (GOLDEN_DIR / "04_ga4_key_events.py").read_text(encoding="utf-8")
    interpreter = create_interpreter(code)

    context = {
        "ga4_conversions_count:G-XXXXXXXX:purchase": 2,
        "ga4_conversions_count:G-XXXXXXXX:generate_lead": 1,
    }
    res = interpreter.evaluate(context)
    assert res.score == 220.0  # (2 * 100) + (1 * 20)


def test_positive_script_05_inventory_exclusions_eval():
    code = (GOLDEN_DIR / "05_inventory_policy_exclusions.py").read_text(encoding="utf-8")
    interpreter = create_interpreter(code)

    res_excluded = interpreter.evaluate({"domain": "bot-farm.net"})
    assert res_excluded.is_excluded is True
    assert res_excluded.score is None

    res_good = interpreter.evaluate({"domain": "goodsite.org"})
    assert res_good.is_excluded is False
    assert res_good.score == 1.4

    res_fallback = interpreter.evaluate({"domain": "other.com"})
    assert res_fallback.is_excluded is False
    assert res_fallback.score == 0.7


def test_positive_script_06_site_id_overrides_eval():
    code = (GOLDEN_DIR / "06_inventory_site_id_overrides.py").read_text(encoding="utf-8")
    interpreter = create_interpreter(code)

    res_site = interpreter.evaluate({"site_id": "11223344", "domain": "irrelevant.com"})
    assert res_site.score == 2.5

    res_domain = interpreter.evaluate({"site_id": "99999999", "domain": "partnerapp.io"})
    assert res_domain.score == 1.8

    res_default = interpreter.evaluate({"site_id": "99999999", "domain": "unknown.com"})
    assert res_default.score == 0.5


def test_positive_script_07_allowlist_only_fallback_eval():
    code = (GOLDEN_DIR / "07_allowlist_only_fallback.py").read_text(encoding="utf-8")
    interpreter = create_interpreter(code)

    res_allowed = interpreter.evaluate({"domain": "premium-sports.com"})
    assert res_allowed.score == 2.0

    res_blocked = interpreter.evaluate({"domain": "unregistered-blog.com"})
    assert res_blocked.is_excluded is True
    assert res_blocked.score is None


NEGATIVE_FIXTURES = [
    ("08_invalid_syntax_loop.py", "DISALLOWED_SYNTAX_NODE"),
    ("09_invalid_syntax_import.py", "DISALLOWED_SYNTAX_NODE"),
    ("10_invalid_unknown_signal.py", "UNKNOWN_FUNCTION"),
    ("11_invalid_negative_score.py", "NEGATIVE_SCORE_POLICY"),
]


@pytest.mark.parametrize("filename,expected_code", NEGATIVE_FIXTURES)
def test_negative_golden_scripts_fail_with_expected_code(filename: str, expected_code: str):
    script_path = GOLDEN_DIR / filename
    assert script_path.exists(), f"Negative script missing: {filename}"
    code = script_path.read_text(encoding="utf-8")

    report = lint_script(code)
    assert not report.is_valid, f"{filename} unexpectedly marked as valid"

    diagnostic_codes = [d.code for d in report.diagnostics]
    assert expected_code in diagnostic_codes, (
        f"{filename} expected diagnostic code '{expected_code}' but got {diagnostic_codes}"
    )
