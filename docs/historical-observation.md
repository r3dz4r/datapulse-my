# Historical observation envelope contract

Contract version: `historical-observation/v1` — defined 2026-09-13.
Machine contract: [`historical-observation.schema.json`](https://github.com/r3dz4r/datapulse-my/blob/main/historical-observation.schema.json) (JSON Schema draft 2020-12).

## Purpose

A historical-observation envelope is the fixed, testable shape for one filed
observation of an upstream dataset: what was requested, what was actually
captured, how it was normalised, how it relates to the observation before it,
and what a consumer may conclude from it.

The contract exists to prevent one specific failure: a schema that permits a
claim the system cannot support. If an envelope could assert a digest for
bytes that were never captured, or present an attestation-chain value as
same-dataset history, then an unverifiable or stale vintage would read as
replayable — and every downstream artefact would inherit the overstatement.
Every rule below exists to keep filed claims exactly as strong as the
evidence behind them.

This page defines the contract only. There is no capture code, no storage
layout, no signing flow, and no MCP surface for it yet; those later phases
must build against this shape, not redefine it. `datapulse.json`,
`health/latest.json`, `record-evidence/v1` and the existing attestation
canonical form are unchanged by this contract.

## Scope and non-goals

In scope: the envelope schema, its semantic rules, and its test fixtures
(`scripts/tests/test_historical_observation_schema.py`).

Not in scope for this phase: capturing bytes, storing envelopes, signing or
verifying them, generating Merkle proofs, exposing any MCP tool, route or
resource, and any change to the ten-status health taxonomy or to
`health.schema.json`, `datapulse.schema.json`, `record-evidence.schema.json`,
`passport.schema.json`, or the attestation canonical form.

## Envelope members

All members are required. Optional knowledge is expressed as explicit
`null` values plus entries in `unknown_reasons` — unknown, unavailable and
not-applicable are different states and are never collapsed into an empty
string or a positive default.

| Member | Meaning |
|---|---|
| `schema` | Constant `historical-observation/v1` |
| `observation_id` | Stable id of this observation (`obs-…`), unique across datasets and cycles |
| `dataset_id` | Manifest id of the observed dataset |
| `source_identity` | Declared or independently supported identity of the source, with a basis and a fixed limitation |
| `source_url` | Canonical catalogue URL |
| `observed_request_url` | The URL actually requested (may differ after redirects or mirror selection) |
| `observed_at` | Instant DataPulse filed the observation (digests computed, envelope sealed) |
| `retrieved_at` | Instant the source request completed; null when no completed request exists |
| `source_content_date` | Date the content itself is about (its vintage); null when not extractable |
| `source_version` | Explicit `unknown`, or a `{value, basis}` pair — never a bare fabricated string |
| `capture_policy` | What the pipeline intended to retain |
| `capture_status` | What was actually retained; only `captured` means the source bytes are held in full |
| `source_digest` | SHA-256 over exactly the captured source bytes; null unless `capture_status` is `captured` |
| `observation_digest` | Domain-separated digest over this envelope's canonical form (excluding itself) |
| `shape_fingerprint` | `shape-v1` structural fingerprint (keys, types, headers), or null |
| `normalized_projection` | Whether a normalised projection is retained, its format and record count |
| `normalization_profile_version` | Version of the normalisation rules; projections compare only within a version |
| `previous_observation_id` | Immediately preceding observation of the same dataset; null for the first |
| `previous_observation_digest` | Digest of that preceding same-dataset observation; null for the first |
| `change_from_previous` | `changed`, `unchanged`, `incomparable`, `first_observation` or `unknown` |
| `verification` | Cryptographic verification state, with method and a fixed limitation |
| `attestation_ref` | Reference to the attestation-plane entry covering this cycle; nullable |
| `witness_refs` | Independent corroborating record references; possibly empty |
| `claim_boundary` | Non-empty `may_conclude` and `may_not_conclude` lists for this observation |
| `unknown_reasons` | Closed-vocabulary list of members whose values are explicitly unknown |
| `cycle_root` | Merkle-style commitment over all observation digests in the cycle |
| `contract_digest` | Digest of the pinned code that produced this observation |
| `superseded_by` | Observation that replaces this one; null while current |
| `invalidated_by` | Observation id or contract digest that invalidated this one; null while it stands |
| `declared` | What the source or contract declares, each entry with a basis |
| `observed` | What DataPulse actually observed, each entry with a basis |
| `publisher_credential` | Reserved; must be null in this phase |
| `verifier_credential` | Reserved; must be null in this phase |
| `replay_state` | One of the six replay vocabulary values below |

## Digest namespaces

Digests are domain-separated by prefix so a value from one plane can never be
presented as a value from another:

| Prefix | Plane |
|---|---|
| `sha256:` | Raw source bytes (`source_digest`) |
| `observation:sha256:` | One envelope (`observation_digest`, `previous_observation_digest`) |
| `cycle-root:sha256:` | The aggregate commitment over a whole cycle |
| `contract:sha256:` | The producing code |

The attestation plane (`.attestations/chain_head.json`) uses bare 64-character
hex for `chain_head`, `previous_chain_head` and `dataset_links_sha256`, with no
`observation:` prefix. That difference is deliberate: a bare chain-head hex
string fails `previous_observation_digest` validation by construction.

## Semantic rules

These six rules are contract, not guidance. The schema enforces the parts a
schema can enforce; the tests defend them; the rest are producer obligations
that the envelope's basis fields make auditable.

### 1. `previous_observation_digest` is same-dataset history

It points at the immediately preceding observation **of the same `dataset_id`**.
It is never the attestation chain head, never `previous_chain_head`, never a
`dataset_links` aggregate, and never an observation of a different dataset.
The `observation:sha256:` namespace and the coupling that a digest requires
its `previous_observation_id` are the schema-level teeth; the same-dataset
scope itself is a producer obligation, auditable because the id names its
dataset. The cycle-wide aggregate lives separately in `cycle_root` and
`attestation_ref`.

### 2. `shape_fingerprint` is not a source-content digest

It is a value-insensitive structural summary — JSON keys and types, CSV
headers, archive member headers — produced by the `shape-v1` algorithm. Two
contents with identical shape but different values share a fingerprint. The
envelope carries the limitation as a constant string so it cannot be dropped
in presentation. Only `source_digest` speaks about content bytes, and only
when they were captured.

### 3. `source_digest` is asserted only for actually captured bytes

The schema requires `source_digest` to be null unless `capture_status` is
`captured`. A `partial` capture (for example a truncated transfer), a
metadata-only pass, a failed fetch, or no fetch at all cannot assert a
digest — a digest over anything other than the defined source bytes would
misrepresent the source. `capture_policy` records intent; `capture_status`
records outcome; a policy of `full_source_bytes` never licenses a digest when
the outcome was `partial`.

### 4. `source_identity` does not certify authority

`source_identity` records a value plus a basis: `declared_by_source`,
`independently_supported`, or `unknown`. Declared identity is what the source
says about itself; independently supported identity is what separate evidence
supports. Neither is a certification of authority, control, or authenticity,
and the envelope says so in a constant limitation string. Consumers needing
authority must establish it through their own trust decisions.

### 5. `verification_status` and `freshness_status` are different axes

`verification.verification_status` (`verified`, `unverified`, `failed`,
`unknown`) is cryptographic and procedural state: digests recomputed,
signatures checked. The health taxonomy (`fresh`, `aging`, `stale`, … in
`health.schema.json`) is a freshness classification. They must not be
conflated in either direction: a cryptographically verified observation can
carry hopelessly stale content, and a fresh classification says nothing about
whether any bytes were captured. The envelope deliberately carries no health
status at all. The only shared word between the vocabularies is `unknown`,
which honestly means "not established" on both axes.

### 6. Three times, kept separate

`source_content_date` is when the content says it happened (the vintage).
`retrieved_at` is when DataPulse pulled the bytes. `observed_at` is when
DataPulse filed the observation. None may be inferred from another: content
can claim any vintage regardless of retrieval time, and sealing an envelope
can happen after retrieval. Consumers computing staleness must say which
clock they are using.

## Additional binding members

These members are additive to the core observation fields, and each exists
for a reason:

- **`cycle_root`** — a Merkle-style commitment (`merkle-sha256`) over all
  observation digests retained in one cycle, so a third party can verify a
  single observation against one root without holding the set. Precedent: a
  central-bank research prototype for verifiable official statistics
  aggregates dataset fingerprints under Merkle proofs for exactly this
  third-party-verification-without-the-set property. Recording the root here
  is the contract; proof issuance is a later phase.
- **`contract_digest`, `superseded_by`, `invalidated_by`** — an observation's
  validity is bound to the digest of the code that produced it. A material
  change to that code produces a different `contract_digest` and invalidates
  prior verifications (via `invalidated_by`) rather than letting them persist
  silently; `superseded_by` tracks ordinary replacement by a newer
  observation. Precedent: a frontier AI vendor's component review is anchored
  to an exact commit, does not carry forward, and forces re-review on
  material change.
- **`declared` and `observed`** — what the source or contract declares, and
  what DataPulse actually observed, recorded as separate members with
  per-entry bases rather than inferred from one another. A declaration with
  no matching observation is visible as such, and vice versa.
- **`publisher_credential` and `verifier_credential`** — reserved and
  nullable, constrained to null in this phase, so publisher and verifier
  identity can later be expressed as standards-shaped credentials instead of
  bespoke fields. Populating them is a schema contract change, not a producer
  decision — reserved fields must not become unreviewed claim surface.
- **`replay_state`** — the explicit replay vocabulary below, referenced from
  the envelope.

## Replay state vocabulary

`replay_state` is one of: `replayable`, `metadata_only`, `partial`,
`incomparable`, `not_replayable`, `unknown`. It is a separate vocabulary from
the ten health statuses.

Two non-implication rules hold:

1. **A `fresh` health status does not imply `replayable`.** Freshness is about
   vintage classification; an observation can be classified fresh while
   retaining no bytes at all (`replay_state: metadata_only` or
   `not_replayable`).
2. **A `replayable` capture does not imply semantic truth.** Replay means the
   captured bytes can be re-obtained and checked against `source_digest`. It
   says nothing about whether the content is correct, complete, or honestly
   published by the upstream source.

The schema adds one load-bearing constraint: `replayable` requires
`capture_status: captured` and a non-null `source_digest`. No capture, no
replay claim.

## Declared versus observed

`declared.entries` and `observed.entries` are independent lists of
`{subject, value, basis}` records. Agreement between them is a finding a
consumer may check for, never a default the envelope asserts. The typed
members above (`source_version`, `source_identity`, capture members) remain
the canonical typed surface; these lists carry the declared/observed
distinction for everything else worth recording.

## What a consumer may conclude

From a schema-valid envelope, and only from the members that actually carry
values:

- a source was observed at `observed_request_url`, with the request completing
  at `retrieved_at`, and the observation filed at `observed_at`;
- the recorded `source_digest` — when present — is bound to exactly the bytes
  captured at that time, and those bytes were captured in full;
- `observation_digest` commits to this envelope's canonical form, and
  `cycle_root` commits to the set of observation digests for the cycle;
- when `replay_state` is `replayable`, the source content can be re-fetched
  and checked against `source_digest`;
- `previous_observation_digest` refers to the prior observation of the same
  dataset, enabling same-dataset change history via `change_from_previous`;
- the producing code is identified by `contract_digest`, so a verification is
  only as current as that digest;
- unknowns are explicit: members listed in `unknown_reasons` are not silently
  defaulted.

## What a consumer may not conclude

- that the content is fresh, authoritative, complete, or correct — freshness
  lives on the health axis, authority is never certified (rules 4 and 5);
- that a `verified` verification status implies anything about freshness or
  semantic truth;
- that a matching `shape_fingerprint` implies matching content (rule 2);
- that a `source_digest` exists for anything less than a full capture
  (rule 3);
- that `previous_observation_digest` or `attestation_ref` says anything about
  other datasets or the whole chain beyond what `cycle_root` commits to
  (rule 1);
- that `declared` entries are observations, or `observed` entries are
  declarations — they are never inferred from one another;
- that `replay_state` implies the ten-status taxonomy or vice versa (both
  non-implication rules).

Each envelope additionally carries its own `claim_boundary`, which must
state `may_conclude` and `may_not_conclude` for that specific observation.

## Validation and verification procedure

1. Validate against `historical-observation.schema.json` with a draft 2020-12
   validator (`Draft202012Validator`). Schema validity is the entry
   condition, not the conclusion.
2. Check the coupling rules held: unknowns are reasoned, digests match capture
   state, replay claims have captures, previous-digest has previous-id.
3. To verify one observation: recompute `observation_digest` over the
   canonical envelope; if the cycle set is available, check membership
   against `cycle_root`.
4. To verify currency: compare the envelope's `contract_digest` against the
   digest of the code you trust; a mismatch means the verification belongs to
   a different code contract (check `invalidated_by` / `superseded_by`).
5. Treat any failed, incomplete, or unsupported step as a bounded failure:
   the envelope supports weaker conclusions, not stronger ones.

A matching identifier without a matching digest is not sufficient. A valid
digest without a trustworthy source or policy is not sufficient. A valid
signature without semantic ground truth is not sufficient.

## Relationship to existing artifacts

- `health.schema.json` — the freshness/health axis. This envelope shares no
  status vocabulary with it beyond the word `unknown`.
- `record-evidence.schema.json` — per-record evidence for specific datasets;
  a separate contract that remains the compatibility authority for its
  surface.
- `.attestations/chain_head.json` — the signed daily aggregate chain.
  Observations reference it via `attestation_ref` and never borrow its
  digest values into same-dataset history.
- `scripts/shape_fingerprint.py` — defines the `shape-v1` fingerprint
  algorithm referenced by `shape_fingerprint.algorithm`.

## Change policy

This contract is versioned as `historical-observation/v1`. Adding a member or
opening a reserved member is a material change: it requires a new schema
version, a new `contract_digest` for consuming code, and explicit re-review —
prior verifications do not carry forward silently. Tightening a rule is
likewise a version change; loosening one requires operator sign-off because
it widens what the system can claim.
