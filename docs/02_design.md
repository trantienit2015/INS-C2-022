# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `ClaimsTriageOrchestrationGraph`
- **L1 Base**: AgentBaseGraph (outer) — Cat 2 composition: outer `AgentBaseGraph` +
  `GraphNode` (`main` slot, `ClaimsWorkflowGraphNode`) wrapping an inner `BaseGraph`
  (`ClaimsTriageWorkflowGraph`, `src/graph/domain_workflow_graph.py`).
- **Three-Layer Separation**:
  - State: flat TypedDict composition (no Pydantic — msgpack incompatible), every
    agent-specific field wrapped `NotRequired[...]`
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Architecture Overview

### Outer Node Configuration

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | schema_version, session_id, trust_level | — | — | InitializeNode (default) |
| pre_process | `FNOLIngestNode` — ingest + validate mass FNOL batch; reject malformed | `user_input` (JSON) | `fnol_batch`, `rejected_fnols`, `validated_input` | FunctionNode |
| main | `ClaimsWorkflowGraphNode` — wraps inner Cat 2 subgraph | `validated_input` | `fast_track_claims`, `adjuster_queue_claims`, `adjuster_approved_settlements`, `payout_authorizations`, `notifications` | GraphNode |
| post_process | `ReportNode` — assemble operations triage report | merged inner fields | `triage_report`, `formatted_output` | FunctionNode |
| finalize | response_metadata, total_time_ms | — | — | FinalizeNode (default) |

### Inner Subgraph Node Configuration (`ClaimsTriageWorkflowGraph`)

| Node | Responsibility | Output |
|------|---------------|--------|
| coverage_check | `CoverageCheckNode` — verify coverage line, deductible, policy status, exclusions | `coverage_decisions` |
| triage_score | `TriageScoreNode` — score severity x coverage match x fast-track eligibility (local scorer, pattern ref) | `triage_scores` |
| routing | `RoutingNode` — split below-threshold (fast-track) vs complex/large-value (adjuster queue) | `fast_track_claims`, `adjuster_queue_claims` |
| hitl_gate | `HITLGateNode` — D6 `interrupt()` for adjuster review; skips itself when queue is empty; never auto-approves | `adjuster_approved_settlements` |
| payout_auth | `PayoutAuthNode` — generate payout authorization; mandatory S-4 audit event per payout (pattern ref); convergence point for both tracks | `payout_authorizations` |
| notify | `NotifyNode` — policyholder payout/status notification (pattern ref) | `notifications` |

### Data Flow

```
Outer:
  START → initialize → pre_process(FNOLIngestNode) → main(ClaimsWorkflowGraphNode)
        → post_process(ReportNode) → finalize → END

Inner (inside main):
  START → coverage_check → triage_score → routing
        → hitl_gate (interrupt() only if adjuster_queue_claims non-empty)
        → payout_auth (fast_track + adjuster_approved converge here)
        → notify → END
```

Data crosses the outer/inner boundary as a JSON string: `FNOLIngestNode` serializes
`{cat_event_id, fnol_batch}` into `validated_input`; `ClaimsWorkflowGraphNode.extract_input()`
passes that string to the inner subgraph; `CoverageCheckNode` (first inner step)
`json.loads()`s it back into `fnol_batch`. `merge_output()` maps the inner
`get_output()` fields back into the outer state.

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `fnol_batch` | `NotRequired[list[dict]]` | validated FNOLs for this CAT event | outer pre_process |
| `cat_event_id` | `NotRequired[str]` | CAT event identifier | outer pre_process |
| `rejected_fnols` | `NotRequired[list[dict]]` | malformed FNOLs rejected at ingest | outer pre_process |
| `coverage_decisions` | `NotRequired[list[dict]]` | per-claim coverage decision | inner (merged) |
| `triage_scores` | `NotRequired[list[dict]]` | per-claim triage score | inner (merged) |
| `fast_track_claims` | `NotRequired[list[dict]]` | below-threshold claims | inner (merged) |
| `adjuster_queue_claims` | `NotRequired[list[dict]]` | complex/large-value claims | inner (merged) |
| `adjuster_approved_settlements` | `NotRequired[list[dict]]` | HITL-approved settlements | inner (merged) |
| `payout_authorizations` | `NotRequired[list[dict]]` | audited payout records | inner (merged) |
| `notifications` | `NotRequired[list[dict]]` | policyholder notifications | inner (merged) |
| `triage_report` | `NotRequired[dict]` | final operations report | outer post_process |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, caller_trust_level)
- [x] S-2: no domain-specific `_extra_security_gate_input()` beyond the default PII scan —
      FNOL policyholder PII is already covered by the framework's `user_input` scan.
