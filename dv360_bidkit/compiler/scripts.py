"""Canonical RuleSet to DV360 Custom Bidding DSL Compiler.

Compiles structured RuleSet objects and optional customer InventoryPolicies
into deterministic, production-grade DV360 Python scripts.
"""

from __future__ import annotations

import json
from typing import Any

from dv360_bidkit.compiler.budgets import check_script_budgets
from dv360_bidkit.compiler.simplify import simplify_ruleset
from dv360_bidkit.contracts.exceptions import BudgetExceededError, CompilationError
from dv360_bidkit.contracts.schemas import (
    AggregationMode,
    CompilationResult,
    Diagnostic,
    InventoryAction,
    InventoryEntityType,
    InventoryPolicy,
    Rule,
    RuleCondition,
    RuleSet,
    ScriptBudgets,
)
from dv360_bidkit.io.inventory import is_entry_expired
from dv360_bidkit.linter.ast_validator import lint_script


def _format_condition(cond: RuleCondition) -> str:
    """Formats a single RuleCondition into DV360 DSL condition text."""
    val = cond.value
    if isinstance(val, str):
        val_str = f'"{val}"'
    elif isinstance(val, list):
        sorted_items = sorted(str(x) for x in val)
        val_str = "[" + ", ".join(f'"{x}"' for x in sorted_items) + "]"
    elif isinstance(val, bool):
        val_str = "True" if val else "False"
    else:
        val_str = str(val)

    return f"{cond.field} {cond.operator} {val_str}"


def _format_entity_list(values: list[str], *, as_int_if_numeric: bool = False) -> str:
    """Formats a sorted, deduplicated list of entity values into a Python list literal."""
    unique_vals = sorted(set(values))
    if as_int_if_numeric and all(v.isdigit() for v in unique_vals):
        return "[" + ", ".join(str(int(v)) for v in unique_vals) + "]"
    return "[" + ", ".join(f'"{v}"' for v in unique_vals) + "]"


