# Integration patterns

DataPulse is most useful when its evidence changes a downstream decision. The patterns below keep the public trust layer separate from any private or paid vertical product.

## Pattern 1 — RAG freshness gate

```text
retrieve candidate → inspect DataPulse status → verify evidence → allow or refuse retrieval
```

Use this when stale or structurally degraded source material could produce a misleading answer. Store the dataset ID, observation time, status, and evidence reference with the retrieved context.

## Pattern 2 — Agent citation loop

```text
search → get dataset → inspect provenance/licence → verify evidence → answer with limits
```

The final answer should cite the publisher and preserve the DataPulse observation separately. Do not present DataPulse as the publisher.

## Pattern 3 — CI data contract gate

A pipeline can check before processing:

- source is reachable;
- status is within the project’s allowed set;
- schema fingerprint matches the expected baseline;
- record count is within the declared tolerance;
- licence is present when required;
- evidence object verifies.

The project must define its own acceptance policy. DataPulse’s public status is evidence input, not an automatic universal pass/fail rule.

## Pattern 4 — Reproducible research notebook

Pin:

- dataset ID;
- official source URL;
- DataPulse evidence object or release;
- observation timestamp;
- status and methodology version;
- content/schema digest where available;
- claim scope and limitations.

A notebook using an unqualified latest endpoint may be convenient but is not fully reproducible.

## Pattern 5 — Governance review

For a regulated or high-consequence workflow, require:

1. source-of-record identification;
2. licence and attribution review;
3. freshness and schema evidence;
4. independent receipt verification;
5. human approval for the intended use;
6. preserved decision record;
7. re-verification trigger.

Automation can record the evidence and the human decision. It must not invent or upgrade a human-verification rung.

## Pattern 6 — DataPulse and Malaysia Data Engine

The public DataPulse layer can provide source observation and evidence context to a private vertical workflow. The Engine may apply stricter local policy, packaging, reconciliation, or paid-product controls.

Keep the boundary explicit:

```text
DataPulse public source evidence
        ↓
private vertical policy and transformation
        ↓
product-specific output and buyer workflow
```

A DataPulse health status does not automatically certify the Engine’s derived output, and an Engine result does not upgrade DataPulse’s source-of-record authority.

## Anti-patterns

- Treating an HTTP success as freshness proof.
- Feeding stale or unknown data into a “latest” answer without qualification.
- Treating a signed artifact as semantically true.
- Copying DataPulse’s current counts or tool list into application code.
- Using a homepage link as a substitute for a pinned evidence object.
- Treating the public MCP server as an enterprise security gateway.
- Claiming an integration is reproducible without recording the exact evidence subject and timestamp.
