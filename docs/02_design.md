# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `PublicPropertyDisposalEvidenceAgent`
- **L1 Base**: **AgentBaseGraph** (outer graph) — Cat 2, GraphNode composition wrapping an
  inner domain workflow graph. No Level-2 base type (RAGAgent/ChatAgent/ReActAgent/
  DocGenerationAgent) is used; this is L1-direct per the approved proposal (§2, §5 of
  `engineer_proposal.md`).
- **Three-Layer Separation**:
  - State: flat TypedDict composition (no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Architecture Overview

This is a **Cat 2** template: it orchestrates a specific job-to-be-done (determining
disposal due-diligence readiness for a municipal asset case) via a fixed multi-step
workflow, not a single reusable capability (Cat 1) and not an autonomous self-directed
loop (Cat 3).

Two layers, per the standard Cat 2 pattern:

- **Outer graph** (`src/graph/graph.py`) — inherits `AgentBaseGraph`. Standard 5-node
  backbone (`initialize → pre_process → main → post_process → finalize`). Domain
  complexity is hidden inside the `main` slot via a `GraphNode` subclass
  (`DisposalEvidenceWorkflowGraphNode`).
- **Inner graph** (`src/graph/domain_workflow_graph.py`) — inherits `BaseGraph` (fully
  custom topology, no pre_process/main/post_process slots). Implements the four
  domain-specific steps between CaseIntake and OutputValidate: Retrieve → Normalize →
  EvidenceCheck → PacketAssemble.

Mapping from the proposal's 6-step workflow (`engineer_proposal.md` §4) onto the
AgentCore two-layer pattern:

| Proposal step | AgentCore location |
|---|---|
| 1. CaseIntake (S-1 gate) | Outer `pre_process` |
| 2. Retrieve | Inner `retrieve` |
| 3. Normalize | Inner `normalize` |
| 4. EvidenceCheck | Inner `evidence_check` |
| 5. PacketAssemble | Inner `packet_assemble` |
| 6. OutputValidate (S-3 gate) | Outer `post_process` |

### Node Configuration (outer graph)

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | Sets schema_version, session_id, caller_trust_level | — | `schema_version`, `session_id`, `caller_trust_level` | InitializeNode (default) |
| pre_process | S-1 gate: reject requests where the `asset_id` does not exist in the configured register or the `case_type` is outside scope (sale/lease_termination/transfer) (`_extra_security_gate_input()`); sets `validated_input` | `user_input` | `validated_input`, `asset_id`, `case_type`, `status` | `FunctionNode` (`CaseIntakeNode`) |
| main | Runs the inner domain workflow graph (Retrieve→Normalize→EvidenceCheck→PacketAssemble) and merges its output | `validated_input`, `asset_id`, `case_type` | `draft_packet`, `gap_findings`, `checklist_status`, `status` | `GraphNode` (`DisposalEvidenceWorkflowGraphNode`) |
| post_process | S-3 gate (mandatory): block any buyer, price, or disposal-decision inference in `draft_packet`; verify every finding cites a source record and checklist item; shape `formatted_output` | `draft_packet`, `gap_findings`, `checklist_status` | `formatted_output`, `status` | `FunctionNode` (`OutputValidateNode`) |
| finalize | Builds `response_metadata`, `total_time_ms` | — | `response_metadata`, `total_time_ms` | FinalizeNode (default) |

### Node Configuration (inner graph — `domain_workflow_graph.py`)

| Node | Responsibility | Input State | Output State |
|------|---------------|-------------|--------------|
| retrieve | Pulls the asset register entry, title/restriction records, appraisal documents, and council-resolution record for `asset_id` | `asset_id`, `case_type` | `raw_evidence`, `rule_reference` |
| normalize | Maps retrieved records into the fixed disposition-dossier schema fields (appraisal date/value, title status, restriction flags, resolution reference) | `raw_evidence` | `normalized_fields` |
| evidence_check | Rule/checklist engine compares `normalized_fields` against the disposition checklist; flags missing, stale, or conflicting evidence per item | `normalized_fields`, `rule_reference` | `checklist_status`, `gap_findings` |
| packet_assemble | LLM synthesis of the source-linked evidence-gap and review packet, one row per checklist item, citing the originating record | `normalized_fields`, `checklist_status`, `gap_findings`, `rule_reference` | `draft_packet` |

### Data Flow

```
START → initialize → pre_process → main → {route} → post_process → finalize → END
                                            ↓ (retry)
                                          pre_process

Inside `main` (DisposalEvidenceWorkflowGraphNode.execute()):
  GraphNode.get_subgraph() → DisposalEvidenceWorkflowGraph.invoke(validated_input, ctx=ctx)
  Inner graph: START → retrieve → normalize → evidence_check → packet_assemble → END
  merge_output() maps inner sub_result fields back into outer state.
```

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `asset_id` | `str` | Municipal asset identifier, validated by S-1 in `pre_process` against the configured asset register | Yes |
| `case_type` | `str` | Disposition-case type: `sale`, `lease_termination`, or `transfer` — validated in scope by S-1 | Yes |
| `raw_evidence` | `dict` | Retrieved asset register entry, title/restriction records, appraisal documents, council-resolution record (inner `retrieve`) | No (set by inner graph) |
| `rule_reference` | `dict` | Retrieved disposition-checklist rules applicable to the asset/case type (inner `retrieve`) | No |
| `normalized_fields` | `dict` | Structured dossier fields from Normalize: appraisal date/value, title status, restriction flags, resolution reference | No |
| `checklist_status` | `dict` | Per-checklist-item match results from EvidenceCheck | No |
| `gap_findings` | `list[dict]` | Missing/stale/conflicting evidence findings, each with source citation and checklist-item reference | No |
| `draft_packet` | `dict` | Assembled evidence-gap and review packet prior to the S-3 output gate | No |
| `formatted_output` | `dict` | Final gate-cleared review packet (confirmed evidence, gaps, conflicts, checklist status) | No |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)

