# DV360 BidKit Pro

`dv360-bidkit-pro` is the enterprise extension for programmatic trading desks, media agencies, and algorithmic bidders running production campaigns on Google Display & Video 360.

::: tip Commercial License
Get instant access to pre-compiled native binary wheels (Linux, macOS, Windows) and commercial license keys:

👉 **[Purchase DV360 BidKit Pro on Polar.sh](https://buy.polar.sh/polar_cl_jeD6EDIDtJxQJiCWKF1dfQ9vWHUomQUV7XxQD3Yj7bT)**
:::

---

## What Pro Delivers

While the open-core `dv360-bidkit` handles grammar linting, basic rule compilation, and simulation, `dv360-bidkit-pro` provides the statistical algorithms and automated campaign packaging needed for enterprise-scale value bidding:

| Capability | Core (`dv360-bidkit`) | Pro (`dv360-bidkit-pro`) |
| :--- | :---: | :---: |
| **AST Linter & Google 2026 DSL Validator** | ✅ | ✅ |
| **Pre-Flight Local Simulator (No `eval()`)** | ✅ | ✅ |
| **Google S2 Training Readiness Standards** | ✅ | ✅ |
| **RuleSet Compiler & Simplifier** | ✅ | ✅ |
| **Active View Empirical Bayes Shrinkage** | ❌ | ✅ |
| **Client Funnel Weighting (`bidkit-pro weights`)** | ❌ | ✅ |
| **Automated Ternary Outlier Capping** | ❌ | ✅ |
| **Impression-Weighted Rule Quantization** | ❌ | ✅ |
| **Multi-Objective Pareto Trade-Off Grids** | ❌ | ✅ |
| **Turnkey Campaign Bundle Export (8 artifacts)** | ❌ | ✅ |
| **Pre-Compiled Native C-Extensions (Cython)** | ❌ | ✅ |

---

## Commercial Value Analysis: €100,000 Monthly Spend Scenario

How does running custom bidding with DV360 BidKit translate into tangible operational and media performance? Below is an illustrative comparative analysis for an enterprise programmatic campaign spending €100,000/month:

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

## The 4 Custom Bidding Traps Solved by Pro

### 1. Small-Sample Winner's Curse (Publisher Noise)
* **Problem:** Long-tail domains with small impression counts (e.g., $3/3$ viewable impressions $= 100\%$) get assigned maximum bid multipliers by naive rules, burning budget on unverified tail traffic.
* **Pro Solution:** Empirical Bayes shrinkage calibrates domain scores towards global baseline performance ($\lambda_i = \frac{n_i}{n_i + k^*}$), pulling low-volume publishers toward the campaign mean while granting confidence only to statistically significant volume.

### 2. Proxy Domination in Multi-Objective Funnels
* **Problem:** When combining high-funnel proxies (e.g., Active View viewability or clicks) with low-funnel Floodlight conversions, high-frequency proxies generate $>90\%$ of total score mass, causing Google's ML model to ignore conversions completely.
* **Pro Solution:** `bidkit-pro weights` enforces econometric transition caps ($w_{\text{proxy}} \le w_{\text{macro}} \times P(\text{Macro} \mid \text{Proxy})$) and mass balances proxy weights so the primary conversion retains $65\%$ of score mass.

### 3. Score Variance Inflation & Pacing Starvation
* **Problem:** Uncapped continuous Floodlight revenue values or extreme viewability durations cause $\max / \text{median} > 20\times$, which destabilizes DV360's daily budget pacing multipliers ($\alpha_t$) and causes bid starvation.
* **Pro Solution:** Automated 95th-percentile ternary outlier capping compiles compliant `(cap if val > cap else val)` expressions into the script.

### 4. Rule Budget Overflow
* **Problem:** Granular domain scoring easily exceeds DV360's script size and evaluation step limits.
* **Pro Solution:** Pro's impression-weighted quantization compresses thousands of domain rules into optimal discrete scoring tiers while minimizing distortion.

---

## Pro Installation & Authentication

### Step 1: Purchase & Download Bundle
1. Purchase a license on **[Polar.sh](https://buy.polar.sh/polar_cl_jeD6EDIDtJxQJiCWKF1dfQ9vWHUomQUV7XxQD3Yj7bT)**.
2. Download your license benefit: `dv360-bidkit-pro-0.1.0-all-wheels.zip`.

### Step 2: Install Platform Binary
Extract the zip and install the matching pre-compiled Cython wheel for your platform (Python 3.10–3.13 on Linux, macOS, or Windows):

```bash
unzip dv360-bidkit-pro-0.1.0-all-wheels.zip
pip install --find-links . dv360-bidkit-pro
```

### Step 3: Authenticate
Authenticate your license using the `BK_PRO_...` key from your Polar receipt:

```bash
# Via CLI command:
bidkit-pro auth --key BK_PRO_your_license_key

# Or via environment variable:
export BIDKIT_PRO_API_KEY="BK_PRO_your_license_key"
```

Pro validates your license with Polar.sh and stores a cryptographically signed 24-hour HMAC cache locally (`~/.bidkit_license.cache`), allowing offline and CI/CD operation without constant API pings.

---

## Pro CLI Commands

### `bidkit-pro weights`
Audits candidate proxy signals and computes mass-balanced optimal weights:

```bash
bidkit-pro weights \
  --report dv360_performance.csv \
  --mapping mapping.json \
  --macro "conversions" \
  --proxies "viewable_impressions,clicks" \
  --out weights.json
```

### `bidkit-pro build`
Builds a complete, production-ready campaign bundle:

```bash
bidkit-pro build \
  --report dv360_performance.csv \
  --mapping mapping.json \
  --config campaign.json \
  --weights weights.json \
  --policy policy.csv \
  --out-dir ./output_bundle
```

**Exported Artifacts in `./output_bundle`:**
1. `script.py`: Production DV360 Custom Bidding DSL script.
2. `rules.json`: Compiled RuleSet schema.
3. `configuration.json`: Full campaign configuration.
4. `calibration.csv`: Empirical Bayes domain shrinkage parameters.
5. `diagnostics.json`: Full pre-flight simulation and readiness report.
6. `audit.html`: Visual self-contained HTML audit dashboard.
7. `targeting_block_request.csv`: Domains requiring ad-serving blocks (if present in policy).
8. `manifest.json`: Cryptographic SHA-256 build manifest with input hashes.
