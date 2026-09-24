"""AgentCore Platform v1.0"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class ReportNode(FunctionNode):
    """Outer post_process: assemble the operations triage report.

    Reads the fields merged back from the inner subgraph (fast-track /
    adjuster-queue split, payout authorizations, notifications) and shapes
    the final ``formatted_output`` returned to the caller.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        fast_track = state.get("fast_track_claims", [])
        adjuster_queue = state.get("adjuster_queue_claims", [])
        payouts = state.get("payout_authorizations", [])
        notifications = state.get("notifications", [])
        rejected = state.get("rejected_fnols", [])

        report = {
            "cat_event_id": state.get("cat_event_id", ""),
            "total_ingested": len(state.get("fnol_batch", [])) + len(rejected),
            "rejected_count": len(rejected),
            "fast_track_count": len(fast_track),
            "adjuster_queue_count": len(adjuster_queue),
            "payout_authorized_count": len(payouts),
            "notifications_sent_count": len(notifications),
        }

        emit_trace_event(
            "triage_report_generated",
            {"correlation_id": state.get("correlation_id"), **report},
            state,
        )

        return {
            "triage_report": report,
            "formatted_output": report,
            "status": AgentStatus.SUCCESS.value,
        }
