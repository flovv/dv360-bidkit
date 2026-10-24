"""Synthetic fixtures, benchmark datasets, and demo generators for DV360 Custom Bidding."""

from __future__ import annotations

import random
from pathlib import Path
import pandas as pd

from dv360_bidkit.contracts.schemas import (
    AggregationMode,
    InventoryAction,
    InventoryEntityType,
    InventoryPolicy,
    InventoryPolicyConfig,
    InventoryPolicyEntry,
    ReportMapping,
    ReportRowGrain,
    Rule,
    RuleCondition,
    RuleSet,
)


def generate_synthetic_display_report(
    num_rows: int = 50,
    seed: int = 42,
) -> pd.DataFrame:
    """Generates a synthetic DV360 standard display performance report.

    Guarantees strict denominator consistency: 0 <= viewable <= measurable <= impressions.
    """
    rng = random.Random(seed)

    domains = [
        "spiegel.de", "zeit.de", "bild.de", "faz.net", "sueddeutsche.de",
        "nytimes.com", "wsj.com", "theguardian.com", "bbc.co.uk", "cnn.com",
        "techcrunch.com", "theverge.com", "wired.com", "reuters.com", "bloomberg.com",
        "weather.com", "forbes.com", "cnet.com", "vox.com", "ign.com",
    ]

    line_items = [10101, 10102, 10103]

    rows = []
    for i in range(num_rows):
        domain = rng.choice(domains)
        li_id = rng.choice(line_items)
        device = rng.choice([1, 2, 3])  # 1=Desktop, 2=Smartphone, 3=Tablet
        env = rng.choice([1, 2])        # 1=Web, 2=App

        impressions = rng.randint(200, 5000)
        # Measurable is between 70% and 95% of impressions
        meas_rate = rng.uniform(0.70, 0.95)
        measurable = int(impressions * meas_rate)

        # Viewable is between 40% and 85% of measurable
        view_rate = rng.uniform(0.40, 0.85)
        viewable = int(measurable * view_rate)

        clicks = rng.randint(0, int(impressions * 0.02))
        convs = rng.randint(0, max(1, int(clicks * 0.1)))

        rows.append({
            "Date": "2026-01-15",
            "Advertiser ID": 990011,
            "Line Item ID": li_id,
            "App/URL": domain,
            "Device Type": device,
            "Environment": env,
            "Impressions": impressions,
            "Active View: Measurable Impressions": measurable,
            "Active View: Viewable Impressions": viewable,
            "Clicks": clicks,
            "Total Conversions": convs,
        })

    return pd.DataFrame(rows)


def create_sample_mapping() -> ReportMapping:
    """Returns canonical ReportMapping for synthetic display reports."""
    return ReportMapping(
        canonical_field_map={
            "impressions": "Impressions",
            "measurable_impressions": "Active View: Measurable Impressions",
            "viewable_impressions": "Active View: Viewable Impressions",
            "domain": "App/URL",
            "device_type": "Device Type",
            "environment": "Environment",
            "line_item_id": "Line Item ID",
            "advertiser_id": "Advertiser ID",
            "clicks": "Clicks",
        },
        denominators={
            "viewable_impressions": "measurable_impressions",
            "measurable_impressions": "impressions",
        },
        row_grain=ReportRowGrain.HOMOGENEOUS_AGGREGATE,
        source="Synthetic DV360 ActiveView Report",
        date_window="30d",
        advertiser_scope="Advertiser 990011",
    )


def create_sample_ruleset() -> RuleSet:
    """Returns a sample production RuleSet demonstrating DV360 first-match logic."""
    return RuleSet(
        schema_version="1.0",
        aggregation_mode=AggregationMode.FIRST_MATCH,
        rules=[
            Rule(
                id="high_value_news",
                description="High value tier publishers",
                conditions=[
                    RuleCondition(field="domain", operator="in", value=["spiegel.de", "zeit.de", "faz.net"])
                ],
                score=10.0,
                weight=1.0,
            ),
            Rule(
                id="tech_publishers",
                description="Technology vertical sites",
                conditions=[
                    RuleCondition(field="domain", operator="in", value=["wired.com", "theverge.com", "techcrunch.com"])
                ],
                score=7.5,
                weight=1.0,
            ),
            Rule(
                id="mobile_app_premium",
                description="Mobile App impressions",
                conditions=[
                    RuleCondition(field="device_type", operator="==", value=2),
                    RuleCondition(field="environment", operator="==", value=2),
                ],
                score=5.0,
                weight=1.0,
            ),
        ],
        fallback_score=0.0,
        score_scale=1.0,
        metadata={"author": "DV360 BidKit Team", "objective": "Viewability & Domain Tiering"},
    )


def create_sample_inventory_policy() -> InventoryPolicy:
    """Returns a sample customer InventoryPolicy with score overrides and training exclusions."""
    entries = [
        InventoryPolicyEntry(
            entity_type=InventoryEntityType.DOMAIN,
            entity_value="junkdomain.com",
            action=InventoryAction.EXCLUDE_FROM_TRAINING,
            source="Agency Fraud/MFA Audit",
            as_of="2026-01-01",
            label="MFA Disclosed",
            notes="Excluded from custom bidding training",
        ),
        InventoryPolicyEntry(
            entity_type=InventoryEntityType.DOMAIN,
            entity_value="partner-showcase.com",
            action=InventoryAction.SET_SCORE,
            source="Direct Deal Contract",
            as_of="2026-01-01",
            score=20.0,
            notes="Direct deal score override",
        ),
    ]
    return InventoryPolicy(
        entries=entries,
        config=InventoryPolicyConfig(allow_subdomains=True, strip_www=True),
    )
