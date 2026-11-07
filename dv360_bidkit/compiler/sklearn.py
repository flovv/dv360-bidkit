"""Scikit-Learn DecisionTree to Google DV360 Custom Bidding DSL Compiler.

Bridges modern Python data science and machine learning pipelines (scikit-learn,
XGBoost/LightGBM single trees) with Google Display & Video 360 Custom Bidding.
Compiles fitted DecisionTreeClassifiers and DecisionTreeRegressors into
100% syntactically valid, sandbox-compliant Google DV360 Python DSL scripts.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any, Callable, Literal, Optional, Sequence
import numpy as np

from dv360_bidkit.contracts.exceptions import BudgetExceededError, CompilationError
from dv360_bidkit.contracts.signals import SIGNAL_REGISTRY, is_valid_signal
from dv360_bidkit.linter.ast_validator import lint_script

# DV360 integer dimension signals
INTEGER_SIGNALS = {
    "device_type",
    "environment",
    "hour_of_day",
    "day_of_week",
    "site_id",
    "exchange_id",
    "line_item_id",
    "advertiser_id",
    "campaign_id",
    "partner_id",
    "channel_id",
    "os_id",
    "inventory_source_id",
    "browser_reportable_id",
}

# DV360 boolean signals
BOOLEAN_SIGNALS = {
    "click",
}

# Common data science aliases to canonical DV360 signal names
SIGNAL_ALIASES = {
    "device": "device_type",
    "device_category": "device_type",
    "environment_type": "environment",
    "hour": "hour_of_day",
    "day": "day_of_week",
    "browser": "browser_reportable_id",
    "os": "os_id",
    "viewability": "active_view_viewed",
    "viewed": "active_view_viewed",
    "active_view": "active_view_viewed",
}

MAX_DV360_SCRIPT_BYTES = 65536  # Google hard limit: 64 KB


def canonicalize_feature_name(name: str) -> str:
    """Maps shorthand feature names to canonical DV360 signal identifiers."""
    cleaned = name.strip()
    return SIGNAL_ALIASES.get(cleaned.lower(), cleaned)


def is_integer_feature(name: str) -> bool:
    """Returns True if the feature corresponds to an integer DV360 dimension."""
    canon = canonicalize_feature_name(name)
    if canon in INTEGER_SIGNALS:
        return True
    sig_def = SIGNAL_REGISTRY.get(canon)
    return sig_def is not None and sig_def.return_type == "int"


def _extract_tree(model: Any) -> Any:
    """Extracts internal tree object from scikit-learn or similar model."""
    if hasattr(model, "tree_"):
        return model.tree_
    if hasattr(model, "estimators_"):
        raise CompilationError(
            f"Model {type(model).__name__} is an ensemble. Google DV360 Custom Bidding DSL "
            "requires a deterministic single-tree representation. Pass an individual estimator "
            "(e.g., `rf.estimators_[0]`) or train a single DecisionTreeClassifier / DecisionTreeRegressor."
        )
    raise CompilationError(
        f"Object {type(model).__name__} does not have a `tree_` attribute. "
        "Ensure the model is a fitted scikit-learn DecisionTreeClassifier or DecisionTreeRegressor."
    )


def _compute_leaf_value(
    tree: Any,
    node_id: int,
    is_classifier: bool,
    scale_factor: float,
    round_digits: int,
    score_transform: Optional[Callable[[float], float]] = None,
    min_score: Optional[float] = 0.0,
    max_score: Optional[float] = None,
) -> float:
    """Calculates final numeric bidding weight for a leaf node."""
    raw_val = tree.value[node_id]  # Shape: (1, n_classes) or (1, n_outputs)

    if is_classifier:
        counts = raw_val[0]
        total = float(np.sum(counts))
        if total <= 0:
            prob = 0.0
        elif len(counts) >= 2:
            prob = float(counts[1]) / total
        else:
            prob = float(counts[0]) / total
        score = prob * scale_factor
    else:
        score = float(raw_val[0][0]) * scale_factor

    if score_transform is not None:
        score = score_transform(score)

    if min_score is not None:
        score = max(min_score, score)
    if max_score is not None:
        score = min(max_score, score)

    return round(score, round_digits)


def _format_left_condition(feat_name: str, threshold: float, round_digits: int) -> str:
    """Formats left branch condition (feature <= threshold)."""
    if is_integer_feature(feat_name):
        int_thresh = int(math.floor(threshold))
        return f"{feat_name} <= {int_thresh}"
    return f"{feat_name} <= {round(threshold, round_digits)}"


def _format_right_condition(feat_name: str, threshold: float, round_digits: int) -> str:
    """Formats right branch condition (feature > threshold)."""
    if is_integer_feature(feat_name):
        int_thresh = int(math.floor(threshold))
        return f"{feat_name} >= {int_thresh + 1}"
    return f"{feat_name} > {round(threshold, round_digits)}"


def from_sklearn(
    model: Any,
    feature_names: Optional[Sequence[str]] = None,
    output_style: Literal["conditional", "aggregate"] = "conditional",
    scale_factor: float = 100.0,
    round_digits: int = 4,
    default_fallback: Optional[float] = 1.0,
    score_transform: Optional[Callable[[float], float]] = None,
    min_score: Optional[float] = 0.0,
    max_score: Optional[float] = None,
    include_header: bool = True,
    validate: bool | Literal["strict", "syntax"] = True,
) -> str:
    """Compiles a Scikit-Learn DecisionTree into Google DV360 Custom Bidding Python DSL.

    Parameters
    ----------
    model : DecisionTreeClassifier | DecisionTreeRegressor
        A fitted scikit-learn decision tree estimator.
    feature_names : Sequence[str] | None
        Names of the features used in model training. If None, checks `model.feature_names_in_`
        or defaults to `feature_0`, `feature_1`, etc. Known aliases (e.g., 'device', 'hour')
        are automatically canonicalized to DV360 standard signals ('device_type', 'hour_of_day').
    output_style : 'conditional' | 'aggregate'
        - 'conditional': Compiles into structured nested `if / else` blocks returning scores.
        - 'aggregate': Compiles into DV360 `return first_match_aggregate([([conds], score), ...])`.
    scale_factor : float
        Multiplier applied to tree output (e.g. 100.0 turns 0.0-1.0 probability into 0-100 score).
    round_digits : int
        Precision for leaf scores and continuous split thresholds (default 4).
    default_fallback : float | None
        Default fallback score if no branches match in aggregate mode (default 1.0).
    score_transform : Callable[[float], float] | None
        Optional calibration or monotonic transformation applied to raw leaf score.
    min_score : float | None
        Minimum allowed score bound (default 0.0, since DV360 rejects negative bidding scores).
    max_score : float | None
        Optional maximum allowed score cap.
    include_header : bool
        Whether to generate informative metadata header comments.
    validate : bool | 'strict' | 'syntax'
        - True or 'strict': Full Google DV360 validation against standard signals and AST restrictions.
        - 'syntax': Enforces DV360 sandbox rules (no loops/imports/negative scores) but permits custom feature names.
        - False: Disables AST linting (byte budget is still enforced).

    Returns
    -------
    str
        Syntactically valid, production-ready Google DV360 Custom Bidding DSL Python script.

    Raises
    ------
    CompilationError
        If model is unfitted, ensemble, or fails AST validation.
    BudgetExceededError
        If generated script exceeds Google's 64 KB (65,536 bytes) limit.
    """
    tree = _extract_tree(model)

    # Determine classifier vs regressor
    is_classifier = hasattr(model, "classes_")

    # Resolve feature names
    n_features = tree.n_features
    if feature_names is not None:
        if len(feature_names) != n_features:
            raise CompilationError(
                f"Feature names count ({len(feature_names)}) does not match model feature count ({n_features})."
            )
        resolved_features = [canonicalize_feature_name(f) for f in feature_names]
    elif hasattr(model, "feature_names_in_"):
        resolved_features = [canonicalize_feature_name(f) for f in model.feature_names_in_]
    else:
        resolved_features = [f"feature_{i}" for i in range(n_features)]

    lines: list[str] = []

    if include_header:
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines.append("# ====================================================================")
        lines.append("# Google DV360 Custom Bidding Script")
        lines.append(f"# Compiled by dv360-bidkit from Scikit-Learn {type(model).__name__}")
        lines.append(f"# Generated: {timestamp}")
        lines.append(f"# Model Depth: {tree.max_depth} | Leaf Nodes: {tree.n_leaves} | Style: {output_style}")
        lines.append(f"# Features: {', '.join(resolved_features)}")
        lines.append("# ====================================================================")
        lines.append("")

    if output_style == "conditional":
        # Recursive compilation of nested if/else statements
        def _build_conditional(node_id: int, indent_level: int) -> list[str]:
            res: list[str] = []
            indent = "    " * indent_level

            # Check if leaf node
            if tree.children_left[node_id] == -1 and tree.children_right[node_id] == -1:
                leaf_score = _compute_leaf_value(
                    tree,
                    node_id,
                    is_classifier,
                    scale_factor,
                    round_digits,
                    score_transform,
                    min_score,
                    max_score,
                )
                res.append(f"{indent}return {leaf_score}")
                return res

            feat_idx = tree.feature[node_id]
            feat_name = resolved_features[feat_idx]
            threshold = tree.threshold[node_id]

            left_child = tree.children_left[node_id]
            right_child = tree.children_right[node_id]

            left_cond = _format_left_condition(feat_name, threshold, round_digits)

            res.append(f"{indent}if {left_cond}:")
            res.extend(_build_conditional(left_child, indent_level + 1))
            res.append(f"{indent}else:")
            res.extend(_build_conditional(right_child, indent_level + 1))
            return res

        script_body = _build_conditional(0, 0)
        lines.extend(script_body)

    elif output_style == "aggregate":
        # Collect paths from root to leaves
        paths: list[tuple[list[str], float]] = []

        def _collect_paths(node_id: int, current_conds: list[str]) -> None:
            if tree.children_left[node_id] == -1 and tree.children_right[node_id] == -1:
                leaf_score = _compute_leaf_value(
                    tree,
                    node_id,
                    is_classifier,
                    scale_factor,
                    round_digits,
                    score_transform,
                    min_score,
                    max_score,
                )
                paths.append((current_conds, leaf_score))
                return

            feat_idx = tree.feature[node_id]
            feat_name = resolved_features[feat_idx]
            threshold = tree.threshold[node_id]

            left_child = tree.children_left[node_id]
            right_child = tree.children_right[node_id]

            left_cond = _format_left_condition(feat_name, threshold, round_digits)
            right_cond = _format_right_condition(feat_name, threshold, round_digits)

            _collect_paths(left_child, current_conds + [left_cond])
            _collect_paths(right_child, current_conds + [right_cond])

        _collect_paths(0, [])

        lines.append("return first_match_aggregate([")
        for conds, score in paths:
            conds_str = "[" + ", ".join(conds) + "]"
            lines.append(f"    ({conds_str}, {score}),")

        if default_fallback is not None:
            fb = round(default_fallback, round_digits)
            lines.append(f"    ([], {fb}),")

        lines.append("])")

    else:
        raise CompilationError(f"Unsupported output_style '{output_style}'. Must be 'conditional' or 'aggregate'.")

    full_script = "\n".join(lines) + "\n"

    # Enforce DV360 byte size limit (64 KB)
    byte_count = len(full_script.encode("utf-8"))
    if byte_count > MAX_DV360_SCRIPT_BYTES:
        raise BudgetExceededError(
            f"Compiled script size ({byte_count:,} bytes) exceeds Google DV360 limit of "
            f"{MAX_DV360_SCRIPT_BYTES:,} bytes (64 KB). Prune tree depth or reduce number of leaves."
        )

    # Optional AST validation with dv360-bidkit's linter
    if validate is True or validate == "strict":
        lint_rep = lint_script(full_script)
        if not lint_rep.is_valid:
            err_msgs = [f"Line {d.line}: [{d.code}] {d.message}" for d in lint_rep.diagnostics if d.severity == "error"]
            raise CompilationError(
                f"Compiled script failed Google DV360 AST validation:\n" + "\n".join(err_msgs)
            )
    elif validate == "syntax":
        lint_rep = lint_script(full_script)
        # Allow custom offline feature identifiers, but reject loops, imports, negative scores, etc.
        syntax_errors = [
            f"Line {d.line}: [{d.code}] {d.message}"
            for d in lint_rep.diagnostics
            if d.severity == "error" and d.code != "UNKNOWN_IDENTIFIER"
        ]
        if syntax_errors:
            raise CompilationError(
                f"Compiled script failed Google DV360 syntax validation:\n" + "\n".join(syntax_errors)
            )

    return full_script
