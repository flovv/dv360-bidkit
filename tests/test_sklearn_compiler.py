"""Tests for the Scikit-Learn to DV360 Custom Bidding DSL compiler (from_sklearn)."""

import pytest
import numpy as np
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier
from typer.testing import CliRunner

from dv360_bidkit import from_sklearn, lint_script
from dv360_bidkit.contracts.exceptions import BudgetExceededError, CompilationError
from dv360_bidkit.cli import app


@pytest.fixture
def sample_dataset():
    """Generates synthetic tabular training data with verified DV360 signals."""
    rng = np.random.default_rng(42)
    n = 600
    # Signals: device_type (0..3), environment (10..11), hour_of_day (0..23), day_of_week (0..6)
    device_type = rng.choice([0, 1, 2, 3], size=n)
    environment = rng.choice([10, 11], size=n)
    hour_of_day = rng.integers(0, 24, size=n)
    day_of_week = rng.integers(0, 7, size=n)

    X = np.column_stack([device_type, environment, hour_of_day, day_of_week])
    logits = 0.5 * (device_type == 2) + 0.8 * (hour_of_day >= 18) + 0.6 * (day_of_week >= 5) - 1.2
    y_prob = 1.0 / (1.0 + np.exp(-logits))
    y_class = rng.binomial(1, y_prob)
    y_reg = hour_of_day * 2.5 + day_of_week * 5.0 + 10.0

    return X, y_class, y_reg, ["device_type", "environment", "hour_of_day", "day_of_week"]


def test_classifier_conditional_compilation(sample_dataset):
    X, y_class, _, feature_names = sample_dataset
    clf = DecisionTreeClassifier(max_depth=3, random_state=42)
    clf.fit(X, y_class)

    script = from_sklearn(
        clf,
        feature_names=feature_names,
        output_style="conditional",
        scale_factor=100.0,
    )

    assert "Google DV360 Custom Bidding Script" in script
    assert "Compiled by dv360-bidkit from Scikit-Learn DecisionTreeClassifier" in script
    assert "if " in script
    assert "else:" in script
    assert "return " in script

    # Verify AST linter accepts script with 0 errors
    lint_report = lint_script(script)
    assert lint_report.is_valid, f"Lint diagnostics: {lint_report.diagnostics}"


def test_classifier_aggregate_compilation(sample_dataset):
    X, y_class, _, feature_names = sample_dataset
    clf = DecisionTreeClassifier(max_depth=3, random_state=42)
    clf.fit(X, y_class)

    script = from_sklearn(
        clf,
        feature_names=feature_names,
        output_style="aggregate",
        scale_factor=100.0,
        default_fallback=1.5,
    )

    assert "return first_match_aggregate([" in script
    assert "([], 1.5)" in script

    # Verify AST linter accepts script with 0 errors
    lint_report = lint_script(script)
    assert lint_report.is_valid, f"Lint diagnostics: {lint_report.diagnostics}"


def test_regressor_compilation(sample_dataset):
    X, _, y_reg, feature_names = sample_dataset
    reg = DecisionTreeRegressor(max_depth=3, random_state=42)
    reg.fit(X, y_reg)

    script = from_sklearn(
        reg,
        feature_names=feature_names,
        output_style="conditional",
        scale_factor=1.0,
    )

    assert "DecisionTreeRegressor" in script
    assert "return " in script

    lint_report = lint_script(script)
    assert lint_report.is_valid, f"Lint diagnostics: {lint_report.diagnostics}"


def test_discrete_integer_thresholding():
    """Discrete integer signals (e.g. device_type) must format as `<= 1` and `>= 2` instead of float `<= 1.5`."""
    X = np.array([[0], [1], [2], [3]])
    y = np.array([0, 0, 1, 1])

    clf = DecisionTreeClassifier(max_depth=1)
    clf.fit(X, y)

    cond_script = from_sklearn(clf, feature_names=["device_type"], output_style="conditional")
    assert "device_type <= 1" in cond_script

    agg_script = from_sklearn(clf, feature_names=["device_type"], output_style="aggregate")
    assert "device_type <= 1" in agg_script
    assert "device_type >= 2" in agg_script


