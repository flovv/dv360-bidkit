"""Unit tests for low-level Google integration primitives."""

from dv360_bidkit.integrations.google import (
    ScriptReadinessState,
    parse_script_readiness_response,
    prepare_script_upload_payload,
)


def test_prepare_script_upload_payload():
    payload = prepare_script_upload_payload(
        "return 1.0",
        algorithm_id="algo_999",
        advertiser_id=12345,
    )
    assert payload.algorithm_id == "algo_999"
    assert payload.advertiser_id == 12345
    assert payload.script_content == "return 1.0"


def test_parse_script_readiness_response():
    resp_active = {
        "customBiddingScriptId": "script_123",
        "state": "READINESS_STATE_ACTIVE",
        "createTime": "2026-01-01T00:00:00Z",
    }
    parsed = parse_script_readiness_response(resp_active)
    assert parsed["script_id"] == "script_123"
    assert parsed["is_active"] is True
    assert parsed["state"] == "READINESS_STATE_ACTIVE"

    resp_training = {
        "customBiddingScriptId": "script_456",
        "state": "READINESS_STATE_TRAINING",
    }
    parsed_train = parse_script_readiness_response(resp_training)
    assert parsed_train["is_active"] is False
    assert parsed_train["state"] == "READINESS_STATE_TRAINING"
