"""DV360 Custom Bidding DSL Migration Helper.

Identifies deprecated identifiers and syntax patterns, generates diffs,
and enforces sourced old-to-new value mappings rather than dangerous silent substitutions.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from dv360_bidkit.contracts.signals import SIGNAL_REGISTRY, SignalStatus


class MigrationItem(BaseModel):
    old_signal: str
    suggested_replacement: str
    requires_manual_mapping: bool = False
    reason: str = ""
    line: int | None = None


class MigrationPlan(BaseModel):
    has_deprecations: bool
    items: list[MigrationItem] = Field(default_factory=list)
    proposed_code: str | None = None
    diff: str | None = None
    manual_review_notes: list[str] = Field(default_factory=list)


def migrate_script(
    code: str,
    *,
    id_mapping: dict[str, dict[Any, Any]] | None = None,
) -> MigrationPlan:
    """Analyzes a script for deprecated DV360 signals and generates a safe migration plan.

    Parameters
    ----------
    code : str
        The DV360 Custom Bidding script code.
    id_mapping : dict[str, dict[Any, Any]] | None
        Optional explicit mapping tables for identifier changes (e.g. site_id to domain).

    Returns
    -------
    MigrationPlan
        Contains identified deprecations, proposed replacements, and diff.
    """
    id_mapping = id_mapping or {}
    items: list[MigrationItem] = []
    notes: list[str] = []
    lines = code.splitlines(keepends=True)

    # Check for known deprecations line by line
    modified_lines = list(lines)

    for lineno, line in enumerate(lines, start=1):
        # 1. Universal Analytics functions (has_ga_goal, ga_goals_count)
        if "has_ga_goal" in line or "ga_goals_count" in line:
            func = "has_ga_goal" if "has_ga_goal" in line else "ga_goals_count"
            items.append(
                MigrationItem(
                    old_signal=func,
                    suggested_replacement="ga4_conversions_count(property_id, 'conversion_event_name')",
                    requires_manual_mapping=True,
                    reason="Universal Analytics is deprecated. Migrating to GA4 requires specifying the GA4 Property ID and event name string.",
                    line=lineno,
                )
            )
            notes.append(
                f"Line {lineno}: '{func}' requires GA4 property ID and event name. Manual mapping required; automatic substitution disabled to prevent zero-scoring."
            )

        # 2. conversion_variable_str
        if "conversion_variable_str" in line:
            items.append(
                MigrationItem(
                    old_signal="conversion_variable_str",
                    suggested_replacement="conversion_custom_variable(floodlight_activity_id, model_id, u_variable_index)",
                    requires_manual_mapping=False,
                    reason="Deprecated helper replaced by canonical conversion_custom_variable function.",
                    line=lineno,
                )
            )
            # Safe text replacement of the function name
            modified_lines[lineno - 1] = re.sub(
                r"\bconversion_variable_str\b",
                "conversion_custom_variable",
                modified_lines[lineno - 1],
            )

        # 3. browser_id
        if re.search(r"\bbrowser_id\b", line):
            items.append(
                MigrationItem(
                    old_signal="browser_id",
                    suggested_replacement="device_type / environment / os_id",
                    requires_manual_mapping=True,
                    reason="browser_id is deprecated and unsupported in DV360 v4/v5 custom bidding models.",
                    line=lineno,
                )
            )
            notes.append(
                f"Line {lineno}: 'browser_id' cannot be automatically mapped. Consider segmenting by device_type or os_id."
            )

    has_deprecations = len(items) > 0
    proposed_code = "".join(modified_lines) if has_deprecations else None
    diff_text = None

    if proposed_code and proposed_code != code:
        diff_lines = list(
            difflib.unified_diff(
                code.splitlines(keepends=True),
                proposed_code.splitlines(keepends=True),
                fromfile="original_script.py",
                tofile="migrated_script.py",
            )
        )
        diff_text = "".join(diff_lines)

    return MigrationPlan(
        has_deprecations=has_deprecations,
        items=items,
        proposed_code=proposed_code,
        diff=diff_text,
        manual_review_notes=notes,
    )
