"""AgentCore Platform v1.0"""

# Node contract (agents_layer_design.md §1):
#  - Extend FunctionNode; implement execute(state) -> dict
#  - Return ONLY the fields this node changes (never full state)
#  - Return AgentStatus.<X>.value — never bare Enum or plain string
#  - Read input_context via state.get("input_context", {}) — read-only [C1]
#  - Never import from mediator/, api/, or other agents

from __future__ import annotations

import json
import re
from typing import Any, ClassVar

from framework.errors import SecurityViolationError
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

# Accepted asset_id shape, e.g. "ASSET-001". Adjust only alongside the asset
# register's actual identifier format.
_ASSET_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_]{2,63}$")
_VALID_CASE_TYPES = frozenset({"sale", "lease_termination", "transfer"})


def _parse_case_request(user_input: str) -> dict[str, str]:
    """Parse the {"asset_id": ..., "case_type": ...} request payload.

    Raises SecurityViolationError on invalid JSON — shared by the S-2 gate
    (validation) and execute() (extraction), so the request is parsed with
    identical rules in both places without stashing private keys on state.
    """
    try:
        payload = json.loads(user_input) if user_input else {}
    except (TypeError, json.JSONDecodeError) as exc:
        raise SecurityViolationError(f"CaseIntakeNode: input is not valid JSON: {exc}") from exc
    return {
        "asset_id": payload.get("asset_id", ""),
        "case_type": payload.get("case_type", ""),
    }


class CaseIntakeNode(FunctionNode):
    """S-1 gate: validates asset_id + case_type before evidence retrieval.

    Expects request input as JSON: {"asset_id": "...", "case_type": "sale|lease_termination|transfer"}.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def _extra_security_gate_input(self, state: dict[str, Any]) -> dict[str, Any]:
        """S-2 domain extension: reject requests without a valid asset_id or a
        case_type outside the configured scope (engineer_proposal.md §4,
        CaseIntake step)."""
        parsed = _parse_case_request(state.get("user_input", ""))
        asset_id = parsed["asset_id"]
        case_type = parsed["case_type"]

        if not asset_id or not _ASSET_ID_PATTERN.match(asset_id):
            raise SecurityViolationError("CaseIntakeNode: missing or malformed asset_id")
        if case_type not in _VALID_CASE_TYPES:
            raise SecurityViolationError(
                f"CaseIntakeNode: case_type must be one of {sorted(_VALID_CASE_TYPES)}, got {case_type!r}"
            )
        return state  # required — framework crashes on None

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        parsed = _parse_case_request(state.get("user_input", ""))
        asset_id = parsed["asset_id"]
        case_type = parsed["case_type"]

        # validated_input carries the case identifier bundle across the
        # GraphNode -> inner-graph boundary as JSON (BaseGraph.invoke() only
        # forwards a single string as the inner graph's user_input).
        validated_input = json.dumps({"asset_id": asset_id, "case_type": case_type})

        emit_trace_event("case_validated", {"asset_id": asset_id, "case_type": case_type}, state)

        return {
            "validated_input": validated_input,
            "asset_id": asset_id,
            "case_type": case_type,
            "status": AgentStatus.SUCCESS.value,
        }
