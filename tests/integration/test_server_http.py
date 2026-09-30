# HTTP-level integration test for src/api/server.py's /invoke route.
#
# Regression test per .claude/rules/test_rule.md Rule 3 /
# .claude/rules/implementation_rule.md Rule 3: agent.invoke() is sync and its
# nodes call asyncio.run() internally (RetrieveNode, PacketAssembleNode).
# Calling it directly from an async route (without asyncio.to_thread) raises
# "asyncio.run() cannot be called from a running event loop" inside the
# node, which the node's except-Exception silently turns into
# status: "error" — a 200 response with no visible crash. An in-process
# sync call to agent.invoke() (see tests/integration/test_graph.py) never
# enters an event loop and cannot reproduce this. Only a test that drives
# the ASGI app itself, on a real running event loop, exercises this path.

import json

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_invoke_endpoint_succeeds_over_http(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "true")
    # Every node in this template requires VERIFIED_EXTERNAL (S-1) — the
    # standalone server has no upstream auth middleware, so the caller must
    # authenticate via the entry-point bearer-token boundary to reach that
    # trust level (see src/api/server.py's documented entry-point exception).
    monkeypatch.setenv("INVOKE_AUTH_TOKEN", "test-token")

    from src.api.server import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/invoke",
            json={"input": json.dumps({"asset_id": "ASSET-001", "case_type": "sale"})},
            headers={"Authorization": "Bearer test-token"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert "disclaimer" in body["output"]


@pytest.mark.asyncio
async def test_health_endpoint(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "true")
    from src.api.server import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "agent": "gov-c2-093"}


@pytest.mark.asyncio
async def test_invoke_rejects_wrong_bearer_token_when_auth_configured(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "true")
    monkeypatch.setenv("INVOKE_AUTH_TOKEN", "expected-token")

    from src.api.server import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/invoke",
            json={"input": json.dumps({"asset_id": "ASSET-001", "case_type": "sale"})},
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert resp.status_code == 401
