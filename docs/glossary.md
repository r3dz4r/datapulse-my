# Glossary

## DataPulse terms

**Dataset** — A named collection or series of data exposed by an upstream publisher and represented by a stable DataPulse identifier.

**Publisher** — The organisation that publishes or controls the upstream source. The publisher remains the source of record for the underlying values.

**Source** — The concrete URL, feed, file, API, or rendered page observed by a probe. A publisher can expose multiple sources.

**Observation** — A timestamped record of what DataPulse retrieved or measured. An observation is not a guarantee that the source was correct.

**Probe** — The scheduled or manual operation that accesses a source and records transport, content, freshness, schema, or record-count signals.

**Freshness** — Evidence about how recently the source content appears to have been published or changed, based on the available signal and the declared cadence.

**Stale** — A source that remains observable but is older than the policy permits for its declared or inferred cadence. Stale does not mean discontinued.

**Discontinued** — A source classified as no longer publishing based on explicit upstream evidence or the approved discontinuation rule. Content age alone is insufficient.

**Reference** — A dataset retained for discovery or historical context whose update pattern is intentionally outside ordinary freshness expectations.

**Degraded** — A source that is reachable but fails a structural, schema, record-count, or other configured integrity check.

**Browser-dependent** — A source whose required state cannot be reliably observed through an ordinary direct request and requires a rendered browser path.

**Unknown** — A result where the available evidence is insufficient to establish the relevant condition. Unknown is not pass, fail, fresh, or neutral.

**Evidence** — An observable input or artifact supporting a statement about a source, observation, release, or transformation.

**Evidence receipt** — A compact, machine-readable record linking a subject to its observation time, method, source, measured signals, digests, status, and limitations.

**Provenance** — The lineage connecting a source, observation, transformation, artifact, claim, and verifier.

**Attestation** — A signed or otherwise integrity-protected statement about a specified artifact or event. An attestation does not establish that the underlying data is substantively true.

**Integrity** — Confidence that the bytes, identity, or declared lineage of an artifact have not changed outside the stated verification path.

**Semantic truth** — Whether an underlying value accurately describes the real-world subject. DataPulse does not establish this merely by observing, hashing, or signing a source.

**Source of record** — The official publisher or authority responsible for the underlying data, not DataPulse.

**Trust verdict** — A policy-derived decision about whether a particular evidence-backed use is permitted, cautioned, refused, or indeterminate. It is scoped to the policy and subject.

**Schema drift** — A material change in a source’s structure, field names, types, shape, or other defined contract.

**Reconciliation** — The explicit handling of disagreement between publisher declarations, transport signals, content observations, historical evidence, or downstream interpretations.

**As-of claim** — A claim about what was available or known at a specified time. It requires historical evidence for that time; a current snapshot cannot prove a past state.

## Evidence classes

**Publisher-declared** — A fact stated by the upstream publisher.

**Observed** — A fact directly measured by a DataPulse probe or verifier.

**Derived** — A fact calculated from one or more observations under a named policy.

**Human-reviewed** — A person inspected the stated evidence and recorded a decision. This does not make the underlying source objectively correct.

**Independently verified** — A separate consumer or verifier reproduced the stated evidence or integrity check.

**Disputed** — Evidence or interpretation has been materially challenged and remains unresolved.

**Superseded** — A later object or decision replaces the current one while preserving the earlier record.

## Consumer actions

**Use** — The declared policy permits the consumer’s intended use under the available evidence.

**Warn/review** — The source may be usable, but the consumer must account for a named limitation or verify additional evidence.

**Stop/refuse** — The available evidence does not support the intended use under the policy.

**Reference-use** — The source may be useful for context or historical reference but should not be treated as ordinarily current.

**Indeterminate** — The policy cannot decide because required evidence is missing, conflicting, or unverifiable.
