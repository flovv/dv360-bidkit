"""Attention Fee-Stack & Bounded-Recall Break-Even Economics.

Quantifies:
1. All-in effective CPM and required per-impression yield lift to break even
   when stacking clearing CPM uplift, fixed pre-bid attention segments, SSP
   curation take rates, third-party AI fees, and agency fees.
2. Reach contraction and bounded quadratic recall lift calibrated to
   Simonov, Valletti & Veiga (Journal of Marketing Research, 2025):
       Recall(d) = 0.0747 * d - 0.0028 * d^2, saturated at d_max = 13.34s
   exposing the linear overstatement trap when forecasting attention ROI.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

# Simonov, Valletti & Veiga (JMR 2025) quadratic recall parameters
SIMONOV_RECALL_ALPHA = 0.0747
SIMONOV_RECALL_BETA = 0.0028
SIMONOV_SATURATION_SECONDS = SIMONOV_RECALL_ALPHA / (2.0 * SIMONOV_RECALL_BETA)  # ~13.339s


def bounded_quadratic_recall(dwell_seconds: float) -> float:
    """Computes bounded brand recall probability from cumulative dwell seconds.

    Uses Simonov et al. (2025): Recall(d) = 0.0747*d - 0.0028*d^2,
    capped at the empirical saturation peak (~13.34s) so recall never declines
    beyond saturation.
    """
    if dwell_seconds <= 0.0:
        return 0.0
    d = min(dwell_seconds, SIMONOV_SATURATION_SECONDS)
    return max(0.0, SIMONOV_RECALL_ALPHA * d - SIMONOV_RECALL_BETA * (d ** 2))


class AttentionFeeAnalysis(BaseModel):
    """Structured result of an attention fee-stack & bounded-recall analysis."""

    currency: str = "EUR"
    base_cpm: float
    clearing_cpm: float
    all_in_cpm: float
    fee_overhead_cpm: float
    total_fee_overhead_pct: float
    required_yield_lift_pct: float

    # Volume & reach impact for the given budget and frequency
    budget: float
    frequency: float
    base_impressions: float
    target_impressions: float
    base_reach: float
    target_reach: float
    reach_change_pct: float

    # Dwell & bounded recall vs. naive linear projection
    base_dwell_seconds: float
    target_dwell_seconds: float
    base_cumulative_dwell_seconds: float
    target_cumulative_dwell_seconds: float
    hits_recall_saturation: bool
    base_recall_rate: float
    target_recall_rate: float
    base_recalling_users: float
    target_recalling_users: float
    bounded_recall_lift_pct: float
    naive_linear_recall_lift_pct: float
    linear_overstatement_ratio: float | None = Field(
        default=None,
        description="Ratio of naive linear recall lift to bounded user-level recall lift.",
    )

    # Decision guidance
    verdict: Literal["VIABLE", "MARGINAL", "FEE_TRAP"]
    recommendation: str


def analyze_attention_fee_economics(
    *,
    base_cpm: float,
    cpm_uplift_pct: float = 15.0,
    prebid_cpm_fee: float = 0.0,
    curation_fee_pct: float = 0.0,
    ai_fee_pct: float = 0.0,
    agency_fee_pct: float = 0.0,
    budget: float = 100_000.0,
    frequency: float = 6.0,
    base_dwell_seconds: float = 1.10,
    target_dwell_seconds: float = 2.40,
    currency: str = "EUR",
) -> AttentionFeeAnalysis:
    """Models fee-stack compounding and bounded user-level recall economics.

    Parameters
    ----------
    base_cpm : float
        Baseline clearing CPM before attention steering (must be > 0).
    cpm_uplift_pct : float
        Expected clearing CPM increase (%) when bidding on higher-attention supply.
    prebid_cpm_fee : float
        Fixed CPM surcharge for 3P pre-bid attention segments (e.g. 0.25 display, 0.30 CTV).
    curation_fee_pct : float
        SSP curation take rate percentage (e.g. 11.0 for 11% median take rate).
    ai_fee_pct : float
        Third-party AI / custom-bidding vendor percentage fee (e.g. 6.0).
    agency_fee_pct : float
        Optional agency optimization percentage fee (e.g. 3.0).
    budget : float
        Fixed media budget used to evaluate reach contraction (must be > 0).
    frequency : float
        Average impression frequency per unique user (must be > 0).
    base_dwell_seconds : float
        Baseline average visual dwell per impression in seconds (must be > 0).
    target_dwell_seconds : float
        Expected average visual dwell per impression under attention steering (must be > 0).
    currency : str
        Currency code for display formatting (default: EUR).
    """
    if base_cpm <= 0:
        raise ValueError("base_cpm must be positive.")
    if budget <= 0:
        raise ValueError("budget must be positive.")
    if frequency <= 0:
        raise ValueError("frequency must be positive.")
    if base_dwell_seconds <= 0 or target_dwell_seconds <= 0:
        raise ValueError("base_dwell_seconds and target_dwell_seconds must be positive.")
    total_pct_take = curation_fee_pct + ai_fee_pct + agency_fee_pct
    if total_pct_take < 0 or total_pct_take >= 90.0:
        raise ValueError("Combined percentage fees must be in [0, 90).")
    if prebid_cpm_fee < 0:
        raise ValueError("prebid_cpm_fee must be non-negative.")

    clearing_cpm = base_cpm * (1.0 + cpm_uplift_pct / 100.0)
    # Standard ad-tech gross-up for percentage take rates + fixed pre-bid CPM surcharge
    all_in_cpm = (clearing_cpm / (1.0 - total_pct_take / 100.0)) + prebid_cpm_fee
    fee_overhead_cpm = all_in_cpm - clearing_cpm
    total_fee_overhead_pct = ((all_in_cpm / clearing_cpm) - 1.0) * 100.0
    required_yield_lift_pct = ((all_in_cpm / base_cpm) - 1.0) * 100.0

    # Fixed-budget volume & reach contraction
    base_impressions = (budget / base_cpm) * 1000.0
    target_impressions = (budget / all_in_cpm) * 1000.0
    base_reach = base_impressions / frequency
    target_reach = target_impressions / frequency
    reach_change_pct = ((target_reach / base_reach) - 1.0) * 100.0

    # Cumulative user-level dwell & Simonov et al. (2025) bounded recall
    base_cum_dwell = base_dwell_seconds * frequency
    target_cum_dwell = target_dwell_seconds * frequency
    hits_saturation = target_cum_dwell >= SIMONOV_SATURATION_SECONDS

    base_recall = bounded_quadratic_recall(base_cum_dwell)
    target_recall = bounded_quadratic_recall(target_cum_dwell)
    base_recalling_users = base_reach * base_recall
    target_recalling_users = target_reach * target_recall

    bounded_recall_lift_pct = (
        ((target_recalling_users / base_recalling_users) - 1.0) * 100.0
        if base_recalling_users > 0
        else 0.0
    )

    base_total_dwell = base_impressions * base_dwell_seconds
    target_total_dwell = target_impressions * target_dwell_seconds
    naive_linear_lift_pct = ((target_total_dwell / base_total_dwell) - 1.0) * 100.0

    overstatement_ratio: float | None = None
    if bounded_recall_lift_pct > 0.01:
        overstatement_ratio = round(naive_linear_lift_pct / bounded_recall_lift_pct, 2)

    # Verdict logic
    if required_yield_lift_pct <= 20.0 and bounded_recall_lift_pct > 0:
        verdict: Literal["VIABLE", "MARGINAL", "FEE_TRAP"] = "VIABLE"
        recommendation = (
            f"Fee load is disciplined (+{required_yield_lift_pct:.1f}% break-even hurdle). "
            "Validate incremental lift via a holdout or geo-lift test against a zero-fee native DV360 Python control arm."
        )
    elif required_yield_lift_pct <= 35.0 and bounded_recall_lift_pct > 0:
        verdict = "MARGINAL"
        recommendation = (
            f"Moderate fee hurdle (+{required_yield_lift_pct:.1f}% yield lift required to break even). "
            "Ensure curated deals replace redundant SSP hops (SPO) rather than stacking fees, or test a zero-fee DV360 concave Python script first."
        )
    else:
        verdict = "FEE_TRAP"
        recommendation = (
            f"High fee-stack hurdle (+{required_yield_lift_pct:.1f}% yield lift required; bounded recall lift is {bounded_recall_lift_pct:+.1f}%). "
            "Drop stacked vendor/curation fees on low-CPM display and deploy a zero-fee native DV360 Python custom bidding script with upstream MFA exclusions."
        )

    return AttentionFeeAnalysis(
        currency=currency.upper(),
        base_cpm=round(base_cpm, 4),
        clearing_cpm=round(clearing_cpm, 4),
        all_in_cpm=round(all_in_cpm, 4),
        fee_overhead_cpm=round(fee_overhead_cpm, 4),
        total_fee_overhead_pct=round(total_fee_overhead_pct, 2),
        required_yield_lift_pct=round(required_yield_lift_pct, 2),
        budget=round(budget, 2),
        frequency=round(frequency, 2),
        base_impressions=round(base_impressions, 1),
        target_impressions=round(target_impressions, 1),
        base_reach=round(base_reach, 1),
        target_reach=round(target_reach, 1),
        reach_change_pct=round(reach_change_pct, 2),
        base_dwell_seconds=round(base_dwell_seconds, 3),
        target_dwell_seconds=round(target_dwell_seconds, 3),
        base_cumulative_dwell_seconds=round(base_cum_dwell, 2),
        target_cumulative_dwell_seconds=round(target_cum_dwell, 2),
        hits_recall_saturation=hits_saturation,
        base_recall_rate=round(base_recall, 4),
        target_recall_rate=round(target_recall, 4),
        base_recalling_users=round(base_recalling_users, 1),
        target_recalling_users=round(target_recalling_users, 1),
        bounded_recall_lift_pct=round(bounded_recall_lift_pct, 2),
        naive_linear_recall_lift_pct=round(naive_linear_lift_pct, 2),
        linear_overstatement_ratio=overstatement_ratio,
        verdict=verdict,
        recommendation=recommendation,
    )
