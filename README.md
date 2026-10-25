# dv360-bidkit

[![PyPI version](https://img.shields.io/pypi/v/dv360-bidkit.svg)](https://pypi.org/project/dv360-bidkit/)
[![CI](https://github.com/flovv/dv360-bidkit/actions/workflows/ci.yml/badge.svg)](https://github.com/flovv/dv360-bidkit)
[![Python versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://github.com/flovv/dv360-bidkit)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Polar Pro](https://img.shields.io/badge/Polar.sh-Get%20Pro%20License-blueviolet)](https://buy.polar.sh/polar_cl_jeD6EDIDtJxQJiCWKF1dfQ9vWHUomQUV7XxQD3Yj7bT)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-dv360--custom--bidding-purple)](https://skills.sh/flovv/dv360-bidkit/dv360-custom-bidding)

**Turn DV360 report data into verified, high-performance custom bidding algorithms without guesswork, AST syntax errors, or platform rejections.**

`dv360-bidkit` is an open-source, agent-ready programmatic bidding engine engineered for Google Display & Video 360 (DV360). It lints custom bidding scripts against Google's 2026 DSL specification, runs deterministic local simulations without `eval()`/`exec()`, checks Google S2 training readiness (500 advertiser / 50 line-item positives), and compiles structured rulesets into production-grade Python scripts.

---

## Quickstart: Inspectable Demo in 1 Command

`dv360-bidkit` includes realistic synthetic display report fixtures requiring **zero external Google Cloud or DV360 API credentials**. Install and run an inspectable pre-flight evaluation pass in a single command:

```bash
# Install from PyPI:
pip install dv360-bidkit

# Run instant diagnostic simulation:
bidkit demo
```

### Inspectable Terminal Output:
```text
                       DV360 BidKit Open-Core Demo Simulation                        
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric                ┃ Observed Value ┃ Google S2 / Health Standard              ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Total Impressions     │        273,146 │ Historical baseline sample               │
│ Positive Impressions  │         93,878 │ ≥ 500 required by Google S2              │
│ Positive Scoring Rate │          34.4% │ Target: 5% – 40% for active bidding      │
│ Weighted Mean Score   │           2.41 │ Scale baseline                           │
│ Gini Inequality       │          0.712 │ 0 = flat, 1 = extreme concentration      │
│ Max-to-Median Ratio   │           1.3x │ ≤ 20.0x prevents DSP pacing starvation   │
│ Readiness Status      │ MEETS_MINIMUM_HISTORY │ Google Custom Bidding training readiness │
└───────────────────────┴────────────────┴──────────────────────────────────────────┘

✓ Demo bundle successfully generated in: demo
  • Report: demo/report.csv
  • Mapping: demo/mapping.json
  • Rules: demo/rules.json
  • Policy: demo/policy.json
  • Compiled Script: demo/script.py
  • Diagnostics JSON: demo/diagnostics.json
  • Pro Config: demo/campaign.json
```

---

## The 4 Fatal Pitfalls of DV360 Custom Bidding

DV360 custom bidding models replace Google's standard click/conversion heuristics with a custom machine-learning reward function. However, four subtle pitfalls routinely undermine live campaigns:

### 1. Small-Sample Winner's Curse (Publisher Noise)
* **The Pitfall:** Long-tail domains with small impression samples (e.g., `3/3` viewable impressions $= 100\%$) receive maximum bid multipliers under naive scoring rules, wasting budget on unverified tail traffic.
* **The Solution:** Never bid on raw empirical rates. `dv360-bidkit-pro` applies Empirical Bayes shrinkage towards the campaign's baseline viewability ($\lambda_i = \frac{n_i}{n_i + k^*}$), pulling low-volume publishers toward the global mean while granting full confidence only to high-volume domains.

### 2. Score Mass Domination (Objective Dilution)
* **The Pitfall:** In multi-objective funnels blending purchases with proxy signals (e.g. Add-to-Cart or Clicks), high-frequency proxy signals can inadvertently capture $90\%+$ of total score mass ($M = \sum N_k w_k$). Google's bidding algorithm optimizes purely for the proxy and ignores primary conversions.
* **The Solution:** Enforce transition-bounded econometric caps ($w_{\text{proxy}} \le w_{\text{macro}} \times P(\text{Macro} \mid \text{Proxy})$) and allocate at least $65\%$ of expected score mass to primary conversions using `bidkit-pro weights`.

### 3. Pacing Starvation from Outlier Spikes
* **The Pitfall:** Uncapped continuous metrics (e.g., e-commerce transaction values or duration) create extreme score spikes. If the ratio of maximum score to positive median ($\max / \text{median}$) exceeds $20\times$, DV360's dual pacing controller ($\alpha_t$) destabilizes, causing immediate bid starvation.
* **The Solution:** Apply 95th-percentile Winsorization caps emitted as DV360-compliant ternary expressions (`cap if val > cap else val`).

### 4. Model Training Exclusion vs. Ad-Serving Blocks
* **The Pitfall:** Returning `None` in a custom bidding script (`return None`) excludes an impression from **model training**; it does **NOT** block the ad from serving.
* **The Solution:** Programmatic traders must maintain a strict separation between algorithm exclusions (`return None` for model health) and ad-serving blocks. `dv360-bidkit` exports `targeting_block_request.csv` as an actionable checklist for trafficking into DV360 Line Item targeting.

---

## Community (Open-Source Core) vs. Pro

`dv360-bidkit` (Open-Source Core) is the **Safety and Execution Rail**: it ensures scripts are syntactically valid, budget-compliant, and accurately simulated.  
`dv360-bidkit-pro` (Commercial) is the **Econometric Brain**: it eliminates manual weight guessing, calculates optimal proxy weights, shrinks long-tail publisher noise, and exports complete production bundles.

| Feature | Open-Source Core (`dv360-bidkit`) | Commercial Pro (`dv360-bidkit-pro`) |
| :--- | :---: | :---: |
| **Licensing** | Public MIT | Proprietary License ([Polar.sh](https://buy.polar.sh)) |
| **DV360 DSL Grammar & Syntax Linter (2026.1 Registry)** | ✅ Included | ✅ Included |
| **Safe AST Pre-Flight Simulator (No `eval`/`exec`)** | ✅ Included | ✅ Included |
| **Google S2 Training Readiness Check (500 / 50 Positives)** | ✅ Included | ✅ Included |
| **Deterministic RuleSet Compiler (`sum`, `max`, `first_match`)** | ✅ Included (Manual weights) | ✅ Included (Auto-calibrated) |
| **Customer Inventory Policy Loader (Exclusions & Overrides)** | ✅ Included | ✅ Included |
| **DV360 Report Loader (Preamble & Footer Auto-Stripping)** | ✅ Included | ✅ Included |
| **Attention Dwell Prior Tables (Simonov & Valletti / Lumen)** | ✅ Open Normative Factors | ✅ Multi-Factor Joint Calibration |
| **MFA (Made-For-Advertising) Clutter Discounting Engine** | ❌ (Manual domain lists) | ✅ Automated Spillover & MFA Discount |
| **Empirical Bayes Viewability Shrinkage (MML Auto-Tuning)** | ❌ (Static rules only) | ✅ Automatic $\lambda_i$ shrinkage |
| **Client Funnel Proxy Screening & Mass-Balanced Weighting** | ❌ (Manual guesswork) | ✅ `bidkit-pro weights` |
| **Automated 95th-Percentile Ternary Outlier Capping** | ❌ (Manual coding) | ✅ DV360-safe ternary emit |
| **Impression-Weighted Rule Quantization ($K$-Bins)** | ❌ (Exact rules only) | ✅ Bounded RMSE & $R^2$ |
| **Multi-Objective Pareto Trade-Off Scenarios (80/20, 50/50)** | ❌ | ✅ Gini & decile evaluation |
| **Customer Inventory Spend & Coverage Impact Audit** | ❌ | ✅ Projected coverage & spend |
| **Production Campaign Bundle Exporter & Audit HTML** | ❌ Basic HTML | ✅ Full 8-artifact bundle |

### Commercial Value Analysis: €100,000 Monthly Spend Scenario

| Dimension / Metric | Plain DV360 (Standard Bidding) | Open-Core (`dv360-bidkit`) | Enterprise Pro (`dv360-bidkit-pro`) |
| :--- | :--- | :--- | :--- |
| **AST Linter & Platform Rejections** | N/A (Standard DV360 CPA/CPC) | **0h turnaround** (catches syntax & type errors locally) | **0h turnaround** (validated before artifact packaging) |
| **Script Engineering & QA Time** | 10–15 hours manual Python scripting per campaign | **2–3 hours** (automated compilation & local simulation) | **< 30 minutes** (end-to-end automated pipeline & CLI) |
| **Outlier & Pacing Starvation Risk** | High risk ($\max/\text{median} > 20\times$ destabilizes pacing $\alpha_t$) | Manual inspection required via diagnostic JSON | **Automated 95th-percentile ternary capping** eliminates starvation |
| **Attention & Dwell Optimization** | 3rd-party vendor fees ($0.20–$0.40 CPM) or run unweighted | **Zero-vendor-fee open dwell tables** (format, position, device) | **Dynamic multi-factor calibration** with automated MFA & clutter discounting |
| **Small-Sample Tail Noise Waste** | Unprotected (long-tail domains get maximum bid weights) | Manual domain exclusions via `policy.csv` | **Empirical Bayes shrinkage** ($\lambda_i$) prevents ~€4k–€8k tail overspend |
| **Multi-Objective Funnel Optimization** | Single Floodlight conversion event only | Manual proxy weights (risk of proxy domination) | **Econometric mass balancing** preserves 65% conversion mass |
| **Pre-Flight Simulation & Safety** | None (upload and wait for Google's model to train) | **Deterministic AST simulation** against historical CSVs | **Turnkey 8-artifact campaign bundle** with HTML audit report |
| **Modeled Media Efficiency Uplift** | Baseline (€100k gross media spend) | **~€3,000 – €5,000** in avoided misconfigurations + engineering time saved | **~€15,000 – €25,000** modeled value uplift (reduced tail waste + balanced pacing) |

> [!NOTE]
> **Illustrative Scenario Model & Methodology Disclaimer**  
> Media efficiency projections (~€15k–€25k) represent a modeled statistical counterfactual on a €100,000/month display/video campaign exhibiting typical publisher-tail noise and multi-step conversion funnels. Actual media uplift depends on campaign targeting, bid floors, inventory composition, and baseline conversion rates. Guaranteed software capabilities are strictly engineering and computational: 100% adherence to Google's 2026.1 AST specification, zero platform rejection turnaround delay, deterministic local evaluation without `eval()`, and reproducible mathematical shrinkage.

---

## Command Line Interface (CLI)

```bash
# 1. Generate synthetic benchmark data and starter rules
bidkit demo --out-dir ./demo

# 2. Lint an existing script against the 2026.1 signal registry
bidkit lint script.py --format text

# 3. Compile a structured RuleSet and inventory policy into a DV360 script
bidkit compile --rules rules.json --policy policy.csv --out script.py

# 4. Simulate a script against historical DV360 report data
bidkit evaluate script.py --report report.csv --mapping mapping.json --out diagnostics.json

# 5. Render evaluation diagnostics to an HTML visual report
bidkit report diagnostics.json --out audit.html
```

---

## Python SDK Quickstart

```python
import json
from dv360_bidkit import (
    load_report,
    load_inventory_policy,
    compile_script,
    evaluate_script,
    lint_script,
    ReportMapping,
    RuleSet,
    Rule,
    RuleCondition,
    AggregationMode,
)

# 1. Define custom bidding rules
ruleset = RuleSet(
    aggregation_mode=AggregationMode.FIRST_MATCH,
    rules=[
        Rule(
            id="premium_news",
            conditions=[RuleCondition(field="domain", operator="in", value=["spiegel.de", "zeit.de"])],
            score=10.0,
        ),
        Rule(
            id="mobile_web",
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
comp_result = compile_script(ruleset)
print(comp_result.script_code)

# 3. Validate against syntax and signal registry
lint_rep = lint_script(comp_result.script_code)
assert lint_rep.is_valid

# 4. Pre-flight simulation on customer report
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
eval_rep = evaluate_script(comp_result.script_code, data, history_window_days=30)

print(f"Readiness: {eval_rep.readiness.status.value}")
print(f"Positively Scored Impressions: {eval_rep.metrics.positive_score_impressions:,}")
```

---

## Core Data Contracts

### 1. Report Mapping (`ReportMapping`)
Maps raw DV360 Standard or Instant Report column headers (English or German) to canonical fields:
```json
{
  "canonical_field_map": {
    "impressions": "Impressions",
    "measurable_impressions": "Active View: Measurable Impressions",
    "viewable_impressions": "Active View: Viewable Impressions",
    "domain": "App/URL",
    "device_type": "Device Type",
    "environment": "Environment",
    "line_item_id": "Line Item ID",
    "advertiser_id": "Advertiser ID",
    "clicks": "Clicks",
    "conversions": "Total Conversions"
  },
  "denominators": {
    "viewable_impressions": "measurable_impressions",
    "measurable_impressions": "impressions"
  },
  "row_grain": "homogeneous_aggregate",
  "date_window": "30d"
}
```

### 2. Customer Inventory Policy (`InventoryPolicy`)
Customer-defined domain and site lists specifying score overrides, training exclusions, or ad-serving block requests:
```csv
entity_type,entity_value,action,source,as_of,expiry,score,label
domain,fraud-network.com,exclude_from_training,audit_2026,2026-01-01,,0.0,Excluded from model
domain,direct-partner.com,set_score,pmp_deal,2026-01-01,2026-12-31,25.0,Preferred Deal Floor
domain,toxic-site.com,targeting_block_request,safety,2026-01-01,,0.0,Block Ad Serving
```

---

## ⚡ Commercial Pro Tier (`dv360-bidkit-pro`)

`dv360-bidkit-pro` is available for enterprise programmatic trading desks and agencies requiring automated Active View quality shrinkage, multi-objective Floodlight funnel balancing, and turnkey campaign bundle compilation:

👉 **[Get DV360 BidKit Pro License on Polar.sh](https://buy.polar.sh/polar_cl_jeD6EDIDtJxQJiCWKF1dfQ9vWHUomQUV7XxQD3Yj7bT)**

### Pro Installation & Setup

1. **Obtain License & Download Wheel Bundle:** Purchase on [Polar.sh](https://buy.polar.sh/polar_cl_jeD6EDIDtJxQJiCWKF1dfQ9vWHUomQUV7XxQD3Yj7bT) to receive your `BK_PRO_...` license key and pre-compiled native binary wheel bundle (`dv360-bidkit-pro-0.1.0-all-wheels.zip`).
2. **Install Platform Wheel:**
   ```bash
   unzip dv360-bidkit-pro-0.1.0-all-wheels.zip
   pip install --find-links . dv360-bidkit-pro
   ```
3. **Authenticate:**
   ```bash
   bidkit-pro auth --key BK_PRO_...
   ```

---

## 🤖 Agentic Custom Bidding Skill (`dv360-custom-bidding`)

`dv360-bidkit` ships with an Antigravity / Cursor / Claude Code agent skill: [`skills/dv360-custom-bidding/SKILL.md`](skills/dv360-custom-bidding/SKILL.md).

Equipped with this skill, AI coding assistants can:
1. Parse client DV360 report files and generate exact `ReportMapping` definitions.
2. Formulate multi-vector scoring algorithms and verify them against the DV360 signal registry.
3. Simulate positive score density to prevent `READINESS_STATE_INSUFFICIENT_DATA` launch failures.
4. Call `bidkit-pro weights` and `bidkit-pro build` to export production campaign bundles.

Install directly via [skills.sh](https://skills.sh/flovv/dv360-bidkit/dv360-custom-bidding) into Cursor, Claude Code, Antigravity, Copilot, and other agent environments:
```bash
npx skills add flovv/dv360-bidkit
```

---

## Documentation & AI Retrieval Index

- **Documentation Source:** [`docs/`](docs/)
- **Algorithmic Research Foundations:** [`docs/algorithmic_research_foundations.md`](docs/algorithmic_research_foundations.md)
- **LLM Summary Index:** [`docs/llms.txt`](docs/llms.txt)
- **Full Technical Reference:** [`docs/llms-full.txt`](docs/llms-full.txt)

---

## License

`dv360-bidkit` is open-source software licensed under the [MIT License](LICENSE).  
Commercial Pro extensions (`dv360-bidkit-pro`) are available under proprietary commercial licenses via Polar.sh.
