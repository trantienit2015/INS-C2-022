# INS-C2-022 — Unit Tests: NotifyNode

from framework.schemas.agent_status import AgentStatus
from src.nodes.notify_node import NotifyNode


class TestNotifyNode:
    def setup_method(self):
        self.node = NotifyNode()

    def test_success_path(self):
        state = {
            "payout_authorizations": [{"claim_id": "C1", "audit_ref": "a"}],
            "correlation_id": "cid-1",
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert len(result["notifications"]) == 1
        assert result["notifications"][0]["claim_id"] == "C1"

    def test_no_payouts_no_notifications(self):
        result = self.node.execute({"payout_authorizations": []})
        assert result["status"] == AgentStatus.SUCCESS
        assert result["notifications"] == []
