# AI Agent Skill (`dv360-custom-bidding`)

`dv360-bidkit` ships with an out-of-the-box agent skill: [`skills/dv360-custom-bidding/SKILL.md`](https://github.com/flovv/dv360-bidkit/blob/main/skills/dv360-custom-bidding/SKILL.md).

Equipped with this skill, AI coding assistants (Cursor, Claude Code, Antigravity, GitHub Copilot) act as expert programmatic bidding engineers who never hallucinate unsupported DV360 syntax or uncalibrated weights.

---

## Installation into Agent Environments

### 1. Via skills.sh (Universal Agent Installer)

Install directly with one command:

```bash
npx skills add flovv/dv360-bidkit
```

### 2. Manual Drop-In

Copy the skill directory into your project's agent folder:

```bash
# For Cursor / Antigravity:
mkdir -p .agents/skills/dv360-custom-bidding
cp -r skills/dv360-custom-bidding/* .agents/skills/dv360-custom-bidding/

# For Claude Code:
mkdir -p .claude/skills/dv360-custom-bidding
cp -r skills/dv360-custom-bidding/* .claude/skills/dv360-custom-bidding/
```

---

## Agent Guidelines Enforced by the Skill

When the skill is active, AI models are constrained by strict domain rules:

1. **The Engine Executes All Calculations:**  
   The AI assistant will never write custom heuristic formulas or ad-hoc viewability calculations in Python. It always invokes `dv360_bidkit` functions (`lint_script()`, `compile_script()`, `evaluate_script()`, `fit_display_quality_proxy()`, or `evaluate_and_calibrate_funnel_weights()`).
2. **Model Training Exclusions vs. Ad-Serving Blocks:**  
   In DV360, `return None` excludes an impression from ML model training; it **does NOT block the ad from serving**. The agent will never claim custom bidding scripts enforce publisher blacklists. Ad-serving blocks must be exported to line-item targeting exclusion lists (`targeting_block_request.csv`).
3. **Econometric Transition Caps on Proxies:**  
   The agent will enforce $w_{\text{proxy}} \le w_{\text{macro}} \times P(\text{Macro} \mid \text{Proxy})$, preventing uncalibrated proxy values from dominating model training.
4. **Outlier Capping on Continuous Distributions:**  
   The agent automatically enforces ternary caps (`(cap if val > cap else val)`) on revenue and duration signals at the 95th percentile to prevent pacing controller destabilization.
5. **No Runtime Wildcard Subdomain Claims:**  
   The agent knows Google's scoring engine evaluates exact string equality and numeric ranges, and will not emit regex or dynamic `.endswith()` patterns in compiled scripts.

---

## Example Agent Prompt

Once the skill is installed, you can simply ask your AI coding assistant:

> *"Analyze `client_q3_report.csv`, map the columns, check whether we have enough historical volume for Google S2 readiness, and compile a 3-tier viewability and Floodlight conversion bidding script."*

The agent will load the report using `ReportMapping`, simulate performance with `evaluate_script()`, diagnose readiness metrics, and output verified, production-ready DV360 DSL.
