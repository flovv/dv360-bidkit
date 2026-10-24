"""DV360 Custom Bidding signal and function registry.

Every signal/function records its signature, data type, applicability,
Google documentation reference, verification date, and status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SignalStatus(str, Enum):
    VERIFIED = "verified"
    DEPRECATED = "deprecated"
    UNVERIFIED = "unverified"


class SignalKind(str, Enum):
    DIMENSION = "dimension"
    FUNCTION = "function"
    AGGREGATION = "aggregation"
    CASTING = "casting"


class Applicability(str, Enum):
    ALL = "all"
    DISPLAY = "display"
    VIDEO = "video"
    CTV = "ctv"
    APP = "app"


@dataclass(frozen=True)
class SignalDefinition:
    name: str
    kind: SignalKind
    return_type: str
    applicability: Applicability = Applicability.ALL
    min_args: int = 0
    max_args: int = 0
    param_types: list[str] = field(default_factory=list)
    status: SignalStatus = SignalStatus.VERIFIED
    source_url: str = "https://support.google.com/displayvideo/answer/11967043"
    verification_date: str = "2026-01-15"
    deprecated_replacement: str | None = None
    notes: str = ""


# Default canonical registry version
REGISTRY_VERSION = "2026.1"

# Sourced registry of signals and built-in functions
SIGNAL_REGISTRY: dict[str, SignalDefinition] = {
    # Aggregation functions
    "sum_aggregate": SignalDefinition(
        name="sum_aggregate",
        kind=SignalKind.AGGREGATION,
        return_type="float",
        min_args=1,
        max_args=1,
        param_types=["list[tuple[list[bool], float]]"],
        status=SignalStatus.VERIFIED,
        notes="Evaluates all criteria. Sums the scores for which criteria evaluate to true.",
    ),
    "max_aggregate": SignalDefinition(
        name="max_aggregate",
        kind=SignalKind.AGGREGATION,
        return_type="float",
        min_args=1,
        max_args=1,
        param_types=["list[tuple[list[bool], float]]"],
        status=SignalStatus.VERIFIED,
        notes="Evaluates all criteria. Returns highest score among matched criteria.",
    ),
    "first_match_aggregate": SignalDefinition(
        name="first_match_aggregate",
        kind=SignalKind.AGGREGATION,
        return_type="float",
        min_args=1,
        max_args=1,
        param_types=["list[tuple[list[bool], float]]"],
        status=SignalStatus.VERIFIED,
        notes="Sequential evaluation: returns weight of the first criteria that evaluates to true.",
    ),

    # Casting functions
    "float": SignalDefinition(
        name="float",
        kind=SignalKind.CASTING,
        return_type="float",
        min_args=1,
        max_args=1,
        param_types=["Any"],
        status=SignalStatus.VERIFIED,
        notes="Casts expression to floating-point number.",
    ),
    "int": SignalDefinition(
        name="int",
        kind=SignalKind.CASTING,
        return_type="int",
        min_args=1,
        max_args=1,
        param_types=["Any"],
        status=SignalStatus.VERIFIED,
        notes="Casts expression to integer.",
    ),
    "str": SignalDefinition(
        name="str",
        kind=SignalKind.CASTING,
        return_type="str",
        min_args=1,
        max_args=1,
        param_types=["Any"],
        status=SignalStatus.VERIFIED,
        notes="Casts expression to string.",
    ),
    "bool": SignalDefinition(
        name="bool",
        kind=SignalKind.CASTING,
        return_type="bool",
        min_args=1,
        max_args=1,
        param_types=["Any"],
        status=SignalStatus.VERIFIED,
        notes="Casts expression to boolean.",
    ),

    # Conversion functions (Floodlight)
    "total_conversion_count": SignalDefinition(
        name="total_conversion_count",
        kind=SignalKind.FUNCTION,
        return_type="float",
        min_args=2,
        max_args=2,
        param_types=["int", "int"],
        status=SignalStatus.VERIFIED,
        notes="Returns count of conversions for floodlight activity ID and attribution model ID (0=default last touch).",
    ),
    "total_conversion_value": SignalDefinition(
        name="total_conversion_value",
        kind=SignalKind.FUNCTION,
        return_type="float",
        min_args=2,
        max_args=2,
        param_types=["int", "int"],
        status=SignalStatus.VERIFIED,
        notes="Returns total monetary revenue from Floodlight sales activity and attribution model ID.",
    ),
    "total_conversion_quantity": SignalDefinition(
        name="total_conversion_quantity",
        kind=SignalKind.FUNCTION,
        return_type="float",
        min_args=2,
        max_args=2,
        param_types=["int", "int"],
        status=SignalStatus.VERIFIED,
        notes="Returns total transaction item quantity for Floodlight activity ID and attribution model ID.",
    ),
    "conversion_custom_variable": SignalDefinition(
        name="conversion_custom_variable",
        kind=SignalKind.FUNCTION,
        return_type="str",
        min_args=3,
        max_args=3,
        param_types=["int", "int", "int"],
        status=SignalStatus.VERIFIED,
        notes="Returns string value of Floodlight custom variable (u-index) for given activity and model ID.",
    ),

    # Google Analytics 4
    "ga4_conversions_count": SignalDefinition(
        name="ga4_conversions_count",
        kind=SignalKind.FUNCTION,
        return_type="int",
        min_args=2,
        max_args=2,
        param_types=["int", "str"],
        status=SignalStatus.VERIFIED,
        notes="Returns count of GA4 conversion events for property_id and conversion_event_name.",
    ),

    # Built-in Dimensions / Signals
    "device_type": SignalDefinition(
        name="device_type",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="Device category: 0=Desktop, 1=Other, 2=Smartphone, 3=Tablet, 4=Connected TV, 5=Smart TV, 6=Set top box.",
    ),
    "environment": SignalDefinition(
        name="environment",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="Serving environment: 10=Web, 11=App, 12=Other.",
    ),
    "country_code": SignalDefinition(
        name="country_code",
        kind=SignalKind.DIMENSION,
        return_type="str",
        notes="Two-letter ISO 3166-1 country code (e.g. 'US', 'DE', 'GB').",
    ),
    "domain": SignalDefinition(
        name="domain",
        kind=SignalKind.DIMENSION,
        return_type="str",
        applicability=Applicability.DISPLAY,
        notes="Normalized domain/site hostname. Not available for Connected TV (CTV requires site_id).",
    ),
    "site_id": SignalDefinition(
        name="site_id",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="DV360 site identifier. Required for Connected TV app inventory.",
    ),
    "exchange_id": SignalDefinition(
        name="exchange_id",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="Ad exchange ID.",
    ),
    "line_item_id": SignalDefinition(
        name="line_item_id",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="DV360 Line Item ID.",
    ),
    "advertiser_id": SignalDefinition(
        name="advertiser_id",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="DV360 Advertiser ID.",
    ),
    "campaign_id": SignalDefinition(
        name="campaign_id",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="DV360 Campaign ID.",
    ),
    "partner_id": SignalDefinition(
        name="partner_id",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="DV360 Partner ID.",
    ),
    "channel_id": SignalDefinition(
        name="channel_id",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="DV360 Channel ID.",
    ),
    "os_id": SignalDefinition(
        name="os_id",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="Operating System ID.",
    ),
    "inventory_source_id": SignalDefinition(
        name="inventory_source_id",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="Inventory Source / Deal ID.",
    ),
    "day_of_week": SignalDefinition(
        name="day_of_week",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="Day of the week (0=Sunday .. 6=Saturday).",
    ),
    "hour_of_day": SignalDefinition(
        name="hour_of_day",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="Hour of day (0..23) in browser-local timezone.",
    ),
    "browser_reportable_id": SignalDefinition(
        name="browser_reportable_id",
        kind=SignalKind.DIMENSION,
        return_type="int",
        notes="Reportable web browser identifier in DV360.",
    ),
    "click": SignalDefinition(
        name="click",
        kind=SignalKind.DIMENSION,
        return_type="bool",
        notes="Whether the impression led to a user click.",
    ),

    # Deprecated signals
    "browser_id": SignalDefinition(
        name="browser_id",
        kind=SignalKind.DIMENSION,
        return_type="int",
        status=SignalStatus.DEPRECATED,
        deprecated_replacement="browser_reportable_id",
        notes="Deprecated by Google in newer custom bidding API releases. Use browser_reportable_id.",
    ),
    "has_ga_goal": SignalDefinition(
        name="has_ga_goal",
        kind=SignalKind.FUNCTION,
        return_type="bool",
        min_args=2,
        max_args=2,
        param_types=["int", "int"],
        status=SignalStatus.DEPRECATED,
        deprecated_replacement="ga4_conversions_count",
        notes="Universal Analytics is deprecated. Migrate to ga4_conversions_count with GA4 property ID and event name.",
    ),
    "ga_goals_count": SignalDefinition(
        name="ga_goals_count",
        kind=SignalKind.FUNCTION,
        return_type="int",
        min_args=2,
        max_args=2,
        param_types=["int", "int"],
        status=SignalStatus.DEPRECATED,
        deprecated_replacement="ga4_conversions_count",
        notes="Universal Analytics is deprecated. Migrate to ga4_conversions_count.",
    ),
    "conversion_variable_str": SignalDefinition(
        name="conversion_variable_str",
        kind=SignalKind.FUNCTION,
        return_type="str",
        min_args=2,
        max_args=2,
        param_types=["int", "int"],
        status=SignalStatus.DEPRECATED,
        deprecated_replacement="conversion_custom_variable",
        notes="Use conversion_custom_variable(floodlight_activity_id, model_id, u_variable_index).",
    ),
}


def get_signal_definition(name: str) -> SignalDefinition | None:
    """Retrieve signal definition from registry if exists."""
    return SIGNAL_REGISTRY.get(name)


def is_valid_signal(name: str) -> bool:
    """Check if identifier is recognized in signal registry."""
    return name in SIGNAL_REGISTRY
