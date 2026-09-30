"""AgentCore Platform v1.0"""

# Service layer: pure domain logic. No LLM call, no external network call,
# no credentials — rule-matching only.

from __future__ import annotations

from datetime import date
from typing import Any


class EvidenceCheckService:
    """Pure rule-matching: compares normalized fields against the
    disposition checklist; flags missing, stale, or conflicting evidence.

    Usage from a node::

        service = EvidenceCheckService()
        result = service.check(normalized_fields, rule_reference)
    """

    def check(self, normalized_fields: dict[str, Any], rule_reference: dict[str, Any]) -> dict[str, Any]:
        """Match normalized_fields against rule_reference.

        Returns:
            dict with keys "checklist_status" (dict[item_id, "confirmed"|"missing"|"stale"])
            and "gap_findings" (list of dicts, each citing a checklist item).
        """
        checklist_items = rule_reference.get("checklist_items", [])

        checklist_status: dict[str, str] = {}
        gap_findings: list[dict[str, Any]] = []

        for item in checklist_items:
            item_id = item.get("id", "")
            required_field = item.get("field")
            if required_field and normalized_fields.get(required_field) in (None, "", {}):
                checklist_status[item_id] = "missing"
                gap_findings.append(
                    {
                        "type": "missing_evidence",
                        "checklist_item": item_id,
                        "rule_reference": item.get("citation", item_id),
                        "detail": f"Required field '{required_field}' not present in retrieved evidence.",
                    }
                )
            else:
                checklist_status[item_id] = "confirmed"

        stale_finding = self._check_appraisal_staleness(normalized_fields, rule_reference)
        if stale_finding is not None:
            checklist_status["appraisal_current"] = "stale"
            gap_findings.append(stale_finding)

        return {"checklist_status": checklist_status, "gap_findings": gap_findings}

    def _check_appraisal_staleness(
        self, normalized_fields: dict[str, Any], rule_reference: dict[str, Any]
    ) -> dict[str, Any] | None:
        appraisal_date = normalized_fields.get("appraisal_date")
        max_age_days = rule_reference.get("appraisal_max_age_days")
        as_of_date = rule_reference.get("as_of_date")
        if not (appraisal_date and max_age_days and as_of_date):
            return None
        try:
            age_days = (date.fromisoformat(as_of_date) - date.fromisoformat(appraisal_date)).days
        except (TypeError, ValueError):
            return None
        if age_days <= max_age_days:
            return None
        return {
            "type": "stale_evidence",
            "checklist_item": "appraisal_current",
            "rule_reference": "disposition-checklist §2-1",
            "detail": f"Appraisal dated {appraisal_date} exceeds max age of {max_age_days} days as of {as_of_date}.",
        }
