"""AgentCore Platform v1.0"""

# Coverage-line / deductible / exclusion evaluation. Pure deterministic logic
# (config-driven policy rules) — no agenticstar imports, no side effects.

from __future__ import annotations
from typing import Any


def evaluate_coverage(claim: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Verify coverage line, deductible, policy status, and exclusions for one claim.

    ``policy`` is the policy record looked up for ``claim["policy_number"]``.
    Returns a coverage decision dict — never raises; unresolvable inputs are
    routed to ``pending`` so a human adjuster can resolve them.
    """
    claim_id = claim.get("claim_id", "")

    if not policy:
        return {"claim_id": claim_id, "decision": "pending", "reason": "policy not found"}

    if policy.get("status") != "active":
        return {"claim_id": claim_id, "decision": "excluded", "reason": "policy not active"}

    coverage_line = claim.get("coverage_line", "")
    covered_lines = policy.get("covered_lines", [])
    if coverage_line not in covered_lines:
        return {"claim_id": claim_id, "decision": "excluded", "reason": f"{coverage_line} not covered"}

    exclusions = policy.get("exclusions", [])
    peril = claim.get("peril", "")
    if peril in exclusions:
        return {"claim_id": claim_id, "decision": "excluded", "reason": f"peril '{peril}' excluded"}

    deductible = policy.get("deductible", 0)
    claim_amount = claim.get("estimated_amount", 0)
    net_amount = max(0, claim_amount - deductible)

    return {
        "claim_id": claim_id,
        "decision": "covered",
        "deductible": deductible,
        "net_amount": net_amount,
    }
