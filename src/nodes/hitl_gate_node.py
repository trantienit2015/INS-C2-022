"""AgentCore Platform v1.0"""

# Inner subgraph node — D6 HITL gate for the adjuster queue (design
# decision: HITLGateNode is an independent node, not inline logic folded into
# RoutingNode/PayoutAuthNode). The framework owns pause/resume; this node
# only owns the trigger condition (a non-empty adjuster queue). Requires
# hitl.enabled:true + memory_enabled:true on BOTH the inner subgraph config
# and the outer agent config (config/agent.yaml) — see src/graph/graph.py.
#
# FunctionNode (verified pattern — a sibling template's HITL gate node): the S-2/S-3
# @final gates on FunctionNode apply normally; this node does not need to
# bypass them since it does not introduce a new external input/output
# surface beyond the domain fields already covered by those gates.

from typing import Any, ClassVar

from langgraph.types import interrupt

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class HITLGateNode(FunctionNode):
    """Adjuster reviews/approves/modifies claims routed to the adjuster queue.

    Never auto-approves: an empty adjuster queue skips the interrupt entirely;
    a non-empty queue always suspends for a human decision. SLA timeout
    escalation to the claims manager is an ops-layer concern (queue/alerting
    outside this graph), documented in docs/02_design.md — this node's
    responsibility ends at pausing for review.
    """

    # S-1: inner subgraph node — trust authenticated once at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        adjuster_queue = state.get("adjuster_queue_claims", [])

        if not adjuster_queue:
            emit_trace_event(
                "adjuster_review_skipped",
                {"correlation_id": state.get("correlation_id")},
                state,
            )
            return {"adjuster_approved_settlements": [], "status": AgentStatus.SUCCESS.value}

        # hitl_draft prevents re-computation on resume (framework contract).
        feedback = interrupt(
            {
                "draft": adjuster_queue,
                "reason": "adjuster review required for complex/large-value claims",
            }
        )

        approved = feedback.get("approved_settlements", []) if isinstance(feedback, dict) else []

        emit_trace_event(
            "adjuster_review_completed",
            {"correlation_id": state.get("correlation_id"), "approved_count": len(approved)},
            state,
        )

        return {
            "hitl_draft": adjuster_queue,
            "hitl_feedback": feedback,
            "adjuster_approved_settlements": approved,
            "status": AgentStatus.SUCCESS.value,
        }
