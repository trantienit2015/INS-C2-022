"""AgentCore Platform v1.0"""

from typing import Any, ClassVar
from uuid import uuid4

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class PayoutAuthNode(FunctionNode):
    """Inner subgraph step 5: generate payout authorization records.

    Convergence point for both routing tracks — fast-track claims (never saw
    the HITL gate) and adjuster-approved settlements (survived HITL review).
    Emits a mandatory S-4 audit event for EVERY payout, per the flagship
    money-moving control (pattern ref).
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        # Preservation-variant check: every payout authorization record must
        # keep its audit reference — a payout without one would be a
        # FSA-scrutinized control gap, not just a formatting issue.
        for record in state.get("payout_authorizations", []):
            if not record.get("audit_ref"):
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": ["PayoutAuthNode: payout record missing audit_ref"],
                }
        return state

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        fast_track = state.get("fast_track_claims", [])
        approved = state.get("adjuster_approved_settlements", [])

        authorizations = []
        if not fast_track and not approved:
            emit_trace_event(
                "payout_authorization_skipped",
                {"correlation_id": state.get("correlation_id"), "reason": "no claims to authorize"},
                state,
            )
        for item in fast_track + approved:
            audit_ref = str(uuid4())
            authorizations.append(
                {
                    "claim_id": item.get("claim_id"),
                    "net_amount": item.get("net_amount", 0),
                    "track": "fast_track" if item in fast_track else "adjuster_approved",
                    "audit_ref": audit_ref,
                }
            )
            # Mandatory per-payout audit event — flagship money-moving control.
            emit_trace_event(
                "payout_authorized",
                {
                    "correlation_id": state.get("correlation_id"),
                    "claim_id": item.get("claim_id"),
                    "audit_ref": audit_ref,
                },
                state,
            )

        return {"payout_authorizations": authorizations, "status": AgentStatus.SUCCESS.value}
