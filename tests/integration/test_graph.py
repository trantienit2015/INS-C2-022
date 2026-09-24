# INS-C2-022 — Integration Tests: full outer graph compile + invoke
#
# Covers the Cat 2 outer/inner composition end-to-end:
#   fast-track claim   -> single invoke() -> payout authorized, no adjuster review
#   adjuster-queue claim -> invoke() suspends (AWAITING_HUMAN) -> resume() completes

import json

from langgraph.checkpoint.memory import InMemorySaver

from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from src.graph.graph import Graph

FAST_TRACK_INPUT = json.dumps({
    "cat_event_id": "CAT-2026-07",
    "fnol_batch": [
        {
            "claim_id": "C-LOW-1",
            "policy_number": "P1",
            "coverage_line": "auto",
            "peril": "flood",
            "severity": 0.1,
            "estimated_amount": 1000,
            "policy": {
                "status": "active",
                "covered_lines": ["auto"],
                "exclusions": [],
                "deductible": 100,
            },
        }
    ],
})

ADJUSTER_QUEUE_INPUT = json.dumps({
    "cat_event_id": "CAT-2026-07",
    "fnol_batch": [
        {
            "claim_id": "C-HIGH-1",
            "policy_number": "P2",
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


def _ctx() -> InvocationContext:
    return InvocationContext(caller_trust_level=TrustLevel.VERIFIED_EXTERNAL)


class TestClaimsTriageOrchestrationGraph:
    def setup_method(self):
        self.agent = Graph(config={
            "fast_track_threshold": 0.4,
            "memory_enabled": True,
            "hitl": {"enabled": True, "max_hitl": 8},
        })
        self.agent.compile(checkpointer=InMemorySaver())

    def test_fast_track_claim_authorizes_payout_without_hitl(self):
        result = self.agent.invoke(FAST_TRACK_INPUT, ctx=_ctx())
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["node_history"]

    def test_adjuster_queue_claim_suspends_then_resumes(self):
        suspended = self.agent.invoke(ADJUSTER_QUEUE_INPUT, ctx=_ctx())
        assert suspended["status"] == AgentStatus.AWAITING_HUMAN.value
        assert suspended.get("thread_id")

        resumed = self.agent.resume(
            thread_id=suspended["thread_id"],
            feedback={"approved_settlements": [{"claim_id": "C-HIGH-1", "net_amount": 499000}]},
        )
        assert resumed["status"] == AgentStatus.SUCCESS.value

    def test_empty_batch_returns_error(self):
        empty_input = json.dumps({"cat_event_id": "CAT-2026-07", "fnol_batch": []})
        result = self.agent.invoke(empty_input, ctx=_ctx())
        assert result["status"] == AgentStatus.ERROR.value
