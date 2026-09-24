# INS-C2-022 — Unit Tests: CoverageCheckNode

import json

from framework.schemas.agent_status import AgentStatus
from src.nodes.coverage_check_node import CoverageCheckNode


class TestCoverageCheckNode:
    def setup_method(self):
        self.node = CoverageCheckNode()

    def test_success_path(self):
        fnol_batch = [
            {
                "claim_id": "C1",
                "policy_number": "P1",
                "coverage_line": "auto",
                "peril": "flood",
                "estimated_amount": 5000,
                "policy": {
                    "status": "active",
                    "covered_lines": ["auto"],
                    "exclusions": [],
                    "deductible": 500,
                },
            }
        ]
        state = {"user_input": json.dumps({"fnol_batch": fnol_batch}), "correlation_id": "cid-1"}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["coverage_decisions"][0]["decision"] == "covered"
        assert result["coverage_decisions"][0]["net_amount"] == 4500

    def test_empty_inner_input_error(self):
        state = {"user_input": json.dumps({"fnol_batch": []}), "correlation_id": "cid-2"}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR

    def test_empty_inner_input_emits_trace_event(self, monkeypatch):
        # S-4: the reject early-return must also emit a domain event, not only
        # the success path (finding-recipes.md 3a "sot path").
        calls = []
        monkeypatch.setattr(
            "src.nodes.coverage_check_node.emit_trace_event",
            lambda event_type, payload, state: calls.append((event_type, payload)),
        )
        state = {"user_input": json.dumps({"fnol_batch": []}), "correlation_id": "cid-2"}
        self.node.execute(state)
        assert len(calls) == 1
        event_type, payload = calls[0]
        assert event_type == "coverage_check_rejected"
        assert payload == {"correlation_id": "cid-2", "reason": "no_fnols_in_inner_input"}

    def test_success_path_emits_trace_event(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "src.nodes.coverage_check_node.emit_trace_event",
            lambda event_type, payload, state: calls.append((event_type, payload)),
        )
        fnol_batch = [
            {
                "claim_id": "C1",
                "policy_number": "P1",
                "coverage_line": "auto",
                "peril": "flood",
                "estimated_amount": 5000,
                "policy": {
                    "status": "active",
                    "covered_lines": ["auto"],
                    "exclusions": [],
                    "deductible": 500,
                },
            }
        ]
        state = {"user_input": json.dumps({"fnol_batch": fnol_batch}), "correlation_id": "cid-1"}
        self.node.execute(state)
        assert len(calls) == 1
        event_type, payload = calls[0]
        assert event_type == "coverage_checked"
        # non-sensitive: only counts + correlation_id, no raw claim/policy content
        for key in payload:
            assert key in {"correlation_id", "covered", "excluded", "pending"}

    def test_excluded_peril(self):
        fnol_batch = [
            {
                "claim_id": "C2",
                "policy_number": "P2",
                "coverage_line": "auto",
                "peril": "war",
                "estimated_amount": 1000,
                "policy": {
                    "status": "active",
                    "covered_lines": ["auto"],
                    "exclusions": ["war"],
                    "deductible": 0,
                },
            }
        ]
        state = {"user_input": json.dumps({"fnol_batch": fnol_batch}), "correlation_id": "cid-3"}
        result = self.node.execute(state)
        assert result["coverage_decisions"][0]["decision"] == "excluded"
