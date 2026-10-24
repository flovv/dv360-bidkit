"""Data sufficiency and signal coverage verification for DV360 Custom Bidding evaluation.

Verifies that all signals referenced in a script are present in the report dataset,
distinguishes homogeneous aggregate rows from insufficient summary statistics,
and prevents automatic zero-filling of missing signals.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from dv360_bidkit.contracts.schemas import MetricStatus, ReportData, ReportRowGrain
from dv360_bidkit.contracts.signals import SIGNAL_REGISTRY, SignalKind
from dv360_bidkit.linter.ast_validator import _wrap_top_level_returns


class DataSufficiencyReport(BaseModel):
    is_sufficient: bool
    required_signals: list[str] = Field(default_factory=list)
    available_signals: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    row_grain: ReportRowGrain = ReportRowGrain.HOMOGENEOUS_AGGREGATE
    assumptions: list[str] = Field(default_factory=list)
    unavailable_metrics: list[str] = Field(default_factory=list)


ALLOWED_BUILTIN_NAMES = {"True", "False", "None", "true", "false", "_dv360_script_wrapper"}


def extract_required_signals(code: str) -> set[str]:
    """Extracts all signal dimension and function identifiers referenced in the script."""
    wrapped_code, _ = _wrap_top_level_returns(code)
    tree = ast.parse(wrapped_code)
    signals: set[str] = set()
    local_vars: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    local_vars.add(target.id)

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            name = node.id
            if name not in ALLOWED_BUILTIN_NAMES and name not in local_vars:
                signals.add(name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                fname = node.func.id
                if fname not in ("sum_aggregate", "max_aggregate", "first_match_aggregate", "float", "int", "str", "bool"):
                    signals.add(fname)

    return signals


def verify_data_sufficiency(code: str, data: ReportData) -> DataSufficiencyReport:
    """Verifies whether the input report dataset contains sufficient signals to evaluate the script.

    Parameters
    ----------
    code : str
        The DV360 Custom Bidding script code.
    data : ReportData
        The customer report data and mapping.

    Returns
    -------
    DataSufficiencyReport
        Coverage status, missing signals, and sufficiency flags.
    """
    required = extract_required_signals(code)
    # Available fields include both mapped canonical fields and raw dataframe columns
    available_canonical = set(data.mapping.canonical_field_map.keys())
    available_df_cols = set(data.df.columns)
    available_all = available_canonical.union(available_df_cols)

    missing = required - available_all

    assumptions: list[str] = []
    unavailable: list[str] = []

    # Check row grain constraints
    if data.mapping.row_grain == ReportRowGrain.SUMMARY:
        # Summary metrics cannot reconstruct individual event thresholds
        # Example: average time on screen cannot evaluate `time_on_screen > 10`
        assumptions.append(
            "Report contains summary metrics. Threshold conditions on unbundled continuous distributions cannot be evaluated."
        )
        for sig in required:
            if "time" in sig or "duration" in sig or "seconds" in sig:
                unavailable.append(sig)

    elif data.mapping.row_grain == ReportRowGrain.HOMOGENEOUS_AGGREGATE:
        # Check whether all required dimensions are present as grouping keys
        unrepresented = required - available_all
        if unrepresented:
            assumptions.append(
                f"Aggregated report is missing required signals {sorted(unrepresented)}. Script evaluation requires exact values per row."
            )

    is_sufficient = len(missing) == 0 and len(unavailable) == 0

    return DataSufficiencyReport(
        is_sufficient=is_sufficient,
        required_signals=sorted(required),
        available_signals=sorted(available_all.intersection(required)),
        missing_signals=sorted(missing),
        row_grain=data.mapping.row_grain,
        assumptions=assumptions,
        unavailable_metrics=unavailable,
    )
