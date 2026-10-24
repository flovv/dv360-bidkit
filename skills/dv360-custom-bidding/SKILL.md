---
name: dv360-custom-bidding
description: Validate, lint, simulate, calibrate, and compile DV360 Custom Bidding algorithms and scripts using dv360-bidkit and dv360-bidkit-pro.
version: 0.1.0
author: flovv
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [dv360, custom-bidding, display-video-360, rtb, programmatic, viewability, empirical-bayes, value-based-bidding, floodlight]
    related_skills: []
---

# DV360 Custom Bidding Skill (`dv360-custom-bidding`)

Validates, simulates, calibrates, and compiles Google Display & Video 360 (DV360) Custom Bidding scripts and multi-objective funnel algorithms:
- **`dv360-bidkit` (Open-Core):** Fast AST-based linter for Google Custom Bidding grammar, 2026 signal registry verification, pre-flight simulation without `eval()`/`exec()`, Google S2 readiness checks (500 advertiser / 50 line item positives), deterministic RuleSet compilation, and customer inventory policy management.
- **`dv360-bidkit-pro` (Commercial):** Display Active View quality proxy fitting via automated Empirical Bayes shrinkage, client funnel evaluation and mass-balanced optimal weighting (`bidkit-pro weights`), multi-objective Pareto trade-off scenario grids, customer inventory impact audits, and complete production campaign bundle export (`script.py`, `rules.json`, `configuration.json`, `calibration.csv`, `diagnostics.json`, `audit.html`, `manifest.json`).

> [!IMPORTANT]
> **Division of Responsibilities:**
> * **The Engine (`dv360_bidkit` / `dv360_bidkit_pro`) executes all calculations:** Never write custom AST parsers, heuristic viewability formulas, or custom evaluation loops. Always invoke `lint_script()`, `compile_script()`, `evaluate_script()`, `fit_display_quality_proxy()`, or `evaluate_and_calibrate_funnel_weights()`.
> * **The Agent formats inputs and guides decisions:** Inspect client reports, define column mappings, run pre-flight simulations, audit proxy signals, check readiness diagnostics, and guide traders on Pareto trade-offs.
> * **Model Training vs. Targeting Distinction:** In DV360 custom bidding, `return None` excludes an impression from machine-learning model training; it does NOT block the ad from serving. Blocking requires line-item targeting lists. Never claim custom bidding scripts enforce publisher blacklists.

---

## Pro Licensing & Availability

Check whether Pro is available:
```python
try:
    import dv360_bidkit_pro as pro
    is_pro = True
except ImportError:
    is_pro = False
```

Pro requires a commercial license key or local dev bypass:
- **Environment Variable:** `os.environ["BIDKIT_PRO_API_KEY"] = "BK_PRO_..."`
- **Parameter:** Pass `api_key="BK_PRO_..."` directly into Pro functions.
- **Local Dev / CI Bypass:** Set `os.environ["BIDKIT_OFFLINE_LICENSE"] = "1"` or use a test key prefixed with `BK_TEST_`.

---

## Quick Reference: CLI Commands

| Task | Command |
| :--- | :--- |
| **Generate Demo Data** | `bidkit demo --out-dir demo` |
| **Lint Script** | `bidkit lint <script.py> [--format json]` |
| **Compile Rules** | `bidkit compile --rules <rules.json> [--policy <policy.json>] --out <script.py>` |
| **Evaluate Script** | `bidkit evaluate <script.py> --report <report.csv> --mapping <mapping.json> --out <diagnostics.json>` |
| **Render HTML Report** | `bidkit report <diagnostics.json> --out <audit.html>` |
| **Authenticate Pro** | `bidkit-pro auth [--key <key>]` |
| **Audit & Calibrate Weights** | `bidkit-pro weights --report <report.csv> --mapping <mapping.json> --macro "<col>" --proxies "<col1,col2>" --out <weights.json>` |
| **Build Campaign Bundle** | `bidkit-pro build --report <report.csv> --mapping <mapping.json> --config <campaign.json> [--weights <weights.json>] [--policy <policy.json>] --out-dir <bundle_dir>` |

---

## Core Data Contracts

### 1. Report Mapping (`ReportMapping`)
Maps customer CSV column headers to canonical DV360 BidKit fields:
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
  "date_window": "30d",
  "advertiser_scope": "Advertiser 12345"
}
```

### 2. Inventory Policy (`InventoryPolicy`)
Customer domain/site lists for score overrides and model training exclusions:
```json
{
  "entries": [
    {
      "entity_type": "domain",
      "entity_value": "spam-network.com",
      "action": "exclude_from_training",
      "source": "Agency Fraud Audit",
      "as_of": "2026-01-01"
    },
    {
      "entity_type": "domain",
      "entity_value": "direct-partner.com",
      "action": "set_score",
      "source": "Direct Contract",
      "as_of": "2026-01-01",
      "score": 25.0
    }
  ],
  "config": {
    "allow_subdomains": true,
    "strip_www": true,
    "unknown_action": "neutral_fallback"
  }
}
```

---

## Essential Workflows & Code Recipes

### Recipe 1: Linting an LLM-Generated Custom Bidding Script
Always lint generated scripts to catch syntax violations before uploading to DV360:
```python
from dv360_bidkit import lint_script

script_code = """
return first_match_aggregate([
    ([domain == "spiegel.de"], 10.0),
    ([device_type == 2], 5.0),
    ([True], 1.0)
])
"""