def test_signal_aliases_canonicalization(sample_dataset):
    X, y_class, _, _ = sample_dataset
    clf = DecisionTreeClassifier(max_depth=2, random_state=42)
    clf.fit(X, y_class)

    # User passes shorthand aliases: 'device', 'environment_type', 'hour', 'day'
    aliases = ["device", "environment_type", "hour", "day"]
    script = from_sklearn(clf, feature_names=aliases, output_style="conditional")

    # Script should canonicalize to standard DV360 signal names
    assert "device_type" in script
    assert "environment" in script
    assert "hour_of_day" in script
    assert "day_of_week" in script


def test_score_bounds_and_custom_transform(sample_dataset):
    X, y_class, _, feature_names = sample_dataset
    clf = DecisionTreeClassifier(max_depth=3, random_state=42)
    clf.fit(X, y_class)

    # Clamp scores between 10.0 and 60.0
    script = from_sklearn(
        clf,
        feature_names=feature_names,
        scale_factor=100.0,
        min_score=10.0,
        max_score=60.0,
        score_transform=lambda s: s * 2.0,
    )

    import re
    scores = [float(x) for x in re.findall(r"return\s+([0-9\.]+)", script)]
    assert len(scores) > 0
    assert all(10.0 <= s <= 60.0 for s in scores)


def test_custom_offline_features_with_syntax_validation():
    """Custom offline features (e.g. from Kaggle) compile cleanly when validate='syntax'."""
    X = np.array([[10.5, 2.0], [5.2, 8.1], [15.1, 1.2], [3.3, 9.4]])
    y = np.array([0, 1, 0, 1])
    clf = DecisionTreeClassifier(max_depth=2)
    clf.fit(X, y)

    script = from_sklearn(
        clf,
        feature_names=["custom_feature_a", "custom_feature_b"],
        validate="syntax",
    )
    assert "custom_feature_a" in script
    assert "return " in script


def test_rejects_ensemble():
    X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
    y = np.array([0, 1, 0, 1])
    rf = RandomForestClassifier(n_estimators=3, random_state=42)
    rf.fit(X, y)

    with pytest.raises(CompilationError, match="ensemble"):
        from_sklearn(rf)

    # However, passing an individual estimator from the forest should work!
    single_tree_script = from_sklearn(
        rf.estimators_[0],
        feature_names=["device_type", "hour_of_day"],
        validate=True,
    )
    assert "return " in single_tree_script


def test_rejects_unfitted_model():
    clf = DecisionTreeClassifier(max_depth=3)
    with pytest.raises(CompilationError, match="tree_"):
        from_sklearn(clf)


def test_feature_count_mismatch(sample_dataset):
    X, y_class, _, _ = sample_dataset
    clf = DecisionTreeClassifier(max_depth=2)
    clf.fit(X, y_class)

    with pytest.raises(CompilationError, match="Feature names count"):
        from_sklearn(clf, feature_names=["only_one_feature"])


def test_cli_tree_demo(tmp_path):
    runner = CliRunner()
    out_file = tmp_path / "compiled_tree.py"
    result = runner.invoke(app, ["tree-demo", "--max-depth", "2", "--style", "conditional", "--out", str(out_file)])
    assert result.exit_code == 0
    assert "Scikit-Learn -> Google DV360 Custom Bidding DSL Compilation" in result.output
    assert "DecisionTreeClassifier" in result.output
    assert "Compiled DV360 Script" in result.output
    assert out_file.exists()
    assert "if " in out_file.read_text(encoding="utf-8")

    agg_result = runner.invoke(app, ["tree-demo", "--max-depth", "2", "--style", "aggregate"])
    assert agg_result.exit_code == 0
    assert "first_match_aggregate" in agg_result.output
