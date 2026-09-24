"""AgentCore Platform v1.0"""

# Outer graph for INS-C2-022 (Cat 2: outer AgentBaseGraph + GraphNode(main) +
# inner BaseGraph subgraph). The ClaimsWorkflowGraphNode class lives in this
# same file (NOT under src/nodes/) so tests/proof_of_boundary/test_pb_invoke_
# order.py (which auto-discovers every BaseNode subclass under src/nodes/)
# does not trip on it — GraphNode intentionally does not run the standard
# S-1..S-4 node lifecycle itself; it delegates gating to the inner subgraph.

from typing import Any, ClassVar

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphBubbleUp

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.nodes.fnol_ingest_node import FNOLIngestNode
from src.nodes.report_node import ReportNode
from src.nodes.routing_node import DEFAULT_FAST_TRACK_THRESHOLD
from src.schemas.state import State


class ClaimsWorkflowGraphNode(GraphNode):
    """Wraps the inner mass-surge claims triage workflow; assigned to the
    outer `main` slot.

    The inner subgraph is compiled with its own checkpointer, so when the
    inner HITLGateNode's D6 interrupt() fires, the inner subgraph.invoke()
    call returns normally with status=AWAITING_HUMAN (LangGraph's own
    __interrupt__ mechanism, not a raised exception). GraphNode.execute()
    (inherited, not overridden here) detects that status and, because
    propagate_hitl=True, calls interrupt() itself — which the OUTER graph's
    own checkpointer-equipped Pregel loop then converts into the outer
    AWAITING_HUMAN result. error_strategy="propagate" matches the verified
    a sibling template; _handle_call_error is overridden defensively so a
    GraphBubbleUp reaching this path any other way is re-raised rather than
    wrapped into a SubgraphError.
    """

    # S-1: the outer main-slot wrapper is the first node to receive caller input,
    # so it must enforce the agent-level trust floor from config/agent.yaml
    # (VERIFIED_EXTERNAL) rather than inheriting BaseNode's permissive ANONYMOUS.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL
    error_strategy: ClassVar[str] = "propagate"
    propagate_hitl: ClassVar[bool] = True

    def __init__(self, fast_track_threshold: float = DEFAULT_FAST_TRACK_THRESHOLD):
        super().__init__()
        self._fast_track_threshold = fast_track_threshold
        # Cache the compiled subgraph (with its checkpointer) so the SAME
        # thread/checkpoint survives the invoke -> interrupt -> resume cycle.
        self._subgraph: Any = None

    def get_subgraph(self) -> Any:
        if self._subgraph is None:
            from src.graph.domain_workflow_graph import ClaimsTriageWorkflowGraph

            sg = ClaimsTriageWorkflowGraph(config=self._parent_config())
            sg.compile(checkpointer=InMemorySaver())
            self._subgraph = sg
        return self._subgraph

    def extract_input(self, state: AgentState) -> str:
        # S-4: runs inside GraphNode.execute() — audit dispatch into the inner subgraph.
        emit_trace_event(
            "claims_workflow_dispatched",
            {"correlation_id": state.get("correlation_id")},
            state,
        )
        return str(state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        # S-4: runs inside GraphNode.execute() — audit the subgraph outcome.
        # Only fires on real completion (not when the inner graph is
        # suspended awaiting adjuster review — merge_output does not run then).
        emit_trace_event(
            "claims_workflow_completed",
            {
                "correlation_id": state.get("correlation_id"),
                "payout_count": len(sub_result.get("payout_authorizations", [])),
            },
            state,
        )
        return {
            "fast_track_claims": sub_result.get("fast_track_claims", []),
            "adjuster_queue_claims": sub_result.get("adjuster_queue_claims", []),
            "adjuster_approved_settlements": sub_result.get("adjuster_approved_settlements", []),
            "payout_authorizations": sub_result.get("payout_authorizations", []),
            "notifications": sub_result.get("notifications", []),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        return {
            "fast_track_threshold": self._fast_track_threshold,
            "memory_enabled": True,
            "hitl": {"enabled": True},
        }

    def _handle_call_error(self, subgraph: Any, e: Any, state: Any) -> Any:
        # Inner interrupt() arrives here as a raised GraphBubbleUp — re-raise
        # it so it reaches the LangGraph runtime as AWAITING_HUMAN instead of
        # being wrapped into a SubgraphError -> outer `error`.
        if isinstance(e, GraphBubbleUp) or "interrupt" in type(e).__name__.lower():
            raise e
        return super()._handle_call_error(subgraph, e, state)


class ClaimsTriageOrchestrationGraph(AgentBaseGraph):
    """CAT Claims Triage & Rapid Payout Orchestration Agent (INS-C2-022)."""

    @property
    def name(self) -> str:
        return "ins-c2-022"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # fills: initialize, finalize (required)
        threshold = self.config.get("fast_track_threshold", DEFAULT_FAST_TRACK_THRESHOLD)
        self._nodes["pre_process"] = FNOLIngestNode()
        self._nodes["main"] = ClaimsWorkflowGraphNode(fast_track_threshold=threshold)
        self._nodes["post_process"] = ReportNode()

    # add_edges() is NOT overridden — backbone wiring belongs to the framework.


Graph = ClaimsTriageOrchestrationGraph  # alias for agent.yaml module:"src.graph"
