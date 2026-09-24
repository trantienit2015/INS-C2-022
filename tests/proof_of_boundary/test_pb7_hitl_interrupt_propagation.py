# PB-7: HITL Interrupt Propagation (framework contract)
#
# Verifies interrupt() inside the inner subgraph's HITLGateNode raises
# GraphInterrupt, the signal propagates through BaseNode.__call__() (which
# explicitly re-raises GraphBubbleUp — see framework/nodes/base_node.py),
# is NOT caught by the application error boundary, and status is NOT set to
# "error" — it surfaces as AWAITING_HUMAN through the Cat 2 outer/inner
# GraphNode boundary (propagate_hitl=True).

import json

from langgraph.checkpoint.memory import InMemorySaver

from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from src.graph.graph import Graph

ADJUSTER_QUEUE_INPUT = json.dumps({
    "cat_event_id": "CAT-2026-07-TEST",
    "fnol_batch": [
        {
            "claim_id": "C-HIGH-1",
            "policy_number": "P1",
            "coverage_line": "commercial",
            "peril": "flood",
            "severity": 0.95,
            "estimated_amount": 500000,
            "policy": {
                "status": "active",
                "covered_lines": ["commercial"],
                "exclusions": [],
                "deductible": 1000,
            },
        }
    ],
})


class TestPB7HitlInterruptPropagation:
    """PB-7: interrupt() propagates as AWAITING_HUMAN, never as status=error."""

    def _agent(self) -> Graph:
        agent = Graph(config={
            "fast_track_threshold": 0.4,
            "memory_enabled": True,
            "hitl": {"enabled": True, "max_hitl": 8},
        })
        agent.compile(checkpointer=InMemorySaver())
        return agent

    def test_adjuster_queue_claim_surfaces_as_awaiting_human_not_error(self):
        agent = self._agent()
        ctx = InvocationContext(caller_trust_level=TrustLevel.VERIFIED_EXTERNAL)

        result = agent.invoke(ADJUSTER_QUEUE_INPUT, ctx=ctx)

        assert result["status"] == AgentStatus.AWAITING_HUMAN.value
        assert result["status"] != AgentStatus.ERROR.value
        assert result.get("thread_id")

    def test_resume_after_interrupt_completes_successfully(self):
        agent = self._agent()
        ctx = InvocationContext(caller_trust_level=TrustLevel.VERIFIED_EXTERNAL)

        suspended = agent.invoke(ADJUSTER_QUEUE_INPUT, ctx=ctx)
        resumed = agent.resume(
            thread_id=suspended["thread_id"],
            feedback={"approved_settlements": [{"claim_id": "C-HIGH-1", "net_amount": 499000}]},
        )

        assert resumed["status"] == AgentStatus.SUCCESS.value
