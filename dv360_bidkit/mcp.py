"""
Model Context Protocol (MCP) server for dv360-bidkit.
Enables Claude Desktop, Cursor, and agent runtimes to validate, compile,
and inspect DV360 custom bidding algorithms over stdio or JSON-RPC.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

from dv360_bidkit import __version__
from dv360_bidkit.compiler import compile_script
from dv360_bidkit.contracts import RuleSet
from dv360_bidkit.io import load_inventory_policy
from dv360_bidkit.linter import lint_script

# Empirical attention normative benchmarks (Simonov & Valletti 2024 / Lumen Research)
ATTENTION_BENCHMARKS = {
    "source_studies": [
        "Simonov & Valletti (2024) - Attention Spillovers from News to Ads (Working Papers)",
        "Lumen Research Normative Eye-Tracking Database (Display & Video)"
    ],
    "empirical_elasticities": {
        "recall_lift_per_second_dwell": "+3.4 percentage points (p < 0.001)",
        "purchase_intent_lift_per_second_dwell": "+0.7 percentage points (p = 0.02)",
        "editorial_content_spillover_gamma": 0.017,
        "viewability_to_human_gaze_ratio": "8% - 15% of viewable impressions receive active gaze"
    },
    "format_benchmarks": {
        "billboard_970x250": {"apm": 650, "relative_bid_multiplier": 2.0},
        "half_page_300x600": {"apm": 550, "relative_bid_multiplier": 1.8},
        "in_read_video": {"apm": 450, "relative_bid_multiplier": 1.6},
        "medium_rectangle_300x250": {"apm": 110, "relative_bid_multiplier": 1.0},
        "leaderboard_728x90": {"apm": 60, "relative_bid_multiplier": 0.6},
        "mobile_banner_320x50": {"apm": 35, "relative_bid_multiplier": 0.4}
    },
    "position_benchmarks": {
        "in_article_embedded": {"multiplier": 1.4, "note": "High scroll-pause rate"},
        "above_the_fold_header": {"multiplier": 1.0, "note": "Rapid fast-scroll trap"},
        "below_the_fold_footer": {"multiplier": 0.5, "note": "Low active viewability"}
    },
    "device_benchmarks": {
        "desktop": {"avg_gaze_seconds": 1.4, "multiplier": 1.2},
        "mobile_smartphone": {"avg_gaze_seconds": 0.9, "multiplier": 0.9}
    }
}

TOOLS = [
    {
        "name": "validate_custom_bidding_script",
        "description": "Lint and validate a Google Display & Video 360 (DV360) custom bidding script against the official 2026 DSL specification. Verifies AST syntax, signal registry compliance, and characters/node limits.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script_code": {
                    "type": "string",
                    "description": "The Python code of the DV360 custom bidding script to validate."
                }
            },
            "required": ["script_code"]
        }
    },
    {
        "name": "get_attention_benchmarks",
        "description": "Retrieve empirical attention factors and dwell benchmarks (Simonov & Valletti 2024 / Lumen Research) including format APM (Attentive Seconds Per Mille), fold multipliers, and editorial spillovers.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "compile_custom_bidding_script",
        "description": "Compile a structured DV360 RuleSet JSON (and optional inventory policy CSV/JSON) into a production-grade, Google DSL compliant Python custom bidding script.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ruleset_json": {
                    "type": "string",
                    "description": "JSON string matching the DV360 RuleSet schema (aggregation mode, rules list, conditions, weights)."
                },
                "policy_csv": {
                    "type": "string",
                    "description": "Optional inventory policy CSV string containing domain inclusions/exclusions and overrides."
                }
            },
            "required": ["ruleset_json"]
        }
    }
]


def handle_tool_call(name: str, arguments: Dict[str, Any]) -> Any:
    if name == "validate_custom_bidding_script":
        script_code = arguments.get("script_code", "")
        report = lint_script(script_code)
        return {
            "is_valid": report.is_valid,
            "syntax_version": report.syntax_version,
            "diagnostics": [
                {
                    "code": d.code,
                    "message": d.message,
                    "severity": d.severity.value,
                    "line": d.line
                }
                for d in report.diagnostics
            ],
            "ast_summary": report.ast_summary
        }

    elif name == "get_attention_benchmarks":
        return ATTENTION_BENCHMARKS

    elif name == "compile_custom_bidding_script":
        ruleset_raw = arguments.get("ruleset_json", "{}")
        policy_csv = arguments.get("policy_csv")

        if isinstance(ruleset_raw, str):
            rules_dict = json.loads(ruleset_raw)
        else:
            rules_dict = ruleset_raw

        ruleset = RuleSet.model_validate(rules_dict)
        policy = load_inventory_policy(policy_csv) if policy_csv else None

        result = compile_script(ruleset, policy=policy)
        return {
            "script_code": result.script_code,
            "character_count": len(result.script_code),
            "max_character_limit": 65536,
            "within_dsl_budget": len(result.script_code) <= 65536
        }

    else:
        raise ValueError(f"Unknown tool: {name}")


def run_stdio_server() -> None:
    """Run MCP server over standard input/output (stdio JSON-RPC)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "dv360-bidkit-mcp",
                        "version": __version__
                    }
                }
            }
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": TOOLS
                }
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                result_data = handle_tool_call(tool_name, arguments)
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result_data, indent=2)
                            }
                        ]
                    }
                }
            except Exception as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "isError": True,
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error executing {tool_name}: {str(e)}"
                            }
                        ]
                    }
                }
        else:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found"
                }
            }

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
