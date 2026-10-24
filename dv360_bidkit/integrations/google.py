"""Low-level Google DV360 API custom bidding upload and readiness primitives.

References:
- S4: Script upload workflow (https://developers.google.com/display-video/api/guides/tasks/implement-custom-bidding/upload-script)
- S5: v4 script creation reference (https://developers.google.com/display-video/api/reference/rest/v4/customBiddingAlgorithms.scripts/create)
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ScriptReadinessState(str, Enum):
    STATE_UNSPECIFIED = "STATE_UNSPECIFIED"
    ACTIVE = "READINESS_STATE_ACTIVE"
    INSUFFICIENT_DATA = "READINESS_STATE_INSUFFICIENT_DATA"
    TRAINING = "READINESS_STATE_TRAINING"
    EVALUATION_FAILURE = "READINESS_STATE_EVALUATION_FAILURE"


class GoogleScriptUploadPayload(BaseModel):
    partner_id: int | None = None
    advertiser_id: int | None = None
    algorithm_id: str
    script_content: str
    target_readiness_state: ScriptReadinessState = ScriptReadinessState.STATE_UNSPECIFIED


def prepare_script_upload_payload(
    script_content: str,
    *,
    algorithm_id: str,
    advertiser_id: int | None = None,
    partner_id: int | None = None,
) -> GoogleScriptUploadPayload:
    """Prepares structured payload for DV360 customBiddingAlgorithms.scripts.create API."""
    return GoogleScriptUploadPayload(
        algorithm_id=algorithm_id,
        advertiser_id=advertiser_id,
        partner_id=partner_id,
        script_content=script_content,
    )


def parse_script_readiness_response(response_dict: dict[str, Any]) -> dict[str, Any]:
    """Extracts readiness state and errors from DV360 API script response."""
    raw_state = response_dict.get("state", "STATE_UNSPECIFIED")
    try:
        readiness_state = ScriptReadinessState(raw_state)
    except ValueError:
        readiness_state = ScriptReadinessState.STATE_UNSPECIFIED

    errors = response_dict.get("errors", [])
    script_id = response_dict.get("customBiddingScriptId")
    create_time = response_dict.get("createTime")

    return {
        "script_id": script_id,
        "state": readiness_state.value,
        "is_active": readiness_state == ScriptReadinessState.ACTIVE,
        "errors": errors,
        "create_time": create_time,
    }