report = lint_script(script_code)
if not report.is_valid:
    for diag in report.diagnostics:
        print(f"[{diag.severity.value.upper()}] {diag.code}: {diag.message}")
        if diag.corrective_action:
            print(f"  Fix: {diag.corrective_action}")
else:
    print("✓ Script is 100% compliant with DV360 Custom Bidding DSL.")
```

### Recipe 2: Pre-Flight Simulation & Readiness Check
Simulate a script against historical DV360 report data to verify positive score density and Google S2 readiness:
```python
from dv360_bidkit import load_report, evaluate_script, ReportMapping

mapping = ReportMapping(
    canonical_field_map={
        "impressions": "Impressions",
        "domain": "App/URL",
        "device_type": "Device Type",
        "line_item_id": "Line Item ID"
    },
    date_window="30d"
)
report_data = load_report("dv360_performance.csv", mapping=mapping)

eval_report = evaluate_script(script_code, report_data, history_window_days=30)
m = eval_report.metrics
r = eval_report.readiness

print(f"Readiness: {r.status.value}")
print(f"Observed Positives: {r.observed_advertiser_positives:,} (Required: {r.required_advertiser_positives:,})")
print(f"Gini Concentration: {m.gini_coefficient.value}")
print(f"Max/Median Ratio: {m.max_to_median_ratio.value}x")
```

### Recipe 3: Client-Specific Funnel Evaluation & Weighting (`bidkit-pro`)
Evaluate client performance data to screen candidate proxy signals and generate balanced weights:
```python
from dv360_bidkit import load_report, ReportMapping
from dv360_bidkit_pro import evaluate_and_calibrate_funnel_weights

mapping = ReportMapping(
    canonical_field_map={
        "impressions": "Impressions",
        "purchases": "Total Conversions",
        "add_to_cart": "Add to Cart",
        "clicks": "Clicks",
        "viewable": "Active View: Viewable Impressions"
    }
)
report_data = load_report("client_funnel.csv", mapping=mapping)

weighting_report = evaluate_and_calibrate_funnel_weights(
    report_data,
    macro_column="purchases",
    candidate_proxies=["add_to_cart", "clicks", "viewable"],
    macro_weight=100.0,
    target_macro_mass_share=0.65  # 65% macro / 35% proxies
)

print(f"Starvation Risk: {weighting_report.projected_starvation_risk}")
for proxy in weighting_report.evaluated_proxies:
    print(f"  {proxy.proxy_name}: Status={proxy.status.upper()} | Lift={proxy.lift:.2f}x | Calibrated Weight={proxy.final_calibrated_weight}")
```

### Recipe 4: Build Full Campaign Bundle (`bidkit-pro`)
Fit Active View proxy via Empirical Bayes shrinkage, apply calibrated funnel weights and Floodlight recipes (including DV360-compliant ternary caps), quantize domain rules, and export the campaign bundle (including `targeting_block_request.csv` if ad-serving block requests are present):
```python
from dv360_bidkit import load_report, load_inventory_policy, ReportMapping
from dv360_bidkit_pro import (
    ProConfig,
    ProfileType,
    FloodlightRecipe,
    build_campaign_bundle,
    export_campaign_bundle
)

config = ProConfig(
    profile=ProfileType.DISPLAY_VIEWABILITY,
    auto_tune_shrinkage=True,
    score_scale=10.0,
    quantize_bins=15,
    objective_recipes=[
        FloodlightRecipe(
            activity_id=123456,
            attribution_model_id=0,
            counting_method="value",
            weight=25.0,
            cap=100.0  # Emits DV360 ternary cap: (100.0 if val > 100.0 else val)
        )
    ]
)

policy = load_inventory_policy("inventory_policy.json")
bundle = build_campaign_bundle(
    report_data,
    config=config,
    policy=policy,
    weights_report=weighting_report,  # Optional: pipe calibrated weights directly into build
)
export_campaign_bundle(bundle, output_dir="./output_bundle")
```

---

## Best Practices & Anti-Patterns

1. **Econometric Transition Bound:**  
   Always cap proxy weights at $w_{\text{proxy}} \le w_{\text{macro}} \times P(\text{Macro} \mid \text{Proxy})$. Never value an Add-to-Cart higher than its empirical conversion rate to purchase.
2. **Prevent Proxy Domination (Score Mass Rule):**  
   Ensure the macro conversion retains at least **$50\% \text{ to } 75\%$** of the total score mass ($M = \sum N_k w_k$). If a dense proxy signal generates $90\%$ of total score mass, Google's model will optimize purely for the proxy and ignore conversions.
3. **Outlier Capping on Continuous Values:**  
   Always cap continuous metrics (revenue/conversion value, time on screen) at the **95th percentile**. Uncapped outliers cause `SCORE_VARIANCE_INFLATION` ($\max / \text{median} > 20\times$), destabilizing DV360's daily pacing multipliers ($\alpha_t$) and triggering bid starvation.
4. **Reject Click-Only Proxies:**  
   Never rely solely on raw Clicks (`CTR`) as an alternative bidding signal. Click optimization attracts accidental clicks, bot traffic, and low-dwell MFA inventory. Use Active View viewability ($\ge 5\text{s}$) or mid-funnel actions instead.
5. **CTV Web Domain Separation:**  
   Connected TV (`device_type == 4`) apps report app bundle IDs, not web domains. Never mix web domain rules with CTV targeting.
