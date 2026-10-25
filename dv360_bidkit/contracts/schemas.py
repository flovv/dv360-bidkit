"""Core Pydantic data schemas and contract definitions for dv360-bidkit."""

from __future__ import annotations

from enum import Enum
from typing import Any
import pandas as pd
from pydantic import BaseModel, Field, field_validator


class AggregationMode(str, Enum):
    SUM = "sum"
    MAX = "max"
    FIRST_MATCH = "first_match"


class RuleCondition(BaseModel):
    field: str
    operator: str = Field(description="Comparison operator, e.g. '==', '!=', 'in', '<', '>', '<=', '>='")
    value: Any

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        allowed = {"==", "!=", "<", "<=", ">", ">=", "in", "not in"}
        if v not in allowed:
            raise ValueError(f"Operator '{v}' is not supported. Must be one of {allowed}")
        return v


class Rule(BaseModel):
    id: str = Field(description="Stable unique rule identifier")
    description: str = ""
    conditions: list[RuleCondition] = Field(default_factory=list)
    score: float = Field(default=0.0, description="Score assigned when conditions match")
    weight: float = Field(default=1.0, description="Multiplier or weight")
    score_expression: str | None = Field(
        default=None,
        description="Optional DV360 DSL expression for dynamic/capped scores (e.g. '50.0 if val > 50.0 else val')",
    )


class RuleSet(BaseModel):
    schema_version: str = "1.0"
    aggregation_mode: AggregationMode = AggregationMode.FIRST_MATCH
    rules: list[Rule] = Field(default_factory=list)
    fallback_score: float = 0.0
    score_scale: float | None = Field(default=None, description="Explicit score scale multiplier")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportRowGrain(str, Enum):
    IMPRESSION = "impression"
    HOMOGENEOUS_AGGREGATE = "homogeneous_aggregate"
    SUMMARY = "summary"


