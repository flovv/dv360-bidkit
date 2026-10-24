"""dv360-bidkit: DV360 Custom Bidding DSL Linter, Pre-Flight Simulator, and Rule Compiler."""

from dv360_bidkit.compiler.scripts import compile_script
from dv360_bidkit.contracts.exceptions import (
    BidkitError,
    BudgetExceededError,
    CompilationError,
    CompressionBudgetError,
    DataSufficiencyError,
    EvaluationError,
    InventoryPolicyError,
    LintError,
    ReportMappingError,
)
from dv360_bidkit.contracts.schemas import (
    AggregationMode,
    ArtifactManifest,
    CompilationResult,
    Diagnostic,
    DiagnosticSeverity,
    EvaluationMetrics,
    EvaluationReport,
    InventoryAction,
    InventoryEntityType,
    InventoryPolicy,
    InventoryPolicyConfig,
    InventoryPolicyEntry,
    LintReport,
    MetricStatus,
    MetricValue,
    ReadinessAssessment,
    ReadinessStatus,
    ReportData,
    ReportMapping,
    ReportRowGrain,
    Rule,
    RuleCondition,
    RuleSet,
    ScriptBudgets,
)
from dv360_bidkit.evaluator.diagnostics import evaluate_script
from dv360_bidkit.io.inventory import (
    extract_targeting_block_requests,
    is_entry_expired,
    load_inventory_policy,
    match_inventory_entity,
    normalize_domain,
)
from dv360_bidkit.io.reports import load_report
from dv360_bidkit.linter.ast_validator import lint_script
from dv360_bidkit.reporting.basic import render_report

__version__ = "0.1.0"

__all__ = [
    # Primary API entry points
    "compile_script",
    "evaluate_script",
    "extract_targeting_block_requests",
    "is_entry_expired",
    "lint_script",
    "load_inventory_policy",
    "load_report",
    "match_inventory_entity",
    "normalize_domain",
    "render_report",
    # Contract schemas
    "AggregationMode",
    "ArtifactManifest",
    "CompilationResult",
    "Diagnostic",
    "DiagnosticSeverity",
    "EvaluationMetrics",
    "EvaluationReport",
    "InventoryAction",
    "InventoryEntityType",
    "InventoryPolicy",
    "InventoryPolicyConfig",
    "InventoryPolicyEntry",
    "LintReport",
    "MetricStatus",
    "MetricValue",
    "ReadinessAssessment",
    "ReadinessStatus",
    "ReportData",
    "ReportMapping",
    "ReportRowGrain",
    "Rule",
    "RuleCondition",
    "RuleSet",
    "ScriptBudgets",
    # Exceptions
    "BidkitError",
    "BudgetExceededError",
    "CompilationError",
    "CompressionBudgetError",
    "DataSufficiencyError",
    "EvaluationError",
    "InventoryPolicyError",
    "LintError",
    "ReportMappingError",
]
