"""AgentCore Platform v1.0"""

# Mock-mode stub data. Used only when mock_mode_enabled() is True (see
# src/services/mock_mode.py). Keeps deterministic fixtures out of the
# services themselves.

from __future__ import annotations

from typing import Any

# Verbatim disclaimer per engineer_proposal.md §10 (Security & compliance).
PACKET_DISCLAIMER = (
    "This packet identifies evidence gaps only. All disposal determinations, "
    "approvals, notices, and enforcement require authorized staff review and action."
)


async def stub_retrieve_evidence(asset_id: str, case_type: str) -> dict[str, Any]:
    """Deterministic fixture standing in for the asset register / title /
    appraisal / council-resolution record stores and the disposition-checklist KB."""
    return {
        "raw_evidence": {
            "asset_id": asset_id,
            "case_type": case_type,
            "asset_register": {"address": "1-2-3 Chuo, Sample City", "category": "land"},
            "title_record": {"status": "clear", "restrictions": []},
            "appraisal": {"date": "2026-05-01", "value": 12000000},
            "council_resolution": {"reference": None, "date": None},
            "valuation": {"value": 12500000, "date": "2026-05-15"},
        },
        "rule_reference": {
            "version": "2026-mock-1",
            "as_of_date": "2026-07-22",
            "appraisal_max_age_days": 365,
            "checklist_items": [
                {"id": "appraisal_current", "field": "appraisal_value", "citation": "disposition-checklist §2-1"},
                {"id": "title_clear", "field": "title_status", "citation": "disposition-checklist §2-2"},
                {
                    "id": "restriction_review",
                    "field": "restriction_flags",
                    "citation": "disposition-checklist §2-3",
                },
                {
                    "id": "council_resolution",
                    "field": "resolution_reference",
                    "citation": "disposition-checklist §3-1",
                },
                {
                    "id": "valuation_current",
                    "field": "valuation_value",
                    "citation": "disposition-checklist §2-4",
                },
            ],
        },
    }


async def stub_assemble_packet(
    normalized_fields: dict[str, Any],
    checklist_status: dict[str, Any],
    gap_findings: list[dict[str, Any]],
    rule_reference: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic fixture standing in for LLM-assisted packet synthesis."""
    confirmed_evidence = [
        {"checklist_item": item_id, "status": status, "rule_reference": item_id}
        for item_id, status in checklist_status.items()
        if status == "confirmed"
    ]
    return {
        "confirmed_evidence": confirmed_evidence,
        "gaps": [g for g in gap_findings if g.get("type") == "missing_evidence"],
        "conflicts": [g for g in gap_findings if g.get("type") != "missing_evidence"],
        "checklist_status": checklist_status,
        "rule_version": rule_reference.get("version", "unknown"),
        "disclaimer": PACKET_DISCLAIMER,
    }
