# GOV-C2-093 — Municipal Public-Property Disposal Due-Diligence Evidence Reviewer

> **Category**: Cat 2 (orchestrates a specific job-to-be-done: disposal due-diligence evidence review)
> **Industry**: GOV (government)

## Overview

Triggered when a municipal public-property management officer opens a case to sell, terminate
a lease on, or transfer an unused municipal asset. The agent retrieves the asset register
entry, title/restriction records, appraisal documents, and council-resolution record for the
asset, normalizes them against the locally configured disposition checklist, checks each
required evidence item for presence and consistency, and assembles a source-linked
human-review packet listing confirmed evidence, gaps, and conflicts. It never recommends a
buyer, price, or disposal decision itself — those determinations remain with authorized
public-property management staff.

- **CaseIntake** (S-1 gate) — validates the asset ID exists in the configured register and the
  disposition-case type (sale, lease termination, transfer) is within scope; rejects otherwise.
- **Retrieve** — pulls the asset register entry, title/restriction records, appraisal
  documents, and council-resolution record for the given asset ID.
- **Normalize** — maps retrieved records into the fixed disposition-dossier schema fields
  (appraisal date/value, title status, restriction flags, resolution reference).
- **EvidenceCheck** — rule/checklist engine compares normalized fields against the disposition
  checklist; flags missing, stale, or conflicting evidence per item.
- **PacketAssemble** — LLM synthesis of a structured, source-linked evidence-gap and review
  packet, one row per checklist item.
- **OutputValidate** (S-3 gate, mandatory) — blocks any buyer, price, or disposal-decision
  inference; verifies every finding cites a source record and checklist item.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| **Anthropic API key** | Required for the PacketAssemble step's LLM-assisted synthesis (outside mock mode — see below). |
| Python | >=3.11 |

```bash
pip install -e .
```

### Behaviour without the platform

This agent is written against the `agenticstar-agentcore` framework and is
runnable standalone via `src/api/server.py` — it does not require the wider
AgentCore platform (registry, gateway, orchestrator) to function. Outside the
platform: request authentication falls back to an optional bearer token read
from an environment variable (unset means every caller is treated as
unauthenticated), there is no persistent checkpointer unless you wire one
yourself, and the Anthropic API key is read directly from the process
environment rather than through the platform's secret-provisioning layer.
Setting `USE_MOCK=true` runs the Retrieve and PacketAssemble steps against
deterministic fixtures instead of the asset register / KB and the LLM client —
see `src/services/mock_mode.py`.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

`input` is a JSON string: `{"asset_id": "...", "case_type": "sale|lease_termination|transfer"}`.

```bash
curl -X POST http://127.0.0.1:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": "{\"asset_id\": \"ASSET-001\", \"case_type\": \"sale\"}"}'
```

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and operational documentation
```

See `docs/` for the design spec and test specification.

## Customising

1. Adjust `config/` for your own environment and disposition checklist.
2. Replace the asset register / title / appraisal / council-resolution data
   sources with your own.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.
