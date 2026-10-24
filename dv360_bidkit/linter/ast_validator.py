"""DV360 Custom Bidding DSL AST Validator and Linter.

Parses DV360 custom bidding scripts using Python's AST parser, supports
top-level return statements, enforces strict AST node allowlists,
validates signals and function arities against the registry, and checks
for deprecated syntax, CTV domain conditions, and negative scores.
"""

from __future__ import annotations

import ast
import re
from typing import Any

from dv360_bidkit.contracts.schemas import (
    Diagnostic,
    DiagnosticSeverity,
    LintReport,
)
from dv360_bidkit.contracts.signals import (
    Applicability,
    REGISTRY_VERSION,
    SIGNAL_REGISTRY,
    SignalKind,
    SignalStatus,
)

# Nodes allowed in DV360 custom bidding scripts
ALLOWED_NODE_TYPES: set[type[ast.AST]] = {
    ast.Module,
    ast.FunctionDef,  # When wrapped in a top-level function
    ast.Return,
    ast.Expr,
    ast.Assign,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Call,
    ast.Constant,
    ast.Name,
    ast.List,
    ast.Tuple,
    ast.BoolOp,
    ast.IfExp,  # ternary: a if cond else b
    ast.If,
    ast.Pass,
    ast.Store,
    ast.Load,
}

# Operators allowed
ALLOWED_OPERATOR_TYPES: set[type[ast.AST]] = {
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.And,
    ast.Or,
    ast.Not,
    ast.USub,
    ast.UAdd,
}

ALLOWED_BUILTIN_NAMES = {"True", "False", "None", "true", "false"}


def _wrap_top_level_returns(code: str) -> tuple[str, bool]:
    """Wraps code in a function if it contains top-level return statements.

    Returns the (modified_code, was_wrapped).
    """
    try:
        ast.parse(code)
        return code, False
    except SyntaxError as e:
        if "'return' outside function" in str(e):
            # Indent all lines by 4 spaces and wrap in a function
            indented = "\n".join("    " + line if line.strip() else "" for line in code.splitlines())
            wrapped = f"def _dv360_script_wrapper():\n{indented}\n"
            return wrapped, True
        # Re-raise other syntax errors
        raise


