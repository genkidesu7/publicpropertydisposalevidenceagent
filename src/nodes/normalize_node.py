"""AgentCore Platform v1.0"""

# Inner domain-workflow node (src/graph/domain_workflow_graph.py topology).
# Deterministic mapping of raw_evidence into the fixed disposition-dossier
# schema fields (no LLM call — see NormalizationService docstring).

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.normalization_service import NormalizationService


class NormalizeNode(FunctionNode):
    """Maps raw_evidence to normalized_fields via NormalizationService."""

    # S-1: reads asset-derived records — verified caller only.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw_evidence = state.get("raw_evidence") or {}
        if not raw_evidence:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["NormalizeNode: raw_evidence missing — Retrieve must run first"],
            }

        service = NormalizationService()
        normalized_fields = service.normalize(raw_evidence)

        emit_trace_event(
            "fields_normalized",
            {"field_count": len(normalized_fields)},
            state,
        )

        return {
            "normalized_fields": normalized_fields,
            "status": AgentStatus.SUCCESS.value,
        }
