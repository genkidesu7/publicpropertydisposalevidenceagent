"""AgentCore Platform v1.0"""

# Node contract (agents_layer_design.md §1):
#  - Extend FunctionNode; implement execute(state) -> dict
#  - Return ONLY the fields this node changes (never full state)
#  - Return AgentStatus.<X>.value — never bare Enum or plain string
#  - Never import from mediator/, api/, or other agents

from __future__ import annotations

import re
from typing import Any, ClassVar

from framework.errors import SecurityViolationError
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

# Blocks any buyer, price, or disposal-decision inference from leaving the
# packet (engineer_proposal.md §4, OutputValidate step — mandatory S-3 gate).
_BLOCKED_PATTERNS = (
    re.compile(r"\brecommend(?:ed)?\s+buyer\b", re.IGNORECASE),
    re.compile(r"\b(approved|denied|rejected)\b", re.IGNORECASE),
    re.compile(r"\bsell\s+(?:to|for)\b", re.IGNORECASE),
    re.compile(r"[¥$]\s?\d", re.IGNORECASE),
)


class OutputValidateNode(FunctionNode):
    """S-3 gate (mandatory): blocks buyer/price/disposal-decision language and
    verifies every finding cites a source record and checklist item."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        draft_packet = state.get("draft_packet") or {}
        if not draft_packet:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["OutputValidateNode: draft_packet missing — main step must run first"],
            }

        emit_trace_event(
            "packet_gate_cleared",
            {
                "gap_count": len(draft_packet.get("gaps", [])),
                "conflict_count": len(draft_packet.get("conflicts", [])),
            },
            state,
        )

        return {
            "formatted_output": draft_packet,
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """S-3 domain extension (mandatory, not optional for this template):
        - Content filtering: block any buyer, price, or disposal-decision language.
        - Preservation verification: every gap/conflict entry must cite a
          source record / checklist reference — reject output that silently drops it.
        """
        packet = result.get("formatted_output")
        if not isinstance(packet, dict):
            return result

        for section in ("gaps", "conflicts"):
            for entry in packet.get(section, []):
                text_blob = " ".join(str(v) for v in entry.values())
                for pattern in _BLOCKED_PATTERNS:
                    if pattern.search(text_blob):
                        raise SecurityViolationError(
                            f"OutputValidateNode: S-3 blocked buyer/price/disposal-decision "
                            f"language in packet {section} entry: {pattern.pattern!r}"
                        )
                if not entry.get("rule_reference"):
                    raise SecurityViolationError(
                        f"OutputValidateNode: S-3 preservation check failed — "
                        f"{section} entry missing required rule_reference citation"
                    )

        return result  # required — framework returns this directly
