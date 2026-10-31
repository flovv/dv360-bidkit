import json
from dv360_bidkit.mcp import handle_tool_call, TOOLS, ATTENTION_BENCHMARKS


def test_mcp_tools_list():
    tool_names = [t["name"] for t in TOOLS]
    assert "validate_custom_bidding_script" in tool_names
    assert "get_attention_benchmarks" in tool_names
    assert "compile_custom_bidding_script" in tool_names


def test_mcp_validate_tool():
    # Valid script
    res = handle_tool_call("validate_custom_bidding_script", {"script_code": "return 1.0\n"})
    assert res["is_valid"] is True
    assert res["syntax_version"] == "2026.1"

    # Invalid script
    res_invalid = handle_tool_call("validate_custom_bidding_script", {"script_code": "import os; os.system('ls')"})
    assert res_invalid["is_valid"] is False
    assert len(res_invalid["diagnostics"]) > 0


def test_mcp_attention_benchmarks_tool():
    res = handle_tool_call("get_attention_benchmarks", {})
    assert "format_benchmarks" in res
    assert "billboard_970x250" in res["format_benchmarks"]
    assert res["format_benchmarks"]["billboard_970x250"]["relative_bid_multiplier"] == 2.0


def test_mcp_compile_tool():
    ruleset_dict = {
        "aggregation": "max",
        "baseline_weight": 1.0,
        "rules": [
            {
                "id": "rule_mobile",
                "conditions": [{"field": "device_type", "operator": "==", "value": 2}],
                "weight": 0.8
            }
        ]
    }
    res = handle_tool_call("compile_custom_bidding_script", {"ruleset_json": json.dumps(ruleset_dict)})
    assert "script_code" in res
    assert res["within_dsl_budget"] is True
    assert "device_type == 2" in res["script_code"]
