# PB-6: Invoke Execution Order Verification
# Verifies BaseNode.__call__() enforces: S-1 trust gate -> S-4 node_start ->
# S-2 _security_gate_input() -> execute() -> S-3 _security_gate_output() ->
# S-4 node_complete, for every concrete node under src/nodes/.

import importlib
import inspect
import json
import pkgutil

import pytest

# Each node has different execute()-level requirements (valid case JSON,
# raw_evidence present, etc.) — a single generic state dict would make some
# nodes raise inside execute() before reaching the S-3 gate, which would be
# a false PB-6 failure (wrong domain input), not an invoke-order violation.
_VALID_CASE_PAYLOAD = json.dumps({"asset_id": "ASSET-001", "case_type": "sale"})

_NODE_STATE_OVERRIDES: dict[str, dict] = {
    "CaseIntakeNode": {"user_input": _VALID_CASE_PAYLOAD},
    "RetrieveNode": {"validated_input": _VALID_CASE_PAYLOAD},
    "NormalizeNode": {"raw_evidence": {"appraisal": {"date": "2026-05-01", "value": 1}}},
    "EvidenceCheckNode": {"normalized_fields": {"appraisal_value": 1}, "rule_reference": {}},
    "PacketAssembleNode": {
        "normalized_fields": {},
        "checklist_status": {"appraisal_current": "confirmed"},
        "gap_findings": [],
        "rule_reference": {"version": "test"},
    },
    "OutputValidateNode": {
        "draft_packet": {
            "confirmed_evidence": [],
            "gaps": [],
            "conflicts": [],
            "checklist_status": {},
            "rule_version": "test",
            "disclaimer": "test",
        }
    },
}


def _discover_node_classes() -> list[type]:
    """Import every module under src/nodes/ and collect concrete BaseNode subclasses."""
    from framework.nodes.base_node import BaseNode

    try:
        pkg = importlib.import_module("src.nodes")
    except ImportError:
        return []

    discovered = []
    for _, modname, _ in pkgutil.walk_packages(pkg.__path__, prefix="src.nodes."):
        module = importlib.import_module(modname)
        for attr in vars(module).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseNode)
                and attr is not BaseNode
                and attr.__module__ == modname
                and not inspect.isabstract(attr)
            ):
                discovered.append(attr)
    return discovered


class TestInvokeOrder:
    """PB-6: __call__ must run S-1 -> node_start -> S-2 -> execute() -> S-3 -> node_complete."""

    def test_call_order_for_every_node(self, monkeypatch):
        # Retrieve/Normalize/PacketAssemble call services gated by
        # mock_mode_enabled() — force mock mode so execute() completes
        # without a real KB/LLM call and without requiring a bound secret
        # provider.
        monkeypatch.setenv("USE_MOCK", "true")

        node_classes = _discover_node_classes()
        if not node_classes:
            pytest.skip("no concrete BaseNode subclasses found under src/nodes/")

        import framework.nodes.base_node as base_node_module

        failures: list[str] = []
        for node_cls in node_classes:
            order: list[str] = []
            monkeypatch.setattr(
                base_node_module,
                "emit_trace_event",
                lambda event_type, _payload, _state, _o=order: _o.append(f"event:{event_type}"),
            )

            for method_name, label in (
                ("_security_gate_input", "security_gate_input"),
                ("execute", "execute"),
                ("_security_gate_output", "security_gate_output"),
            ):
                original = getattr(node_cls, method_name)

                def spy(self, arg, _o=order, _label=label, _orig=original):
                    _o.append(_label)
                    return _orig(self, arg)

                monkeypatch.setattr(node_cls, method_name, spy)

            instance = node_cls()
            state = {
                "caller_trust_level": node_cls.required_trust_level.value,
                "correlation_id": "pb6-invoke-order-test",
                "session_id": "pb6-session",
                "thread_id": "pb6-thread",
                "trace_id": "pb6-trace",
            }
            state.update(_NODE_STATE_OVERRIDES.get(node_cls.__name__, {}))
            instance(state)

            expected = [
                "event:node_start",
                "security_gate_input",
                "execute",
                "security_gate_output",
                "event:node_complete",
            ]
            if order != expected:
                failures.append(
                    f"{node_cls.__name__}: invoke order violation.\n" f"expected: {expected}\nactual:   {order}"
                )

        assert not failures, "\n\n".join(failures)
