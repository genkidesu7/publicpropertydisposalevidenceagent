"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict (see ADR-005 for the prohibited
# alternatives). LangGraph checkpoints use msgpack serialization, so only
# plain serializable fields are allowed. Do NOT add credentials or secrets.

from typing import Any

from framework.schemas.agent_state import AgentState


class State(AgentState):
    """Agent state for PublicPropertyDisposalEvidenceAgent.

    All shared fields (user_input, status, session_id, node_history,
    error_log, hitl_*, etc.) are inherited from AgentState. Fields below are
    specific to the disposal due-diligence evidence workflow — see
    docs/02_design.md "State Definition".
    """

    asset_id: str
    case_type: str
    raw_evidence: dict[str, Any]
    rule_reference: dict[str, Any]
    normalized_fields: dict[str, Any]
    checklist_status: dict[str, Any]
    gap_findings: list[dict[str, Any]]
    draft_packet: dict[str, Any]
