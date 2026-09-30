"""AgentCore Platform v1.0"""

# Inner graph for the Cat 2 disposal due-diligence evidence-review domain
# workflow. Instantiated by DisposalEvidenceWorkflowGraphNode.get_subgraph()
# in src/graph/graph.py. This is the ONLY accepted path for a Cat 2 inner
# graph (not src/subagents/).

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_status import AgentStatus

from src.nodes.evidence_check_node import EvidenceCheckNode
from src.nodes.normalize_node import NormalizeNode
from src.nodes.packet_assemble_node import PacketAssembleNode
from src.nodes.retrieve_node import RetrieveNode
from src.schemas.state import State


class DisposalEvidenceWorkflowGraph(BaseGraph):
    """Inner graph: retrieve -> normalize -> evidence_check -> packet_assemble.

    Fully custom linear topology (BaseGraph) — the four domain steps don't map
    onto the pre_process/main/post_process shape, per docs/02_design.md
    Design Decision Record.
    """

    @property
    def name(self) -> str:
        return "disposal-evidence-workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        """No mandatory config for this inner graph."""
        pass

    def register_nodes(self) -> None:
        """No super() call — BaseGraph.register_nodes() is abstract."""
        self._nodes["retrieve"] = RetrieveNode()
        self._nodes["normalize"] = NormalizeNode()
        self._nodes["evidence_check"] = EvidenceCheckNode()
        self._nodes["packet_assemble"] = PacketAssembleNode()

    def add_edges(self) -> None:
        """Linear topology: retrieve -> normalize -> evidence_check -> packet_assemble."""
        self._sg.add_edge(START, "retrieve")
        self._sg.add_edge("retrieve", "normalize")
        self._sg.add_edge("normalize", "evidence_check")
        self._sg.add_edge("evidence_check", "packet_assemble")
        self._sg.add_edge("packet_assemble", END)

    def route(self, state: State) -> str:
        """Required by BaseGraph ABC; not referenced (linear topology, no conditional edges)."""
        return END if state.get("status") == AgentStatus.ERROR.value else "packet_assemble"

    def get_output(self, state: State) -> dict[str, Any]:
        """Shape the sub_result dict consumed by the outer GraphNode.merge_output()."""
        return {
            "draft_packet": state.get("draft_packet", {}),
            "gap_findings": state.get("gap_findings", []),
            "checklist_status": state.get("checklist_status", {}),
            "status": state.get("status"),
        }
