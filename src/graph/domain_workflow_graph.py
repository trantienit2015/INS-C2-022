"""AgentCore Platform v1.0"""

# Inner graph for the Cat 2 mass-surge claims triage workflow. Instantiated
# by ClaimsWorkflowGraphNode.get_subgraph() in graph.py — receives only the
# JSON-string user_input the outer FNOLIngestNode serialized, not the outer
# state directly (Cat 2 GraphNode boundary).

from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from src.nodes.coverage_check_node import CoverageCheckNode
from src.nodes.triage_score_node import TriageScoreNode
from src.nodes.routing_node import RoutingNode, DEFAULT_FAST_TRACK_THRESHOLD
from src.nodes.hitl_gate_node import HITLGateNode
from src.nodes.payout_auth_node import PayoutAuthNode
from src.nodes.notify_node import NotifyNode
from src.schemas.state import State
from typing import Any


class ClaimsTriageWorkflowGraph(BaseGraph):
    """Inner graph: coverage check -> triage score -> routing -> HITL gate
    (skips itself when the adjuster queue is empty) -> payout auth (both
    tracks converge here) -> notify.
    """

    @property
    def name(self) -> str:
        return "cat_claims_triage_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        pass

    def register_nodes(self) -> None:
        threshold = (
            self.config.get("fast_track_threshold", DEFAULT_FAST_TRACK_THRESHOLD)
            if hasattr(self, "config")
            else DEFAULT_FAST_TRACK_THRESHOLD
        )
        self._nodes["coverage_check"] = CoverageCheckNode()
        self._nodes["triage_score"] = TriageScoreNode()
        self._nodes["routing"] = RoutingNode(fast_track_threshold=threshold)
        self._nodes["hitl_gate"] = HITLGateNode()
        self._nodes["payout_auth"] = PayoutAuthNode()
        self._nodes["notify"] = NotifyNode()

    def add_edges(self) -> None:
        self._sg.add_edge(START, "coverage_check")
        # Conditional: an empty/malformed inbound batch (CoverageCheckNode
        # ERROR) must short-circuit to END — the remaining steps are pure
        # logic on already-validated lists and would otherwise silently
        # overwrite the ERROR status with SUCCESS on empty input.
        self._sg.add_conditional_edges("coverage_check", self.route)
        self._sg.add_edge("triage_score", "routing")
        self._sg.add_edge("routing", "hitl_gate")
        self._sg.add_edge("hitl_gate", "payout_auth")
        self._sg.add_edge("payout_auth", "notify")
        self._sg.add_edge("notify", END)

    def route(self, state: AgentState) -> str:
        return END if state.get("status") == AgentStatus.ERROR.value else "triage_score"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        return {
            "fast_track_claims": state.get("fast_track_claims", []),
            "adjuster_queue_claims": state.get("adjuster_queue_claims", []),
            "adjuster_approved_settlements": state.get("adjuster_approved_settlements", []),
            "payout_authorizations": state.get("payout_authorizations", []),
            "notifications": state.get("notifications", []),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