class ReportMapping(BaseModel):
    canonical_field_map: dict[str, str] = Field(
        default_factory=dict,
        description="Map canonical field (e.g. 'impressions', 'domain', 'line_item_id') to report column name"
    )
    denominators: dict[str, str] = Field(
        default_factory=dict,
        description="Explicit denominator column map (e.g. 'viewable_impressions' -> 'measurable_impressions')"
    )
    row_grain: ReportRowGrain = ReportRowGrain.HOMOGENEOUS_AGGREGATE
    source: str = "DV360 Standard/ActiveView Report"
    date_window: str | None = None
    advertiser_scope: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class ReportData(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    df: pd.DataFrame
    mapping: ReportMapping
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def row_count(self) -> int:
        return len(self.df)


class InventoryEntityType(str, Enum):
    DOMAIN = "domain"
    SITE_ID = "site_id"
    APP_ID = "app_id"
    APP_BUNDLE = "app_bundle"
    STORE_URL = "store_url"


class InventoryAction(str, Enum):
    ANNOTATE = "annotate"
    SET_SCORE = "set_score"
    EXCLUDE_FROM_TRAINING = "exclude_from_training"
    TARGETING_BLOCK_REQUEST = "targeting_block_request"


class InventoryPolicyEntry(BaseModel):
    entity_type: InventoryEntityType
    entity_value: str
    action: InventoryAction
    source: str
    as_of: str
    namespace: str = "domain"
    label: str | None = None
    expiry: str | None = None
    score: float | None = None
    notes: str | None = None


class InventoryPolicyConfig(BaseModel):
    allow_subdomains: bool = Field(
        default=False,
        description="If True, boundary-aware parent domain matching is enabled (e.g. *.example.com matches example.com)"
    )
    strip_www: bool = Field(default=True, description="Strip 'www.' prefix when normalizing domain")
    web_only_domains: bool = Field(
        default=False,
        description="If True, domain exclusions/overrides are restricted to web environments (environment in [10, 11]) to prevent false blocks on CTV (device_type == 4) and In-App (environment == 12)."
    )
    unknown_action: str = Field(
        default="neutral_fallback",
        description="'neutral_fallback' lets ordinary rules score unknown inventory; 'allowlist_only' scores unmatched as unmatched_score"
    )
    unmatched_score: float | None = None
    unmatched_exclude: bool = Field(
        default=False,
        description="If True in allowlist_only mode, exclude unmatched entities from model training (return None)"
    )


class InventoryPolicy(BaseModel):
    entries: list[InventoryPolicyEntry] = Field(default_factory=list)
    config: InventoryPolicyConfig = Field(default_factory=InventoryPolicyConfig)
    normalization_metadata: dict[str, Any] = Field(default_factory=dict)


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Diagnostic(BaseModel):
    code: str
    severity: DiagnosticSeverity
    message: str
    rule_id: str | None = None
    line: int | None = None
    col: int | None = None
    evidence: str | None = None
    corrective_action: str | None = None


class LintReport(BaseModel):
    is_valid: bool
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    ast_summary: dict[str, Any] = Field(default_factory=dict)
    syntax_version: str = "2026.1"

    @property
    def has_errors(self) -> bool:
        return any(d.severity == DiagnosticSeverity.ERROR for d in self.diagnostics)

    @property
    def has_warnings(self) -> bool:
        return any(d.severity == DiagnosticSeverity.WARNING for d in self.diagnostics)


class MetricStatus(str, Enum):
    COMPUTED = "computed"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class MetricValue(BaseModel):
    status: MetricStatus
    value: float | None = None
    denominator_label: str | None = None
    assumption: str | None = None


class EvaluationMetrics(BaseModel):
    total_impressions: int = 0
    excluded_impressions: int = 0
    error_impressions: int = 0
    zero_score_impressions: int = 0
    positive_score_impressions: int = 0
    positive_rate_all: MetricValue = Field(
        default_factory=lambda: MetricValue(status=MetricStatus.UNAVAILABLE)
    )
    positive_rate_scored: MetricValue = Field(
        default_factory=lambda: MetricValue(status=MetricStatus.UNAVAILABLE)
    )
    weighted_mean: MetricValue = Field(
        default_factory=lambda: MetricValue(status=MetricStatus.UNAVAILABLE)
    )
    weighted_std: MetricValue = Field(
        default_factory=lambda: MetricValue(status=MetricStatus.UNAVAILABLE)
    )
    weighted_median: MetricValue = Field(
        default_factory=lambda: MetricValue(status=MetricStatus.UNAVAILABLE)
    )
    weighted_cv: MetricValue = Field(
        default_factory=lambda: MetricValue(status=MetricStatus.UNAVAILABLE)
    )
    gini_coefficient: MetricValue = Field(
        default_factory=lambda: MetricValue(status=MetricStatus.UNAVAILABLE),
        description="Weighted Gini inequality of score distribution (0 = uniform, 1 = concentrated)",
    )
    top_decile_share: MetricValue = Field(
        default_factory=lambda: MetricValue(status=MetricStatus.UNAVAILABLE),
        description="Fraction of total score mass accounted for by the top 10% highest-scoring impressions",
    )
    max_to_median_ratio: MetricValue = Field(
        default_factory=lambda: MetricValue(status=MetricStatus.UNAVAILABLE),
        description="Ratio of maximum score to positive median score (detects pacing-destabilizing spikes)",
    )
    min_score: float | None = None
    max_score: float | None = None
    distinct_score_count: int = 0


class ReadinessStatus(str, Enum):
    READINESS_UNKNOWN = "READINESS_UNKNOWN"
    MEETS_MINIMUM_HISTORY = "MEETS_MINIMUM_HISTORY"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    BELOW_SCORE_THRESHOLD = "BELOW_SCORE_THRESHOLD"


class ReadinessAssessment(BaseModel):
    status: ReadinessStatus = ReadinessStatus.READINESS_UNKNOWN
    verified_history_window_days: int | None = None
    required_advertiser_positives: int = 500
    observed_advertiser_positives: int = 0
    required_line_item_positives: int = 50
    observed_line_item_positives: dict[str, int] = Field(default_factory=dict)
    experimental_warnings: list[str] = Field(default_factory=list)
    source_reference: str = "Google Help S2: Custom Bidding Training Requirements (https://support.google.com/displayvideo/answer/9723477)"


class EvaluationReport(BaseModel):
    metrics: EvaluationMetrics = Field(default_factory=EvaluationMetrics)
    readiness: ReadinessAssessment = Field(default_factory=ReadinessAssessment)
    assumptions: list[str] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class ScriptBudgets(BaseModel):
    max_bytes: int = 65536
    max_chars: int = 65536
    max_ast_nodes: int = 5000
    max_rules: int = 10000


class CompilationResult(BaseModel):
    script_code: str
    ast_nodes: int
    byte_count: int
    char_count: int
    rule_count: int
    budgets_passed: bool
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class ArtifactManifest(BaseModel):
    manifest_version: str = "1.0"
    core_version: str = "0.1.1"
    pro_version: str | None = None
    profile_version: str | None = None
    registry_version: str = "2026.1"
    input_hashes: dict[str, str] = Field(default_factory=dict)
    output_hashes: dict[str, str] = Field(default_factory=dict)
    seed: int | None = None
    timestamp: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)
    normalized_config: dict[str, Any] = Field(default_factory=dict)
