"""Diagnostics and readiness assessment for DV360 Custom Bidding simulations.

Computes weighted impression score distributions, positive score fractions,
Gini / weighted quantiles, and checks minimum history readiness criteria
against Google DV360 specification S2 (500 positives per advertiser, 50 per line item).
"""

from __future__ import annotations

import math
from typing import Any
import numpy as np

from dv360_bidkit.contracts.schemas import (
    Diagnostic,
    DiagnosticSeverity,
    EvaluationMetrics,
    EvaluationReport,
    MetricStatus,
    MetricValue,
    ReadinessAssessment,
    ReadinessStatus,
    ReportData,
)
from dv360_bidkit.evaluator.coverage import verify_data_sufficiency
from dv360_bidkit.evaluator.interpreter import create_interpreter


def compute_weighted_quantile(
    values: np.ndarray,
    weights: np.ndarray,
    quantile: float,
) -> float:
    """Computes weighted quantile for 1D arrays."""
    sorter = np.argsort(values)
    sorted_values = values[sorter]
    sorted_weights = weights[sorter]

    cum_weights = np.cumsum(sorted_weights)
    cutoff = quantile * cum_weights[-1]
    idx = np.searchsorted(cum_weights, cutoff)
    idx = min(idx, len(sorted_values) - 1)
    return float(sorted_values[idx])


def compute_weighted_gini(values: np.ndarray, weights: np.ndarray) -> float:
    """Computes weighted Gini coefficient for 1D arrays."""
    if len(values) == 0:
        return 0.0
    sorter = np.argsort(values)
    sorted_values = values[sorter]
    sorted_weights = weights[sorter]

    cum_weights = np.cumsum(sorted_weights)
    total_weight = cum_weights[-1]
    if total_weight <= 0:
        return 0.0

    cum_weighted_values = np.cumsum(sorted_values * sorted_weights)
    total_val = cum_weighted_values[-1]
    if total_val <= 0:
        return 0.0

    cum_w_norm = cum_weights / total_weight
    cum_v_norm = cum_weighted_values / total_val

    trapz_fn = getattr(np, "trapezoid", getattr(np, "trapz", None))
    if trapz_fn is not None:
        b_area = float(trapz_fn(cum_v_norm, cum_w_norm))
    else:
        # manual trapezoidal integration fallback
        dx = np.diff(cum_w_norm)
        b_area = float(np.sum(dx * (cum_v_norm[:-1] + cum_v_norm[1:]) / 2.0))

    gini = 1.0 - 2.0 * b_area
    return float(np.clip(gini, 0.0, 1.0))


def compute_top_decile_share(values: np.ndarray, weights: np.ndarray) -> float:
    """Computes fraction of total score mass accounted for by the top 10% highest-scoring impressions."""
    if len(values) == 0:
        return 0.0
    sorter = np.argsort(values)[::-1]
    sorted_values = values[sorter]
    sorted_weights = weights[sorter]

    total_weight = float(np.sum(sorted_weights))
    total_mass = float(np.sum(sorted_values * sorted_weights))
    if total_weight <= 0 or total_mass <= 0:
        return 0.0

    target_weight = 0.10 * total_weight
    cum_weights = np.cumsum(sorted_weights)
    idx = int(np.searchsorted(cum_weights, target_weight))
    idx = min(idx, len(sorted_values) - 1)

    top_mass = float(np.sum(sorted_values[: idx + 1] * sorted_weights[: idx + 1]))
    return float(np.clip(top_mass / total_mass, 0.0, 1.0))


