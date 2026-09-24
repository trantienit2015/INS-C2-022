# INS-C2-022 — Unit Tests: FNOLIngestNode

import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.fnol_ingest_node import FNOLIngestNode


class TestFNOLIngestNode:
    def setup_method(self):
        self.node = FNOLIngestNode()

    def _state(self, user_input: str) -> dict:
        return {
            "user_input": user_input,
            "caller_trust_level": TrustLevel.VERIFIED_EXTERNAL.value,
            "node_history": [],
            "error_log": [],
            "execution_time": {},
        }

    def test_success_path(self):
        payload = json.dumps({
            "cat_event_id": "CAT-2026-07",
            "fnol_batch": [
                {"claim_id": "C1", "policy_number": "P1", "coverage_line": "auto"},
                {"claim_id": "C2", "policy_number": "P2"},  # missing coverage_line -> rejected
            ],
        })
        result = self.node.execute(self._state(payload))
        assert result["status"] == AgentStatus.SUCCESS
        assert len(result["fnol_batch"]) == 1
        assert len(result["rejected_fnols"]) == 1
        assert json.loads(result["validated_input"])["cat_event_id"] == "CAT-2026-07"

    def test_empty_batch_error(self):
        payload = json.dumps({"cat_event_id": "CAT-2026-07", "fnol_batch": []})
        result = self.node.execute(self._state(payload))
        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]

    def test_malformed_input_error(self):
        result = self.node.execute(self._state("not json"))
        assert result["status"] == AgentStatus.ERROR

    def test_trust_gate_denies_anonymous(self):
        state = self._state(json.dumps({"cat_event_id": "x", "fnol_batch": []}))
        state["caller_trust_level"] = TrustLevel.ANONYMOUS.value
        result = self.node(state)
        assert result["status"] == AgentStatus.ERROR.value
        assert "S-1 trust gate denied" in result["error_log"][0]
