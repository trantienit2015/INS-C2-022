# INS-C2-022 — Unit Tests: RoutingNode

from framework.schemas.agent_status import AgentStatus
from src.nodes.routing_node import RoutingNode


class TestRoutingNode:
    def setup_method(self):
        self.node = RoutingNode(fast_track_threshold=0.4)

    def test_success_path_splits_by_threshold(self):
        state = {
            "triage_scores": [
                {"claim_id": "C1", "score": 0.1},
                {"claim_id": "C2", "score": 0.9},
            ],
            "correlation_id": "cid-1",
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert len(result["fast_track_claims"]) == 1
        assert len(result["adjuster_queue_claims"]) == 1
        assert result["fast_track_claims"][0]["claim_id"] == "C1"

    def test_empty_scores(self):
        result = self.node.execute({"triage_scores": [], "correlation_id": "cid-2"})
        assert result["status"] == AgentStatus.SUCCESS
        assert result["fast_track_claims"] == []
        assert result["adjuster_queue_claims"] == []

    def test_default_threshold_used_without_constructor_arg(self):
        node = RoutingNode()
        result = node.execute({"triage_scores": [{"claim_id": "C1", "score": 0.99}]})
        assert result["adjuster_queue_claims"]