`gap_findings` is a plain `list[dict]`, replaced wholesale by `packet_assemble` on each
invocation — not `Annotated[list, operator.add]`, since it is not an append-only
accumulator across multiple node calls within one invocation.

## Framework Utilization

### Services (`src/services/`)

- **`evidence_retrieval_service.py`** — retrieves the asset register entry, title and
  restriction records, appraisal documents, and council-resolution record for an
  `asset_id` + `case_type`, scoped to `kb_path: ./kb/` (per-municipality config surface,
  per `engineer_proposal.md` §10). Used by inner `retrieve`.
- **`normalization_service.py`** — maps raw retrieved records into the fixed
  disposition-dossier schema fields (appraisal date/value, title status, restriction
  flags, resolution reference); deterministic field mapping, no LLM call. Used by inner
  `normalize`.
- **`evidence_check_service.py`** — pure rule-matching logic: compares normalized fields
  against the locally configured disposition checklist, no LLM or external call. Used by
  inner `evidence_check`.
- **`packet_service.py`** — wraps the shared platform LLM client (via `framework`/
  `shared` — no direct provider SDK import) to synthesize the source-linked evidence-gap
  and review packet structure (confirmed evidence, gaps, conflicts, checklist status)
  with source/checklist citations. Used by inner `packet_assemble` and referenced by the
  outer `post_process` S-3 preservation check.

All services live in `src/services/`, contain no `agenticstar` imports, and receive
credentials only via `ctx.secrets.require()` (declared in `config/agent.yaml`
`requires.secrets` — `ANTHROPIC_API_KEY` for the packet-assembly service's LLM client).

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, permissions, credential handle)
- [x] ConnectionPolicy (retry/timeout strategy) — `max_retry: 3` per `config/agent.yaml`
- [x] SecurityViolationError
- [x] S-2: `_extra_security_gate_input()` — validates `asset_id` exists in the
      configured asset register and `case_type` is one of `sale` / `lease_termination` /
      `transfer`; rejects out-of-scope or unregistered asset cases. Runs after the
      default PII scan on `user_input`/`validated_input`.
- [x] S-3: `_extra_security_gate_output()` — mandatory domain check: scans
      `formatted_output` for buyer, price, or disposal-decision language and raises
      `SecurityViolationError` if found; verifies every entry in `gap_findings` /
      `checklist_status` cites a source record and checklist item (preservation
      variant — rejects output that drops required citations). Runs after the default
      credential scan.
