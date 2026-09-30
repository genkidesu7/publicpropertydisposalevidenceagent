"""AgentCore Platform v1.0"""

# Inner domain-workflow node (src/graph/domain_workflow_graph.py topology).
# Matches normalized fields against the disposition checklist.

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.evidence_check_service import EvidenceCheckService


class EvidenceCheckNode(FunctionNode):
    """Flags missing, stale, or conflicting evidence against checklist rules."""

    # S-1: matches asset-derived fields against checklist rules — verified caller.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        normalized_fields = state.get("normalized_fields") or {}
        rule_reference = state.get("rule_reference") or {}
        if not normalized_fields:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["EvidenceCheckNode: normalized_fields missing — Normalize must run first"],
            }

        service = EvidenceCheckService()
        result = service.check(normalized_fields, rule_reference)

        emit_trace_event(
            "evidence_checked",
            {"gap_count": len(result.get("gap_findings", []))},
            state,
        )

        return {
            "checklist_status": result.get("checklist_status", {}),
            "gap_findings": result.get("gap_findings", []),
            "status": AgentStatus.SUCCESS.value,
        }
