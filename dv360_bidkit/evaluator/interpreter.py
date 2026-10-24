"""Safe AST interpreter for DV360 Custom Bidding scripts.

Executes supported AST nodes directly against impression row data
without invoking Python's eval() or exec(). Enforces depth and
operation count budgets, handles short-circuit evaluation, and
implements DV360 aggregate functions (sum_aggregate, max_aggregate, first_match_aggregate).
"""

from __future__ import annotations

import ast
import math
from typing import Any, Callable

from dv360_bidkit.contracts.exceptions import EvaluationError
from dv360_bidkit.linter.ast_validator import _wrap_top_level_returns


class EvaluationResult:
    __slots__ = ("score", "is_excluded", "error")

    def __init__(
        self,
        score: float | None = None,
        is_excluded: bool = False,
        error: str | None = None,
    ):
        self.score = score
        self.is_excluded = is_excluded
        self.error = error

    def __repr__(self) -> str:
        return f"EvaluationResult(score={self.score}, is_excluded={self.is_excluded}, error={self.error})"


class ASTInterpreter:
    def __init__(
        self,
        tree: ast.AST,
        *,
        max_ops: int = 25000,
        max_depth: int = 50,
    ):
        self.tree = tree
        self.max_ops = max_ops
        self.max_depth = max_depth
        self.op_count = 0
        self.depth = 0

    def _tick(self) -> None:
        self.op_count += 1
        if self.op_count > self.max_ops:
            raise EvaluationError(f"Execution exceeded budget of {self.max_ops} operations.")

    def evaluate(self, context: dict[str, Any]) -> EvaluationResult:
        """Evaluates AST tree against row context dictionary."""
        self.op_count = 0
        self.depth = 0
        local_vars: dict[str, Any] = {}

        try:
            val, returned = self._eval_node(self.tree, context, local_vars)
            if not returned:
                # If no return statement was encountered, default is excluded or 0.0
                return EvaluationResult(score=0.0, is_excluded=False)

            if val is None:
                # return None signals exclusion from model training
                return EvaluationResult(score=None, is_excluded=True)

            score_val = float(val)
            if math.isnan(score_val) or math.isinf(score_val):
                return EvaluationResult(
                    score=None,
                    is_excluded=False,
                    error=f"Non-finite score encountered: {score_val}",
                )
            if score_val < 0.0:
                return EvaluationResult(
                    score=None,
                    is_excluded=False,
                    error=f"Negative score encountered: {score_val} (policy requires non-negative scores)",
                )

            return EvaluationResult(score=score_val, is_excluded=False)
        except ZeroDivisionError:
            return EvaluationResult(score=None, is_excluded=False, error="Division by zero")
        except Exception as exc:
            return EvaluationResult(score=None, is_excluded=False, error=str(exc))

    def _eval_node(
        self,
        node: ast.AST,
        context: dict[str, Any],
        local_vars: dict[str, Any],
    ) -> tuple[Any, bool]:
        """Evaluates AST node. Returns (value, is_returned_flag)."""
        self._tick()
        self.depth += 1
        if self.depth > self.max_depth:
            self.depth -= 1
            raise EvaluationError(f"Call depth exceeded limit of {self.max_depth}.")

        try:
            # Module
            if isinstance(node, ast.Module):
                for stmt in node.body:
                    res, returned = self._eval_node(stmt, context, local_vars)
                    if returned:
                        return res, True
                return None, False

            # FunctionDef (wrapper)
            if isinstance(node, ast.FunctionDef):
                for stmt in node.body:
                    res, returned = self._eval_node(stmt, context, local_vars)
                    if returned:
                        return res, True
                return None, False

            # Assign
            if isinstance(node, ast.Assign):
                rhs, _ = self._eval_node(node.value, context, local_vars)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        local_vars[target.id] = rhs
                return None, False

            # Return
            if isinstance(node, ast.Return):
                if node.value is None:
                    return None, True
                val, _ = self._eval_node(node.value, context, local_vars)
                return val, True

            # Expr
            if isinstance(node, ast.Expr):
                return self._eval_node(node.value, context, local_vars)

            # If statement
            if isinstance(node, ast.If):
                test_val, _ = self._eval_node(node.test, context, local_vars)
                body = node.body if bool(test_val) else node.orelse
                for stmt in body:
                    res, returned = self._eval_node(stmt, context, local_vars)
                    if returned:
                        return res, True
                return None, False

            # Ternary IfExp (a if cond else b)
            if isinstance(node, ast.IfExp):
                test_val, _ = self._eval_node(node.test, context, local_vars)
                if bool(test_val):
                    return self._eval_node(node.body, context, local_vars)
                return self._eval_node(node.orelse, context, local_vars)

            # Constant (literals)
            if isinstance(node, ast.Constant):
                return node.value, False

            # Name
            if isinstance(node, ast.Name):
                name = node.id
                if name == "True":
                    return True, False
                if name == "False":
                    return False, False
                if name == "None":
                    return None, False
                if name in local_vars:
                    return local_vars[name], False
                if name in context:
                    return context[name], False
                # If identifier is not in context, raise or return None
                return None, False

            # List & Tuple
            if isinstance(node, (ast.List, ast.Tuple)):
                elements = [self._eval_node(elt, context, local_vars)[0] for elt in node.elts]
                return elements, False

            # UnaryOp
            if isinstance(node, ast.UnaryOp):
                operand, _ = self._eval_node(node.operand, context, local_vars)
                if isinstance(node.op, ast.Not):
                    return not operand, False
                if operand is None:
                    raise EvaluationError(f"Cannot apply unary {type(node.op).__name__} to None")
                if isinstance(node.op, ast.USub):
                    return -operand, False
                if isinstance(node.op, ast.UAdd):
                    return +operand, False
                raise EvaluationError(f"Unsupported unary operator: {type(node.op).__name__}")

            # BinOp
            if isinstance(node, ast.BinOp):
                left, _ = self._eval_node(node.left, context, local_vars)
                right, _ = self._eval_node(node.right, context, local_vars)
                if left is None or right is None:
                    raise EvaluationError(f"Arithmetic operation on None operand: left={left}, right={right}")
                if isinstance(node.op, ast.Add):
                    return left + right, False
                if isinstance(node.op, ast.Sub):
                    return left - right, False
                if isinstance(node.op, ast.Mult):
                    return left * right, False
                if isinstance(node.op, ast.Div):
                    if right == 0:
                        raise ZeroDivisionError("Division by zero")
                    return left / right, False
                if isinstance(node.op, ast.FloorDiv):
                    if right == 0:
                        raise ZeroDivisionError("Floor division by zero")
                    return left // right, False
                if isinstance(node.op, ast.Mod):
                    if right == 0:
                        raise ZeroDivisionError("Modulo by zero")
                    return left % right, False
                if isinstance(node.op, ast.Pow):
                    return left ** right, False
                raise EvaluationError(f"Unsupported binary operator: {type(node.op).__name__}")

            # BoolOp (and, or) with short-circuiting
            if isinstance(node, ast.BoolOp):
                if isinstance(node.op, ast.And):
                    for val_node in node.values:
                        res, _ = self._eval_node(val_node, context, local_vars)
                        if not bool(res):
                            return False, False
                    return True, False
                if isinstance(node.op, ast.Or):
                    for val_node in node.values:
                        res, _ = self._eval_node(val_node, context, local_vars)
                        if bool(res):
                            return True, False
                    return False, False
                raise EvaluationError(f"Unsupported bool operator: {type(node.op).__name__}")

            # Compare
            if isinstance(node, ast.Compare):
                current_left, _ = self._eval_node(node.left, context, local_vars)
                for op, comparator_node in zip(node.ops, node.comparators):
                    comp_val, _ = self._eval_node(comparator_node, context, local_vars)
                    matched = self._eval_comparison(current_left, op, comp_val)
                    if not matched:
                        return False, False
                    current_left = comp_val
                return True, False

            # Call
            if isinstance(node, ast.Call):
                return self._eval_call(node, context, local_vars)

            raise EvaluationError(f"Unsupported AST node in evaluation: {type(node).__name__}")
        finally:
            self.depth -= 1

    def _eval_comparison(self, left: Any, op: ast.cmpop, right: Any) -> bool:
        """Evaluates comparison operator."""
        if isinstance(op, ast.Eq):
            return bool(left == right)
        if isinstance(op, ast.NotEq):
            return bool(left != right)
        if isinstance(op, ast.In):
            if right is None:
                return False
            return bool(left in right)
        if isinstance(op, ast.NotIn):
            if right is None:
                return True
            return bool(left not in right)

        # Ordering comparisons require non-null values
        if left is None or right is None:
            return False

        if isinstance(op, ast.Lt):
            return bool(left < right)
        if isinstance(op, ast.LtE):
            return bool(left <= right)
        if isinstance(op, ast.Gt):
            return bool(left > right)
        if isinstance(op, ast.GtE):
            return bool(left >= right)

        raise EvaluationError(f"Unsupported comparison operator: {type(op).__name__}")

    def _eval_call(
        self,
        node: ast.Call,
        context: dict[str, Any],
        local_vars: dict[str, Any],
    ) -> tuple[Any, bool]:
        """Evaluates a function call."""
        if not isinstance(node.func, ast.Name):
            raise EvaluationError("Only direct named function calls are supported.")

        func_name = node.func.id

        # Built-in aggregate functions
        if func_name in ("sum_aggregate", "max_aggregate", "first_match_aggregate"):
            if not node.args:
                return 0.0, False
            criteria_list_arg, _ = self._eval_node(node.args[0], context, local_vars)
            return self._eval_aggregate(func_name, criteria_list_arg), False

        # Built-in type casting
        if func_name == "float":
            arg_val, _ = self._eval_node(node.args[0], context, local_vars)
            return float(arg_val), False
        if func_name == "int":
            arg_val, _ = self._eval_node(node.args[0], context, local_vars)
            return int(arg_val), False
        if func_name == "str":
            arg_val, _ = self._eval_node(node.args[0], context, local_vars)
            return str(arg_val), False
        if func_name == "bool":
            arg_val, _ = self._eval_node(node.args[0], context, local_vars)
            return bool(arg_val), False

        # Conversion / GA4 helper dispatch
        # Checks if row context provides a function or table lookup
        args = [self._eval_node(arg, context, local_vars)[0] for arg in node.args]

        if func_name in context and callable(context[func_name]):
            return context[func_name](*args), False

        # Default handler for Floodlight / GA4 function lookups in row context dict
        # e.g. key `total_conversion_count:12345:0` or `total_conversion_count`
        compound_key = f"{func_name}:" + ":".join(str(a) for a in args)
        if compound_key in context:
            return context[compound_key], False

        # Check general column name fallback
        if func_name in context:
            return context[func_name], False
        if func_name == "total_conversion_count" and "conversions" in context:
            return context["conversions"], False
        if func_name == "total_conversion_value" and "conversion_value" in context:
            return context["conversion_value"], False

        # If signal is absent from row context and report mapping, signal evaluation error
        if func_name.startswith("total_conversion_") or func_name in ("conversion_custom_variable", "ga4_conversions_count"):
            raise EvaluationError(f"Missing signal data in row context for '{func_name}' (expected column or key '{compound_key}').")

        raise EvaluationError(f"Function '{func_name}' has no runtime definition in evaluator.")

    def _eval_aggregate(self, func_name: str, criteria_list: Any) -> float:
        """Evaluates DV360 aggregate criteria list.

        Each entry is typically ([condition_list_or_bool], weight).
        """
        if not isinstance(criteria_list, (list, tuple)):
            return 0.0

        matched_weights: list[float] = []

        for item in criteria_list:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue

            cond_expr = item[0]
            weight = float(item[1])

            # Condition can be a single boolean or list of booleans (AND-ed)
            is_match = False
            if isinstance(cond_expr, (list, tuple)):
                is_match = all(bool(c) for c in cond_expr) if cond_expr else True
            else:
                is_match = bool(cond_expr)

            if is_match:
                if func_name == "first_match_aggregate":
                    return weight
                matched_weights.append(weight)

        if func_name == "sum_aggregate":
            return sum(matched_weights)
        if func_name == "max_aggregate":
            return max(matched_weights) if matched_weights else 0.0

        return 0.0


def create_interpreter(code: str) -> ASTInterpreter:
    """Creates an ASTInterpreter from DV360 script source code."""
    wrapped_code, _ = _wrap_top_level_returns(code)
    tree = ast.parse(wrapped_code)
    return ASTInterpreter(tree)
