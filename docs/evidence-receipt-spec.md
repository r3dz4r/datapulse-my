# Evidence receipt specification

## Purpose

An evidence receipt is a compact, machine-readable record of what DataPulse observed about a subject and how a consumer can verify that record. It is evidence about an observation, not a certificate that the upstream data is substantively true.

The existing `record-evidence/v1` contract remains the compatibility authority unless a separately approved version says otherwise. This page explains the minimum semantics consumers should expect and the boundaries they must preserve.

## Receipt subject

A receipt must identify its subject precisely:

- canonical dataset, tool, server, release, or artifact identifier;
- publisher or producer where applicable;
- source URL or endpoint;
- object type and contract version;
- observation or creation time;
- retrieval/access method;
- policy or methodology version.

A receipt for a portfolio snapshot must not be described as a complete per-dataset receipt unless the coverage has been verified.

## Evidence fields

A receipt should expose, when available, or explicitly represent as null/unknown:

| Field | Meaning |
|---|---|
| `subject_id` | Stable identity of the observed subject |
| `observed_at` | When the source or artifact was observed |
| `retrieved_at` | When DataPulse retrieved it, if distinct |
| `source_url` | Exact source location used |
| `access_method` | Direct HTTP, API, browser, file, or other declared method |
| `transport` | Status, content type, redirects, and relevant access signals |
| `content_date` | Date extracted from source content, if any |
| `freshness_signal` | Signal and extraction method used |
| `schema_fingerprint` | Structural identity or comparison result |
| `record_count` | Observed count, with an explicit completeness caveat |
| `licence` | Recorded licence or attribution information |
| `status` | Current policy classification |
| `reason_codes` | Stable reasons supporting the classification |
| `content_digest` | Digest of the covered content or canonical payload |
| `provenance_refs` | Links to source, transformation, or release lineage |
| `attestation_refs` | Integrity/attestation references, if present |
| `limitations` | Known blind spots, exclusions, and unresolved conflicts |
| `supersedes` / `superseded_by` | Relationship to corrected or replaced objects |

Unknown, unavailable, and not-applicable are different states and must not be collapsed into an empty string or a positive default.

## Verification procedure

A consumer should:

1. validate the object type and supported contract version;
2. resolve the subject identity without silently normalising identifiers;
3. validate the schema and required fields;
4. verify the digest over the stated canonical payload;
5. verify any signature or transparency evidence under an already trusted policy;
6. confirm the observation time, source, and policy are appropriate for the intended use;
7. inspect limitations, conflicts, and supersession links;
8. treat a failed, incomplete, or unsupported step as a bounded verification failure.

A matching identifier without a matching digest is not sufficient. A valid digest without a trustworthy source or policy is not sufficient. A valid signature without semantic ground truth is not sufficient.

## Evidence and authority model

| Receipt statement | Establishes | Does not establish |
|---|---|---|
| Source URL was observed | Access to that location at a time | Publisher ownership or truth |
| Content digest matches | Covered bytes are unchanged | Content is correct |
| Schema fingerprint matches | Shape matched the baseline | Every value is valid |
| Licence field is present | A licence statement was recorded | Every downstream use is legally safe |
| Attestation verifies | Integrity of the attested statement | Upstream values are true |
| Human review is recorded | A named review occurred under a policy | Objective correctness |
| Status is `fresh` | Freshness signals satisfied policy | Future freshness or semantic accuracy |

## Coverage boundary

Before claiming receipt coverage, distinguish:

- portfolio-level evidence;
- per-dataset metadata envelopes;
- per-dataset signed receipts;
- source-specific or browser-dependent exceptions;
- historical snapshots versus current observations.

If a documented route returns HTML, a redirect, or an incomplete object where a machine receipt was promised, the route is not compliant until repaired or the public claim is narrowed.

## Example interpretation

A defensible statement is:

> DataPulse observed `fuelprice` through the documented source path at the receipt’s `observed_at` time. The receipt records the status, source, licence context, and measured signals. The receipt’s digest verifies the covered artifact; it does not certify that every upstream price is correct.

## Related documents

- [Trust contract](trust-contract.md)
- [Status semantics](status-semantics.md)
- [Reproducibility](reproducibility.md)
- [Glossary](glossary.md)
