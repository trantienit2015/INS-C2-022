# Test Specification

## Test Strategy
- Coverage target: every node ≥1 unit success path + ≥1 error/edge path; full outer/inner
  graph ≥1 integration compile+invoke (fast-track path + adjuster-queue/HITL path).
- Test types: Unit (`tests/unit/`) / Integration (`tests/integration/`) /
  Proof-of-Boundary (`tests/proof_of_boundary/`)

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict extending `AgentState`, all agent fields `NotRequired` | Type check pass, no Pydantic/dataclass | PASS |
| TC-02 | Empty/malformed FNOL batch input yields fail-closed ERROR, no raise | Error raised, no exception | PASS |
| TC-03 | No JWT/Credential in src/, no direct `os.environ` (excl. entry-point boundary) | CI `gate-credential-scan`: 0 violations | PASS |
| TC-04 | InvocationContext via `configurable` only, never stored in State post-invoke | Direct access raises error | PASS |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `node_start`/`node_complete`/`node_error` absent from `execute()` body | PASS |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `TypeError` at class definition if overridden | PASS |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | `TypeError` at class definition if overridden | PASS |
| TC-08 | `required_trust_level` declared valid + enforced on every node | Insufficient trust → ERROR, no raise | PASS |
| TC-09 | S-2: `_extra_security_gate_input()` — none needed beyond default PII scan | N/A (no domain hook added — default scan on `user_input` sufficient) | N/A |
| TC-10 | S-3: `_extra_security_gate_output()` non-trivial — `PayoutAuthNode` preservation check | Rejects a payout record missing `audit_ref` | PASS |
| TC-11 | S-4: at least one domain `emit_trace_event()` inside each `execute()` | ≥1 domain event per node, incl. GraphNode hooks | PASS |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures | PASS |
| PB-2 | State serialization | Post-invoke State is primitives only | No Pydantic/dataclass | PASS |
| PB-3 | Level 2 → External service | N/A — deterministic local scorer/coverage-rules, no external service call in this template | N/A | N/A |
| PB-4 | Import isolation | No Level 0 imports | AST scan: 0 violations | PASS |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | Inspection pass | PASS |
| PB-6 | Invoke execution order | `__call__()`: S-1 → S-4 `node_start` → S-2 → `execute()` → S-3 → S-4 `node_complete`, for every node under `src/nodes/` | Order verified | PASS |
| PB-7 | HITL interrupt propagation | `interrupt()` inside `HITLGateNode` surfaces as `AWAITING_HUMAN` through the Cat 2 outer/inner GraphNode boundary; resume completes | Never `status=error` | PASS |

## Business Logic Tests

| TC-ID | Test | Input | Expected Result | Result |
|-------|------|-------|----------------|--------|
| BL-01 | Fast-track claim (below threshold) authorizes payout without adjuster review | 1 FNOL, severity 0.1, auto coverage | `status=SUCCESS`, payout authorized, no HITL suspend | PASS |
| BL-02 | Adjuster-queue claim (above threshold) suspends for HITL review then resumes | 1 FNOL, severity 0.95, commercial coverage | `status=AWAITING_HUMAN` → resume → `status=SUCCESS` | PASS |
| BL-03 | Excluded peril is not paid out | FNOL with peril in policy exclusions | `coverage_decisions` decision=`excluded`, no payout for that claim | PASS |
| BL-04 | Malformed FNOLs are rejected, not fatal to the batch | Mixed valid/invalid FNOLs | Valid FNOLs proceed; invalid tracked in `rejected_fnols` | PASS |
| BL-05 | Every payout emits a mandatory S-4 audit event | ≥1 payout authorized | `payout_authorized` event emitted per payout, incl. `audit_ref` | PASS |

## Test Execution Summary
- Execution date: 2026-07-13
- Total tests: unit (8 node files + TC-01..08 compliance) + integration (3) + PB (4)
- Pass / Fail / Skip: see CI `run-tests` job output (local wheel rc1 artifacts documented
  in the project standard — CI wheel 1.0.0 is gate of record)
- Coverage: every node has ≥1 success + ≥1 error/edge unit test; full graph covered by
  both the fast-track and adjuster-queue/HITL integration paths
