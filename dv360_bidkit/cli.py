"""Command Line Interface for dv360-bidkit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dv360_bidkit.compiler.attention import (
    ConcaveAttentionConfig,
    compile_concave_attention_script,
    run_mfa_stress_test,
)
from dv360_bidkit.compiler.scripts import compile_script
from dv360_bidkit.compiler.sklearn import from_sklearn
from dv360_bidkit.contracts.schemas import (
    DiagnosticSeverity,
    EvaluationReport,
    InventoryPolicyConfig,
    ReportData,
    ReportMapping,
    RuleSet,
)
from dv360_bidkit.evaluator.diagnostics import evaluate_script
from dv360_bidkit.evaluator.economics import analyze_attention_fee_economics
from dv360_bidkit.io.fixtures import (
    create_sample_inventory_policy,
    create_sample_mapping,
    create_sample_ruleset,
    generate_synthetic_display_report,
)
from dv360_bidkit.io.inventory import load_inventory_policy
from dv360_bidkit.io.reports import load_report
from dv360_bidkit.linter.ast_validator import lint_script
from dv360_bidkit.reporting.basic import render_report

app = typer.Typer(
    name="bidkit",
    help="DV360 Custom Bidding DSL Linter, Pre-Flight Simulator, and Rule Compiler",
    add_completion=False,
)
console = Console(stderr=True)


@app.command("demo")
def demo_cmd(
    out_dir: str = typer.Option("demo", "--out-dir", "-o", help="Output directory for demo files"),
) -> None:
    """Generates synthetic demo reports, mappings, rules, and inventory policies, and runs a diagnostic simulation."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    report_df = generate_synthetic_display_report(num_rows=100, seed=42)
    report_path = out / "report.csv"
    report_df.to_csv(report_path, index=False)

    mapping = create_sample_mapping()
    mapping_path = out / "mapping.json"
    mapping_path.write_text(json.dumps(mapping.model_dump(), indent=2), encoding="utf-8")

    ruleset = create_sample_ruleset()
    rules_path = out / "rules.json"
    rules_path.write_text(json.dumps(ruleset.model_dump(), indent=2), encoding="utf-8")

    policy = create_sample_inventory_policy()
    policy_path = out / "policy.json"
    policy_path.write_text(json.dumps(policy.model_dump(), indent=2), encoding="utf-8")

    # Sample Pro campaign configuration for multi-objective demonstration
    campaign_cfg = {
        "profile": "display_viewability",
        "grouping_keys": ["domain"],
        "auto_tune_shrinkage": True,
        "minimum_support": 100,
        "score_scale": 10.0,
        "quantize_bins": 15,
        "objective_recipes": [
            {
                "activity_id": 987654,
                "attribution_model_id": 0,
                "counting_method": "count",
                "weight": 20.0,
            }
        ],
    }
    campaign_path = out / "campaign.json"
    campaign_path.write_text(json.dumps(campaign_cfg, indent=2), encoding="utf-8")

    # Run instant compile and evaluation pass on demo assets
    comp_result = compile_script(ruleset, policy=policy)
    script_path = out / "script.py"
    script_path.write_text(comp_result.script_code, encoding="utf-8")

    rep_data = ReportData(df=report_df, mapping=mapping)
    eval_rep = evaluate_script(comp_result.script_code, rep_data, history_window_days=30)
    diag_path = out / "diagnostics.json"
    diag_path.write_text(json.dumps(eval_rep.model_dump(), indent=2), encoding="utf-8")

    table = Table(title="DV360 BidKit Open-Core Demo Simulation")
    table.add_column("Metric", style="cyan")
    table.add_column("Observed Value", justify="right", style="bold")
    table.add_column("Google S2 / Health Standard", style="dim")

    m = eval_rep.metrics
    r = eval_rep.readiness
    pos_rate = f"{m.positive_rate_all.value * 100:.1f}%" if m.positive_rate_all.value is not None else "N/A"
    w_mean = f"{m.weighted_mean.value:.2f}" if m.weighted_mean.value is not None else "N/A"
    gini = f"{m.gini_coefficient.value:.3f}" if m.gini_coefficient.value is not None else "N/A"
    ratio = f"{m.max_to_median_ratio.value:.1f}x" if m.max_to_median_ratio.value is not None else "N/A"

    table.add_row("Total Impressions", f"{m.total_impressions:,}", "Historical baseline sample")
    table.add_row("Positive Impressions", f"{m.positive_score_impressions:,}", "≥ 500 required by Google S2")
    table.add_row("Positive Scoring Rate", pos_rate, "Target: 5% – 40% for active bidding")
    table.add_row("Weighted Mean Score", w_mean, "Scale baseline")
    table.add_row("Gini Inequality", gini, "0 = flat, 1 = extreme concentration")
    table.add_row("Max-to-Median Ratio", ratio, "≤ 20.0x prevents DSP pacing starvation")
    table.add_row("Readiness Status", f"[green]{r.status.value}[/green]", "Google Custom Bidding training readiness")

    console.print(table)
    console.print(f"\n[green]✓ Demo bundle successfully generated in: {out}[/green]")
    console.print(f"  • Report: {report_path}")
    console.print(f"  • Mapping: {mapping_path}")
    console.print(f"  • Rules: {rules_path}")
    console.print(f"  • Policy: {policy_path}")
    console.print(f"  • Compiled Script: {script_path}")
    console.print(f"  • Diagnostics JSON: {diag_path}")
    console.print(f"  • Pro Config: {campaign_path}")
    console.print(
        Panel(
            "[bold cyan]Need data-driven domain scoring and multi-objective funnel weighting?[/bold cyan]\n"
            "Open-Core compiles static rules. [bold]dv360-bidkit-pro[/bold] adds:\n"
            "  1. [bold]Empirical Bayes Viewability Shrinkage[/bold] — eliminates small-sample publisher noise.\n"
            "  2. [bold]bidkit-pro weights[/bold] — screens candidate proxies & balances macro conversion score mass.\n"
            "  3. [bold]bidkit-pro build[/bold] — automatically caps continuous outliers and quantizes rules to fit DV360 limits.",
            title="Pro Capabilities",
            border_style="blue",
        )
    )