def evaluate_script(
    code: str,
    data: ReportData,
    *,
    history_window_days: int | None = None,
) -> EvaluationReport:
    """Evaluates a DV360 Custom Bidding script against a customer report dataset.

    Parameters
    ----------
    code : str
        The custom bidding script source text.
    data : ReportData
        The customer report data and column mapping.
    history_window_days : int | None
        Optional history window in days. If provided, enables readiness assessment.

    Returns
    -------
    EvaluationReport
        Detailed impression score metrics, coverage, and readiness assessment.
    """
    coverage_report = verify_data_sufficiency(code, data)
    assumptions = list(coverage_report.assumptions)
    diagnostics: list[Diagnostic] = []
    errors: list[str] = []

    interpreter = create_interpreter(code)
    df = data.df
    mapping = data.mapping

    # Determine impression weight column
    imp_col = mapping.canonical_field_map.get("impressions", "impressions")
    has_weights = imp_col in df.columns

    # Line item column for readiness check
    li_col = mapping.canonical_field_map.get("line_item_id", "line_item_id")
    has_line_items = li_col in df.columns

    total_imp = 0
    excluded_imp = 0
    error_imp = 0
    zero_imp = 0
    positive_imp = 0

    scored_values: list[float] = []
    scored_weights: list[float] = []
    positive_values: list[float] = []
    positive_weights: list[float] = []

    line_item_positives: dict[str, int] = {}

    # Iterate rows and evaluate AST
    for idx, row in df.iterrows():
        # Build context from row
        row_dict = row.to_dict()
        # Add canonical field aliases
        for canonical, col in mapping.canonical_field_map.items():
            if col in row_dict:
                row_dict[canonical] = row_dict[col]

        weight = int(row_dict[imp_col]) if has_weights and row_dict[imp_col] is not None else 1
        if weight <= 0:
            continue

        total_imp += weight
        res = interpreter.evaluate(row_dict)

        if res.error:
            error_imp += weight
            if len(errors) < 10:
                errors.append(f"Row {idx}: {res.error}")
            continue

        if res.is_excluded or res.score is None:
            excluded_imp += weight
            continue

        score = res.score
        scored_values.append(score)
        scored_weights.append(weight)

        if score == 0.0:
            zero_imp += weight
        elif score > 0.0:
            positive_imp += weight
            positive_values.append(score)
            positive_weights.append(weight)

            if has_line_items and li_col in row_dict:
                li_id = str(row_dict[li_col])
                line_item_positives[li_id] = line_item_positives.get(li_id, 0) + weight

    # Metric computations
    metrics = EvaluationMetrics(
        total_impressions=total_imp,
        excluded_impressions=excluded_imp,
        error_impressions=error_imp,
        zero_score_impressions=zero_imp,
        positive_score_impressions=positive_imp,
    )

    # Positive rates
    if total_imp > 0:
        metrics.positive_rate_all = MetricValue(
            status=MetricStatus.COMPUTED,
            value=positive_imp / total_imp,
            denominator_label="total_supplied_impressions",
        )
    else:
        metrics.positive_rate_all = MetricValue(
            status=MetricStatus.UNAVAILABLE,
            denominator_label="total_supplied_impressions",
            assumption="No impressions supplied",
        )

    scored_imp = total_imp - excluded_imp - error_imp
    if scored_imp > 0:
        metrics.positive_rate_scored = MetricValue(
            status=MetricStatus.COMPUTED,
            value=positive_imp / scored_imp,
            denominator_label="successfully_scored_impressions",
        )
    else:
        metrics.positive_rate_scored = MetricValue(
            status=MetricStatus.UNAVAILABLE,
            denominator_label="successfully_scored_impressions",
            assumption="No successfully scored impressions",
        )

    # Distribution statistics on scored impressions
    if scored_values and scored_imp > 0:
        val_arr = np.array(scored_values, dtype=float)
        wt_arr = np.array(scored_weights, dtype=float)

        w_mean = float(np.average(val_arr, weights=wt_arr))
        w_var = float(np.average((val_arr - w_mean) ** 2, weights=wt_arr))
        w_std = math.sqrt(max(0.0, w_var))

        metrics.weighted_mean = MetricValue(status=MetricStatus.COMPUTED, value=w_mean)
        metrics.weighted_std = MetricValue(status=MetricStatus.COMPUTED, value=w_std)
        metrics.min_score = float(np.min(val_arr))
        metrics.max_score = float(np.max(val_arr))
        metrics.distinct_score_count = len(np.unique(val_arr))

        if w_mean > 0:
            metrics.weighted_cv = MetricValue(status=MetricStatus.COMPUTED, value=w_std / w_mean)
        else:
            metrics.weighted_cv = MetricValue(
                status=MetricStatus.UNAVAILABLE,
                assumption="Mean is zero or negative; CV undefined",
            )

        # Gini inequality and concentration
        w_gini = compute_weighted_gini(val_arr, wt_arr)
        metrics.gini_coefficient = MetricValue(status=MetricStatus.COMPUTED, value=round(w_gini, 4))

        top_share = compute_top_decile_share(val_arr, wt_arr)
        metrics.top_decile_share = MetricValue(status=MetricStatus.COMPUTED, value=round(top_share, 4))
    else:
        metrics.weighted_mean = MetricValue(status=MetricStatus.UNAVAILABLE)
        metrics.weighted_std = MetricValue(status=MetricStatus.UNAVAILABLE)
        metrics.weighted_cv = MetricValue(status=MetricStatus.UNAVAILABLE)
        metrics.gini_coefficient = MetricValue(status=MetricStatus.UNAVAILABLE)
        metrics.top_decile_share = MetricValue(status=MetricStatus.UNAVAILABLE)

    # Positive median and Max-to-Median ratio
    if positive_values and positive_imp > 0:
        pos_val_arr = np.array(positive_values, dtype=float)
        pos_wt_arr = np.array(positive_weights, dtype=float)
        p_med = compute_weighted_quantile(pos_val_arr, pos_wt_arr, 0.5)
        metrics.weighted_median = MetricValue(
            status=MetricStatus.COMPUTED,
            value=p_med,
            denominator_label="positive_impressions",
        )
        if p_med > 0 and metrics.max_score is not None:
            ratio = float(metrics.max_score / p_med)
            metrics.max_to_median_ratio = MetricValue(status=MetricStatus.COMPUTED, value=round(ratio, 2))
            if ratio > 20.0:
                diagnostics.append(
                    Diagnostic(
                        code="SCORE_VARIANCE_INFLATION",
                        severity=DiagnosticSeverity.WARNING,
                        message=f"Max-to-median score ratio ({ratio:.1f}x) exceeds recommended threshold (20x). Outlier scores can destabilize DSP pacing controllers and cause bid starvation.",
                        corrective_action="Cap maximum conversion/quality rewards or apply log scaling.",
                    )
                )
    else:
        metrics.weighted_median = MetricValue(
            status=MetricStatus.UNAVAILABLE,
            denominator_label="positive_impressions",
            assumption="No positive scores observed",
        )
        metrics.max_to_median_ratio = MetricValue(status=MetricStatus.UNAVAILABLE)

    # Readiness Assessment (Google S2 specification)
    readiness = ReadinessAssessment(
        observed_advertiser_positives=positive_imp,
        observed_line_item_positives=line_item_positives,
    )

    if history_window_days is not None or mapping.date_window is not None:
        readiness.verified_history_window_days = history_window_days or 30
        if positive_imp < readiness.required_advertiser_positives:
            readiness.status = ReadinessStatus.INSUFFICIENT_HISTORY
            diagnostics.append(
                Diagnostic(
                    code="READINESS_ADVERTISER_MINIMUM_UNMET",
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Observed {positive_imp} positive impressions in window, below DV360 required minimum of {readiness.required_advertiser_positives} per advertiser (Google S2).",
                    corrective_action="Broaden rule criteria or extend history window before training model.",
                )
            )
        else:
            # Check line items if present
            unmet_lis = [li for li, cnt in line_item_positives.items() if cnt < readiness.required_line_item_positives]
            if unmet_lis:
                readiness.status = ReadinessStatus.BELOW_SCORE_THRESHOLD
                readiness.experimental_warnings.append(
                    f"{len(unmet_lis)} line item(s) have fewer than {readiness.required_line_item_positives} positive impressions."
                )
            else:
                readiness.status = ReadinessStatus.MEETS_MINIMUM_HISTORY
    else:
        readiness.status = ReadinessStatus.READINESS_UNKNOWN
        readiness.experimental_warnings.append(
            "Date window/history scope not established; readiness returned as READINESS_UNKNOWN."
        )

    return EvaluationReport(
        metrics=metrics,
        readiness=readiness,
        assumptions=assumptions,
        coverage=coverage_report.model_dump(),
        errors=errors,
        diagnostics=diagnostics,
    )
