"""AgentCore Platform v1.0"""

# Service layer: domain queries, external API wrappers, data aggregation.
# Must NOT contain business logic, routing, or credentials.
# Nodes call this; this calls shared/services/ for external integrations.

from __future__ import annotations

from typing import Any

from src.services.mock_mode import mock_mode_enabled

_VALID_CASE_TYPES = frozenset({"sale", "lease_termination", "transfer"})


class EvidenceRetrievalAssetNotFoundError(Exception):
    """asset_id is unknown, or case_type is outside the configured scope."""


class EvidenceRetrievalService:
    """Retrieves the asset register entry, title/restriction records,
    appraisal documents, and council-resolution record plus the applicable
    disposition-checklist rules for a given asset case, scoped to
    kb_path: ./kb/.

    Usage from a node::

        service = EvidenceRetrievalService()
        result = await service.retrieve(asset_id, case_type)
    """

    def __init__(self) -> None:
        self._mock_mode: bool = mock_mode_enabled()

    async def retrieve(self, asset_id: str, case_type: str) -> dict[str, Any]:
        """Retrieve raw_evidence and rule_reference for an asset disposal case.

        Returns:
            dict with keys "raw_evidence" and "rule_reference".

        Raises:
            EvidenceRetrievalAssetNotFoundError: asset_id missing/unknown, or
                case_type outside the configured scope (sale/lease_termination/transfer).
        """
        if not asset_id:
            raise EvidenceRetrievalAssetNotFoundError("EvidenceRetrievalService.retrieve: asset_id is required")
        if case_type not in _VALID_CASE_TYPES:
            raise EvidenceRetrievalAssetNotFoundError(
                f"EvidenceRetrievalService.retrieve: case_type {case_type!r} is outside configured scope"
            )
        return await self._call_external(asset_id, case_type)

    async def _call_external(self, asset_id: str, case_type: str) -> dict[str, Any]:
        if self._mock_mode:
            from src.services.mock_data import stub_retrieve_evidence

            return await stub_retrieve_evidence(asset_id, case_type)
        raise NotImplementedError(
            "EvidenceRetrievalService._call_external: not yet wired. "
            "Wire shared/services/<kb_client> and the asset-register/title/appraisal/"
            "council-resolution record store clients in the next sprint."
        )
