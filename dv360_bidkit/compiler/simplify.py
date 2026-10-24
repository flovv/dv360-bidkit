"""Semantics-preserving rule simplification for DV360 Custom Bidding scripts.

Simplifies redundant conditions and groups contiguous identical scores with domain
lists using 'in [...]' syntax, while strictly preserving rule evaluation order,
precedence, and aggregation multiplicity.
"""

from __future__ import annotations

from dv360_bidkit.contracts.schemas import AggregationMode, Rule, RuleCondition, RuleSet


def simplify_ruleset(ruleset: RuleSet) -> RuleSet:
    """Applies semantics-preserving simplification to a RuleSet.

    Strictly preserves evaluation order, precedence, and aggregation semantics:
    - Never reorders rules across different conditions or precedence tiers.
    - Only coalesces contiguous runs of single-domain equality rules with identical
      score, weight, and score_expression.
    - Under SUM aggregation, never collapses duplicate conditions (which would drop
      additive score contributions).
    """
    if not ruleset.rules or len(ruleset.rules) < 2:
        return ruleset

    simplified_rules: list[Rule] = []
    i = 0
    n = len(ruleset.rules)

    while i < n:
        curr = ruleset.rules[i]

        # Check if curr is a candidate for contiguous domain grouping
        is_domain_eq = (
            len(curr.conditions) == 1
            and curr.conditions[0].field == "domain"
            and curr.conditions[0].operator == "=="
            and curr.score_expression is None
        )

        if not is_domain_eq:
            simplified_rules.append(curr)
            i += 1
            continue

        # Look ahead for contiguous rules that can be safely merged
        curr_domain = str(curr.conditions[0].value)
        domains = [curr_domain]
        j = i + 1

        while j < n:
            next_rule = ruleset.rules[j]
            is_next_domain_eq = (
                len(next_rule.conditions) == 1
                and next_rule.conditions[0].field == "domain"
                and next_rule.conditions[0].operator == "=="
                and next_rule.score_expression is None
                and round(next_rule.score, 6) == round(curr.score, 6)
                and round(next_rule.weight, 6) == round(curr.weight, 6)
            )
            if not is_next_domain_eq:
                break

            next_domain = str(next_rule.conditions[0].value)

            # In SUM aggregation, if next_domain is already in domains,
            # merging would eliminate an additive term! So stop merging.
            if ruleset.aggregation_mode == AggregationMode.SUM and next_domain in domains:
                break

            domains.append(next_domain)
            j += 1

        if len(domains) == 1:
            simplified_rules.append(curr)
        else:
            # For FIRST_MATCH / MAX, deduplicate domains while preserving semantics
            if ruleset.aggregation_mode != AggregationMode.SUM:
                unique_domains = sorted(set(domains))
            else:
                unique_domains = sorted(domains)

            if len(unique_domains) == 1 and ruleset.aggregation_mode != AggregationMode.SUM:
                simplified_rules.append(
                    Rule(
                        id=f"rule_domain_{unique_domains[0]}",
                        conditions=[RuleCondition(field="domain", operator="==", value=unique_domains[0])],
                        score=curr.score,
                        weight=curr.weight,
                    )
                )
            else:
                simplified_rules.append(
                    Rule(
                        id=f"rule_grouped_domains_score_{round(curr.score, 6)}",
                        conditions=[RuleCondition(field="domain", operator="in", value=unique_domains)],
                        score=curr.score,
                        weight=curr.weight,
                    )
                )

        i = j

    return RuleSet(
        schema_version=ruleset.schema_version,
        aggregation_mode=ruleset.aggregation_mode,
        rules=simplified_rules,
        fallback_score=ruleset.fallback_score,
        score_scale=ruleset.score_scale,
        metadata={**ruleset.metadata, "simplified": True},
    )
