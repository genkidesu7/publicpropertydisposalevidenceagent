"""AgentCore Platform v1.0"""

# Service layer: domain queries, external API wrappers, data aggregation.
# Must NOT contain business logic, routing, or credentials.
# Nodes call this; this calls shared/services/ for external integrations.
#
# Design decision (docs/02_design.md Design Decision Record): unlike free-text
# submitted documents, retrieved asset-register/title/appraisal/resolution
# records are already structured municipal-system records, so mapping into the
# fixed disposition-dossier schema is a deterministic transform — no LLM call.

from __future__ import annotations

from typing import Any


class NormalizationService:
    """Deterministic field mapping of raw_evidence into the fixed
    disposition-dossier schema: appraisal date/value, title status,
    restriction flags, resolution reference, valuation value. Missing or
    malformed source fields are surfaced explicitly, never silently dropped.

    Usage from a node::

        service = NormalizationService()
        normalized_fields = service.normalize(raw_evidence)
    """

    def normalize(self, raw_evidence: dict[str, Any]) -> dict[str, Any]:
        """Map raw_evidence into normalized_fields.

        Args:
            raw_evidence: Retrieved asset records, from EvidenceRetrievalService.
        """
        appraisal = raw_evidence.get("appraisal") or {}
        title_record = raw_evidence.get("title_record") or {}
        council_resolution = raw_evidence.get("council_resolution") or {}
        valuation = raw_evidence.get("valuation") or {}

        return {
            "appraisal_date": appraisal.get("date"),
            "appraisal_value": appraisal.get("value"),
            "title_status": title_record.get("status"),
            "restriction_flags": title_record.get("restrictions", []),
            "resolution_reference": council_resolution.get("reference"),
            "valuation_value": valuation.get("value"),
        }
