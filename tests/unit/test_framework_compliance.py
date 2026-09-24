# INS-C2-022 - Framework compliance tests TC-01..TC-08 (code review round 1).
# Reference shape: the standard framework-compliance test module,
# adapted to this template's real architecture (Cat 2: outer FNOLIngestNode pre_process +
# GraphNode-wrapped inner coverage_check/triage_score/routing/hitl_gate/payout_auth/notify
# + ReportNode post_process).

import json
import os
import re

import pytest
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.nodes import (
    coverage_check_node,
    fnol_ingest_node,
    hitl_gate_node,
    notify_node,
    payout_auth_node,
    report_node,
    routing_node,
    triage_score_node,
)
from src.schemas.state import State

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
TRUST = TrustLevel.VERIFIED_EXTERNAL.value

FAST_TRACK_INPUT = json.dumps({
    "cat_event_id": "CAT-TC",
    "fnol_batch": [{
        "claim_id": "C1", "policy_number": "P1", "coverage_line": "auto",
        "peril": "flood", "severity": 0.1, "estimated_amount": 1000,
        "policy": {"status": "active", "covered_lines": ["auto"], "exclusions": [], "deductible": 100},
    }],
})


def _src_files():
    for root, _d, files in os.walk(_SRC):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


# TC-01 - State is a flat TypedDict extending AgentState; added fields are
# JSON-serializable primitives (NotRequired-wrapped).
class TestTC01StateContract:
    def test_state_is_typeddict_extending_agent_state(self):
        assert hasattr(State, "__annotations__")
        assert "user_input" in State.__annotations__
        assert set(AgentState.__annotations__).issubset(set(State.__annotations__))

    def test_added_fields_are_json_safe(self):
        added = [k for k in State.__annotations__ if k not in AgentState.__annotations__]
        assert added, "State must declare agent-specific fields"
        for name in added:
            ann_str = str(State.__annotations__[name])
            assert any(t in ann_str for t in ("str", "int", "bool", "float", "list", "dict")), (
                f"{name}: {ann_str} - fields must be JSON-serializable primitives/containers"
            )


# TC-02 - Empty/missing/invalid input yields a fail-closed ERROR outcome, no raise.
class TestTC02Validation:
    def test_empty_input_no_raise(self):
        out = fnol_ingest_node.FNOLIngestNode().execute({"user_input": ""})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]

    def test_malformed_json_no_raise(self):
        out = fnol_ingest_node.FNOLIngestNode().execute({"user_input": "not json"})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]


# TC-03 - No JWT / API keys / secrets in src/; no direct os.environ reads
# (entry-point auth boundary at src/api/ is the documented exception).
class TestTC03NoCredentials:
    def test_no_credential_literals(self):
        pat = re.compile(r"(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")
        offenders = [fp for fp in _src_files() if pat.search(open(fp, encoding="utf-8").read())]
        assert offenders == []

    def test_no_os_environ_secret_reads(self):
        # Entry-point exception (framework contract):
        # src/api/server.py reads INVOKE_AUTH_TOKEN to authenticate the caller
        # BEFORE any InvocationContext exists, so ctx.secrets cannot apply. It is a
        # deployment-level caller credential, not an agent secret, and never enters state.
        offenders = []
        for fp in _src_files():
            if os.path.normpath(fp).endswith(os.path.join("src", "api", "server.py")):
                continue
            if "api" in fp.replace("\\", "/").split("/"):
                continue  # entry-point auth boundary exception (framework contract)
            if "os.environ" in open(fp, encoding="utf-8").read():
                offenders.append(fp)
        assert offenders == []


# TC-04 - InvocationContext is never stored in State after invoke.
class TestTC04ContextIsolation:
    def test_no_invocationcontext_in_state_after_invoke(self):
        from src.graph.graph import Graph

        agent = Graph()
        agent.compile()
        ctx = InvocationContext(session_id="tc04", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="tester-tc04")
        result = agent.invoke(FAST_TRACK_INPUT, ctx=ctx)
        for v in result.values():
            assert not isinstance(v, InvocationContext)

    def test_from_state_available(self):
        assert hasattr(InvocationContext, "from_state")


# TC-05 - Domain events: outer/inner nodes emit >=1 domain event; no node under
# src/nodes/ ever re-emits a framework backbone lifecycle event.
class TestTC05Audit:
    def test_fnol_ingest_emits_domain_event(self, monkeypatch):
        events = []
        monkeypatch.setattr(fnol_ingest_node, "emit_trace_event", lambda e, p, s: events.append(e))
        out = fnol_ingest_node.FNOLIngestNode().execute({
            "user_input": json.dumps({"cat_event_id": "x", "fnol_batch": [
                {"claim_id": "C1", "policy_number": "P1", "coverage_line": "auto"}
            ]})
        })
        assert out["status"] == AgentStatus.SUCCESS
        assert "fnol_batch_validated" in events
        assert not ({"node_start", "node_complete", "node_error", "node_skip"} & set(events))

    def test_source_has_no_backbone_events(self):
        pat = re.compile(r'emit_trace_event\(\s*["\'](node_start|node_complete|node_error|node_skip)["\']')
        offenders = [fp for fp in _src_files() if pat.search(open(fp, encoding="utf-8").read())]
        assert offenders == []


# TC-06 / TC-07 - S-2/S-3 gates are @final on FunctionNode (overriding raises TypeError at class def).
class TestTC0607FinalGates:
    def test_input_gate_is_final(self):
        with pytest.raises(TypeError):

            class BadIn(FunctionNode):  # noqa: N801
                def _security_gate_input(self, state):
                    return state

    def test_output_gate_is_final(self):
        with pytest.raises(TypeError):

            class BadOut(FunctionNode):  # noqa: N801
                def _security_gate_output(self, result):
                    return result

    def test_extra_hook_is_overridable(self):
        assert (
            payout_auth_node.PayoutAuthNode._extra_security_gate_output
            is not FunctionNode._extra_security_gate_output
        )

    def test_output_gate_blocks_missing_audit_ref(self):
        # The @final S-3 hook actually fires (not vacuous): a payout record
        # missing its audit_ref is blocked by the domain-specific hook.
        node = payout_auth_node.PayoutAuthNode()
        out = node._extra_security_gate_output({"payout_authorizations": [{"claim_id": "C1"}]})
        assert out["status"] == AgentStatus.ERROR


# TC-08 - required_trust_level declared valid + enforced: insufficient trust -> ERROR, no raise.
class TestTC08TrustGate:
    def test_declared_trust_levels_valid(self):
        for cls in (
            fnol_ingest_node.FNOLIngestNode,
            coverage_check_node.CoverageCheckNode,
            triage_score_node.TriageScoreNode,
            routing_node.RoutingNode,
            hitl_gate_node.HITLGateNode,
            payout_auth_node.PayoutAuthNode,
            notify_node.NotifyNode,
            report_node.ReportNode,
        ):
            assert cls.required_trust_level in (TrustLevel.ANONYMOUS, TrustLevel.VERIFIED_EXTERNAL, TrustLevel.INTERNAL)

    def test_insufficient_trust_returns_error(self):
        node = fnol_ingest_node.FNOLIngestNode()
        out = node({"caller_trust_level": TrustLevel.ANONYMOUS.value, "user_input": FAST_TRACK_INPUT})
        assert str(out.get("status")).lower().endswith("error")

    def test_sufficient_trust_succeeds(self):
        node = fnol_ingest_node.FNOLIngestNode()
        out = node({"caller_trust_level": TRUST, "user_input": FAST_TRACK_INPUT})
        assert out["status"] == AgentStatus.SUCCESS
