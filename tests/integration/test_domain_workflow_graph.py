# Integration test: inner domain workflow graph .compile() + .invoke()
# end-to-end (mock mode). See tests/integration/test_graph.py for the outer
# graph equivalent — both are required because the outer/inner boundary
# (validated_input vs user_input forwarding) can only be verified by
# actually compiling and invoking, not by calling execute()/route() directly.

import json

import pytest

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.context import bound_secrets
from shared.secrets.inmemory_provider import InMemoryProvider

from src.graph.domain_workflow_graph import DisposalEvidenceWorkflowGraph


@pytest.fixture
def inner_graph(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "true")
    graph = DisposalEvidenceWorkflowGraph()
    graph.compile()
    graph.provision_secrets(InMemoryProvider({"ANTHROPIC_API_KEY": "test-value"}))
    return graph


def test_inner_graph_runs_full_topology(inner_graph):
    ctx = InvocationContext(session_id="s1", correlation_id="c1", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL)
    payload = json.dumps({"asset_id": "ASSET-001", "case_type": "sale"})
    with bound_secrets(InMemoryProvider({"ANTHROPIC_API_KEY": "test-value"})):
        result = inner_graph.invoke(payload, ctx=ctx)
    assert result["status"] == "success"
    assert result["draft_packet"]["checklist_status"]["appraisal_current"] == "confirmed"
    assert result["draft_packet"]["checklist_status"]["council_resolution"] == "missing"