- [x] S-3: `_extra_security_gate_output()` on `PayoutAuthNode` — preservation-variant check
      that every payout authorization record retains its `audit_ref` (a payout without one
      would be a 金融庁-scrutinized control gap).
- [x] S-4: `emit_trace_event()` — at least one domain event inside every `execute()`
      (`fnol_batch_validated`, `coverage_checked`, `claims_triage_scored`, `claims_routed`,
      `adjuster_review_completed`/`adjuster_review_skipped`, `payout_authorized` per payout,
      `policyholder_notifications_dispatched`, `triage_report_generated`, plus the
      `claims_workflow_dispatched`/`claims_workflow_completed` pair emitted inside
      `ClaimsWorkflowGraphNode`'s `extract_input()`/`merge_output()` hooks).

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass (all inner/outer domain nodes here, incl. `HITLGateNode`) →
>   framework `@final` gate always runs automatically.
> - `GraphNode` (`ClaimsWorkflowGraphNode`) → deliberate no-op (inner subgraph's own gates
>   already applied to each inner node).

### HITL Compliance (D6, hitl.enabled: true)

- `config/agent.yaml`: `memory_enabled: true` (mandatory) + `hitl: {enabled: true, max_hitl: 8}`.
- Trigger condition: `HITLGateNode.execute()` calls `interrupt()` only when
  `adjuster_queue_claims` is non-empty — never auto-approves a complex/large-value claim.
- The inner subgraph is compiled with its own `InMemorySaver` checkpointer (cached on the
  `ClaimsWorkflowGraphNode` instance so the same thread survives invoke → interrupt →
  resume). `ClaimsWorkflowGraphNode.propagate_hitl = True` surfaces the inner
  `AWAITING_HUMAN` status to the outer caller once the outer graph's own checkpointer
  (`src/api/server.py`: `agent.compile(checkpointer=InMemorySaver())`) is attached.
- SLA timeout → escalation to the claims manager is an ops-layer concern (external
  queue/alerting on a suspended `thread_id`), outside this graph's synchronous nodes.

### Composition Pattern

- **Pattern**: GraphNode (subgraph) — Cat 2 (outer `AgentBaseGraph` + `GraphNode` `main` +
  inner `BaseGraph`)
- **Composition target**: `src/graph/domain_workflow_graph.py::ClaimsTriageWorkflowGraph`
- **Error propagation strategy**: `propagate` (`ClaimsWorkflowGraphNode.error_strategy`) —
  matches the verified sibling pattern; the HITL suspend path does not raise
  an exception (LangGraph's own `__interrupt__` signal, converted to a normal
  `AWAITING_HUMAN` return by `BaseGraph.invoke()`), so `error_strategy="propagate"` only
  affects genuine node ERROR results.

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | AgentBaseGraph | Fixed multi-step pipeline, not an autonomous loop |
| Composition pattern | Flat Cat 1 style | GraphNode + inner subgraph | GraphNode + inner subgraph | Cat 2 mandate (architecture mandate) — `gate-composition` requires it |
| Coverage/policy data source | Live policy-system integration | Policy embedded per-FNOL | Policy embedded per-FNOL | Per-insurer policy-system integration is out of scope for this template (documented dependency gap, §12 of the proposal) |
| Fraud investigation | In-scope | Deferred | Deferred to a separate template | Explicit scope boundary per proposal §4 |

## Open PM/Engineering Items (tracked, non-blocking)

Per the proposal §7 summary: the auto fast-track payout threshold policy
(`config/agent.yaml` → `agent.config.fast_track_threshold`, default `0.4`) and the two
pattern-reference dependency fallbacks (an external HITL pattern → local D6 `interrupt()`;
an external scorer pattern → local `src/services/claims_triage_scorer.py`) are PM-owned decisions
tracked here per docs/02_design.md convention; engineering is not blocked on either.
