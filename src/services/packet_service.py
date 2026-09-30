"""AgentCore Platform v1.0"""

# Service layer: domain queries, external API wrappers, data aggregation.
# Must NOT contain business logic, routing, or credentials.
# Nodes call this; this calls shared/services/ for external integrations.

from __future__ import annotations

from typing import Any

from src.services.mock_mode import mock_mode_enabled


class PacketService:
    """LLM synthesis of the source-linked evidence-gap and review packet:
    confirmed evidence, gap list, conflict list, checklist status per item —
    each linked to its source record and applicable checklist item.

    Usage from a node::

        service = PacketService()
        draft_packet = await service.assemble(
            normalized_fields, checklist_status, gap_findings, rule_reference, credential_handle
        )
    """

    def __init__(self) -> None:
        self._mock_mode: bool = mock_mode_enabled()

    async def assemble(
        self,
        normalized_fields: dict[str, Any],
        checklist_status: dict[str, Any],
        gap_findings: list[dict[str, Any]],
        rule_reference: dict[str, Any],
        credential_handle: str,
    ) -> dict[str, Any]:
        """Assemble the draft review packet.

        Args:
            credential_handle: Opaque handle from InvocationContext.secrets.require().
                Never log or store this value. Not required in mock mode.
        """
        if not self._mock_mode and not credential_handle:
            raise ValueError(
                "PacketService.assemble: credential_handle is empty — check InvocationContext configuration"
            )
        return await self._call_llm(
            normalized_fields, checklist_status, gap_findings, rule_reference, credential_handle
        )

    async def _call_llm(
        self,
        normalized_fields: dict[str, Any],
        checklist_status: dict[str, Any],
        gap_findings: list[dict[str, Any]],
        rule_reference: dict[str, Any],
        credential_handle: str,  # noqa: ARG002
    ) -> dict[str, Any]:
        if self._mock_mode:
            from src.services.mock_data import stub_assemble_packet

            return await stub_assemble_packet(normalized_fields, checklist_status, gap_findings, rule_reference)
        raise NotImplementedError(
            "PacketService._call_llm: not yet wired. Wire shared/services/<llm_client> in the next sprint."
        )
