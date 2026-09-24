"""AgentCore Platform v1.0"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.claims_triage_scorer import score_claim

FAST_TRACK_ELIGIBLE_LINES = {"auto", "property", "home"}


class TriageScoreNode(FunctionNode):
    """Inner subgraph step 2: score severity x coverage match x fast-track
    eligibility (local scorer — documented pattern ref, documented fallback)."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        decisions = state.get("coverage_decisions", [])
        fnol_batch = state.get("fnol_batch", [])
        fnol_by_id = {f.get("claim_id"): f for f in fnol_batch}

        scores = []
        for decision in decisions:
            if decision["decision"] != "covered":
                continue
            fnol = fnol_by_id.get(decision["claim_id"], {})
            severity = float(fnol.get("severity", 0.5))
            net_amount = decision.get("net_amount", 0)
            coverage_match = 1.0 if net_amount > 0 else 0.5
            fast_track_eligible = fnol.get("coverage_line", "") in FAST_TRACK_ELIGIBLE_LINES

            score = score_claim(severity, coverage_match, fast_track_eligible)
            scores.append(
                {
                    "claim_id": decision["claim_id"],
                    "score": score,
                    "net_amount": net_amount,
                    "fast_track_eligible": fast_track_eligible,
                }
            )

        emit_trace_event(
            "claims_triage_scored",
            {"correlation_id": state.get("correlation_id"), "scored_count": len(scores)},
            state,
        )

        return {"triage_scores": scores, "status": AgentStatus.SUCCESS.value}
