"""AgentCore Platform v1.0"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.claims_triage_scorer import is_fast_track

DEFAULT_FAST_TRACK_THRESHOLD = 0.4


class RoutingNode(FunctionNode):
    """Inner subgraph step 3: route below-threshold claims to fast-track
    payout; complex/large-value claims to the adjuster queue.

    The fast-track threshold is configurable (``config/agent.yaml`` ->
    forwarded via ``GraphNode._parent_config()``), never hard-coded.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, fast_track_threshold: float = DEFAULT_FAST_TRACK_THRESHOLD):
        self._fast_track_threshold = fast_track_threshold

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        scores = state.get("triage_scores", [])

        fast_track, adjuster_queue = [], []
        for item in scores:
            if is_fast_track(item["score"], self._fast_track_threshold):
                fast_track.append(item)
            else:
                adjuster_queue.append(item)

        emit_trace_event(
            "claims_routed",
            {
                "correlation_id": state.get("correlation_id"),
                "fast_track_count": len(fast_track),
                "adjuster_queue_count": len(adjuster_queue),
                "threshold": self._fast_track_threshold,
            },
            state,
        )

        return {
            "fast_track_claims": fast_track,
            "adjuster_queue_claims": adjuster_queue,
            "status": AgentStatus.SUCCESS.value,
        }
