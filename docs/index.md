---
layout: home

hero:
  name: "DV360 BidKit"
  text: "Production Custom Bidding DSL Engine"
  tagline: "Turn DV360 report data into verified, high-performance custom bidding algorithms without guesswork, AST syntax errors, or platform rejections."
  actions:
    - theme: brand
      text: Quickstart Guide
      link: /quickstart
    - theme: alt
      text: Get Pro License
      link: https://buy.polar.sh/polar_cl_jeD6EDIDtJxQJiCWKF1dfQ9vWHUomQUV7XxQD3Yj7bT
    - theme: alt
      text: GitHub
      link: https://github.com/flovv/dv360-bidkit

features:
  - icon: 🛡️
    title: Google 2026.1 AST Linter
    details: Complete AST-based parser validating functions, dimension codes, return structures, and deprecation checks before platform upload.
  - icon: ⚡
    title: Pre-Flight Simulator
    details: Deterministic local evaluation against historical report CSVs without eval() or exec(), computing score distributions and positive rates.
  - icon: 📊
    title: Google S2 Readiness Checks
    details: Validates 500 advertiser / 50 line-item positive thresholds, max/median ratios (<20x), and Gini inequality to prevent pacing starvation.
  - icon: 🎯
    title: Deterministic RuleSet Compiler
    details: Compiles customer business rules, ternary outlier caps, and inventory policies into compliant, budget-bounded Python DSL.
  - icon: 🤖
    title: Agent-Ready AI Skill
    details: Native dv360-custom-bidding skill empowering Cursor, Claude Code, Antigravity, and Copilot to write bug-free bidding scripts.
  - icon: 💎
    title: Pro Commercial Extensions
    details: Empirical Bayes Active View shrinkage, client funnel mass-balancing, Pareto trade-off scenario grids, and turnkey campaign bundles.
---

# DV360 BidKit Documentation

**DV360 Custom Bidding DSL Linter, Pre-Flight Simulator, and Rule Compiler**

`dv360-bidkit` provides an open-source MIT-licensed toolkit for engineering, validating, and compiling Google Display & Video 360 (DV360) custom bidding algorithms.

---

## Architecture: Open-Core vs. Pro

`dv360-bidkit` follows an open-core architecture where the fundamental compiler, grammar validator, and local AST execution engine are open-source, while algorithmic calibration and funnel optimization are commercial:

```mermaid
flowchart TD
    subgraph OpenCore["dv360-bidkit (Open-Source Core — MIT)"]
        A[DV360 DSL Grammar & Signal Registry]
        B[AST Linter & Deprecation Checker]
        C[Safe AST Interpreter & Simulator]
        D[RuleSet Compiler & Simplifier]
        E[Report Loader & Preamble/Footer Stripper]
        F[Customer Inventory Policy Normalizer]
    end

    subgraph ProExtension["dv360-bidkit-pro (Commercial Extension)"]
        G[Empirical Bayes Viewability Shrinkage Calibration]
        H[Client Funnel Screening & Mass-Balanced Weighting]
        I[Automated Ternary Outlier Capping]
        J[Impression-Weighted Rule Quantization]
        K[Multi-Objective Pareto Frontier Scenarios]
        L[Turnkey Production Bundle Exporter]
    end

    E --> C
    D --> B
    B --> C
    G --> H
    H --> J
    J --> D
    F --> D
    D --> L
```

::: tip DV360 BidKit Pro Commercial License
Supercharge your custom bidding workflows with automated Empirical Bayes Active View calibration, multi-objective funnel mass balancing (`bidkit-pro weights`), ternary outlier capping, and complete campaign bundle export.

