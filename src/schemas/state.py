"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict. LangGraph checkpoints use msgpack
# serialization, so only plain serializable fields are allowed. Do NOT add
# credentials or secrets. All agent-specific fields are NotRequired (project standard) —
# they may be absent from an early checkpoint or before the node that fills
# them has run.

from typing import Any, NotRequired

from framework.schemas.agent_state import AgentState


class State(AgentState):
    """State for the CAT Claims Triage & Rapid Payout Orchestration Agent.

    Inner-subgraph fields travel as a JSON string via ``validated_input``
    (Cat 2 GraphNode boundary — the inner graph never sees the outer state
    directly) and are re-materialized here by ``merge_output()`` once the
    inner subgraph completes.
    """

    # -- outer pre_process (FNOLIngestNode) --
    fnol_batch: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]
    cat_event_id: NotRequired[str]  # type: ignore[valid-type]
    rejected_fnols: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]

    # -- merged back from the inner subgraph (ClaimsWorkflowGraphNode.merge_output) --
    coverage_decisions: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]
    triage_scores: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]
    fast_track_claims: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]
    adjuster_queue_claims: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]
    adjuster_approved_settlements: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]
    payout_authorizations: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]
    notifications: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]

    # -- outer post_process (ReportNode) --
    triage_report: NotRequired[dict[str, Any]]  # type: ignore[valid-type]
