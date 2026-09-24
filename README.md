# INS-C2-022 — CAT Claims Triage & Rapid Payout Orchestration Agent

> **Category**: Cat 2 (orchestrates multiple steps to accomplish a specific use case)
> **Industry**: INS

## Overview

Orchestrates first-notice-of-loss triage for a catastrophe claims surge. The
agent ingests a batch of loss notifications, rejecting malformed ones, checks
coverage, scores each claim for triage, then routes it: claims below the
configured fast-track threshold proceed to rapid payout authorisation, while
the rest are queued for an adjuster. Settlements above the threshold suspend
for human approval before any payout is authorised. The agent then issues
claimant notifications and renders an operations triage report.

The pipeline runs as a Cat 2 composition: an outer graph ingests and validates
the batch and renders the report, while the domain workflow (coverage check →
triage scoring → routing → approval gate → payout authorisation →
notification) runs as an inner subgraph.

Payout authorisation moves money, so the fast-track threshold is configuration
rather than a hard-coded constant, and anything above it goes through the
human approval gate.

The agent is fully deterministic — it calls no language model and needs no
model API credentials.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Without it, start-up fails immediately (see *Behaviour without the platform* below). Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| Python | >=3.11 |

```bash
pip install -e .
```

### Behaviour without the platform

The framework is designed to run **only** on AGENTIC STAR. There is no fallback or degraded
mode. If the platform is unreachable or the SDK version does not match, the agent raises
`PlatformRequired` during graph compile / start-up preflight rather than starting in a partially
working state. This is intentional — a half-running agent is worse than one that refuses to start.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests run without a platform connection. Running the agent itself does not.

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and test specification
```

See `docs/02_design.md` for the design and `docs/03_test_spec.md` for the test specification.

## Customising

1. Adjust `config/` for your own environment and policies.
2. Replace the knowledge sources and sample data with your own.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.
