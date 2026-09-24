"""AgentCore Platform v1.0"""

# Local triage-scoring service (pattern ref: ScoringRankingAgent —
# documented local fallback per docs/12 Dependencies; that pattern template is closed at
# stage:proposal so this template does not import it).
#
# Pure deterministic logic — no agenticstar imports, no side effects.

from __future__ import annotations

SEVERITY_WEIGHT = 0.5
COVERAGE_WEIGHT = 0.3
FAST_TRACK_WEIGHT = 0.2


def score_claim(severity: float, coverage_match: float, fast_track_eligible: bool) -> float:
    """Score a single claim: severity x coverage match x fast-track eligibility.

    All inputs are normalized 0.0-1.0. Returns a triage score 0.0-1.0 where
    higher means more complex/higher-value (routed to adjuster review).
    """
    severity = max(0.0, min(1.0, severity))
    coverage_match = max(0.0, min(1.0, coverage_match))
    fast_track_penalty = 0.0 if fast_track_eligible else 1.0

    return round(
        severity * SEVERITY_WEIGHT + (1.0 - coverage_match) * COVERAGE_WEIGHT + fast_track_penalty * FAST_TRACK_WEIGHT,
        4,
    )


def is_fast_track(score: float, threshold: float) -> bool:
    """Below the configurable threshold -> fast-track payout, no adjuster review."""
    return score < threshold
