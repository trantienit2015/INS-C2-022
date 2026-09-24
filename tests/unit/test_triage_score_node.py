# INS-C2-022 — Unit Tests: TriageScoreNode

from framework.schemas.agent_status import AgentStatus
from src.nodes.triage_score_node import TriageScoreNode


class TestTriageScoreNode:
    def setup_method(self):
        self.node = TriageScoreNode()

    def test_success_path(self):
        state = {
            "coverage_decisions": [{"claim_id": "C1", "decision": "covered", "net_amount": 4500}],
            "fnol_batch": [{"claim_id": "C1", "coverage_line": "auto", "severity": 0.2}],
            "correlation_id": "cid-1",
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert len(result["triage_scores"]) == 1
        assert 0.0 <= result["triage_scores"][0]["score"] <= 1.0

    def test_skips_non_covered(self):
        state = {
            "coverage_decisions": [{"claim_id": "C1", "decision": "excluded"}],
            "fnol_batch": [{"claim_id": "C1", "coverage_line": "auto", "severity": 0.5}],
            "correlation_id": "cid-2",
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["triage_scores"] == []

    def test_empty_decisions(self):
        state = {"coverage_decisions": [], "fnol_batch": [], "correlation_id": "cid-3"}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["triage_scores"] == []
