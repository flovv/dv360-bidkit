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
from dv360_bidkit.compiler import (
    ConcaveAttentionConfig,
    compile_concave_attention_script,
    compile_script,
    run_mfa_stress_test,
)
from dv360_bidkit.contracts import RuleSet
from dv360_bidkit.io import load_inventory_policy
from dv360_bidkit.evaluator.economics import analyze_attention_fee_economics
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
    },
    {
        "name": "check_attention_fee_economics",
        "description": "Compute attention fee-stack break-even yield hurdles (clearing CPM uplift, pre-bid CPM surcharges, SSP curation take rates, 3P AI fees) and compare naive linear recall forecasts against Simonov et al. (JMR 2025) bounded quadratic recall.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "base_cpm": {"type": "number", "description": "Baseline clearing CPM (e.g. 4.50 display, 22.0 CTV)."},
                "cpm_uplift_pct": {"type": "number", "description": "Expected clearing CPM uplift % (default 15.0)."},
                "prebid_cpm_fee": {"type": "number", "description": "Fixed 3P pre-bid attention segment CPM surcharge (default 0.0)."},
                "curation_fee_pct": {"type": "number", "description": "SSP curation take rate % (e.g. 11.0 median, default 0.0)."},
                "ai_fee_pct": {"type": "number", "description": "Third-party AI fee % (default 0.0)."},
                "agency_fee_pct": {"type": "number", "description": "Agency optimization fee % (default 0.0)."},
                "budget": {"type": "number", "description": "Fixed media budget (default 100000.0)."},
                "frequency": {"type": "number", "description": "Average impressions per user (default 6.0)."},
                "base_dwell_seconds": {"type": "number", "description": "Baseline average dwell per impression in seconds (default 1.10)."},
                "target_dwell_seconds": {"type": "number", "description": "Expected average dwell per impression in seconds (default 2.40)."},
                "currency": {"type": "string", "description": "Currency code (default EUR)."}
            },
            "required": ["base_cpm"]
        }
    },
    {
        "name": "compile_concave_attention_script",
        "description": "Compile a zero-fee, DV360 DSL-compliant concave attention + outcome custom bidding script (capped time_on_screen_seconds + log decay + eye-tracking format multipliers + Floodlight/GA4 anchor) and optionally run the 4-strategy sticky-MFA stress test.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dwell_cap_seconds": {"type": "number", "description": "Upper cap on time_on_screen_seconds (default 20.0)."},
                "floodlight_activity_id": {"type": "integer", "description": "Optional Floodlight Activity ID."},
                "conversion_weight": {"type": "number", "description": "Weight for Floodlight/GA4 conversions (default 25.0)."},
                "use_conversion_value": {"type": "boolean", "description": "Use total_conversion_value instead of count (default false)."},
                "ga4_property_id": {"type": "integer", "description": "Optional GA4 property ID."},
                "ga4_event_name": {"type": "string", "description": "Optional GA4 conversion event name."},
                "excluded_domains": {"type": "array", "items": {"type": "string"}, "description": "Optional list of MFA domains to exclude."},
                "run_stress_test": {"type": "boolean", "description": "Whether to include the 4-strategy sticky-MFA stress test (default true)."}
            }
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

    elif name == "check_attention_fee_economics":
        res = analyze_attention_fee_economics(
            base_cpm=float(arguments.get("base_cpm", 4.50)),
            cpm_uplift_pct=float(arguments.get("cpm_uplift_pct", 15.0)),
            prebid_cpm_fee=float(arguments.get("prebid_cpm_fee", 0.0)),
            curation_fee_pct=float(arguments.get("curation_fee_pct", 0.0)),
            ai_fee_pct=float(arguments.get("ai_fee_pct", 0.0)),
            agency_fee_pct=float(arguments.get("agency_fee_pct", 0.0)),
            budget=float(arguments.get("budget", 100000.0)),
            frequency=float(arguments.get("frequency", 6.0)),
            base_dwell_seconds=float(arguments.get("base_dwell_seconds", 1.10)),
            target_dwell_seconds=float(arguments.get("target_dwell_seconds", 2.40)),
            currency=str(arguments.get("currency", "EUR")),
        )
        return res.model_dump()

    elif name == "compile_concave_attention_script":
        cfg = ConcaveAttentionConfig(
            dwell_cap_seconds=float(arguments.get("dwell_cap_seconds", 20.0)),
            floodlight_activity_id=arguments.get("floodlight_activity_id"),
            conversion_weight=float(arguments.get("conversion_weight", 25.0)),
            use_conversion_value=bool(arguments.get("use_conversion_value", False)),
            ga4_property_id=arguments.get("ga4_property_id"),
            ga4_event_name=arguments.get("ga4_event_name"),
            excluded_domains=list(arguments.get("excluded_domains") or []),
        )
        script = compile_concave_attention_script(cfg, validate=True)
        stress = run_mfa_stress_test(config=cfg) if arguments.get("run_stress_test", True) else None
        return {
            "script_code": script,
            "byte_length": len(script.encode("utf-8")),
            "mfa_stress_test": stress.model_dump() if stress else None,
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
