# Agent workflows

These workflows describe jobs rather than individual tools. Tool names and schemas remain owned by the live MCP advertisement and generated [MCP reference](mcp-reference.md).

## Workflow 1 — Find a current licensed source

**Intent:** Find an official Malaysian dataset that can support a time-sensitive answer.

1. Search by topic and, when relevant, licence.
2. Inspect the strongest candidate.
3. Reject candidates with stale, unreachable, degraded, or unknown-freshness status unless the user accepts the limitation.
4. Verify provenance/evidence for the selected candidate.
5. Return the official source, status, observation time, licence context, and limitations.

**Stop condition:** No candidate has evidence sufficient for the requested currentness or licence requirement.

## Workflow 2 — Decide whether a dataset is safe to cite

**Intent:** Decide whether a report or answer may cite a dataset.

1. Retrieve the dataset detail.
2. Identify the exact claim the user wants to make.
3. Compare the claim’s time scope with the observed freshness signal.
4. Check schema/record-count condition and licence context.
5. Verify the relevant evidence object.
6. Cite the publisher and DataPulse observation separately.

**Stop condition:** The claim requires evidence that the receipt does not cover, or a required signal is unknown.

## Workflow 3 — Investigate a stale source

**Intent:** Explain why a source cannot be treated as current.

1. Inspect the source status and freshness signal.
2. Compare source-declared cadence with observed content date and retrieval time.
3. Check whether the source is reachable and structurally usable.
4. Distinguish stale from discontinued.
5. Search for a documented successor or alternate official route.
6. Report the latest supported claim and the exact limitation.

**Do not:** replace stale data with an estimate unless the user explicitly requests a separate modelling task and the estimate is labelled as such.

## Workflow 4 — Detect structural change

**Intent:** Determine whether a source changed shape.

1. Retrieve the current dataset evidence.
2. Inspect schema fingerprint, fields, and record-count observations.
3. Compare with the relevant historical baseline.
4. Classify additive, breaking, semantic, or indeterminate change.
5. Stop downstream use when the intended consumer contract is no longer established.

**Stop condition:** The baseline or evidence is missing, so no safe comparison can be made.

## Workflow 5 — Produce a reproducible citation

**Intent:** Allow another person to reconstruct what the agent relied on.

Record:

- dataset ID;
- official source URL;
- DataPulse evidence URL/object;
- observation timestamp;
- status and methodology version;
- content/schema digest where available;
- licence/attribution;
- exact claim scope;
- limitations and any independent verification.

Prefer a pinned release, snapshot, digest, or evidence object over an unqualified “latest” URL.

## Workflow 6 — Refuse to overclaim

**Intent:** Handle insufficient evidence safely.

Use this response pattern:

> I found the official source, but DataPulse cannot establish that it is current/suitable for this claim because `<specific missing or conflicting evidence>`. The source was last observed at `<time>` with status `<status>`. I can provide the source for manual review, but I cannot present the claim as verified.

## Tool-call discipline

- Start with the narrowest tool that answers the user’s intent.
- Do not enumerate the entire catalogue when a filtered search is sufficient.
- Do not call verification tools after the evidence subject is already known to be invalid.
- Preserve raw reason codes and evidence references in downstream records.
- Treat network, schema, and policy failures as different failure classes.

## Related documents

- [Agent quickstart](agent-quickstart.md)
- [Status semantics](status-semantics.md)
- [Evidence receipt specification](evidence-receipt-spec.md)
- [Trust contract](trust-contract.md)
- [Integration patterns](integration-patterns.md)
