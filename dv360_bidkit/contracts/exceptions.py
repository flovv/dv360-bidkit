"""Exception hierarchy for dv360-bidkit."""

from __future__ import annotations


class BidkitError(Exception):
    """Base exception for all dv360-bidkit errors."""


class LintError(BidkitError):
    """Raised when script linting or AST validation fails."""


class CompilationError(BidkitError):
    """Raised when compilation of a RuleSet into a DV360 script fails."""


class BudgetExceededError(CompilationError):
    """Raised when a compiled script exceeds character, byte, node, or rule budgets."""


class EvaluationError(BidkitError):
    """Raised when script simulation or evaluation fails."""


class DataSufficiencyError(EvaluationError):
    """Raised when input report data is insufficient or required signals are missing."""


class ReportMappingError(BidkitError):
    """Raised when column mapping, unit conversion, or denominator checks fail."""


class InventoryPolicyError(BidkitError):
    """Raised when inventory policy contains conflicts, invalid hostnames, or invalid actions."""


class CompressionBudgetError(BidkitError):
    """Raised when compression cannot meet both size budget and error tolerance."""
