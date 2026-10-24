"""Low-level Google DV360 API custom bidding upload and readiness primitives.

References:
- S4: Script upload workflow (https://developers.google.com/display-video/api/guides/tasks/implement-custom-bidding/upload-script)
- S5: v4 script creation reference (https://developers.google.com/display-video/api/reference/rest/v4/customBiddingAlgorithms.scripts/create)
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ScriptState(str, Enum):
    STATE_UNSPECIFIED = "STATE_UNSPECIFIED"
    ACCEPTED = "ACCEPTED"
    ACTIVE = "READINESS_STATE_ACTIVE"
    TRAINING = "READINESS_STATE_TRAINING"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


# Alias for backwards compatibility
ScriptReadinessState = ScriptState


class GoogleScriptUploadPayload(BaseModel):
    partner_id: int | None = None
    advertiser_id: int | None = None
    algorithm_id: str
    script_content: str
    target_state: ScriptState = ScriptState.STATE_UNSPECIFIED


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
    """Extracts state, active status, and errors from DV360 API script response.

    DV360 v4 API specifies:
    - state: ACCEPTED | REJECTED | PENDING | STATE_UNSPECIFIED
    - active: boolean flag indicating if script is currently active for scoring
    """
    raw_state = response_dict.get("state", "STATE_UNSPECIFIED")
    try:
        script_state = ScriptState(raw_state)
    except ValueError:
        script_state = ScriptState.STATE_UNSPECIFIED

    is_active = bool(response_dict.get("active", False)) or script_state in (ScriptState.ACCEPTED, ScriptState.ACTIVE)
    errors = response_dict.get("errors", [])
    script_id = response_dict.get("customBiddingScriptId")
    create_time = response_dict.get("createTime")

    return {
        "script_id": script_id,
        "state": script_state.value,
        "is_active": is_active,
        "errors": errors,
        "create_time": create_time,
    }
