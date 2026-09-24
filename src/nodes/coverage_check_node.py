"""AgentCore Platform v1.0"""

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.coverage_rules import evaluate_coverage


class CoverageCheckNode(FunctionNode):
    """Inner subgraph step 1: verify coverage line, deductible, policy status,
    exclusions per claim.

    Runs inside the Cat 2 inner subgraph — receives only ``user_input``
    (JSON string set by the outer FNOLIngestNode), not the outer state.
    Policy data is expected embedded per-FNOL as ``fnol["policy"]``
    (per-insurer policy-system integration is out of scope for this
    template — see docs/02_design.md dependency notes).
    """

    # S-1: inner subgraph node — trust authenticated once at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("user_input", "")
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
            fnol_batch = payload.get("fnol_batch") if isinstance(payload, dict) else None
        except (ValueError, TypeError):
            fnol_batch = None

        if not isinstance(fnol_batch, list) or not fnol_batch:
            emit_trace_event(
                "coverage_check_rejected",
                {"correlation_id": state.get("correlation_id"), "reason": "no_fnols_in_inner_input"},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["CoverageCheckNode: no FNOLs in inner input"],
            }

        decisions = [evaluate_coverage(fnol, fnol.get("policy", {})) for fnol in fnol_batch]

        emit_trace_event(
            "coverage_checked",
            {
                "correlation_id": state.get("correlation_id"),
                "covered": sum(1 for d in decisions if d["decision"] == "covered"),
                "excluded": sum(1 for d in decisions if d["decision"] == "excluded"),
                "pending": sum(1 for d in decisions if d["decision"] == "pending"),
            },
            state,
        )

        return {
            "fnol_batch": fnol_batch,
            "coverage_decisions": decisions,
            "status": AgentStatus.SUCCESS.value,
        }
