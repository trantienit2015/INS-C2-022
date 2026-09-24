# INS-C2-022 — Unit Tests: HITLGateNode

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
import src.nodes.hitl_gate_node as hitl_gate_node
from src.nodes.hitl_gate_node import HITLGateNode


class TestHITLGateNode:
    def setup_method(self):
        self.node = HITLGateNode()

    def test_empty_queue_skips_interrupt(self):
        """No adjuster-queue claims -> success without ever calling interrupt()."""
        state = {"adjuster_queue_claims": [], "correlation_id": "cid-1"}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["adjuster_approved_settlements"] == []

    def test_non_empty_queue_calls_interrupt_and_uses_feedback(self, monkeypatch):
        """Simulate resume: interrupt() returns the human's approved settlements."""
        approved = [{"claim_id": "C1", "net_amount": 9000}]
        monkeypatch.setattr(
            hitl_gate_node, "interrupt", lambda payload: {"approved_settlements": approved}
        )
        state = {
            "adjuster_queue_claims": [{"claim_id": "C1", "score": 0.9}],
            "correlation_id": "cid-2",
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["adjuster_approved_settlements"] == approved
        assert result["hitl_draft"] == state["adjuster_queue_claims"]

    def test_trust_level_declared(self):
        assert HITLGateNode.required_trust_level == TrustLevel.ANONYMOUS
