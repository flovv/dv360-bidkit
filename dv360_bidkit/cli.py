"""Command Line Interface for dv360-bidkit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dv360_bidkit.compiler.scripts import compile_script
from dv360_bidkit.contracts.schemas import (
    DiagnosticSeverity,
    EvaluationReport,
    InventoryPolicyConfig,
    ReportData,
    ReportMapping,
    RuleSet,
)
from dv360_bidkit.evaluator.diagnostics import evaluate_script
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
) -> None:
    """Compiles a RuleSet into a production DV360 Custom Bidding script."""
    rules_path = Path(rules)
    if not rules_path.exists():
        console.print(f"[red]Error: Rules file '{rules}' not found.[/red]")
        sys.exit(2)

    try:
        rules_dict = json.loads(rules_path.read_text(encoding="utf-8"))
        ruleset = RuleSet(**rules_dict)
    except Exception as exc:
        console.print(f"[red]Error parsing rules: {exc}[/red]")
        sys.exit(2)

    inv_policy = None
    if policy:
        try:
            inv_policy = load_inventory_policy(policy)
        except Exception as exc:
            console.print(f"[red]Error loading inventory policy: {exc}[/red]")
            sys.exit(2)

    result = compile_script(ruleset, policy=inv_policy)
    out_path = Path(out)

    if not result.budgets_passed:
        console.print("[red]Compilation failed budget and validation checks:[/red]")
        for diag in result.diagnostics:
            if diag.severity == DiagnosticSeverity.ERROR:
                console.print(f"[red]  ERROR: [{diag.code}] {diag.message}[/red]")
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.script_code, encoding="utf-8")

    console.print(f"[green]✓ Compiled script written to: {out}[/green]")
    console.print(f"  Rules: {result.rule_count} | AST nodes: {result.ast_nodes} | Size: {result.byte_count} bytes")


@app.command("evaluate")
def evaluate_cmd(
    script: str = typer.Argument(..., help="Path to custom bidding script"),
    report: str = typer.Option(..., "--report", "-r", help="Path to report CSV"),
    mapping: str = typer.Option(..., "--mapping", "-m", help="Path to mapping JSON"),
    out: str = typer.Option("diagnostics.json", "--out", "-o", help="Output path for evaluation diagnostics JSON"),
) -> None:
    """Evaluates a script against historical report data."""
    script_path = Path(script)
    report_path = Path(report)
    mapping_path = Path(mapping)

    if not script_path.exists() or not report_path.exists() or not mapping_path.exists():
        console.print("[red]Error: One or more input files do not exist.[/red]")
        sys.exit(2)

    try:
        mapping_dict = json.loads(mapping_path.read_text(encoding="utf-8"))
        rep_mapping = ReportMapping(**mapping_dict)
        report_data = load_report(report_path, mapping=rep_mapping)
    except Exception as exc:
        console.print(f"[red]Error loading data/mapping: {exc}[/red]")
        sys.exit(2)

    code = script_path.read_text(encoding="utf-8")
    eval_report = evaluate_script(code, report_data)

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(eval_report.model_dump(), indent=2), encoding="utf-8")

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
