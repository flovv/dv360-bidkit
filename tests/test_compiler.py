"""Unit tests for RuleSet compiler, simplification, and budget checking."""

import pytest
from dv360_bidkit.compiler.budgets import check_script_budgets
from dv360_bidkit.compiler.scripts import compile_script
from dv360_bidkit.compiler.simplify import simplify_ruleset
from dv360_bidkit.contracts.schemas import (
    AggregationMode,
    InventoryAction,
    InventoryEntityType,
    InventoryPolicy,
    InventoryPolicyEntry,
    Rule,
    RuleCondition,
    RuleSet,
    ScriptBudgets,
)
from dv360_bidkit.linter.ast_validator import lint_script


def test_compiler_deterministic_output():
    ruleset = RuleSet(
        schema_version="1.0",
        aggregation_mode=AggregationMode.FIRST_MATCH,
        rules=[
            Rule(
                id="r1",
                conditions=[RuleCondition(field="domain", operator="==", value="site1.com")],
                score=10.0,
            ),
            Rule(
                id="r2",
                conditions=[RuleCondition(field="domain", operator="==", value="site2.com")],
                score=5.0,
            ),
        ],
        fallback_score=1.0,
    )
    res1 = compile_script(ruleset)
    res2 = compile_script(ruleset)
    assert res1.script_code == res2.script_code
    assert res1.budgets_passed
    # Result passes linter
    assert lint_script(res1.script_code).is_valid


def test_compiler_no_15_rule_cap():
    # Build 30 rules to confirm no artificial cap
    rules = [
        Rule(
            id=f"rule_{i}",
            conditions=[RuleCondition(field="domain", operator="==", value=f"domain{i}.com")],
            score=float(i + 1),
        )
        for i in range(30)
    ]
    ruleset = RuleSet(aggregation_mode=AggregationMode.FIRST_MATCH, rules=rules, fallback_score=0.5)
    res = compile_script(ruleset, simplify=False)
    assert res.rule_count == 30
    assert res.budgets_passed
    assert lint_script(res.script_code).is_valid


def test_compiler_simplification_groups_domains():
    # Multiple rules with same score simplified into 'in [...]'
    rules = [
        Rule(
            id=f"r_{d}",
            conditions=[RuleCondition(field="domain", operator="==", value=d)],
            score=5.0,
        )
        for d in ["alpha.com", "beta.com", "gamma.com"]
    ]
    ruleset = RuleSet(aggregation_mode=AggregationMode.FIRST_MATCH, rules=rules)
    simplified = simplify_ruleset(ruleset)
    assert len(simplified.rules) == 1
    assert simplified.rules[0].conditions[0].operator == "in"
    assert sorted(simplified.rules[0].conditions[0].value) == ["alpha.com", "beta.com", "gamma.com"]


def test_compiler_with_inventory_exclusions():
    ruleset = RuleSet(
        aggregation_mode=AggregationMode.FIRST_MATCH,
        rules=[
            Rule(
                id="r1",
                conditions=[RuleCondition(field="domain", operator="==", value="safe.com")],
                score=5.0,
            )
        ],
        fallback_score=1.0,
    )
    policy = InventoryPolicy(
        entries=[
            InventoryPolicyEntry(
                entity_type=InventoryEntityType.DOMAIN,
                entity_value="toxic.com",
                action=InventoryAction.EXCLUDE_FROM_TRAINING,
                source="test",
                as_of="2026-01-01",
            )
        ]
    )
    res = compile_script(ruleset, policy=policy)
    assert 'if domain in ["toxic.com"]:' in res.script_code
    assert "return None" in res.script_code
    assert lint_script(res.script_code).is_valid


def test_script_budgets_detection():
    long_code = "# " + ("x" * 1000) + "\nreturn 1.0\n"
    budgets = ScriptBudgets(max_chars=500)
    passed, chars, bytes_len, nodes, diags = check_script_budgets(long_code, rule_count=1, budgets=budgets)
    assert not passed
    assert any(d.code == "BUDGET_CHAR_LIMIT_EXCEEDED" for d in diags)


