# Reproducibility

Reproducibility means another party can identify what DataPulse used, what it generated, and what evidence supported a decision. It does not mean every upstream source is immutable or substantively correct.

## Three reproducibility levels

### Release reproducibility

A release rebuild should use the declared canonical inputs and produce deterministic generated outputs. The repository’s release verifier is the operational authority; this page explains how to interpret its result.

A reproducible release should identify:

- source revision;
- generation profile;
- input schemas and policy versions;
- generated artifact set;
- test and invariant results;
- environment-dependent exceptions;
- release or deployment identity.

### Observation reproducibility

An observation should preserve, where available:

- dataset/source identity;
- exact source URL and access method;
- retrieval and observation timestamps;
- content or response digest;
- content-date and freshness signals;
- schema/record-count observation;
- status and reason codes;
- methodology/probe version;
- licence context;
- evidence and attestation references;
- limitations and conflicts.

If the historical evidence is incomplete, the result is `unknown` or partial reconstruction, not a fabricated past state.

### Claim reproducibility

A claim is reproducible when a consumer can identify:

- the exact proposition;
- its scope and time window;
- the source of record;
- the DataPulse observation or evidence object;
- the policy used to derive the status or decision;
- the digest/release needed to repeat the check;
- the known limitations.

An unpinned “latest” link is useful for discovery but weak for reproducible research.

## Verification procedure

1. Resolve the release, dataset, or evidence subject without silently rewriting identifiers.
2. Retrieve the referenced artifact.
3. Validate its schema and contract version.
4. Recompute the stated digest over the specified payload.
5. Verify signatures or transparency evidence under the relevant policy.
6. Compare timestamps and source identity.
7. Re-run the declared derivation or policy where possible.
8. Record any unavailable input, environment difference, or unresolved conflict.

## What reproducibility does not prove

- Reproducible bytes are not necessarily correct facts.
- A reproducible transformation can consistently implement a wrong assumption.
- A signed release can contain a semantic error.
- A current observation cannot recreate an absent historical observation.
- A publisher’s declared licence still requires interpretation for the downstream use.

## Public verification references

- [Evidence receipt specification](evidence-receipt-spec.md)
- [Trust contract](trust-contract.md)
- [Release verification](release-verification.md)
- [Release process](release-process.md)
- [Health methodology](health-methodology.md)
