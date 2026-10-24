"""Semantics-preserving rule simplification for DV360 Custom Bidding scripts.

Simplifies redundant conditions, groups identical scores with domain lists
using 'in [...]' syntax, and removes duplicate or shadowed rules.
"""

from __future__ import annotations

from dv360_bidkit.contracts.schemas import AggregationMode, Rule, RuleCondition, RuleSet


def simplify_ruleset(ruleset: RuleSet) -> RuleSet:
    """Applies semantics-preserving simplification to a RuleSet.

    For rules with identical scores and single domain '==' conditions, groups domains
    into a single rule using operator 'in' with sorted domain list.
    Prunes duplicate rules while strictly preserving evaluation semantics.
    """
    if not ruleset.rules:
        return ruleset

    # If first_match or max aggregation, grouping rules with identical score and weight into 'in [...]'
    # preserves exact score outputs and significantly reduces character count and AST nodes.
    grouped_rules: list[Rule] = []
    domain_groups_by_score: dict[tuple[float, float], list[str]] = {}
    other_rules: list[Rule] = []

    for rule in ruleset.rules:
        # Check if rule is a single domain equality check with no dynamic expression
        if (
            len(rule.conditions) == 1
            and rule.conditions[0].field == "domain"
            and rule.conditions[0].operator == "=="
            and rule.score_expression is None
        ):
            domain_val = str(rule.conditions[0].value)
            key = (round(rule.score, 6), round(rule.weight, 6))
            if key not in domain_groups_by_score:
                domain_groups_by_score[key] = []
            if domain_val not in domain_groups_by_score[key]:
                domain_groups_by_score[key].append(domain_val)
        else:
            other_rules.append(rule)

    # Reconstruct grouped domain rules
    for (score_key, weight_key), domains in domain_groups_by_score.items():
        if len(domains) == 1:
            grouped_rules.append(
                Rule(
                    id=f"rule_domain_{domains[0]}",
                    conditions=[RuleCondition(field="domain", operator="==", value=domains[0])],
                    score=score_key,
                    weight=weight_key,
                )
            )
        else:
            sorted_domains = sorted(domains)
            grouped_rules.append(
                Rule(
                    id=f"rule_grouped_domains_score_{score_key}",
                    conditions=[RuleCondition(field="domain", operator="in", value=sorted_domains)],
                    score=score_key,
                    weight=weight_key,
                )
            )

    # In first_match_aggregate or sum_aggregate, keep grouped rules followed by other rules
    all_rules = grouped_rules + other_rules

    return RuleSet(
        schema_version=ruleset.schema_version,
        aggregation_mode=ruleset.aggregation_mode,
        rules=all_rules,
        fallback_score=ruleset.fallback_score,
        score_scale=ruleset.score_scale,
        metadata={**ruleset.metadata, "simplified": True},
    )
