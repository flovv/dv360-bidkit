"""Script size, node, and budget validation for compiled DV360 scripts."""

from __future__ import annotations

import ast

from dv360_bidkit.contracts.exceptions import BudgetExceededError
from dv360_bidkit.contracts.schemas import Diagnostic, DiagnosticSeverity, ScriptBudgets
from dv360_bidkit.linter.ast_validator import _wrap_top_level_returns


def check_script_budgets(
    code: str,
    rule_count: int,
    budgets: ScriptBudgets | None = None,
) -> tuple[bool, int, int, int, list[Diagnostic]]:
    """Checks compiled script code against size, byte, node, and rule limits.

    Returns:
        (passed, char_count, byte_count, ast_nodes, diagnostics)
    """
    budgets = budgets or ScriptBudgets()
    char_count = len(code)
    byte_count = len(code.encode("utf-8"))

    wrapped, _ = _wrap_top_level_returns(code)
    try:
        tree = ast.parse(wrapped)
        ast_nodes = sum(1 for _ in ast.walk(tree))
    except Exception:
        ast_nodes = 0

    diagnostics: list[Diagnostic] = []
    passed = True

    if char_count > budgets.max_chars:
        passed = False
        diagnostics.append(
            Diagnostic(
                code="BUDGET_CHAR_LIMIT_EXCEEDED",
                severity=DiagnosticSeverity.ERROR,
                message=f"Script length {char_count} exceeds maximum character budget of {budgets.max_chars}.",
                evidence=f"Characters: {char_count} / {budgets.max_chars}",
                corrective_action="Use rule simplification or domain quantization to reduce script length.",
            )
        )

    if byte_count > budgets.max_bytes:
        passed = False
        diagnostics.append(
            Diagnostic(
                code="BUDGET_BYTE_LIMIT_EXCEEDED",
                severity=DiagnosticSeverity.ERROR,
                message=f"Script size {byte_count} bytes exceeds maximum budget of {budgets.max_bytes} bytes.",
                evidence=f"Bytes: {byte_count} / {budgets.max_bytes}",
                corrective_action="Reduce rule count or compress domain lists.",
            )
        )

    if ast_nodes > budgets.max_ast_nodes:
        passed = False
        diagnostics.append(
            Diagnostic(
                code="BUDGET_NODE_LIMIT_EXCEEDED",
                severity=DiagnosticSeverity.ERROR,
                message=f"Script AST contains {ast_nodes} nodes, exceeding budget of {budgets.max_ast_nodes}.",
                evidence=f"Nodes: {ast_nodes} / {budgets.max_ast_nodes}",
            )
        )

    if rule_count > budgets.max_rules:
        passed = False
        diagnostics.append(
            Diagnostic(
                code="BUDGET_RULE_LIMIT_EXCEEDED",
                severity=DiagnosticSeverity.ERROR,
                message=f"Rule count {rule_count} exceeds budget of {budgets.max_rules}.",
                evidence=f"Rules: {rule_count} / {budgets.max_rules}",
            )
        )

    return passed, char_count, byte_count, ast_nodes, diagnostics
