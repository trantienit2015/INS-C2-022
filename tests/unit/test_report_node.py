# INS-C2-022 — Unit Tests: ReportNode

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.report_node import ReportNode


class TestReportNode:
    def setup_method(self):
        self.node = ReportNode()

    def _state(self, **overrides) -> dict:
        state = {
            "fnol_batch": [{"claim_id": "C1"}, {"claim_id": "C2"}],
            "rejected_fnols": [{"fnol": {}, "reason": "bad"}],
            "fast_track_claims": [{"claim_id": "C1"}],
            "adjuster_queue_claims": [{"claim_id": "C2"}],
            "payout_authorizations": [{"claim_id": "C1", "audit_ref": "a"}],
            "notifications": [{"claim_id": "C1"}],
            "cat_event_id": "CAT-2026-07",
            "caller_trust_level": TrustLevel.VERIFIED_EXTERNAL.value,
        }
        state.update(overrides)
        return state

    def test_success_path(self):
        result = self.node.execute(self._state())
        assert result["status"] == AgentStatus.SUCCESS
        report = result["triage_report"]
        assert report["total_ingested"] == 3
        assert report["rejected_count"] == 1
        assert report["fast_track_count"] == 1
        assert report["adjuster_queue_count"] == 1
        assert report["payout_authorized_count"] == 1
        assert result["formatted_output"] == report

    def test_empty_pipeline_still_succeeds(self):
        result = self.node.execute(self._state(
            fnol_batch=[], rejected_fnols=[], fast_track_claims=[],
            adjuster_queue_claims=[], payout_authorizations=[], notifications=[],
        ))
        assert result["status"] == AgentStatus.SUCCESS
        assert result["triage_report"]["total_ingested"] == 0

    def test_trust_gate_denies_anonymous(self):
        state = self._state()
        state["caller_trust_level"] = TrustLevel.ANONYMOUS.value
        result = self.node(state)
        assert result["status"] == AgentStatus.ERROR.value
