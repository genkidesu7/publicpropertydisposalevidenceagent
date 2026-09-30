"""AgentCore Platform v1.0"""

# Inner domain-workflow node (src/graph/domain_workflow_graph.py topology).
# Retrieves the asset register entry, title/restriction records, appraisal
# documents, and council-resolution record plus the applicable disposition
# checklist for an asset disposal case.

from __future__ import annotations

import asyncio
import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.evidence_retrieval_service import (
    EvidenceRetrievalAssetNotFoundError,
    EvidenceRetrievalService,
)


class RetrieveNode(FunctionNode):
    """Retrieves asset evidence + applicable disposition-checklist rules."""

    # S-1: reads asset/title/appraisal records — requires a verified caller.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # Inner graph starts with fresh state — only "user_input" is forwarded
        # by BaseGraph.invoke(); "validated_input" is not copied in unless the
        # outer GraphNode.extract_input() returned it as user_input. Fall back
        # for both, per sdk-expertise / creat-node skill guidance.
        validated_input = state.get("validated_input", state.get("user_input", ""))
        try:
            payload = json.loads(validated_input) if validated_input else {}
        except (TypeError, json.JSONDecodeError):
            payload = {}

        asset_id = payload.get("asset_id", "")
        case_type = payload.get("case_type", "")

        if not asset_id:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["RetrieveNode: asset_id missing from inner input payload"],
            }

        service = EvidenceRetrievalService()
        try:
            result = asyncio.run(service.retrieve(asset_id, case_type))
        except EvidenceRetrievalAssetNotFoundError as exc:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [f"RetrieveNode: {exc}"],
            }

        emit_trace_event(
            "evidence_retrieved",
            {
                "asset_id": asset_id,
                "record_count": len(result.get("raw_evidence", {})),
            },
            state,
        )

        return {
            "raw_evidence": result.get("raw_evidence", {}),
            "rule_reference": result.get("rule_reference", {}),
            "status": AgentStatus.SUCCESS.value,
        }
