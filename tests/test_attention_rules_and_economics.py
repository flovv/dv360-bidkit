"""Tests for attention AST linter rules and attention fee-stack / bounded recall economics."""

from __future__ import annotations

import json
import pytest
from typer.testing import CliRunner

from dv360_bidkit.cli import app
from dv360_bidkit.evaluator.economics import (
    SIMONOV_SATURATION_SECONDS,
    analyze_attention_fee_economics,
    bounded_quadratic_recall,
)
from dv360_bidkit.linter.ast_validator import lint_script
from dv360_bidkit.mcp import handle_tool_call

runner = CliRunner()


def test_lint_uncapped_linear_dwell_warns():
    script = """
if active_view_viewed:
    return time_on_screen_seconds * 2.0 + total_conversion_count(12345, 0) * 10.0
return 0.0
"""
    report = lint_script(script)
    assert report.is_valid  # warnings only, valid DSL
    codes = {d.code for d in report.diagnostics}
    assert "ATTN_UNCAPPED_DWELL" in codes
    assert "ATTN_STANDALONE_WITHOUT_OUTCOME" not in codes


def test_lint_capped_concave_attention_with_outcome_clean():
    script = """
_capped_t = 20.0 if time_on_screen_seconds > 20.0 else time_on_screen_seconds
_attn = log(_capped_t + 1.0) if active_view_viewed else 0.0
_fmt = 1.4 if (creative_width == 300 and creative_height == 600 and ad_position == 1) else 1.0
_conv = total_conversion_count(12345, 0) * 25.0
return _attn * _fmt + _conv
"""
    report = lint_script(script)
    assert report.is_valid
    codes = {d.code for d in report.diagnostics}
    assert "ATTN_UNCAPPED_DWELL" not in codes
    assert "ATTN_STANDALONE_WITHOUT_OUTCOME" not in codes


def test_lint_standalone_attention_without_outcome_warns():
    script = """
_capped_t = 20.0 if time_on_screen_seconds > 20.0 else time_on_screen_seconds
if active_view_viewed or completed_in_view_audible:
    return log(_capped_t + 1.0)
return 0.0
"""
    report = lint_script(script)
    assert report.is_valid
    codes = {d.code for d in report.diagnostics}
    assert "ATTN_STANDALONE_WITHOUT_OUTCOME" in codes
    assert "ATTN_UNCAPPED_DWELL" not in codes


def test_lint_ctv_domain_mismatch_detects_in_tuple_and_device_5():
    script = """
if device_type in (4, 5) and domain == "example.com":
    return 5.0
return 1.0
"""
    report = lint_script(script)
    assert report.is_valid
    codes = {d.code for d in report.diagnostics}
    assert "CTV_DOMAIN_MISMATCH" in codes


def test_economics_display_curation_fee_hurdle():
    # €4.50 base CPM, +15% clearing uplift, 11% median SSP curation take rate
    res = analyze_attention_fee_economics(
        base_cpm=4.50,
        cpm_uplift_pct=15.0,
        curation_fee_pct=11.0,
    )
    assert res.all_in_cpm == pytest.approx(5.8146, abs=0.01)
    assert res.required_yield_lift_pct == pytest.approx(29.21, abs=0.1)
    assert res.verdict == "MARGINAL"


def test_economics_stacked_display_fee_trap():
    res = analyze_attention_fee_economics(
        base_cpm=4.50,
        cpm_uplift_pct=15.0,
        prebid_cpm_fee=0.25,
        curation_fee_pct=11.0,
        ai_fee_pct=6.0,
        agency_fee_pct=3.0,
    )
    assert res.required_yield_lift_pct > 45.0
    assert res.verdict == "FEE_TRAP"


def test_economics_ctv_prebid_viable():
    # €22.00 CTV, +12% clearing uplift, €0.30 fixed pre-bid segment
    res = analyze_attention_fee_economics(
        base_cpm=22.00,
        cpm_uplift_pct=12.0,
        prebid_cpm_fee=0.30,
    )
    assert res.all_in_cpm == pytest.approx(24.94, abs=0.02)
    assert res.required_yield_lift_pct == pytest.approx(13.36, abs=0.1)
    assert res.verdict == "VIABLE"


def test_economics_bounded_recall_sixfold_overstatement():
    # €100k budget, freq 6, €4.00 -> €4.60 (+3% fee), 1.10s -> 2.40s dwell
    res = analyze_attention_fee_economics(
        base_cpm=4.00,
        cpm_uplift_pct=15.0,
        ai_fee_pct=3.0,
        budget=100_000.0,
        frequency=6.0,
        base_dwell_seconds=1.10,
        target_dwell_seconds=2.40,
    )
    assert res.hits_recall_saturation is True
    assert res.target_cumulative_dwell_seconds == pytest.approx(14.4, abs=0.01)
    assert bounded_quadratic_recall(20.0) == pytest.approx(
        bounded_quadratic_recall(SIMONOV_SATURATION_SECONDS), abs=1e-6
    )
    assert res.bounded_recall_lift_pct == pytest.approx(13.2, abs=0.5)
    assert res.naive_linear_recall_lift_pct > 80.0
    assert res.linear_overstatement_ratio is not None
    assert res.linear_overstatement_ratio > 6.0


def test_cli_fee_check_json():
    result = runner.invoke(
        app,
        [
            "fee-check",
            "--base-cpm",
            "4.50",
            "--cpm-uplift",
            "15",
            "--curation-fee",
            "11",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["currency"] == "EUR"
    assert payload["required_yield_lift_pct"] == pytest.approx(29.21, abs=0.1)


def test_mcp_check_attention_fee_economics():
    out = handle_tool_call(
        "check_attention_fee_economics",
        {
            "base_cpm": 22.0,
            "cpm_uplift_pct": 12.0,
            "prebid_cpm_fee": 0.30,
        },
    )
    assert out["verdict"] == "VIABLE"
    assert out["required_yield_lift_pct"] == pytest.approx(13.36, abs=0.1)