👉 **[Get DV360 BidKit Pro License](https://buy.polar.sh/polar_cl_jeD6EDIDtJxQJiCWKF1dfQ9vWHUomQUV7XxQD3Yj7bT)**
:::

---

## Commercial Value Analysis: €100,000 Monthly Spend Scenario

| Dimension / Metric | Plain DV360 (Standard Bidding) | Open-Core (`dv360-bidkit`) | Enterprise Pro (`dv360-bidkit-pro`) |
| :--- | :--- | :--- | :--- |
| **AST Linter & Platform Rejections** | N/A (Standard DV360 CPA/CPC) | **0h turnaround** (catches syntax & type errors locally) | **0h turnaround** (validated before artifact packaging) |
| **Script Engineering & QA Time** | 10–15 hours manual Python scripting per campaign | **2–3 hours** (automated compilation & local simulation) | **< 30 minutes** (end-to-end automated pipeline & CLI) |
| **Outlier & Pacing Starvation Risk** | High risk ($\max/\text{median} > 20\times$ destabilizes pacing $\alpha_t$) | Manual inspection required via diagnostic JSON | **Automated 95th-percentile ternary capping** eliminates starvation |
| **Small-Sample Tail Noise Waste** | Unprotected (long-tail domains get maximum bid weights) | Manual domain exclusions via `policy.csv` | **Empirical Bayes shrinkage** ($\lambda_i$) prevents ~€4k–€8k tail overspend |
| **Multi-Objective Funnel Optimization** | Single Floodlight conversion event only | Manual proxy weights (risk of proxy domination) | **Econometric mass balancing** preserves 65% conversion mass |
| **Pre-Flight Simulation & Safety** | None (upload and wait for Google's model to train) | **Deterministic AST simulation** against historical CSVs | **Turnkey 8-artifact campaign bundle** with HTML audit report |
| **Modeled Media Efficiency Uplift** | Baseline (€100k gross media spend) | **~€3,000 – €5,000** in avoided misconfigurations + engineering time saved | **~€15,000 – €25,000** modeled value uplift (reduced tail waste + balanced pacing) |

::: tip Illustrative Scenario Model & Methodology Disclaimer
Media efficiency projections (~€15k–€25k) represent a modeled statistical counterfactual on a €100,000/month display/video campaign exhibiting typical publisher-tail noise and multi-step conversion funnels. Actual media uplift depends on campaign targeting, bid floors, inventory composition, and baseline conversion rates. Guaranteed software capabilities are strictly engineering and computational: 100% adherence to Google's 2026.1 AST specification, zero platform rejection turnaround delay, deterministic local evaluation without `eval()`, and reproducible mathematical shrinkage.
:::

---

## Signal Registry Reference (Google 2026.1 Specification)

| Signal / Function | Kind | Return Type | Google Spec Reference | Status | Notes |
|---|---|---|---|---|---|
| `first_match_aggregate` | Aggregation | `float` | S1 | Verified | Sequential evaluation returning first matched criteria weight |
| `sum_aggregate` | Aggregation | `float` | S1 | Verified | Sums matched condition weights |
| `max_aggregate` | Aggregation | `float` | S1 | Verified | Returns highest matched weight |
| `total_conversion_count` | Function | `float` | S1 | Verified | Count of conversions for Floodlight activity ID and model ID (0=last touch) |
| `total_conversion_value` | Function | `float` | S1 | Verified | Monetary revenue value for Floodlight sales activity |
| `total_conversion_quantity` | Function | `float` | S1 | Verified | Total transaction item quantity for Floodlight activity |
| `conversion_custom_variable`| Function | `str` | S1 | Verified | Value of Floodlight custom variable (`u_variable_index`) |
| `ga4_conversions_count` | Function | `int` | S1 | Verified | Count of GA4 events for `property_id` and `conversion_event_name` |
| `domain` | Dimension | `str` | S1 | Verified | Normalized domain hostname (app bundle ID on Connected TV) |
| `site_id` | Dimension | `int` | S1 | Verified | DV360 site identifier |
| `device_type` | Dimension | `int` | S1 | Verified | 1=Desktop, 2=Smartphone, 3=Tablet, 4=Connected TV |
| `environment` | Dimension | `int` | S1 | Verified | 1=Web, 2=App |
| `country_code` | Dimension | `str` | S1 | Verified | ISO 3166-1 alpha-2 country code |
| `line_item_id` | Dimension | `int` | S1 | Verified | DV360 Line Item ID |
| `advertiser_id` | Dimension | `int` | S1 | Verified | DV360 Advertiser ID |
| `browser_id` | Dimension | `int` | S1 | Deprecated | Removed from recent DV360 API releases |

---

## Google S2 Pre-Flight Training Readiness Standards

DV360 models require sufficient positive score historical density over the relevant lookback window (typically 30 days):
* **Advertiser minimum:** $\ge 500$ positively scored impressions across the advertiser.
* **Line item minimum:** $\ge 50$ positively scored impressions per active line item.
* **Score Distribution Health:**
  * Positive Scoring Rate: $5\% \text{ to } 40\%$ (lower risks cold-start starvation; higher risks uninformative bidding).
  * Max-to-Median Score Ratio ($\max / \text{median}$): $\le 20.0\times$ (higher destabilizes DSP daily pacing controllers).
  * Gini Inequality: $0.25 \text{ to } 0.65$ (reflects clear publisher tiering without extreme winner-takes-all distortion).

---

## Command Reference

### `dv360-bidkit` (Core)
* `bidkit demo [--out-dir <dir>]`: Generate synthetic demo fixtures and run an instant pre-flight diagnostic simulation.
* `bidkit lint <script.py> [--format text|json]`: Validate script syntax against AST rules and the 2026.1 signal registry.
* `bidkit compile --rules <rules.json> [--policy <policy.csv>] [--out <script.py>]`: Compile structured rules into production DSL.
* `bidkit evaluate <script.py> --report <report.csv> --mapping <mapping.json> [--out <diagnostics.json>]`: Simulate script performance on historical data.
* `bidkit report <diagnostics.json> [--out <audit.html>]`: Render visual HTML audit report.

### `dv360-bidkit-pro` (Pro)
* `bidkit-pro auth [--key <key>]`: Authenticate commercial license with Polar.sh.
* `bidkit-pro weights --report <report.csv> --mapping <mapping.json> --macro "<col>" --proxies "<col1,col2>" [--out <weights.json>]`: Screen proxies and compute mass-balanced weights.
* `bidkit-pro build --report <report.csv> --mapping <mapping.json> --config <campaign.json> [--weights <weights.json>] [--policy <policy.csv>] [--out-dir <bundle_dir>]`: Export turnkey 8-artifact production bundle.

---

## DV360 BidKit Pro Installation & Authentication

1. **Obtain License & Download Wheel Bundle:** Purchase on [Polar.sh](https://buy.polar.sh/polar_cl_jeD6EDIDtJxQJiCWKF1dfQ9vWHUomQUV7XxQD3Yj7bT) and download `dv360-bidkit-pro-0.1.0-all-wheels.zip`.
2. **Install Platform Binary:**
   ```bash
   unzip dv360-bidkit-pro-0.1.0-all-wheels.zip
   pip install --find-links . dv360-bidkit-pro
   ```
3. **Authenticate License:**
   ```bash
   bidkit-pro auth --key BK_PRO_...
   ```