def compile_script(
    rules: RuleSet,
    *,
    policy: InventoryPolicy | None = None,
    budgets: ScriptBudgets | None = None,
    simplify: bool = True,
) -> CompilationResult:
    """Compiles a RuleSet and optional InventoryPolicy into a canonical DV360 script.

    Parameters
    ----------
    rules : RuleSet
        The structured rule definitions.
    policy : InventoryPolicy | None
        Optional customer inventory policy specifying score overrides or training exclusions.
    budgets : ScriptBudgets | None
        Optional caller-specified budget limits for bytes, characters, AST nodes, and rules.
    simplify : bool
        Whether to apply semantics-preserving rule simplification before compilation.

    Returns
    -------
    CompilationResult
        The compiled script text, node counts, budget checks, and diagnostics.
    """
    effective_ruleset = simplify_ruleset(rules) if simplify else rules
    scale = float(effective_ruleset.score_scale) if effective_ruleset.score_scale is not None else 1.0

    lines: list[str] = [
        "# DV360 Custom Bidding Script",
        "# Generated deterministically by dv360-bidkit",
        "",
    ]

    # 1. Handle training exclusions and score overrides from inventory policy
    # Precedence (Spec Section 5.1): EXCLUDE_FROM_TRAINING > SET_SCORE > ordinary rules
    exclusion_domains: list[str] = []
    exclusion_site_ids: list[str] = []
    domain_overrides: dict[float, list[str]] = {}
    site_id_overrides: dict[float, list[str]] = {}
    allowlist_domains: set[str] = set()
    allowlist_site_ids: set[str] = set()
    override_count = 0

    if policy is not None:
        for entry in policy.entries:
            if is_entry_expired(entry):
                continue
            if entry.action == InventoryAction.EXCLUDE_FROM_TRAINING:
                if entry.entity_type == InventoryEntityType.SITE_ID:
                    exclusion_site_ids.append(entry.entity_value)
                else:
                    exclusion_domains.append(entry.entity_value)
            elif entry.action == InventoryAction.SET_SCORE and entry.score is not None:
                override_score = round(float(entry.score) * scale, 4)
                override_count += 1
                if entry.entity_type == InventoryEntityType.SITE_ID:
                    site_id_overrides.setdefault(override_score, []).append(entry.entity_value)
                    allowlist_site_ids.add(entry.entity_value)
                else:
                    domain_overrides.setdefault(override_score, []).append(entry.entity_value)
                    allowlist_domains.add(entry.entity_value)
            elif entry.action == InventoryAction.ANNOTATE:
                if entry.entity_type == InventoryEntityType.SITE_ID:
                    allowlist_site_ids.add(entry.entity_value)
                else:
                    allowlist_domains.add(entry.entity_value)

    excl_domain_set = set(exclusion_domains)
    excl_site_set = set(exclusion_site_ids)

    if exclusion_domains:
        exclusions_repr = _format_entity_list(exclusion_domains)
        lines.append(f"if domain in {exclusions_repr}:")
        lines.append("    return None  # Excluded from model training by inventory policy")
        lines.append("")

    if exclusion_site_ids:
        site_excl_repr = _format_entity_list(exclusion_site_ids, as_int_if_numeric=True)
        lines.append(f"if site_id in {site_excl_repr}:")
        lines.append("    return None  # Excluded site_id from model training by inventory policy")
        lines.append("")

    # Emit top-level SET_SCORE overrides so matched entities replace the final score
    # rather than adding a bonus in sum_aggregate mode (Spec Section 5.1)
    for override_score in sorted(domain_overrides.keys(), reverse=True):
        active_doms = [d for d in domain_overrides[override_score] if d not in excl_domain_set]
        if active_doms:
            dom_repr = _format_entity_list(active_doms)
            lines.append(f"if domain in {dom_repr}:")
            lines.append(f"    return {override_score:.4f}  # Policy score override")
            lines.append("")

    for override_score in sorted(site_id_overrides.keys(), reverse=True):
        active_sites = [s for s in site_id_overrides[override_score] if s not in excl_site_set]
        if active_sites:
            site_repr = _format_entity_list(active_sites, as_int_if_numeric=True)
            lines.append(f"if site_id in {site_repr}:")
            lines.append(f"    return {override_score:.4f}  # Policy site_id score override")
            lines.append("")

    # Handle allowlist_only mode if configured on InventoryPolicy
    if policy is not None and policy.config.unknown_action == "allowlist_only":
        # Collect domains/site_ids referenced in rules as well
        for r in effective_ruleset.rules:
            for c in r.conditions:
                if c.field == "domain" and c.operator in ("==", "in"):
                    if isinstance(c.value, list):
                        allowlist_domains.update(str(x) for x in c.value)
                    else:
                        allowlist_domains.add(str(c.value))
                elif c.field == "site_id" and c.operator in ("==", "in"):
                    if isinstance(c.value, list):
                        allowlist_site_ids.update(str(x) for x in c.value)
                    else:
                        allowlist_site_ids.add(str(c.value))

        if policy.config.unmatched_exclude:
            if allowlist_domains:
                allow_repr = _format_entity_list(list(allowlist_domains))
                lines.append(f"if domain not in {allow_repr}:")
                lines.append("    return None  # Excluded by allowlist_only policy")
                lines.append("")
            elif allowlist_site_ids:
                allow_site_repr = _format_entity_list(list(allowlist_site_ids), as_int_if_numeric=True)
                lines.append(f"if site_id not in {allow_site_repr}:")
                lines.append("    return None  # Excluded by allowlist_only policy")
                lines.append("")
        elif policy.config.unmatched_score is not None:
            unmatched_scaled = float(policy.config.unmatched_score) * scale
            if allowlist_domains:
                allow_repr = _format_entity_list(list(allowlist_domains))
                lines.append(f"if domain not in {allow_repr}:")
                lines.append(f"    return {unmatched_scaled:.4f}  # Unmatched allowlist_only fallback score")
                lines.append("")
            elif allowlist_site_ids:
                allow_site_repr = _format_entity_list(list(allowlist_site_ids), as_int_if_numeric=True)
                lines.append(f"if site_id not in {allow_site_repr}:")
                lines.append(f"    return {unmatched_scaled:.4f}  # Unmatched allowlist_only fallback score")
                lines.append("")

    # Map aggregation function
    agg_func_map = {
        AggregationMode.SUM: "sum_aggregate",
        AggregationMode.MAX: "max_aggregate",
        AggregationMode.FIRST_MATCH: "first_match_aggregate",
    }
    agg_func = agg_func_map.get(effective_ruleset.aggregation_mode, "first_match_aggregate")

    all_rules = effective_ruleset.rules
    criteria_items: list[str] = []

    for rule in all_rules:
        cond_strings = [_format_condition(c) for c in rule.conditions]
        if not cond_strings:
            cond_expr = "True"
        elif len(cond_strings) == 1:
            cond_expr = cond_strings[0]
        else:
            cond_expr = " and ".join(f"({c})" for c in cond_strings)

        multiplier = float(rule.weight) * scale
        if rule.score_expression:
            if abs(multiplier - 1.0) < 1e-9:
                score_str = f"({rule.score_expression})"
            else:
                score_str = f"(({rule.score_expression}) * {multiplier:.4f})"
        else:
            effective_score = float(rule.score) * multiplier
            score_str = f"{effective_score:.4f}"

        criteria_items.append(f"    ([{cond_expr}], {score_str})")

    # Add fallback rule for first_match if specified
    if effective_ruleset.aggregation_mode == AggregationMode.FIRST_MATCH:
        fallback_base = (
            float(policy.config.unmatched_score)
            if (
                policy is not None
                and policy.config.unknown_action == "allowlist_only"
                and policy.config.unmatched_score is not None
            )
            else float(effective_ruleset.fallback_score)
        )
        fallback = fallback_base * scale
        criteria_items.append(f"    ([True], {fallback:.4f})")

    lines.append(f"return {agg_func}([")
    lines.append(",\n".join(criteria_items))
    lines.append("])")
    lines.append("")

    script_code = "\n".join(lines)

    # Lint generated script to verify syntax correctness
    lint_report = lint_script(script_code)
    diagnostics = list(lint_report.diagnostics)

    # Check budgets
    rule_count = len(all_rules) + override_count
    passed, chars, bytes_len, nodes, budget_diags = check_script_budgets(
        script_code, rule_count, budgets
    )
    diagnostics.extend(budget_diags)

    return CompilationResult(
        script_code=script_code,
        ast_nodes=nodes,
        byte_count=bytes_len,
        char_count=chars,
        rule_count=rule_count,
        budgets_passed=passed and not lint_report.has_errors,
        diagnostics=diagnostics,
    )