def test_compiler_set_score_replaces_in_sum_mode():
    """Verify Spec Section 5.1: SET_SCORE replaces the final score for that entity even in SUM mode."""
    from dv360_bidkit.evaluator.interpreter import create_interpreter

    ruleset = RuleSet(
        aggregation_mode=AggregationMode.SUM,
        rules=[
            Rule(
                id="r1",
                conditions=[RuleCondition(field="domain", operator="==", value="deal.com")],
                score=5.0,
            ),
            Rule(
                id="r2",
                conditions=[RuleCondition(field="device_type", operator="==", value=1)],
                score=3.0,
            ),
        ],
    )
    policy = InventoryPolicy(
        entries=[
            InventoryPolicyEntry(
                entity_type=InventoryEntityType.DOMAIN,
                entity_value="deal.com",
                action=InventoryAction.SET_SCORE,
                source="deal",
                as_of="2026-01-01",
                score=20.0,
            )
        ]
    )

    comp = compile_script(ruleset, policy=policy)
    assert lint_script(comp.script_code).is_valid

    interp = create_interpreter(comp.script_code)
    # deal.com on desktop (device_type=1) should return exactly 20.0, NOT 20.0 + 5.0 + 3.0 = 28.0
    res_deal = interp.evaluate({"domain": "deal.com", "device_type": 1})
    assert res_deal.score == 20.0

    # other.com on desktop should sum matching rules -> 3.0
    res_other = interp.evaluate({"domain": "other.com", "device_type": 1})
    assert res_other.score == 3.0


def test_compiler_site_id_exclusions_and_overrides():
    """Verify site_id exclusions and SET_SCORE overrides compile and evaluate properly."""
    from dv360_bidkit.evaluator.interpreter import create_interpreter

    ruleset = RuleSet(
        aggregation_mode=AggregationMode.FIRST_MATCH,
        rules=[
            Rule(
                id="r1",
                conditions=[RuleCondition(field="device_type", operator="==", value=1)],
                score=4.0,
            )
        ],
        fallback_score=1.0,
    )
    policy = InventoryPolicy(
        entries=[
            InventoryPolicyEntry(
                entity_type=InventoryEntityType.SITE_ID,
                entity_value="11111",
                action=InventoryAction.EXCLUDE_FROM_TRAINING,
                source="audit",
                as_of="2026-01-01",
            ),
            InventoryPolicyEntry(
                entity_type=InventoryEntityType.SITE_ID,
                entity_value="22222",
                action=InventoryAction.SET_SCORE,
                source="deal",
                as_of="2026-01-01",
                score=15.0,
            ),
        ]
    )

    comp = compile_script(ruleset, policy=policy)
    assert "if site_id in [11111]:" in comp.script_code
    assert "if site_id in [22222]:" in comp.script_code
    assert lint_script(comp.script_code).is_valid

    interp = create_interpreter(comp.script_code)
    assert interp.evaluate({"site_id": 11111, "device_type": 1}).is_excluded is True
    assert interp.evaluate({"site_id": 22222, "device_type": 1}).score == 15.0
    assert interp.evaluate({"site_id": 33333, "device_type": 1}).score == 4.0


def test_compiler_allowlist_only_mode():
    """Verify allowlist_only mode with unmatched_exclude and unmatched_score."""
    from dv360_bidkit.contracts.schemas import InventoryPolicyConfig
    from dv360_bidkit.evaluator.interpreter import create_interpreter

    ruleset = RuleSet(
        aggregation_mode=AggregationMode.FIRST_MATCH,
        rules=[
            Rule(
                id="r1",
                conditions=[RuleCondition(field="domain", operator="==", value="trusted.com")],
                score=10.0,
            )
        ],
        fallback_score=1.0,
    )
    policy_excl = InventoryPolicy(
        entries=[],
        config=InventoryPolicyConfig(unknown_action="allowlist_only", unmatched_exclude=True),
    )
    comp_excl = compile_script(ruleset, policy=policy_excl)
    assert lint_script(comp_excl.script_code).is_valid

    interp_excl = create_interpreter(comp_excl.script_code)
    assert interp_excl.evaluate({"domain": "trusted.com"}).score == 10.0
    assert interp_excl.evaluate({"domain": "stranger.com"}).is_excluded is True


def test_compiler_score_expression_ternary_cap():
    """Verify DV360-compliant ternary expression for capped value rules."""
    from dv360_bidkit.evaluator.interpreter import create_interpreter

    ruleset = RuleSet(
        aggregation_mode=AggregationMode.SUM,
        rules=[
            Rule(
                id="capped_rev",
                conditions=[RuleCondition(field="total_conversion_value(555, 0)", operator=">", value=0)],
                score=50.0,
                weight=2.0,
                score_expression="50.0 if total_conversion_value(555, 0) > 50.0 else total_conversion_value(555, 0)",
            )
        ],
    )
    comp = compile_script(ruleset)
    assert lint_script(comp.script_code).is_valid

    interp = create_interpreter(comp.script_code)
    # Revenue = 20.0 -> uncapped -> 20.0 * 2.0 = 40.0
    assert interp.evaluate({"total_conversion_value:555:0": 20.0}).score == 40.0
    # Revenue = 120.0 -> capped at 50.0 -> 50.0 * 2.0 = 100.0
    assert interp.evaluate({"total_conversion_value:555:0": 120.0}).score == 100.0
