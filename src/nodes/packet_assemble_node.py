"""AgentCore Platform v1.0"""

# Inner domain-workflow node (src/graph/domain_workflow_graph.py topology).
# Composes the reviewer packet from normalized fields, checklist status,
# gap findings, and the applicable rule reference.

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.mock_mode import mock_mode_enabled
from src.services.packet_service import PacketService


class PacketAssembleNode(FunctionNode):
    """Composes the draft reviewer packet."""

    # S-1: composes a packet containing asset-derived evidence — verified caller.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        normalized_fields = state.get("normalized_fields") or {}
        checklist_status = state.get("checklist_status") or {}
        gap_findings = state.get("gap_findings") or []
        rule_reference = state.get("rule_reference") or {}

        # Mock mode must short-circuit before any credential is required
        # (.claude/rules/implementation_rule.md Rule 2) — the mock stub path
        # never touches credential_handle.
        if mock_mode_enabled():
            credential_handle = "mock"
        else:
            ctx = InvocationContext.from_state(state)
            credential_handle = ctx.secrets.require("ANTHROPIC_API_KEY")

        service = PacketService()
        draft_packet = asyncio.run(
            service.assemble(normalized_fields, checklist_status, gap_findings, rule_reference, credential_handle)
        )

        emit_trace_event(
            "packet_assembled",
            {
                "gap_count": len(draft_packet.get("gaps", [])),
                "conflict_count": len(draft_packet.get("conflicts", [])),
            },
            state,
        )

        return {
            "draft_packet": draft_packet,
            "status": AgentStatus.SUCCESS.value,
        }
