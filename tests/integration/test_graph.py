# Integration test: outer graph .compile() + .invoke() end-to-end (mock mode).
#
# A unit test that calls execute()/route() directly with a stubbed dict
# bypasses LangGraph's schema projection entirely and can pass while the
# compiled graph is actually broken — see sdk-expertise's "Running and
# smoke-testing locally" section. This test drives the real compiled graph.

import json

import pytest

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.context import bound_secrets
from shared.secrets.inmemory_provider import InMemoryProvider

from src.graph.graph import PublicPropertyDisposalEvidenceAgent


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "true")
    agent = PublicPropertyDisposalEvidenceAgent()
    agent.compile()
    agent.provision_secrets(InMemoryProvider({"ANTHROPIC_API_KEY": "test-value"}))
    return agent


def _invoke(agent, payload: dict):
    ctx = InvocationContext(
        session_id="s1",
        correlation_id="c1",
        caller_trust_level=TrustLevel.VERIFIED_EXTERNAL,
    )
    with bound_secrets(InMemoryProvider({"ANTHROPIC_API_KEY": "test-value"})):
        return agent.invoke(json.dumps(payload), ctx=ctx)


class TestOuterGraphInvoke:
    def test_valid_case_returns_success_packet(self, agent):
        result = _invoke(agent, {"asset_id": "ASSET-001", "case_type": "sale"})
        assert result["status"] == "success"
        assert "gaps" in result["output"]
        assert "disclaimer" in result["output"]
        assert result["node_history"] == [
            "InitializeNode",
            "CaseIntakeNode",
            "DisposalEvidenceWorkflowGraphNode",
            "OutputValidateNode",
            "FinalizeNode",
        ]

    def test_missing_asset_id_routes_to_finalize_with_error(self, agent):
        result = _invoke(agent, {"case_type": "sale"})
        assert result["status"] == "error"

    def test_out_of_scope_case_type_routes_to_finalize_with_error(self, agent):
        result = _invoke(agent, {"asset_id": "ASSET-001", "case_type": "donation"})
        assert result["status"] == "error"

    def test_flags_missing_council_resolution(self, agent):
        """Matches engineer_proposal.md §4 example output — mock fixture has no resolution."""
        result = _invoke(agent, {"asset_id": "ASSET-001", "case_type": "sale"})
        gap_items = [g["checklist_item"] for g in result["output"]["gaps"]]
        assert "council_resolution" in gap_items
