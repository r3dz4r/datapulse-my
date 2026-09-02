# EU-01 Workflow Specs — index

**Date:** 2026-09-02
**Plan reference:** `~/.hermes/notes/2026-08-31-datapulse-september-action-items.md`, Workstream D, EU-01 (line 586–602)
**Status:** Draft, awaiting operator review and Y/N per workflow

The September plan names three required workflows and an optional fourth. All four are drafted here as private YAML, one file per workflow. Plan acceptance is met when each YAML has: named_user, trigger, expected_decision, setup_path, evidence_object, failure_case, success_measure.

| File | Plan name | Status |
|---|---|---|
| `01-pipeline-gate.yaml` | Pipeline Gate | draft |
| `02-agent-mcp.yaml` | Agent / MCP Workflow | draft |
| `03-reproducible-notebook.yaml` | Reproducible Research / Notebook Workflow | draft |
| `04-engine-trust-composition.yaml` | (optional) Engine Trust Composition | draft |

## Posture

- Each workflow tells the **adopter** how to integrate DataPulse evidence into a downstream artifact without claiming more than the verifier confirms.
- Each workflow's `evidence_object` is the smallest JSON the downstream consumer must persist so a reviewer can replay the decision deterministically.
- None of them require a hosted platform, an account, or a payment. They reuse the shipped surfaces (`mcp.tools`, `verify_dataset`, `ai-catalog.json`, `health/latest.json`, per-dataset receipts).

## Decision-dependent

- Workflows 1–3 are required by the September plan.
- Workflow 4 is optional per the plan ("only if already available without opening a new lane"). I included it because the Engine MCP exists at `https://mcp.data-pulse.my/engine` and the composition already exists in code; the workflow is a documentation-only addition, not a new lane.

Operator decisions per workflow:

1. **Pipeline Gate** — confirm or amend the `expected_decision` set: `proceed | retry-with-stale-allowed | block-with-reason | branch-to-stale-only-snapshot`.
2. **Agent / MCP** — confirm the agent's reference URL shape matches what you want agents to publish in their citations.
3. **Reproducible Notebook** — confirm whether you want a sidecar `notes/citations/<dataset_id>-<YYYY-MM-DD>.md` artifact at pin time, or only the in-notebook evidence block.
4. **Engine Trust Composition** — confirm the bundling convention (engine answer carries the stub verbatim) before this gets wired into the engine MCP docs.

Once approved, EU-02 builds the public kit (one copy-safe MCP config, one read-only example, one evidence-first notebook or script, one CI gate example, one "what this does not prove" block, one pinned citation example, one failure exercise using a real DataPulse status, one issue template).
