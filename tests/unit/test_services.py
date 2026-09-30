# Unit tests for src/services/*.py — Task 2-4 acceptance criteria
# (docs/implement_tasks.md).

import pytest

from src.services.evidence_check_service import EvidenceCheckService
from src.services.evidence_retrieval_service import (
    EvidenceRetrievalAssetNotFoundError,
    EvidenceRetrievalService,
)
from src.services.normalization_service import NormalizationService
from src.services.packet_service import PacketService

_RULE_REFERENCE = {
    "version": "2026-mock-1",
    "as_of_date": "2026-07-22",
    "appraisal_max_age_days": 365,
    "checklist_items": [
        {"id": "appraisal_current", "field": "appraisal_value", "citation": "disposition-checklist §2-1"},
        {"id": "council_resolution", "field": "resolution_reference", "citation": "disposition-checklist §3-1"},
    ],
}


class TestEvidenceRetrievalService:
    @pytest.mark.asyncio
    async def test_retrieve_found_asset_mock_mode(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        service = EvidenceRetrievalService()
        result = await service.retrieve("ASSET-001", "sale")
        assert "raw_evidence" in result
        assert "rule_reference" in result

    @pytest.mark.asyncio
    async def test_retrieve_missing_asset_id_raises(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        service = EvidenceRetrievalService()
        with pytest.raises(EvidenceRetrievalAssetNotFoundError):
            await service.retrieve("", "sale")

    @pytest.mark.asyncio
    async def test_retrieve_out_of_scope_case_type_raises(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        service = EvidenceRetrievalService()
        with pytest.raises(EvidenceRetrievalAssetNotFoundError):
            await service.retrieve("ASSET-001", "donation")

    @pytest.mark.asyncio
    async def test_retrieve_not_wired_without_mock(self, monkeypatch):
        """Without mock mode, the real KB client is not yet wired (NotImplementedError)."""
        monkeypatch.delenv("USE_MOCK", raising=False)
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)
        service = EvidenceRetrievalService()
        with pytest.raises(NotImplementedError):
            await service.retrieve("ASSET-001", "sale")


class TestNormalizationService:
    def test_normalize_complete_record(self):
        service = NormalizationService()
        raw_evidence = {
            "appraisal": {"date": "2026-05-01", "value": 12000000},
            "title_record": {"status": "clear", "restrictions": []},
            "council_resolution": {"reference": "council-res-2026-045", "date": "2026-02-01"},
            "valuation": {"value": 12500000, "date": "2026-05-15"},
        }
        result = service.normalize(raw_evidence)
        assert result["appraisal_value"] == 12000000
        assert result["title_status"] == "clear"
        assert result["resolution_reference"] == "council-res-2026-045"

    def test_normalize_missing_fields_surfaced_not_dropped(self):
        service = NormalizationService()
        result = service.normalize({})
        assert result["appraisal_date"] is None
        assert result["appraisal_value"] is None
        assert result["title_status"] is None
        assert result["resolution_reference"] is None
        assert result["restriction_flags"] == []

    def test_normalize_malformed_resolution_reference_surfaced(self):
        service = NormalizationService()
        result = service.normalize({"council_resolution": {"reference": None}})
        assert result["resolution_reference"] is None


class TestEvidenceCheckService:
    def test_all_evidence_present(self):
        service = EvidenceCheckService()
        normalized = {
            "appraisal_value": 1,
            "appraisal_date": "2026-06-01",
            "resolution_reference": "council-res-2026-045",
        }
        result = service.check(normalized, _RULE_REFERENCE)
        assert result["checklist_status"] == {
            "appraisal_current": "confirmed",
            "council_resolution": "confirmed",
        }
        assert result["gap_findings"] == []

    def test_missing_evidence_flagged_with_citation(self):
        service = EvidenceCheckService()
        normalized = {"appraisal_value": 1, "appraisal_date": "2026-06-01"}
        result = service.check(normalized, _RULE_REFERENCE)
        assert result["checklist_status"]["council_resolution"] == "missing"
        gap = next(g for g in result["gap_findings"] if g["checklist_item"] == "council_resolution")
        assert gap["rule_reference"] == "disposition-checklist §3-1"

    def test_stale_appraisal_flagged(self):
        service = EvidenceCheckService()
        normalized = {
            "appraisal_value": 1,
            "appraisal_date": "2020-01-01",
            "resolution_reference": "council-res-2026-045",
        }
        result = service.check(normalized, _RULE_REFERENCE)
        stale = [g for g in result["gap_findings"] if g["type"] == "stale_evidence"]
        assert len(stale) == 1
        assert result["checklist_status"]["appraisal_current"] == "stale"


class TestPacketService:
    @pytest.mark.asyncio
    async def test_assemble_mock_mode_no_credential_required(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        service = PacketService()
        checklist_status = {"appraisal_current": "confirmed", "council_resolution": "missing"}
        gap_findings = [
            {
                "type": "missing_evidence",
                "checklist_item": "council_resolution",
                "rule_reference": "disposition-checklist §3-1",
                "detail": "missing",
            }
        ]
        packet = await service.assemble({}, checklist_status, gap_findings, _RULE_REFERENCE, "")
        assert packet["disclaimer"]
        assert packet["gaps"] == gap_findings
        assert packet["conflicts"] == []
        assert packet["rule_version"] == "2026-mock-1"
        assert all(g.get("rule_reference") for g in packet["gaps"])

    @pytest.mark.asyncio
    async def test_assemble_requires_credential_outside_mock_mode(self, monkeypatch):
        monkeypatch.delenv("USE_MOCK", raising=False)
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)
        service = PacketService()
        with pytest.raises(ValueError):
            await service.assemble({}, {}, [], _RULE_REFERENCE, "")

    @pytest.mark.asyncio
    async def test_assemble_not_wired_without_mock(self, monkeypatch):
        monkeypatch.delenv("USE_MOCK", raising=False)
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)
        service = PacketService()
        with pytest.raises(NotImplementedError):
            await service.assemble({}, {}, [], _RULE_REFERENCE, "mock-credential-handle")
