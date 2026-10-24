"""Diagnostic and pre-flight evaluation engine for DV360 Custom Bidding scripts.

Computes weighted score distribution statistics, Gini inequality, top-decile
concentration, max-to-median ratio, and evaluates Google S2 training readiness
(minimum 500 positives per advertiser, 50 per active line item over verified 30 days).
Strictly couples data sufficiency to evaluation and isolates advertiser scopes.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
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
    if len(values) == 0:
        return 0.0
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
    # Invariant: identical scores have zero inequality
    if np.all(values == values[0]) or np.max(values) == np.min(values):
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

    # Include origin (0, 0) for proper Lorenz curve integration
    cum_w_norm = np.insert(cum_weights / total_weight, 0, 0.0)
    cum_v_norm = np.insert(cum_weighted_values / total_val, 0, 0.0)

    trapz_fn = getattr(np, "trapezoid", getattr(np, "trapz", None))
    if trapz_fn is not None:
        b_area = float(trapz_fn(cum_v_norm, cum_w_norm))
    else:
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
    accum_weight = 0.0
    top_mass = 0.0

    for val, w in zip(sorted_values, sorted_weights):
        remaining_needed = target_weight - accum_weight
        if remaining_needed <= 0:
            break
        take_w = min(w, remaining_needed)
        top_mass += float(val) * take_w
        accum_weight += take_w

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
    line_item_positives: dict[str, int] = {}
    if has_line_items:
        # Initialize ALL line items present in dataset with 0 positives
        for li_val in df[li_col].dropna().unique():
            line_item_positives[str(li_val)] = 0

    # Advertiser column for multi-advertiser isolation
    adv_col = mapping.canonical_field_map.get("advertiser_id", "advertiser_id")
    has_advertisers = adv_col in df.columns
    advertiser_positives: dict[str, int] = {}
    if has_advertisers:
        for adv_val in df[adv_col].dropna().unique():
            advertiser_positives[str(adv_val)] = 0

    total_imp = 0
    excluded_imp = 0
    error_imp = 0
    zero_imp = 0
    positive_imp = 0

    scored_values: list[float] = []
    scored_weights: list[float] = []
    positive_values: list[float] = []
    positive_weights: list[float] = []

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

            if has_line_items and li_col in row_dict and row_dict[li_col] is not None:
                li_id = str(row_dict[li_col])
                line_item_positives[li_id] = line_item_positives.get(li_id, 0) + weight

            if has_advertisers and adv_col in row_dict and row_dict[adv_col] is not None:
                adv_id = str(row_dict[adv_col])
                advertiser_positives[adv_id] = advertiser_positives.get(adv_id, 0) + weight

    # Metric computations
    metrics = EvaluationMetrics(
        total_impressions=total_imp,
        excluded_impressions=excluded_imp,
        error_impressions=error_imp,
        zero_score_impressions=zero_imp,
        positive_score_impressions=positive_imp,
    )

    is_sufficient = coverage_report.is_sufficient

    # Positive rates
    if total_imp > 0 and is_sufficient:
        metrics.positive_rate_all = MetricValue(
            status=MetricStatus.COMPUTED,
            value=positive_imp / total_imp,
            denominator_label="total_supplied_impressions",
        )
    else:
        metrics.positive_rate_all = MetricValue(
            status=MetricStatus.UNAVAILABLE,
            denominator_label="total_supplied_impressions",
            assumption="No impressions supplied or data sufficiency failed",
        )

    scored_imp = total_imp - excluded_imp - error_imp
    if scored_imp > 0 and is_sufficient:
        metrics.positive_rate_scored = MetricValue(
            status=MetricStatus.COMPUTED,
            value=positive_imp / scored_imp,
            denominator_label="successfully_scored_impressions",
        )
    else:
        metrics.positive_rate_scored = MetricValue(
            status=MetricStatus.UNAVAILABLE,
            denominator_label="successfully_scored_impressions",
            assumption="No successfully scored impressions or data sufficiency failed",
        )

    # Distribution statistics on scored impressions
    # Strict Coupling: if data sufficiency check failed, do not produce exact-looking computed metrics
    if scored_values and scored_imp > 0 and is_sufficient:
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
        reason = (
            coverage_report.assumptions[0]
            if coverage_report.assumptions
            else ("Errors encountered during evaluation" if error_imp > 0 else "Insufficient data")
        )
        metrics.weighted_mean = MetricValue(status=MetricStatus.UNAVAILABLE, assumption=reason)
        metrics.weighted_std = MetricValue(status=MetricStatus.UNAVAILABLE, assumption=reason)
        metrics.weighted_cv = MetricValue(status=MetricStatus.UNAVAILABLE, assumption=reason)
        metrics.gini_coefficient = MetricValue(status=MetricStatus.UNAVAILABLE, assumption=reason)
        metrics.top_decile_share = MetricValue(status=MetricStatus.UNAVAILABLE, assumption=reason)

    # Positive median and Max-to-Median ratio
    if positive_values and positive_imp > 0 and is_sufficient:
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
            assumption="No positive scores observed or data sufficiency failed",
        )
        metrics.max_to_median_ratio = MetricValue(status=MetricStatus.UNAVAILABLE)

    # Readiness Assessment (Google S2 specification)
    readiness = ReadinessAssessment(
        observed_advertiser_positives=positive_imp,
        observed_line_item_positives=line_item_positives,
    )

    # Strict date window verification
    is_window_verified = False
    verified_days = 0

    if history_window_days is not None and history_window_days >= 30:
        is_window_verified = True
        verified_days = history_window_days
    elif mapping.date_window is not None:
        dw_str = str(mapping.date_window).strip().lower()
        date_matches = re.findall(r"\d{4}-\d{2}-\d{2}", dw_str)
        if len(date_matches) >= 2:
            try:
                d1 = datetime.strptime(date_matches[0], "%Y-%m-%d")
                d2 = datetime.strptime(date_matches[1], "%Y-%m-%d")
                diff_days = abs((d2 - d1).days) + 1
                if diff_days >= 30:
                    is_window_verified = True
                    verified_days = diff_days
            except Exception:
                pass
        elif any(f"{d}d" in dw_str or f"{d} days" in dw_str for d in range(30, 91)):
            is_window_verified = True
            verified_days = 30

    if not is_window_verified or not is_sufficient:
        readiness.status = ReadinessStatus.READINESS_UNKNOWN
        readiness.verified_history_window_days = None
        if not is_sufficient:
            readiness.experimental_warnings.append(
                "Data sufficiency check failed; readiness returned as READINESS_UNKNOWN."
            )
        else:
            readiness.experimental_warnings.append(
                f"Date window '{mapping.date_window}' could not be verified as a minimum 30-day lookback window; readiness returned as READINESS_UNKNOWN."
            )
    else:
        readiness.verified_history_window_days = verified_days

        # Check advertiser minimums (>= 500 per advertiser, no pooling!)
        adv_failed = False
        if mapping.advertiser_scope:
            target_adv = str(mapping.advertiser_scope)
            obs_cnt = advertiser_positives.get(target_adv, positive_imp)
            if obs_cnt < readiness.required_advertiser_positives:
                adv_failed = True
                readiness.status = ReadinessStatus.INSUFFICIENT_HISTORY
                diagnostics.append(
                    Diagnostic(
                        code="READINESS_ADVERTISER_MINIMUM_UNMET",
                        severity=DiagnosticSeverity.WARNING,
                        message=f"Scoped advertiser '{target_adv}' observed {obs_cnt} positive impressions, below required {readiness.required_advertiser_positives}.",
                        corrective_action="Broaden rule criteria or extend history window before training model.",
                    )
                )
        elif len(advertiser_positives) > 1:
            # Multi-advertiser dataset without advertiser scope: EACH advertiser must meet 500
            failing_advs = [
                adv for adv, cnt in advertiser_positives.items()
                if cnt < readiness.required_advertiser_positives
            ]
            if failing_advs:
                adv_failed = True
                readiness.status = ReadinessStatus.INSUFFICIENT_HISTORY
                diagnostics.append(
                    Diagnostic(
                        code="READINESS_ADVERTISER_MINIMUM_UNMET",
                        severity=DiagnosticSeverity.WARNING,
                        message=(
                            f"Multiple advertisers present without scope isolation. {len(failing_advs)} advertiser(s) "
                            f"have fewer than 500 positive impressions (cannot pool across advertisers)."
                        ),
                        corrective_action="Specify single advertiser scope in mapping.",
                    )
                )
        elif positive_imp < readiness.required_advertiser_positives:
            adv_failed = True
            readiness.status = ReadinessStatus.INSUFFICIENT_HISTORY
            diagnostics.append(
                Diagnostic(
                    code="READINESS_ADVERTISER_MINIMUM_UNMET",
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Observed {positive_imp} positive impressions in window, below DV360 required minimum of {readiness.required_advertiser_positives} per advertiser.",
                    corrective_action="Broaden rule criteria or extend history window before training model.",
                )
            )

        if not adv_failed:
            # Check line items: each active line item must have >= 50
            unmet_lis = [
                li for li, cnt in line_item_positives.items()
                if cnt < readiness.required_line_item_positives
            ]
            if unmet_lis:
                readiness.status = ReadinessStatus.BELOW_SCORE_THRESHOLD
                readiness.experimental_warnings.append(
                    f"{len(unmet_lis)} active line item(s) have fewer than {readiness.required_line_item_positives} positive impressions: {', '.join(unmet_lis)}."
                )
            else:
                readiness.status = ReadinessStatus.MEETS_MINIMUM_HISTORY

    return EvaluationReport(
        metrics=metrics,
        readiness=readiness,
        assumptions=assumptions,
        coverage=coverage_report.model_dump(),
        errors=errors,
        diagnostics=diagnostics,
    )
