"""Unit tests for evaluator, data sufficiency, and S2 readiness checks."""

import pandas as pd
import pytest
from dv360_bidkit.contracts.schemas import (
    MetricStatus,
    ReadinessStatus,
    ReportData,
    ReportMapping,
    ReportRowGrain,
)
from dv360_bidkit.evaluator.coverage import verify_data_sufficiency
from dv360_bidkit.evaluator.diagnostics import evaluate_script
from dv360_bidkit.io.fixtures import generate_synthetic_display_report


def test_evaluator_weighted_metrics():
    # Construct 3 rows:
    # Row 1: 100 imps, domain = 'a.com' -> score 10.0
    # Row 2: 100 imps, domain = 'b.com' -> score 0.0
    # Row 3: 100 imps, domain = 'c.com' -> return None (excluded)
    df = pd.DataFrame([
        {"domain": "a.com", "impressions": 100, "line_item_id": 1},
        {"domain": "b.com", "impressions": 100, "line_item_id": 1},
        {"domain": "c.com", "impressions": 100, "line_item_id": 1},
    ])
    mapping = ReportMapping(
        canonical_field_map={"impressions": "impressions", "domain": "domain", "line_item_id": "line_item_id"},
        row_grain=ReportRowGrain.HOMOGENEOUS_AGGREGATE,
    )
    report_data = ReportData(df=df, mapping=mapping)

    script = """
if domain == "c.com":
    return None
elif domain == "a.com":
    return 10.0
else:
    return 0.0
"""
    eval_rep = evaluate_script(script, report_data)

    m = eval_rep.metrics
    assert m.total_impressions == 300
    assert m.positive_score_impressions == 100
    assert m.zero_score_impressions == 100
    assert m.excluded_impressions == 100
    assert m.error_impressions == 0

    # positive_rate_all = 100 / 300 = 0.3333...
    assert m.positive_rate_all.status == MetricStatus.COMPUTED
    assert pytest.approx(m.positive_rate_all.value, 0.001) == 1.0 / 3.0

    # positive_rate_scored = 100 / 200 = 0.5
    assert m.positive_rate_scored.status == MetricStatus.COMPUTED
    assert pytest.approx(m.positive_rate_scored.value, 0.001) == 0.5

    # Positive median = 10.0
    assert m.weighted_median.status == MetricStatus.COMPUTED
    assert m.weighted_median.value == 10.0


def test_readiness_insufficient_positives():
    df = pd.DataFrame([
        {"domain": "a.com", "impressions": 100, "line_item_id": 1},
    ])
    mapping = ReportMapping(
        canonical_field_map={"impressions": "impressions", "domain": "domain", "line_item_id": "line_item_id"},
        row_grain=ReportRowGrain.HOMOGENEOUS_AGGREGATE,
        date_window="30d",
    )
    report_data = ReportData(df=df, mapping=mapping)
    script = "return 1.0\n"
    eval_rep = evaluate_script(script, report_data, history_window_days=30)

    # 100 observed positives < 500 required minimum
    assert eval_rep.readiness.status == ReadinessStatus.INSUFFICIENT_HISTORY
    assert eval_rep.readiness.observed_advertiser_positives == 100


def test_readiness_meets_minimum():
    df = pd.DataFrame([
        {"domain": "a.com", "impressions": 1000, "line_item_id": 1},
    ])
    mapping = ReportMapping(
        canonical_field_map={"impressions": "impressions", "domain": "domain", "line_item_id": "line_item_id"},
        row_grain=ReportRowGrain.HOMOGENEOUS_AGGREGATE,
        date_window="30d",
    )
    report_data = ReportData(df=df, mapping=mapping)
    script = "return 1.0\n"
    eval_rep = evaluate_script(script, report_data, history_window_days=30)

    # 1000 observed positives >= 500 required minimum
    assert eval_rep.readiness.status == ReadinessStatus.MEETS_MINIMUM_HISTORY


def test_data_sufficiency_summary_grain_threshold_unavailable():
    df = pd.DataFrame([
        {"domain": "a.com", "average_time_seconds": 15.0},
    ])
    mapping = ReportMapping(
        canonical_field_map={"domain": "domain"},
        row_grain=ReportRowGrain.SUMMARY,
    )
    report_data = ReportData(df=df, mapping=mapping)
    script = """
if time_on_screen > 10:
    return 10.0
return 1.0
"""
    suff = verify_data_sufficiency(script, report_data)
    assert not suff.is_sufficient
    assert any("Summary" in a or "summary" in a for a in suff.assumptions)