def lint_script(code: str, *, registry_version: str | None = None) -> LintReport:
    """Lints and validates a DV360 Custom Bidding Python script.

    Parameters
    ----------
    code : str
        The custom bidding script source text.
    registry_version : str | None
        Optional registry version to validate against.

    Returns
    -------
    LintReport
        Structured diagnostics, validity flag, and AST summary.
    """
    diagnostics: list[Diagnostic] = []
    line_offset = 0

    if not code or not code.strip():
        diagnostics.append(
            Diagnostic(
                code="EMPTY_SCRIPT",
                severity=DiagnosticSeverity.ERROR,
                message="Custom bidding script is empty.",
            )
        )
        return LintReport(is_valid=False, diagnostics=diagnostics, ast_summary={})

    try:
        wrapped_code, was_wrapped = _wrap_top_level_returns(code)
        if was_wrapped:
            line_offset = 1
        tree = ast.parse(wrapped_code)
    except SyntaxError as exc:
        diagnostics.append(
            Diagnostic(
                code="PYTHON_SYNTAX_ERROR",
                severity=DiagnosticSeverity.ERROR,
                message=f"Syntax error: {exc.msg}",
                line=exc.lineno,
                col=exc.offset,
                evidence=exc.text.strip() if exc.text else None,
                corrective_action="Verify Python syntax. Check brackets, quotes, and commas.",
            )
        )
        return LintReport(is_valid=False, diagnostics=diagnostics, ast_summary={})

    # AST Traversal & Allowlist checks
    local_variables: set[str] = set()
    total_nodes = 0
    node_type_counts: dict[str, int] = {}
    has_return = False

    # Track conditions for CTV checks
    saw_ctv_device = False
    saw_domain_check = False

    for node in ast.walk(tree):
        total_nodes += 1
        node_name = type(node).__name__
        node_type_counts[node_name] = node_type_counts.get(node_name, 0) + 1

        # Check node against allowlist
        if type(node) not in ALLOWED_NODE_TYPES and type(node) not in ALLOWED_OPERATOR_TYPES:
            actual_line = getattr(node, "lineno", 1) - line_offset
            diagnostics.append(
                Diagnostic(
                    code="DISALLOWED_SYNTAX_NODE",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Disallowed construct '{node_name}'. DV360 Custom Bidding DSL does not permit loops, imports, classes, lambdas, or dynamic execution.",
                    line=actual_line,
                    evidence=f"Found: {node_name}",
                    corrective_action="Remove complex constructs. DV360 scripts only allow basic expressions, aggregate functions, and conditionals.",
                )
            )

        # Track local variable assignment
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    local_variables.add(target.id)

        # Track return
        if isinstance(node, ast.Return):
            has_return = True
            # Check for negative literal score in return
            if isinstance(node.value, ast.UnaryOp) and isinstance(node.value.op, ast.USub):
                if isinstance(node.value.operand, ast.Constant) and isinstance(node.value.operand.value, (int, float)):
                    actual_line = getattr(node, "lineno", 1) - line_offset
                    diagnostics.append(
                        Diagnostic(
                            code="NEGATIVE_SCORE_POLICY",
                            severity=DiagnosticSeverity.ERROR,
                            message=f"Negative score '-{node.value.operand.value}' violates package scoring policy.",
                            line=actual_line,
                            corrective_action="Custom bidding scores must be non-negative (>= 0.0) or None (to exclude).",
                        )
                    )

        # Validate function calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                actual_line = getattr(node, "lineno", 1) - line_offset
                sig = SIGNAL_REGISTRY.get(func_name)
                if sig is None:
                    diagnostics.append(
                        Diagnostic(
                            code="UNKNOWN_FUNCTION",
                            severity=DiagnosticSeverity.ERROR,
                            message=f"Function '{func_name}' is not recognized in DV360 signal registry.",
                            line=actual_line,
                            evidence=f"Call to {func_name}(...)",
                            corrective_action="Use verified functions: sum_aggregate, max_aggregate, first_match_aggregate, total_conversion_count, total_conversion_value, conversion_custom_variable, ga4_conversions_count.",
                        )
                    )
                else:
                    # Check deprecation
                    if sig.status == SignalStatus.DEPRECATED:
                        diagnostics.append(
                            Diagnostic(
                                code="DEPRECATED_SIGNAL",
                                severity=DiagnosticSeverity.WARNING,
                                message=f"Function '{func_name}' is deprecated in DV360. {sig.notes}",
                                line=actual_line,
                                corrective_action=f"Migrate to '{sig.deprecated_replacement}'.",
                            )
                        )
                    # Check arity
                    argc = len(node.args)
                    if argc < sig.min_args or argc > sig.max_args:
                        diagnostics.append(
                            Diagnostic(
                                code="INVALID_FUNCTION_ARITY",
                                severity=DiagnosticSeverity.ERROR,
                                message=f"Function '{func_name}' expects between {sig.min_args} and {sig.max_args} arguments, but received {argc}.",
                                line=actual_line,
                                evidence=f"{func_name} called with {argc} args",
                                corrective_action=f"Check arguments according to DV360 specification: {sig.notes}",
                            )
                        )
                    # Check aggregate function criteria items
                    if sig.kind == SignalKind.AGGREGATION and node.args:
                        first_arg = node.args[0]
                        if isinstance(first_arg, (ast.List, ast.Tuple)):
                            for elt in first_arg.elts:
                                # Each element should be a tuple ([criteria], weight)
                                if isinstance(elt, (ast.Tuple, ast.List)) and len(elt.elts) >= 2:
                                    weight_expr = elt.elts[1]
                                    if isinstance(weight_expr, ast.UnaryOp) and isinstance(weight_expr.op, ast.USub):
                                        if isinstance(weight_expr.operand, ast.Constant) and isinstance(weight_expr.operand.value, (int, float)):
                                            diagnostics.append(
                                                Diagnostic(
                                                    code="NEGATIVE_SCORE_POLICY",
                                                    severity=DiagnosticSeverity.ERROR,
                                                    message=f"Negative weight '-{weight_expr.operand.value}' in {func_name} violates package scoring policy.",
                                                    line=getattr(elt, "lineno", 1) - line_offset,
                                                    corrective_action="Scores and weights in DV360 custom bidding must be non-negative.",
                                                )
                                            )
            else:
                actual_line = getattr(node, "lineno", 1) - line_offset
                diagnostics.append(
                    Diagnostic(
                        code="DYNAMIC_CALL_DISALLOWED",
                        severity=DiagnosticSeverity.ERROR,
                        message="Dynamic or attribute function calls (e.g. obj.method()) are disallowed.",
                        line=actual_line,
                    )
                )

        # Validate identifiers (ast.Name)
        if isinstance(node, ast.Name):
            name = node.id
            actual_line = getattr(node, "lineno", 1) - line_offset
            if (
                name not in ALLOWED_BUILTIN_NAMES
                and name not in local_variables
                and name != "_dv360_script_wrapper"
            ):
                sig = SIGNAL_REGISTRY.get(name)
                if sig is None:
                    # Check if it's the function name in a call, which is checked in ast.Call
                    # If not a registered signal or function, flag unknown identifier
                    diagnostics.append(
                        Diagnostic(
                            code="UNKNOWN_IDENTIFIER",
                            severity=DiagnosticSeverity.ERROR,
                            message=f"Identifier '{name}' is not a recognized DV360 signal, function, or local variable.",
                            line=actual_line,
                            evidence=name,
                            corrective_action="Check signal name against DV360 signals (e.g. device_type, environment, country_code, domain, site_id).",
                        )
                    )
                else:
                    if sig.status == SignalStatus.DEPRECATED:
                        diagnostics.append(
                            Diagnostic(
                                code="DEPRECATED_SIGNAL",
                                severity=DiagnosticSeverity.WARNING,
                                message=f"Signal '{name}' is deprecated. {sig.notes}",
                                line=actual_line,
                                corrective_action=f"Migrate to '{sig.deprecated_replacement}'.",
                            )
                        )

        # Contextual check: CTV domain matching
        if isinstance(node, ast.Compare):
            # Check if comparing device_type == 4 (Connected TV)
            if isinstance(node.left, ast.Name) and node.left.id == "device_type":
                for comp, val in zip(node.ops, node.comparators):
                    if isinstance(comp, ast.Eq) and isinstance(val, ast.Constant) and val.value == 4:
                        saw_ctv_device = True
            elif isinstance(node.left, ast.Name) and node.left.id == "domain":
                saw_domain_check = True

    if saw_ctv_device and saw_domain_check:
        diagnostics.append(
            Diagnostic(
                code="CTV_DOMAIN_MISMATCH",
                severity=DiagnosticSeverity.WARNING,
                message="Script evaluates 'domain' alongside Connected TV (device_type == 4). Connected TV apps report app bundle IDs, not web domains.",
                corrective_action="Target web domains on desktop/mobile and use separate rules for CTV apps.",
            )
        )

    if not has_return:
        diagnostics.append(
            Diagnostic(
                code="MISSING_RETURN",
                severity=DiagnosticSeverity.ERROR,
                message="DV360 custom bidding script must return a final score or an aggregate function (e.g. return sum_aggregate(...)).",
                corrective_action="Add a return statement at the end of the script.",
            )
        )

    has_errors = any(d.severity == DiagnosticSeverity.ERROR for d in diagnostics)
    ast_summary = {
        "total_nodes": total_nodes,
        "node_counts": node_type_counts,
        "local_variables": sorted(local_variables),
    }

    return LintReport(
        is_valid=not has_errors,
        diagnostics=diagnostics,
        ast_summary=ast_summary,
        syntax_version=registry_version or REGISTRY_VERSION,
    )
