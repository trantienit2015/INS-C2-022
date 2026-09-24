"""AgentCore Platform v1.0"""

# Node contract (agents_layer_design.md §1):
#  - Extend FunctionNode; implement execute(state) -> dict
#  - Return ONLY the fields this node changes (never full state)
#  - Return AgentStatus enum constants — never plain strings [A1]
#  - Never import from mediator/, api/, or other agents

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

REQUIRED_FNOL_FIELDS = ("claim_id", "policy_number", "coverage_line")


class FNOLIngestNode(FunctionNode):
    """Outer pre_process: ingest + validate the mass FNOL batch on a CAT event.

    Malformed FNOLs (missing required fields) are rejected and tracked in
    ``rejected_fnols`` rather than failing the whole batch. Policyholder PII
    (name/address/phone) is scanned by the framework S-2 input gate on
    ``user_input`` automatically; no domain PII check is added here.
    """

    # S-1: outer boundary node — trust matches agent.yaml required_trust_level
    # (this agent receives CAT-event batches from an internal ops trigger).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw_input = state.get("user_input", "")
        emit_trace_event(
            "fnol_batch_ingest_started",
            {"correlation_id": state.get("correlation_id")},
            state,
        )

        try:
            payload = json.loads(raw_input) if isinstance(raw_input, str) else raw_input
        except (ValueError, TypeError):
            payload = None

        if not isinstance(payload, dict):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["FNOLIngestNode: user_input is not a valid FNOL batch payload"],
            }

        cat_event_id = payload.get("cat_event_id", "")
        raw_batch = payload.get("fnol_batch", [])
        if not isinstance(raw_batch, list) or not raw_batch:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["FNOLIngestNode: fnol_batch is empty or missing"],
            }

        validated, rejected = [], []
        for fnol in raw_batch:
            if not isinstance(fnol, dict) or any(f not in fnol for f in REQUIRED_FNOL_FIELDS):
                rejected.append({"fnol": fnol, "reason": "missing required field"})
                continue
            validated.append(fnol)

        if not validated:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["FNOLIngestNode: no valid FNOLs after validation"],
                "rejected_fnols": rejected,
            }

        validated_input = json.dumps({"cat_event_id": cat_event_id, "fnol_batch": validated}, ensure_ascii=False)

        emit_trace_event(
            "fnol_batch_validated",
            {
                "correlation_id": state.get("correlation_id"),
                "validated_count": len(validated),
                "rejected_count": len(rejected),
            },
            state,
        )

        return {
            "cat_event_id": cat_event_id,
            "fnol_batch": validated,
            "rejected_fnols": rejected,
            "validated_input": validated_input,
            "status": AgentStatus.SUCCESS.value,
        }
