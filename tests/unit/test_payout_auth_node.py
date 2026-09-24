# INS-C2-022 — Unit Tests: PayoutAuthNode

from framework.schemas.agent_status import AgentStatus
from src.nodes.payout_auth_node import PayoutAuthNode


class TestPayoutAuthNode:
    def setup_method(self):
        self.node = PayoutAuthNode()

    def test_success_path_both_tracks(self):
        state = {
            "fast_track_claims": [{"claim_id": "C1", "net_amount": 500}],
            "adjuster_approved_settlements": [{"claim_id": "C2", "net_amount": 9000}],
            "correlation_id": "cid-1",
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert len(result["payout_authorizations"]) == 2
        assert all(r["audit_ref"] for r in result["payout_authorizations"])

    def test_no_claims_no_error(self):
        result = self.node.execute({"fast_track_claims": [], "adjuster_approved_settlements": []})
        assert result["status"] == AgentStatus.SUCCESS
        assert result["payout_authorizations"] == []

    def test_extra_security_gate_output_rejects_missing_audit_ref(self):
        state = {"payout_authorizations": [{"claim_id": "C1", "net_amount": 1}]}
        result = self.node._extra_security_gate_output(state)
        assert result["status"] == AgentStatus.ERROR

    def test_extra_security_gate_output_passes_with_audit_ref(self):
        state = {"payout_authorizations": [{"claim_id": "C1", "audit_ref": "abc"}]}
        result = self.node._extra_security_gate_output(state)
        assert result is state
