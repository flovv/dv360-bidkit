# Quickstart & CLI Guide

Get started with `dv360-bidkit` in under two minutes.

---

## 1. Installation

`dv360-bidkit` is available as a standard Python package supporting Python 3.10 through 3.13:

```bash
pip install dv360-bidkit
```

Optional dependencies:
```bash
# Jinja template reporting support
pip install "dv360-bidkit[jinja]"

# Google API integration primitives
pip install "dv360-bidkit[google]"
```

---

## 2. One-Command Synthetic Demo

`dv360-bidkit` includes built-in display report generators and pre-flight evaluation fixtures requiring **zero DV360 API or Google Cloud credentials**:

```bash
bidkit demo
```

This command automatically:
1. Generates a realistic DV360 performance report (`demo/report.csv`) with 270k+ impressions.
2. Creates canonical column mappings (`demo/mapping.json`).
3. Formulates a production multi-condition ruleset (`demo/rules.json`) and inventory policy (`demo/policy.json`).
4. Compiles the ruleset into Google-compliant Python DSL (`demo/script.py`).
5. Runs a pre-flight local simulation and outputs a diagnostic readiness table.

---

## 3. CLI Command Reference

### `bidkit lint`
Validates a custom bidding script against Google's 2026 DSL specification:

```bash
# Human-readable colored output:
bidkit lint script.py

# Machine-readable JSON output (for CI/CD pipelines):
bidkit lint script.py --format json
```

**Checks Performed:**
* Disallows unsafe Python constructs (`import`, `while`, `for`, `eval`, `class`, `exec`, `open`).
* Verifies function signatures and argument counts (e.g., `first_match_aggregate`, `total_conversion_count`).
* Verifies dimension ranges (`device_type`, `environment`, `country_code`).
* Detects deprecated signals (e.g., `browser_id`).
* Flags unhandled exceptions or negative scores.

---

### `bidkit compile`
Compiles high-level business rules and customer inventory policies into deterministic DV360 Python DSL:

```bash
bidkit compile --rules rules.json --out script.py
bidkit compile --rules rules.json --policy policy.csv --out script.py
```

**Features:**
* Contiguous run grouping preserving rule evaluation order in `first_match_aggregate`.
* Automatic insertion of model training exclusions (`return None`) from inventory policies.
* Verification of DV360 script budget constraints (total AST characters, line count, nesting limits).

---

### `bidkit evaluate`
Simulates custom bidding script execution on historical report data:

```bash
bidkit evaluate script.py --report dv360_performance.csv --mapping mapping.json --out diagnostics.json
```

**Metrics Computed:**
* **Total & Positive Impressions:** Volume of impressions receiving score $> 0.0$.
* **Positive Scoring Rate:** Target between $5\%$ and $40\%$ for balanced bidding.
* **Weighted Mean Score:** Scale reference for bidding multipliers.
* **Lorenz Gini Inequality:** Measures concentration ($0.25 - 0.65$ indicates healthy publisher differentiation).
* **Max-to-Median Score Ratio:** Asserts $\le 20.0\times$ to avoid pacing controller starvation.
* **Google S2 Training Readiness:** Checks $\ge 500$ advertiser positives and $\ge 50$ line-item positives.

---

### `bidkit report`
Renders an interactive, standalone HTML audit report from evaluation diagnostics:

```bash
bidkit report diagnostics.json --out audit.html
```

---

## 4. Python API Example

```python
from dv360_bidkit import (
    RuleSet,
    Rule,
    RuleCondition,
    AggregationMode,
    compile_script,
    lint_script,
    load_report,
    evaluate_script,
    ReportMapping
)

# 1. Define custom business logic
ruleset = RuleSet(
    aggregation_mode=AggregationMode.FIRST_MATCH,
    rules=[
        Rule(
            conditions=[
                RuleCondition(field="domain", operator="==", value="highqualitynews.com"),
                RuleCondition(field="device_type", operator="in", value=[1, 2]),
            ],
            score=10.0,
        ),
        Rule(
            conditions=[
                RuleCondition(field="device_type", operator="==", value=2),
                RuleCondition(field="environment", operator="==", value=1),
            ],
            score=5.0,
        ),
    ],
    fallback_score=1.0,
)

# 2. Compile to production DV360 Python DSL
result = compile_script(ruleset)
print(result.script_code)

# 3. Lint the generated script
lint_report = lint_script(result.script_code)
assert lint_report.is_valid

# 4. Pre-flight simulate on historical CSV data
mapping = ReportMapping(
    canonical_field_map={
        "impressions": "Impressions",
        "domain": "App/URL",
        "device_type": "Device Type",
        "environment": "Environment",
        "line_item_id": "Line Item ID",
    },
    date_window="30d",
)
data = load_report("dv360_report.csv", mapping=mapping)
eval_report = evaluate_script(result.script_code, data, history_window_days=30)

print(f"Readiness: {eval_report.readiness.status.value}")
print(f"Positive Scoring Rate: {eval_report.metrics.positive_score_rate.value:.1%}")
```