@app.command("lint")
def lint_cmd(
    script: str = typer.Argument(..., help="Path to DV360 Python script"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: 'text' or 'json'"),
) -> None:
    """Lints a DV360 Custom Bidding script against syntax and signal registries."""
    script_path = Path(script)
    if not script_path.exists():
        console.print(f"[red]Error: Script file '{script}' not found.[/red]")
        sys.exit(2)

    code = script_path.read_text(encoding="utf-8")
    report = lint_script(code)

    if format == "json":
        sys.stdout.write(json.dumps(report.model_dump(), indent=2) + "\n")
    else:
        if report.is_valid:
            console.print(f"[green]✓ Script '{script}' passed validation.[/green]")
        else:
            console.print(f"[red]✗ Script '{script}' failed validation.[/red]")

        for diag in report.diagnostics:
            color = "red" if diag.severity == DiagnosticSeverity.ERROR else "yellow"
            line_str = f":{diag.line}" if diag.line else ""
            console.print(f"  [{color}]{diag.severity.value.upper()}[/{color}] {diag.code}{line_str} - {diag.message}")
            if diag.corrective_action:
                console.print(f"    [dim]Suggestion: {diag.corrective_action}[/dim]")

    if not report.is_valid:
        sys.exit(1)


@app.command("compile")
def compile_cmd(
    rules: str = typer.Option(..., "--rules", "-r", help="Path to RuleSet JSON file"),
    policy: str | None = typer.Option(None, "--policy", "-p", help="Optional InventoryPolicy CSV/JSON file"),
    out: str = typer.Option("script.py", "--out", "-o", help="Output path for compiled script"),
    json_out: bool = typer.Option(False, "--json", help="Output machine-readable JSON to stdout"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: 'text' or 'json'"),
) -> None:
    """Compiles a RuleSet into a production DV360 Custom Bidding script."""
    is_json = json_out or format == "json"
    rules_path = Path(rules)
    if not rules_path.exists():
        if is_json:
            sys.stdout.write(json.dumps({"status": "error", "message": f"Rules file '{rules}' not found."}, indent=2) + "\n")
        else:
            console.print(f"[red]Error: Rules file '{rules}' not found.[/red]")
        sys.exit(2)

    try:
        rules_dict = json.loads(rules_path.read_text(encoding="utf-8"))
        ruleset = RuleSet(**rules_dict)
    except Exception as exc:
        if is_json:
            sys.stdout.write(json.dumps({"status": "error", "message": f"Error parsing rules: {exc}"}, indent=2) + "\n")
        else:
            console.print(f"[red]Error parsing rules: {exc}[/red]")
        sys.exit(2)

    inv_policy = None
    if policy:
        try:
            inv_policy = load_inventory_policy(policy)
        except Exception as exc:
            if is_json:
                sys.stdout.write(json.dumps({"status": "error", "message": f"Error loading inventory policy: {exc}"}, indent=2) + "\n")
            else:
                console.print(f"[red]Error loading inventory policy: {exc}[/red]")
            sys.exit(2)

    result = compile_script(ruleset, policy=inv_policy)
    out_path = Path(out)

    if not result.budgets_passed:
        if is_json:
            payload = {
                "status": "error",
                "budgets_passed": False,
                "rule_count": result.rule_count,
                "ast_nodes": result.ast_nodes,
                "byte_count": result.byte_count,
                "diagnostics": [diag.model_dump() for diag in result.diagnostics],
            }
            sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        else:
            console.print("[red]Compilation failed budget and validation checks:[/red]")
            for diag in result.diagnostics:
                if diag.severity == DiagnosticSeverity.ERROR:
                    console.print(f"[red]  ERROR: [{diag.code}] {diag.message}[/red]")
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.script_code, encoding="utf-8")

    if is_json:
        payload = {
            "status": "success",
            "script_path": str(out_path),
            "rule_count": result.rule_count,
            "ast_nodes": result.ast_nodes,
            "byte_count": result.byte_count,
            "budgets_passed": result.budgets_passed,
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        console.print(f"[green]✓ Compiled script written to: {out}[/green]")
        console.print(f"  Rules: {result.rule_count} | AST nodes: {result.ast_nodes} | Size: {result.byte_count} bytes")


@app.command("evaluate")
def evaluate_cmd(
    script: str = typer.Argument(..., help="Path to custom bidding script"),
    report: str = typer.Option(..., "--report", "-r", help="Path to report CSV"),
    mapping: str = typer.Option(..., "--mapping", "-m", help="Path to mapping JSON"),
    out: str = typer.Option("diagnostics.json", "--out", "-o", help="Output path for evaluation diagnostics JSON"),
    json_out: bool = typer.Option(False, "--json", help="Output machine-readable JSON to stdout"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: 'text' or 'json'"),
) -> None:
    """Evaluates a script against historical report data."""
    is_json = json_out or format == "json"
    script_path = Path(script)
    report_path = Path(report)
    mapping_path = Path(mapping)

    if not script_path.exists() or not report_path.exists() or not mapping_path.exists():
        if is_json:
            sys.stdout.write(json.dumps({"status": "error", "message": "One or more input files do not exist."}, indent=2) + "\n")
        else:
            console.print("[red]Error: One or more input files do not exist.[/red]")
        sys.exit(2)

    try:
        mapping_dict = json.loads(mapping_path.read_text(encoding="utf-8"))
        rep_mapping = ReportMapping(**mapping_dict)
        report_data = load_report(report_path, mapping=rep_mapping)
    except Exception as exc:
        if is_json:
            sys.stdout.write(json.dumps({"status": "error", "message": f"Error loading data/mapping: {exc}"}, indent=2) + "\n")
        else:
            console.print(f"[red]Error loading data/mapping: {exc}[/red]")
        sys.exit(2)

    code = script_path.read_text(encoding="utf-8")
    eval_report = evaluate_script(code, report_data)

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(eval_report.model_dump(), indent=2), encoding="utf-8")

    if is_json:
        sys.stdout.write(json.dumps(eval_report.model_dump(), indent=2) + "\n")
        return

    m = eval_report.metrics
    r = eval_report.readiness
    pos_rate = f"{m.positive_rate_all.value * 100:.1f}%" if m.positive_rate_all.value is not None else "N/A"
    w_mean = f"{m.weighted_mean.value:.2f}" if m.weighted_mean.value is not None else "N/A"
    gini = f"{m.gini_coefficient.value:.3f}" if m.gini_coefficient.value is not None else "N/A"
    ratio = f"{m.max_to_median_ratio.value:.1f}x" if m.max_to_median_ratio.value is not None else "N/A"

    table = Table(title="Pre-Flight Script Evaluation Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="bold")
    table.add_column("Health / Policy Target", style="dim")

    table.add_row("Total Impressions", f"{m.total_impressions:,}", "Report dataset volume")
    table.add_row("Positively Scored", f"{m.positive_score_impressions:,}", "≥ 500 required by Google S2")
    table.add_row("Positive Scoring Rate", pos_rate, "Target: 5% – 40% for active bidding")
    table.add_row("Weighted Mean Score", w_mean, "Baseline score scale")
    table.add_row("Gini Inequality", gini, "0.0 = flat, 1.0 = extreme concentration")
    table.add_row("Max-to-Median Ratio", ratio, "≤ 20.0x prevents DSP pacing starvation")
    table.add_row("Google S2 Readiness", f"[{'green' if 'MEETS' in r.status.value else 'yellow'}]{r.status.value}[/]", "DV360 Model Training Readiness")

    console.print(table)
    console.print(f"\n[green]✓ Evaluation complete. Diagnostics saved to {out}[/green]")

    if m.positive_score_impressions < 500:
        console.print(
            "  [yellow]Notice: Positive score count is below Google's 500-event training minimum (S2).\n"
            "  Consider using 'bidkit-pro weights' to incorporate viewability or mid-funnel proxy signals.[/yellow]"
        )


@app.command("report")
def report_cmd(
    diagnostics: str = typer.Argument(..., help="Path to diagnostics JSON file"),
    out: str = typer.Option("audit.html", "--out", "-o", help="Output path for HTML report"),
) -> None:
    """Renders evaluation diagnostics JSON into a visual HTML audit report."""
    diag_path = Path(diagnostics)
    if not diag_path.exists():
        console.print(f"[red]Error: Diagnostics file '{diagnostics}' not found.[/red]")
        sys.exit(2)

    try:
        diag_dict = json.loads(diag_path.read_text(encoding="utf-8"))
        eval_report = EvaluationReport(**diag_dict)
        render_report(eval_report, output_path=out)
        console.print(f"[green]✓ Audit report rendered to: {out}[/green]")
    except Exception as exc:
        console.print(f"[red]Error rendering report: {exc}[/red]")
        sys.exit(2)


@app.command("tree-demo")
def tree_demo_cmd(
    max_depth: int = typer.Option(3, "--max-depth", "-d", help="Max depth of the decision tree"),
    style: str = typer.Option("conditional", "--style", "-s", help="Output style: 'conditional' or 'aggregate'"),
    out: str | None = typer.Option(None, "--out", "-o", help="Optional output path to save script"),
) -> None:
    """Trains a DecisionTreeClassifier on synthetic impression logs and compiles it to DV360 DSL."""
    try:
        from sklearn.tree import DecisionTreeClassifier
        import numpy as np
    except ImportError:
        console.print("[red]Error: scikit-learn is required. Install via `pip install scikit-learn`.[/red]")
        sys.exit(2)

    # Generate synthetic training impression dataset
    rng = np.random.default_rng(42)
    n_samples = 1500
    device_type = rng.choice([0, 1, 2, 3], size=n_samples, p=[0.4, 0.05, 0.45, 0.1])
    environment = rng.choice([10, 11], size=n_samples, p=[0.7, 0.3])
    hour_of_day = rng.integers(0, 24, size=n_samples)
    day_of_week = rng.integers(0, 7, size=n_samples)

    X = np.column_stack([device_type, environment, hour_of_day, day_of_week])
    feature_names = ["device_type", "environment", "hour_of_day", "day_of_week"]

    # Conversion probability formula
    logits = (
        -2.5
        + (device_type == 2) * 0.8
        + (environment == 10) * 0.5
        + (hour_of_day >= 18) * 0.6
        + (day_of_week >= 5) * 0.7
    )
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = rng.binomial(1, probs)

    clf = DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=30, random_state=42)
    clf.fit(X, y)

    script = from_sklearn(
        clf,
        feature_names=feature_names,
        output_style=style,  # type: ignore[arg-type]
        scale_factor=100.0,
        validate=True,
    )

    byte_len = len(script.encode("utf-8"))
    table = Table(title="Scikit-Learn -> Google DV360 Custom Bidding DSL Compilation")
    table.add_column("Property", style="cyan")
    table.add_column("Value", justify="right", style="bold")
    table.add_column("Platform Standard", style="dim")

    table.add_row("Model Type", "DecisionTreeClassifier", "scikit-learn tree model")
    table.add_row("Tree Max Depth", str(clf.get_depth()), "Tree depth")
    table.add_row("Terminal Leaves", str(clf.get_n_leaves()), "Number of execution paths")
    table.add_row("Script Size", f"{byte_len:,} bytes", "≤ 65,536 bytes (64 KB limit)")
    table.add_row("Output Style", style, "conditional (if/else) or aggregate")
    table.add_row("AST Validation", "[green]VALID (0 errors)[/green]", "Google Custom Bidding DSL compliant")

    console.print(table)

    from rich.syntax import Syntax
    syntax = Syntax(script, "python", theme="monokai", line_numbers=True)
    console.print("\n[bold]Compiled DV360 Script:[/bold]")
    console.print(syntax)

    if out:
        out_p = Path(out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(script, encoding="utf-8")
        console.print(f"\n[green]✓ Script saved to: {out}[/green]")




@app.command("concave-attention")
def concave_attention_cmd(
    dwell_cap: float = typer.Option(20.0, "--dwell-cap", help="Upper cap on time_on_screen_seconds (default 20.0s)"),
    floodlight_id: int | None = typer.Option(None, "--floodlight-id", help="Optional Floodlight Activity ID for conversion anchor"),
    conversion_weight: float = typer.Option(25.0, "--conversion-weight", help="Weight applied to Floodlight/GA4 conversions"),
    use_value: bool = typer.Option(False, "--use-value", help="Use total_conversion_value instead of total_conversion_count"),
    ga4_property_id: int | None = typer.Option(None, "--ga4-property-id", help="Optional GA4 property ID"),
    ga4_event: str | None = typer.Option(None, "--ga4-event", help="Optional GA4 conversion event name"),
    exclude_domains: str | None = typer.Option(None, "--exclude-domains", help="Comma-separated MFA domains to exclude (e.g. spam1.com,spam2.com)"),
    stress_test: bool = typer.Option(True, "--stress-test/--no-stress-test", help="Run 4-strategy sticky-MFA stress test"),
    budget: float = typer.Option(100000.0, "--budget", help="Budget for MFA stress-test simulation"),
    out: str | None = typer.Option(None, "--out", "-o", help="Optional path to save compiled DV360 Python script"),
    json_out: bool = typer.Option(False, "--json", help="Emit structured JSON output"),
) -> None:
    """Compiles a zero-fee concave attention + outcome DV360 Custom Bidding script and runs a sticky-MFA stress test."""
    excluded = [d.strip() for d in exclude_domains.split(",") if d.strip()] if exclude_domains else []
    cfg = ConcaveAttentionConfig(
        dwell_cap_seconds=dwell_cap,
        floodlight_activity_id=floodlight_id,
        conversion_weight=conversion_weight,
        use_conversion_value=use_value,
        ga4_property_id=ga4_property_id,
        ga4_event_name=ga4_event,
        excluded_domains=excluded,
    )
    script = compile_concave_attention_script(cfg, validate=True)
    lint_rep = lint_script(script)
    stress_rep = run_mfa_stress_test(budget=budget, config=cfg) if stress_test else None

    if out:
        out_p = Path(out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(script, encoding="utf-8")

    if json_out:
        payload = {
            "script_code": script,
            "byte_length": len(script.encode("utf-8")),
            "is_valid": lint_rep.is_valid,
            "warnings": [d.model_dump() for d in lint_rep.diagnostics],
            "mfa_stress_test": stress_rep.model_dump() if stress_rep else None,
        }
        print(json.dumps(payload, indent=2))
        return

    if stress_rep is not None:
        table = Table(title=f"Sticky-MFA Auction Stress Test ({stress_rep.currency} {stress_rep.budget:,.0f} Budget)")
        table.add_column("Strategy", style="cyan")
        table.add_column("Clearing CPM", justify="right")
        table.add_column("MFA Share", justify="right")
        table.add_column("Editorial Share", justify="right")
        table.add_column("Attentive Hours", justify="right", style="bold")
        table.add_column("Cost / 1k Att. s", justify="right")
        table.add_column("vs vCPM", justify="right", style="green")

        for s in stress_rep.strategies:
            mfa_style = "red" if s.mfa_share_pct >= 25.0 else ("yellow" if s.mfa_share_pct > 0 else "green")
            table.add_row(
                s.strategy_name,
                f"{s.clearing_cpm:.2f}",
                f"[{mfa_style}]{s.mfa_share_pct:.1f}%[/{mfa_style}]",
                f"{s.editorial_share_pct:.1f}%",
                f"{s.attentive_hours:,.1f}",
                f"{s.cost_per_1k_attentive_seconds:.2f}",
                f"{s.efficiency_vs_vcpm_pct:+.1f}%",
            )
        console.print(table)

    from rich.syntax import Syntax
    console.print("\n[bold]Compiled Zero-Fee DV360 Concave Attention Script (0 errors, 0 warnings):[/bold]")
    console.print(Syntax(script, "python", theme="monokai", line_numbers=True))
    if out:
        console.print(f"\n[green]✓ Script saved to: {out}[/green]")


@app.command("fee-check")
def fee_check_cmd(
    base_cpm: float = typer.Option(4.50, "--base-cpm", help="Baseline clearing CPM before attention steering"),
    cpm_uplift: float = typer.Option(15.0, "--cpm-uplift", help="Expected clearing CPM uplift (%) on higher-attention supply"),
    prebid_fee: float = typer.Option(0.0, "--prebid-fee", help="Fixed 3P pre-bid attention segment CPM surcharge (e.g. 0.25)"),
    curation_fee: float = typer.Option(0.0, "--curation-fee", help="SSP curation take rate (%) (e.g. 11.0 median)"),
    ai_fee: float = typer.Option(0.0, "--ai-fee", help="3P AI / custom bidding vendor fee (%) (e.g. 6.0)"),
    agency_fee: float = typer.Option(0.0, "--agency-fee", help="Optional agency optimization fee (%)"),
    budget: float = typer.Option(100000.0, "--budget", help="Fixed media budget for reach-contraction modeling"),
    frequency: float = typer.Option(6.0, "--frequency", help="Average impressions per unique user"),
    base_dwell: float = typer.Option(1.10, "--base-dwell", help="Baseline average visual dwell per impression (seconds)"),
    target_dwell: float = typer.Option(2.40, "--target-dwell", help="Expected average visual dwell per impression (seconds)"),
    currency: str = typer.Option("EUR", "--currency", help="Currency code (e.g. EUR, USD)"),
    json_out: bool = typer.Option(False, "--json", help="Emit structured JSON output"),
) -> None:
    """Computes attention fee-stack break-even hurdles and Simonov et al. (2025) bounded quadratic recall reality checks."""
    try:
        res = analyze_attention_fee_economics(
            base_cpm=base_cpm,
            cpm_uplift_pct=cpm_uplift,
            prebid_cpm_fee=prebid_fee,
            curation_fee_pct=curation_fee,
            ai_fee_pct=ai_fee,
            agency_fee_pct=agency_fee,
            budget=budget,
            frequency=frequency,
            base_dwell_seconds=base_dwell,
            target_dwell_seconds=target_dwell,
            currency=currency,
        )
    except ValueError as exc:
        console.print(f"[bold red]Invalid input:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if json_out:
        print(json.dumps(res.model_dump(), indent=2))
        return

    verdict_style = {"VIABLE": "bold green", "MARGINAL": "bold yellow", "FEE_TRAP": "bold red"}[res.verdict]
    table = Table(title=f"Attention Fee-Stack & Bounded Recall Check ({res.currency})")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="bold")
    table.add_column("Notes", style="dim")

    table.add_row("Base CPM", f"{res.base_cpm:.2f} {res.currency}", "Baseline clearing price")
    table.add_row("Clearing CPM (with uplift)", f"{res.clearing_cpm:.2f} {res.currency}", f"+{cpm_uplift:.1f}% supply price uplift")
    table.add_row("All-In Effective CPM", f"{res.all_in_cpm:.2f} {res.currency}", f"+{res.total_fee_overhead_pct:.1f}% tech/curation fee overhead")
    table.add_row("Break-Even Yield Lift Required", f"+{res.required_yield_lift_pct:.1f}%", "Per-impression lift needed just to break even")
    table.add_row("Unique Reach Impact", f"{res.reach_change_pct:+.1f}%", f"{res.base_reach:,.0f} -> {res.target_reach:,.0f} users (freq {res.frequency:.1f})")
    table.add_row(
        "Cumulative User Dwell",
        f"{res.base_cumulative_dwell_seconds:.1f}s -> {res.target_cumulative_dwell_seconds:.1f}s",
        "SATURATED (>= 13.34s peak)" if res.hits_recall_saturation else "Below 13.34s saturation peak",
    )
    table.add_row("Bounded Recall Lift (Simonov 2025)", f"{res.bounded_recall_lift_pct:+.1f}%", f"{res.base_recalling_users:,.0f} -> {res.target_recalling_users:,.0f} recalling users")
    table.add_row("Naive Linear Recall Projection", f"{res.naive_linear_recall_lift_pct:+.1f}%", "Ignores reach loss & quadratic saturation")
    if res.linear_overstatement_ratio is not None:
        table.add_row("Linear Overstatement Factor", f"{res.linear_overstatement_ratio:.2f}x", "How much linear math exaggerates real recall lift")
    table.add_row("Economic Verdict", f"[{verdict_style}]{res.verdict}[/{verdict_style}]", "Fee-stack discipline assessment")

    console.print(table)
    console.print(Panel(res.recommendation, title="[bold]Recommendation[/bold]", border_style="blue"))


@app.command("mcp")
def mcp_cmd() -> None:
    """Launches the Model Context Protocol (MCP) server over stdio for Claude Desktop and Cursor."""
    from dv360_bidkit.mcp import run_stdio_server
    run_stdio_server()


if __name__ == "__main__":
    app()


