"""AgentCore Platform v1.0"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class NotifyNode(FunctionNode):
    """Inner subgraph step 6 (last): send payout/status notifications to
    policyholders (pattern ref)."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        payouts = state.get("payout_authorizations", [])

        notifications = [
            {
                "claim_id": p["claim_id"],
                "channel": "policyholder_notification",
                "notification_type": "payout_authorized",
            }
            for p in payouts
        ]

        emit_trace_event(
            "policyholder_notifications_dispatched",
            {"correlation_id": state.get("correlation_id"), "notification_count": len(notifications)},
            state,
        )

        return {"notifications": notifications, "status": AgentStatus.SUCCESS.value}