- [x] S-4: `emit_trace_event()` — at least one domain-specific event inside each
      `execute()`:
      - `pre_process`: `case_validated` (`asset_id`, `case_type`)
      - inner `retrieve`: `evidence_retrieved` (`asset_id`, record counts)
      - inner `normalize`: `fields_normalized`
      - inner `evidence_check`: `evidence_checked` (gap/conflict counts)
      - inner `packet_assemble`: `packet_assembled`
      - `post_process`: `packet_gate_cleared`
      (does NOT re-emit `node_start`/`node_complete`/`node_error` — framework-owned)

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass (`pre_process`, `post_process`) → framework `@final` gate
>   always runs automatically; extended via `_extra_security_gate_input()` /
>   `_extra_security_gate_output()` as above
> - `GraphNode` (`main`) → deliberate no-op — the inner graph's own nodes are
>   `FunctionNode` subclasses with their own S-2/S-3 gates; the outer `post_process`
>   FunctionNode applies the mandatory packet-level S-3 gate described above
> - No custom `BaseNode` subclass is used in this template

### Composition Pattern

- **Pattern**: GraphNode (subgraph)
- **Composition target**: `src/graph/domain_workflow_graph.py` —
  `DisposalEvidenceWorkflowGraph` (inherits `BaseGraph`, fully custom `retrieve →
  normalize → evidence_check → packet_assemble` linear topology; no HITL/routing branch
  needed for the initial release, since gap/conflict detection does not require a
  human-in-the-loop pause — the officer/supervisor review happens *after* the packet is
  returned, not mid-graph)
- **Error propagation strategy**: `propagate` (default) — a retrieval, normalization, or
  evidence-check failure inside the inner graph is re-raised as `SubgraphError` and
  routed to `finalize` via the outer graph's standard error routing; no graceful
  degradation is defined for this template, since a partial/degraded evidence packet
  would risk an officer acting on incomplete due-diligence information (proposal's
  Risk #1)
- `propagate_hitl`: `False` (default) — this template does not set `hitl.enabled: true`;
  no HITL interrupts are used at any layer

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | **AgentBaseGraph** | Fixed multi-step workflow for a specific job-to-be-done (Cat 2), not a self-directed think→act→observe loop — proposal §2-2 confirms no autonomous termination logic |
| Composition pattern | Standalone (all logic in outer `main` FunctionNode) | GraphNode (inner domain workflow graph) | **GraphNode** | Four distinct domain steps (Retrieve/Normalize/EvidenceCheck/PacketAssemble) with different responsibilities and failure modes justify a dedicated inner graph rather than one monolithic `main` node; matches the standard Cat 2 pattern (`graph_cat2_sample.py`) |
| Inner graph parent | `BaseGraph` (custom topology) | `AgentBaseGraph` (5-node pipeline) | **BaseGraph** | The four inner steps do not map onto the pre_process/main/post_process shape — each is a distinct sequential transform with its own state output, so a fully custom linear topology is clearer than forcing a 3-slot pipeline |
| S-3 gate strategy | Content filtering only | Content filtering + preservation verification | **Both** | Must block buyer/price/disposal-decision language (filtering) AND must not silently drop required source citations from findings (preservation) — proposal's OutputValidate step requires both per `engineer_proposal.md` §4 |
| HITL | Enabled (interrupt before packet release) | Disabled | **Disabled** | Proposal's human review happens after the agent returns the packet (officer/supervisor approves/returns/requests material) — this is downstream of the agent's own execution, not a mid-graph pause; no `interrupt()` trigger condition applies |
| Error strategy (`GraphNode`) | `propagate` | `handle` | **propagate** | An evidence-check failure should surface as a hard error rather than a degraded packet, since a reviewer must not receive a packet claiming completeness when retrieval/normalization/checking actually failed |
| Normalize implementation | LLM-assisted extraction | Deterministic field mapping | **Deterministic field mapping** | Unlike free-text submitted documents (e.g. tenant rent-evidence submissions in adjacent templates), retrieved asset-register/title/appraisal/resolution records are already structured municipal-system records — mapping to the fixed dossier schema is a deterministic transform, reserving LLM use for PacketAssemble's narrative synthesis only, per `engineer_proposal.md` §10 ("retrieval and evidence-check are deterministic rule/checklist operations") |

---

*Status: completed*
*Date: 2026-07-22*
*Reviewer: TBD*
*Source: `docs/01_proposal.md` (approved), `engineer_proposal.md` §2–§4*
