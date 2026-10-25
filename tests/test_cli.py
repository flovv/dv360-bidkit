"""Unit tests for the bidkit CLI commands."""

import json
from pathlib import Path
from typer.testing import CliRunner

from dv360_bidkit.cli import app

runner = CliRunner()


def test_cli_demo(tmp_path):
    demo_dir = tmp_path / "demo_out"
    result = runner.invoke(app, ["demo", "--out-dir", str(demo_dir)])
    assert result.exit_code == 0
    assert (demo_dir / "report.csv").exists()
    assert (demo_dir / "mapping.json").exists()
    assert (demo_dir / "rules.json").exists()
    assert (demo_dir / "policy.json").exists()


def test_cli_lint_valid(tmp_path):
    script_file = tmp_path / "valid.py"
    script_file.write_text("return 1.0\n", encoding="utf-8")
    result = runner.invoke(app, ["lint", str(script_file)])
    assert result.exit_code == 0


def test_cli_lint_invalid(tmp_path):
    script_file = tmp_path / "invalid.py"
    script_file.write_text("import os\nreturn 1.0\n", encoding="utf-8")
    result = runner.invoke(app, ["lint", str(script_file)])
    assert result.exit_code == 1


def test_cli_compile_and_evaluate(tmp_path):
    # 1. Generate demo
    demo_dir = tmp_path / "demo_cli"
    runner.invoke(app, ["demo", "--out-dir", str(demo_dir)])

    # 2. Compile
    compiled_script = demo_dir / "compiled.py"
    res_comp = runner.invoke(
        app,
        ["compile", "--rules", str(demo_dir / "rules.json"), "--out", str(compiled_script)],
    )
    assert res_comp.exit_code == 0
    assert compiled_script.exists()

    # 3. Evaluate
    diag_file = demo_dir / "diagnostics.json"
    res_eval = runner.invoke(
        app,
        [
            "evaluate",
            str(compiled_script),
            "--report",
            str(demo_dir / "report.csv"),
            "--mapping",
            str(demo_dir / "mapping.json"),
            "--out",
            str(diag_file),
        ],
    )
    assert res_eval.exit_code == 0
    assert diag_file.exists()

    # 4. Report
    html_file = demo_dir / "audit.html"
    res_rep = runner.invoke(app, ["report", str(diag_file), "--out", str(html_file)])
    assert res_rep.exit_code == 0
    assert html_file.exists()
    html_content = html_file.read_text(encoding="utf-8")
    assert "DV360 Custom Bidding Pre-Flight Evaluation" in html_content


def test_cli_compile_and_evaluate_json(tmp_path):
    demo_dir = tmp_path / "demo_json"
    runner.invoke(app, ["demo", "--out-dir", str(demo_dir)])

    # Compile with --json
    compiled_script = demo_dir / "compiled.py"
    res_comp = runner.invoke(
        app,
        ["compile", "--rules", str(demo_dir / "rules.json"), "--out", str(compiled_script), "--json"],
    )
    assert res_comp.exit_code == 0
    comp_data = json.loads(res_comp.output)
    assert comp_data["status"] == "success"
    assert comp_data["budgets_passed"] is True
    assert "rule_count" in comp_data
    assert "ast_nodes" in comp_data

    # Evaluate with --format json
    diag_file = demo_dir / "diagnostics.json"
    res_eval = runner.invoke(
        app,
        [
            "evaluate",
            str(compiled_script),
            "--report",
            str(demo_dir / "report.csv"),
            "--mapping",
            str(demo_dir / "mapping.json"),
            "--out",
            str(diag_file),
            "--format",
            "json",
        ],
    )
    assert res_eval.exit_code == 0
    eval_data = json.loads(res_eval.output)
    assert "metrics" in eval_data
    assert "readiness" in eval_data
    assert eval_data["readiness"]["status"] is not None
