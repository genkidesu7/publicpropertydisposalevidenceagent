"""AgentCore Platform v1.0"""

# Cat 2 — AgentBaseGraph (outer) + GraphNode wrapping the inner domain
# workflow graph (src/graph/domain_workflow_graph.py). See docs/02_design.md.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState

from src.nodes.post_process_node import OutputValidateNode
from src.nodes.pre_process_node import CaseIntakeNode
from src.schemas.state import State

if TYPE_CHECKING:
    from src.graph.domain_workflow_graph import DisposalEvidenceWorkflowGraph


class DisposalEvidenceWorkflowGraphNode(GraphNode):
    """Wraps the inner disposal-evidence domain workflow; assigned to the `main` slot."""

    # propagate: re-raise inner errors as SubgraphError (fail fast) — a
    # degraded evidence packet would risk an officer acting on incomplete
    # due-diligence information (docs/02_design.md Design Decision Record).
    error_strategy: ClassVar[str] = "propagate"

    # This template does not set hitl.enabled: true — human review happens
    # after the agent returns the packet, not mid-graph.
    propagate_hitl: ClassVar[bool] = False

    def get_subgraph(self) -> "DisposalEvidenceWorkflowGraph":
        from src.graph.domain_workflow_graph import DisposalEvidenceWorkflowGraph

        return DisposalEvidenceWorkflowGraph(config=self._parent_config())

    def extract_input(self, state: AgentState) -> str:
        """Return the case-identifier JSON payload set by pre_process."""
        return cast(str, state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        """Map inner sub_result fields back into outer state — explicit mapping only."""
        return {
            "draft_packet": sub_result.get("draft_packet", {}),
            "gap_findings": sub_result.get("gap_findings", []),
            "checklist_status": sub_result.get("checklist_status", {}),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        return {}


class PublicPropertyDisposalEvidenceAgent(AgentBaseGraph):
    """Municipal public-property disposal due-diligence evidence reviewer (Cat 2).

    Backbone: initialize -> pre_process -> main -> post_process -> finalize (fixed).
    Domain logic (retrieve/normalize/evidence_check/packet_assemble) lives in
    DisposalEvidenceWorkflowGraphNode's inner graph.
    """

    @property
    def name(self) -> str:
        return "gov-c2-093"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects InitializeNode + FinalizeNode
        self._nodes["pre_process"] = CaseIntakeNode()
        self._nodes["main"] = DisposalEvidenceWorkflowGraphNode()
        self._nodes["post_process"] = OutputValidateNode()

    # add_edges() is NOT overridden — backbone wiring belongs to the framework.
