# DataPulse MY / Engine trust-stack adoption specification

**Contract version:** `trust-stack/v1.0.0`

**Specification status:** accepted by operator on 2026-09-01; implementation gate authorized

**Date:** 2026-09-01

**Applies to:** DataPulse MY public trust layer and private Malaysia Data Engine consumers

## 1. Purpose and scope

This note is the single implementation contract for jointly adopting:

- #2 SetGo, arXiv:2607.22677, as a six-dimensional metadata-readiness profile;
- #3 ContextNest, arXiv:2607.02116, as governed, content-addressed context;
- #4 F(AI)²R, arXiv:2607.25637, as provenance for AI-in-loop activities, claims, and artifacts;
- #6 Attested Tool-Server Admission, arXiv:2605.24248, as signed, per-tool, fail-closed private-consumer admission; and
- #8 TrustShiftProbe, arXiv:2608.23763, as post-admission behavioural monitoring for staged server defection.

Together they form one evidence/context/provenance/admission/behaviour contract. They remain distinct control planes: metadata readiness does not grant admission; admission does not establish good behaviour; behaviour monitoring does not validate claims; and provenance does not establish truth.

The initial slice is specification and local contract/fixture work only. It does not change code, schemas, keys, generated artifacts, deployed services, or public surfaces. **Readiness, provenance, attestation, and behaviour signals do not establish semantic truth.** Public DataPulse remains free, read-only, and no-auth in the initial slice. Engine and other private consumers may enforce verification locally.

## 2. Current DataPulse/Engine boundary

DataPulse is the public, read-only trust layer. Its current contracts include `datapulse/v1/agent-manifest`, `datapulse/v1/mcp-advertisement`, and `record-evidence/v1`. The MCP advertisement fixes `auth_required` to `false`; every MCP tool has the four mandatory annotations `readOnlyHint`, `destructiveHint`, `idempotentHint`, and `openWorldHint`. The existing ten-status taxonomy remains unchanged.

The private Engine already produces and consumes local evidence and packaging artifacts. It may apply stricter local policy, including rejecting a context or tool call that the unauthenticated public endpoint still serves. Private policy, buyer state, and paid-product concerns do not become DataPulse public contracts.

Trust boundaries are:

1. **Upstream publisher → DataPulse probe:** upstream content and metadata are untrusted observations. Publisher identity, transport, content, and dates are evaluated separately.
2. **DataPulse producer → committed/local artifact:** deterministic generation and schema validation protect form; content digests protect bytes. Neither proves semantic correctness.
3. **DataPulse public transport → consumer:** TLS/reachability and optional signed envelopes are checked independently. The public endpoint performs no client authentication.
4. **Public artifact → Engine policy:** Engine treats every artifact, MCP description, model output, and response as untrusted until local validation and policy evaluation succeed.
5. **Admission → tool invocation:** clearance authorizes only the named server identity, exact tool, exact schema digest, and validity interval. It is not blanket server trust.
6. **Tool invocation → response use:** TrustShift monitoring is a separate post-admission control. A valid clearance never bypasses response validation or answerability checks.
7. **Automated evidence → human authority:** software may record a human decision but may not create, infer, or upgrade a human-verification rung.
8. **Trust-root configuration → verification:** the root is operator-controlled security configuration. Artifacts cannot self-authorize a new root.

## 3. Shared version policy and identifier rules

### 3.1 Envelope and object versions

Each companion artifact MUST be a JSON object with these common fields:

| Field | Requirement |
|---|---|
| `contract_version` | Exact string `trust-stack/v1.0.0`. |
| `object_type` | One of the five registered types below. |
| `object_id` | Stable identifier following section 3.2. |
| `subject_id` | Existing DataPulse dataset/server/tool identifier, or Engine-local identifier with an explicit namespace. |
| `created_at` | UTC RFC 3339 timestamp with `Z`; records observation/generation time, not truth time. |
| `producer` | Stable producer identifier and software/source version; no secrets. |
| `payload` | Type-specific object defined in sections 4–8. |
| `payload_digest` | `sha256:<64 lowercase hex>` over the contract's deterministic JSON serialization of `payload`. |

Registered `object_type` values and schema identifiers are:

| Object type | Schema identifier |
|---|---|
| `readiness_profile` | `https://data-pulse.my/schemas/trust-stack/v1/readiness-profile.json` |
| `governed_context` | `https://data-pulse.my/schemas/trust-stack/v1/governed-context.json` |
| `ai_provenance` | `https://data-pulse.my/schemas/trust-stack/v1/ai-provenance.json` |
| `tool_clearance` | `https://data-pulse.my/schemas/trust-stack/v1/tool-clearance.json` |
| `trustshift_observation` | `https://data-pulse.my/schemas/trust-stack/v1/trustshift-observation.json` |

These are reserved identifiers, not claims that the files or URLs already exist. The first implementation slice uses local schemas and fixtures; publication requires section 15's final gate.

Semantic versioning applies to this shared contract. Patch versions clarify or add non-normative fixtures. Minor versions add optional fields or enum members that old consumers may ignore. Major versions change required fields, digest inputs, identifier meaning, validation, or security decisions. Producers MUST emit one exact version; consumers MUST reject unsupported major versions and MUST NOT silently reinterpret them.

### 3.2 Identifier and digest rules

- Existing DataPulse dataset and MCP tool names remain authoritative; do not rename or normalize them.
- New IDs use `urn:datapulse:trust-stack:<object-type>:<sha256-hex>` where the suffix is the digest of the immutable identity fields defined by that object's schema. Engine-only IDs use `urn:malaysia-data-engine:trust-stack:<object-type>:<sha256-hex>`.
- Content addresses use `sha256:<64 lowercase hex>`, consistent with current evidence digests. Hashes are computed over UTF-8 deterministic JSON using the JSON Canonicalization Scheme (RFC 8785); schemas MUST list the exact included fields and exclude transport wrappers/signatures.
- URI comparison uses the parsed absolute URI after removing only a default port and normalizing the host to lowercase. Paths, queries, fragments, trailing slashes, and percent-encoding MUST NOT be silently rewritten.
- Timestamps are UTC RFC 3339 values. Policy comparisons use the consumer's trusted clock; clock uncertainty is explicit and fails closed where expiry cannot be decided.
- Object IDs are immutable. Corrections create new objects linked by `supersedes`; they never reuse an ID.
- Every cross-object reference carries both the referenced `object_id` and expected `payload_digest`. A matching ID without a matching digest fails validation.

### 3.3 Compatibility rules

The trust-stack artifacts are additive companions. They MUST NOT be inserted as unknown properties into current schemas whose `additionalProperties` is `false`. `record-evidence/v1`, the agent manifest, MCP advertisement, existing tool inputs/outputs, tool count, endpoint, and taxonomy remain byte/behaviour compatible unless a later, separately approved major/publication change says otherwise.

## 4. SetGo readiness profile contract

A `readiness_profile` assesses whether metadata is sufficient for a declared use. It does not rank truth or silently coerce missing evidence.

Required payload fields are `profile_id`, `subject`, `assessed_at`, `policy_id`, `dimensions`, `overall`, `evidence_refs`, and `limitations`. `dimensions` MUST contain exactly these six keys: `fair`, `licensing`, `provenance`, `governance`, `reproducibility`, and `catalogue_readiness`.

Each dimension contains:

- `state`: `pass`, `fail`, `unknown`, or `not_applicable`;
- `checks`: deterministically ordered check IDs with state and evidence references;
- `coverage`: count of evaluated checks over applicable checks;
- `reason_codes`: stable machine-readable codes; and
- `policy_basis`: the exact policy version used.

`unknown` means evidence is missing or cannot be evaluated. It MUST NOT be treated as pass, fail, zero, neutral, or `not_applicable`. `not_applicable` requires an explicit policy rule and reason. If a policy computes a score, unknown checks are excluded from the denominator and the result exposes coverage; a policy may still require full coverage and fail closed. The `overall` field is `ready`, `not_ready`, or `indeterminate`, derived only by the named policy. No global readiness threshold is embedded in this contract.

FAIR/DCAT/DQV/Croissant mappings provide evidence for checks but do not determine their outcome automatically. A profile points to immutable evidence digests and records contradictions rather than choosing the most favourable source.

## 5. ContextNest governed-context contract

A `governed_context` is an immutable, bounded selection of source nodes eligible for a declared consumption event at a declared point in time.

Required payload fields are:

- `context_version_id` and `context_digest`;
- `purpose` and `selection_policy_id`;
- `valid_at` (the point-in-time being reconstructed) and `assembled_at`;
- `source_nodes`, deterministically ordered by `source_node_id`;
- `previous_context_digest` (null only for a declared genesis);
- `checkpoint` containing chain position, previous digest, current digest, and checkpoint policy;
- `eligibility` with separate `approved`, `current`, `attributable`, and `integrity_verified` booleans plus evidence/reason codes;
- `consumption_trace`; and
- `limitations` and `conflicts`.

Each source node has a stable ID, source/publisher reference, content digest, observed time, asserted valid time if supplied, schema version, provenance reference, and selection decision. A source is eligible only if all four eligibility booleans are true under the declared policy. Unknown, stale, digest-mismatched, unattributable, or unapproved sources remain represented but are excluded from the selected context; private policy may reject the entire context.

Point-in-time reconstruction selects only source-node versions whose observation and validity intervals were available under the policy at `valid_at`; later corrections are linked but never backfilled into the historical view. Reconstruction MUST reproduce `context_digest` and checkpoint chain from the same inputs. A missing predecessor may be tolerated only when a trusted checkpoint explicitly bounds the verification start; otherwise verification fails closed.

`consumption_trace` records consumer, activity, context version, policy, decision time, and outcome. It is append-only evidence of what context was used, not proof that the resulting claim was correct.

## 6. F(AI)²R provenance contract

An `ai_provenance` payload is a PROV-style directed acyclic evidence graph with required `entities`, `activities`, `agents`, `claims`, `artifacts`, `edges`, `verification_assertions`, and `conflicts` arrays. Nodes and edges are deterministically ordered by ID.

Required node semantics are:

- `entity`: source data or immutable context, with digest and source reference;
- `activity`: a transformation, probe, selection, generation, model-assisted step, or review, with start/end time, software/model identity where applicable, parameters digest, and input/output links;
- `agent`: software, organization, or human actor. Human records use a non-secret stable reviewer reference;
- `claim`: an explicit proposition with scope and output artifact reference; and
- `artifact`: a generated immutable result with media type, schema, and digest.

Allowed edges map to PROV relations such as `used`, `wasGeneratedBy`, `wasAssociatedWith`, `wasAttributedTo`, `wasDerivedFrom`, and `supports`/`contradicts` as qualified domain relations. Every edge endpoint MUST exist.

The **no-parentless-claim invariant** is mandatory: every claim MUST link to at least one source entity or prior claim and to the generating activity; that activity MUST link to an attributed agent. Missing, cyclic, or digest-mismatched ancestry invalidates the graph. Conflicting parents are preserved and marked; they are not resolved by majority or provenance depth.

Verification is separate from generation. `verification_assertions` use `automated_check`, `human_reviewed`, or `human_verified`. Only an explicitly attributed human review activity may issue `human_reviewed` or `human_verified`; automation and models MUST never mint, infer, copy forward, or upgrade those rungs. A human rung proves that the identified reviewer made the recorded decision under the stated policy, not that the claim is objectively true.

## 7. Attested admission contract

A `tool_clearance` is a signed clearance assertion consumed by Engine/private clients. It is not required from callers of the public DataPulse endpoint and does not add public authentication.

The signed payload requires:

- `clearance_id`, `issuer_id`, and `trust_root_id`;
- `server_identity` containing exact endpoint identity, server name, server/source version, and advertisement digest;
- `issued_at`, `not_before`, `expires_at`, and monotonically comparable issuer `sequence`;
- `allowed_tools`, a non-empty deny-by-default list containing exact tool name, input-schema digest, annotation digest, and permitted read-only effect class;
- `policy_id` and `clearance_subject_digest`; and
- `supersedes` or explicit null.

No wildcard tool names, server identities, schemas, or effect classes are permitted in v1. A tool absent from `allowed_tools` is denied. A changed input schema or annotation digest is a different admission subject and is denied until separately cleared. Clearance does not authorize upstream writes, destructive behaviour, or tools contrary to DataPulse's read-only contract.

The transport envelope SHOULD be DSSE. Verification MUST use an already reviewed implementation and an operator-approved public trust root. Where the existing release path uses Sigstore, its normal bundle/Rekor verification may carry the DSSE/in-toto-style statement; this contract does not define a signature algorithm, certificate authority, log, key, or bespoke cryptography. SLSA claims may describe producer/build provenance but are not a substitute for the per-tool clearance payload.

Private admission order is fixed: parse with size limits → validate supported schema/contract version → resolve the configured `trust_root_id` from trusted local configuration → verify signature/bundle and transparency evidence required by policy → match server identity and advertisement digest → validate time window and trusted-clock tolerance → reject a lower/superseded issuer sequence → match exact tool/schema/annotations/effect → append a tamper-evident decision record → allow or deny. Any missing, ambiguous, invalid, expired, unavailable, or unsupported input fails closed.

Repeated presentation of the same still-current clearance is not itself malicious. It becomes a replay denial when it is expired, not-yet-valid, superseded, below the consumer's accepted issuer sequence, bound to a different server/advertisement/tool schema, or prohibited by policy. The local decision record contains no private keys or bearer secrets.

## 8. TrustShift monitoring contract

Admission is pre-use authorization; TrustShift/SHIELD monitoring is post-admission observation. A `trustshift_observation` payload requires `server_identity`, `tool_identity`, `baseline_policy_id`, `trust_window`, `baseline_digest`, `response_observation`, `signals`, `decision`, and `incident_ref`.

The policy, not this contract, defines the bounded benign trust-window sample count, duration, request fixture set, and tolerances. Baselines are scoped to exact server, tool, schema, clearance, and fixture cohort; they expire or are invalidated on an admitted schema/version change. Fingerprints contain deterministic structural shape/schema results, stable semantic invariants supplied by the fixture/policy, declared response scope, and bounded size/timing classes. Raw sensitive responses are not required in the fingerprint.

Signals are separately reported as `structural_mutation`, `semantic_invariant_violation`, `scope_expansion`, `schema_change`, `replay_pattern`, `availability_degradation`, or `benign_drift_candidate`, each with evidence and confidence/tolerance basis. The decision is `allow`, `quarantine`, `deny`, or `indeterminate`; security-relevant or unexplained mutation fails closed under Engine enforcement policy. Benign drift is never silently absorbed: it is quarantined or reviewed, then a new baseline is built only after the corresponding schema/clearance/policy change is accepted.

Staged-trust incident records link the accepted clearance, baseline, first divergent observation, later observations, decision, and response action. They must make the benign window followed by defection reconstructable.

Detection does not guarantee prevention, availability, or truth. Schema-valid deception may evade a ground-truth-free monitor. TrustShift signals can justify quarantine and investigation; they cannot establish semantic correctness and cannot retroactively make earlier responses true.

## 9. Evidence/authority model

| Signal | Can establish | Cannot establish |
|---|---|---|
| Publisher identity | The content or assertion is attributable to the identified publisher under the identity mechanism used. | That the publisher is authoritative for every field, honest, current, or correct. |
| Reachability/transport | An endpoint responded through the observed transport at a time, and TLS can authenticate the contacted endpoint under its PKI assumptions. | Stable availability, publisher identity beyond the transport credential, unchanged bytes, freshness, or truth. |
| Content integrity | Observed bytes match a digest or verified signed payload and have not changed relative to that commitment. | That committed bytes were correct, complete, lawfully published, fresh, or non-malicious. |
| Freshness/currentness | The observation/source dates satisfy a declared age/currentness policy, subject to clock and publisher-date quality. | Semantic correctness, completeness, or absence of a newer unobserved version. |
| Schema conformance | The object has the expected machine-readable structure, types, required fields, and allowed values. | Truth, sensible values, provenance validity, safe behaviour, or authorization. |
| Semantic correctness | A claim agrees with defined domain rules or reviewed ground truth within the tested scope. | Universal truth outside that scope, future correctness, publisher identity, or integrity unless separately checked. |
| Human verification | The identified human recorded the stated review decision under a named policy and evidence set. | Infallibility, independence, universal truth, or that later versions remain verified. |

Readiness, provenance, attestation, and behaviour are evidence signals, not semantic authority. Conflicting evidence remains explicit. Consumer policy states which authority is acceptable for a purpose; the producer does not promote itself by emitting more metadata.

## 10. Interoperability mapping

| Trust-stack concept | Interoperability choice | Boundary |
|---|---|---|
| Dataset/catalog identity and metadata | DCAT terms and stable DataPulse IDs | DCAT description is not a readiness verdict. |
| Quality observations | DQV measurements/annotations | DQV reports a measure; the named SetGo policy decides readiness. |
| Packaged dataset metadata | Croissant records/distributions | Croissant supplements rather than replaces DataPulse manifests and evidence. |
| Provenance graph | PROV-O entities, activities, agents, and qualified relations | F(AI)²R claim/artifact and verification-rung constraints are a profiled extension. |
| Object validation | JSON Schema Draft 2020-12 | Schema validation proves form only. Current `additionalProperties: false` contracts require companion artifacts rather than injection. |
| Tool discovery/invocation | MCP advertisement, exact tool name/input schema, and all four annotations | MCP discovery is not admission. DataPulse remains read-only/no-auth. |
| Signed statement envelope | DSSE with an existing reviewed implementation | No new signature design or algorithm is specified here. |
| Supply-chain statement | in-toto statement/predicate conventions and SLSA producer provenance where applicable | Build provenance is not per-tool behavioural clearance or semantic truth. |
| Identity/signing/transparency | Existing Sigstore bundle and Rekor verification where already approved | No implicit trust root, key creation, root migration, or claim that log inclusion proves truth. |

Implementations MUST preserve the native standard representation where one exists and add a namespaced DataPulse profile only for constraints absent from that standard. A mapping fixture MUST demonstrate lossless round-trip of IDs, digests, times, and relations. No implementation may label a proprietary look-alike as PROV-O, DCAT/DQV, Croissant, DSSE, in-toto, SLSA, Sigstore, Rekor, JSON Schema, or MCP.

## 11. DataPulse versus Engine responsibilities

| Responsibility | DataPulse | Engine/private consumer |
|---|---|---|
| Readiness | Deterministically derive additive profiles from public metadata/evidence; expose unknowns and conflicts. | Set use-specific thresholds and fail-closed policy without changing public scores. |
| Governed context | Produce immutable source nodes, versions, checkpoints, and reconstruction fixtures. | Verify chains and eligibility before use; record local consumption traces. |
| Provenance | Publish attributable provenance for DataPulse-generated claims/artifacts; never mint human rungs automatically. | Extend provenance through private transformations; preserve public ancestry; obtain real human assertions when required. |
| Admission | Define and locally fixture the clearance format; publish only after root/policy review. The public server does not authenticate callers. | Configure trusted public roots, verify assertions, enforce exact per-tool allowlists, and retain local decisions. |
| TrustShift | Supply deterministic mock/fixture responses if approved; do not attack or burden the live endpoint. | Establish bounded baselines, monitor actual private consumption, quarantine divergence, and investigate incidents. |
| Semantic decisions | Report observed evidence, uncertainty, and conflicts. | Apply domain policy/ground truth and human review for the private use case. |

DataPulse MUST NOT receive Engine secrets, buyer policy, private traces, or paid-product data merely to support this contract. Engine MUST NOT treat DataPulse publication as delegated private authorization.

## 12. Public no-auth/read-only backwards compatibility

The initial slice is strictly additive and local. Public DataPulse remains **free, read-only, and no-auth**. It keeps the existing endpoint, transport, methods, 16-tool surface, inputs, outputs, resources, taxonomy, and `auth_required: false`. Existing clients that know none of `trust-stack/v1.0.0` continue to operate unchanged.

No existing tool becomes conditional on clearance, no caller credential is requested, and no upstream write or destructive action is introduced. Any future public metadata exposure requires additive optional resources or a versioned new surface produced through canonical generators, with all four MCP annotations and existing tests preserved. It must not put new properties into closed v1 objects.

Engine/private consumers may require local verification before they invoke or rely on a public tool. That is consumer-side policy, not public endpoint authentication. If verification configuration is absent, an enforcing private consumer fails closed while the public service remains available to legacy clients.

## 13. Key custody and trust-root gates

This specification names verification fields but approves no trust root. `trust_root_id` is a reference resolved only from trusted, operator-controlled consumer configuration; a downloaded payload, MCP response, DSSE envelope, certificate, or transparency entry MUST NOT add or replace a root.

**Every implementation slice is explicitly prohibited from generating keys, rotating keys, accessing private keys, exporting private-key material, changing signer permissions, or mutating a trust root unless Redza separately approves that exact operation after review.** The prohibition includes convenient test/bootstrap calls against real key stores. Tests use inert unsigned negative fixtures or separately approved public test vectors; they do not create production-like key material in the repository.

Before any enforcement/publication involving signatures, a separate review MUST approve:

1. root owner, scope, public identifier/material, distribution channel, and custody boundary;
2. accepted DSSE/Sigstore verification profile, certificate identity constraints, Rekor/log policy, and trusted-clock policy;
3. issuance authorization, expiry maximum, sequence/supersession, compromise, revocation, rotation, overlap, and recovery procedures;
4. offline/unavailable-root behaviour, audit retention, emergency disable/rollback, and independent test vectors; and
5. exact DataPulse and Engine configuration changes.

Until all gates pass, clearance verification remains local fixture/placeholder mode and admission enforcement is not deployed. Missing, unknown, ambiguous, or unavailable roots fail closed for Engine enforcement; they do not cause the public endpoint to require auth or disappear.

## 14. Threat matrix and concrete test vectors

All fixtures use inert content, fixed timestamps, deterministic IDs, no network, and no key material. Each denial records a stable reason code and never silently falls back.

| # | Threat / vector | Expected result |
|---|---|---|
| 1 | **Stale context:** fix consumer time at `2026-09-01T00:00:00Z`; supply an otherwise valid source outside policy age and a context that marks it current. | Recompute eligibility, flag `stale_context`, exclude the node, fail closed when it is required, and preserve the claimed-versus-observed conflict. |
| 2 | **Forged metadata:** change a readiness licence/publisher field after `payload_digest` is fixed, and separately provide digest-consistent metadata from an unapproved publisher. | First fails integrity; second remains attributable only to the unapproved identity and fails authority/readiness policy. Neither is treated as truth. |
| 3 | **Missing provenance:** provide a claim with no source/prior-claim parent, then one with an activity but no attributed agent. | Reject both with `parentless_claim` or `unattributed_activity`; never infer ancestry or a human rung. |
| 4 | **Replayed/expired clearance:** present a clearance after `expires_at`; also present an older validly formed sequence after a superseding sequence was accepted. | Deny with `clearance_expired` and `clearance_superseded`; append decisions without invoking the tool. A duplicate current assertion remains idempotently valid if all policy checks pass. |
| 5 | **Unauthorized tool:** use a valid clearance for `tool_a` to request absent `tool_b`, and try a wildcard. | Deny with `tool_not_allowlisted`; reject wildcard clearance as schema/policy invalid. |
| 6 | **Changed schema:** keep tool name but change one input-schema property or mandatory MCP annotation so its digest differs. | Deny with `tool_contract_mismatch`; require new clearance and baseline, with no compatibility guess. |
| 7 | **Staged TrustShift:** return the fixed benign corpus through the trust window, then emit (a) added fields, (b) schema-valid reversed domain outcome, and (c) expanded record scope. | Establish the scoped baseline, then emit structural, semantic-invariant, and scope signals; quarantine/deny and link one staged incident. Detection is not reported as truth proof. |
| 8 | **Benign drift:** reorder JSON object keys and vary an explicitly tolerated timing class, then introduce an approved schema version. | Canonical key ordering causes no alert; tolerated timing is recorded; approved schema invalidates the old baseline and requires a reviewed new one rather than silent learning. |
| 9 | **Conflicting evidence:** give two integrity-valid, attributable sources with incompatible values and no approved precedence rule. | Preserve both with `conflicting_evidence`; readiness/context is `indeterminate` or denied according to policy. Do not pick newest, majority, or preferred answer implicitly. |
| 10 | **Unavailable root:** reference an unknown root and simulate configured-root lookup failure/clock uncertainty. | Fail closed with `trust_root_unavailable` or `trusted_time_unavailable`; make no network fallback, root import, tool call, or public-service change. |

Additional invariant tests MUST cover unsupported major versions, cross-object digest mismatch, broken/missing checkpoint predecessor, point-in-time reconstruction before a later correction, cycles in provenance, automated attempts to mint human rungs, wrong server identity, not-yet-valid clearance, malformed/oversized envelopes, deterministic serialization, and lossless standards mapping.

## 15. Minimal sequential implementation plan

The order is exact and deliberately non-parallel:

1. **Spec accepted.** Redza reviews and accepts `trust-stack/v1.0.0`, especially trust boundaries, identifiers, reason codes, compatibility, and key gates. No implementation proceeds from a draft.
2. **DataPulse local contracts.** Add only local JSON Schemas, deterministic serializers/validators, and synthetic fixtures for the five companion object types. Prove the ten vectors, digest determinism, closed-v1 separation, unchanged taxonomy, unchanged MCP advertisement/tool surface, and no key/network/runtime dependency. This is the first implementation slice. Do not publish generated artifacts.
3. **Engine local consumers.** Only after the accepted DataPulse contract/fixture handoff, add offline parsing, reconstruction, provenance validation, placeholder/root-config failure, exact allowlist evaluation, and mock TrustShift monitoring behind an explicit local opt-in policy. Preserve existing Engine behaviour when opt-in is disabled; enforcement mode fails closed when enabled.
4. **Independent verification.** A reviewer not responsible for the implementation reruns both repositories' focused/full tests, all negative vectors, deterministic rebuilds, changed-path checks, and compatibility assertions. The review separately confirms no key operation, public auth change, network probe, generated-public mutation, or semantic-truth overclaim.
5. **Separate publication decision.** Redza reviews the evidence, proposed public fields/resources, trust-root plan, privacy/retention, operational rollback, and served-state verification. Publication, enforcement, root configuration, deployment, service restart, commit, or push requires its own explicit authorization.

Exit criteria for the first slice are: five valid fixtures and their schemas; one invalid fixture per required threat vector; byte-identical repeated serialization; unsupported-version and cross-digest rejection; documented DataPulse→Engine fixture handoff; existing schema/taxonomy/MCP compatibility checks green; and a changed-path allowlist containing only approved local contract/test paths. No trust score, clearance, or baseline is publicly asserted.

## 16. Rollback and evidence requirements

Because the first two implementation slices are additive and local, rollback is removal/disablement of the new local companion-contract modules, fixtures, and Engine opt-in policy. Existing v1 artifacts and public MCP behaviour remain the fallback source. Consumers MUST ignore rather than partially interpret an unsupported companion major version, but an enforcing Engine MUST fail closed rather than bypass its own configured policy.

Before any later publication, preserve:

- accepted spec version and review decision;
- exact source commit/diff and strict changed-path inventory;
- schema validation and all positive/negative fixture results;
- repeated deterministic serialization/reconstruction results;
- compatibility evidence for existing manifests, `record-evidence/v1`, taxonomy, MCP tool count, schemas, annotations, and no-auth/read-only behaviour;
- standards round-trip evidence;
- independent security review and threat-vector results;
- approved public trust-root and key-operations decision, if signatures are in scope;
- privacy/retention decision for consumption/audit/incident traces; and
- pre-publication snapshot, feature/consumer-policy disable path, served-state checks, and rollback owner.

Rollback triggers include unexpected legacy-client breakage, changed public auth/read-only semantics, non-deterministic artifacts, false human-verification elevation, unverifiable ancestry, admission bypass, root ambiguity/unavailability beyond approved policy, unacceptable TrustShift false positives/negatives, leaked private Engine data, or any semantic-truth overclaim. On trigger: stop publication/enforcement, disable the additive consumer path, retain non-sensitive incident evidence, restore the last verified public surface through its canonical producer/deploy process, and require a new review. Do not delete or rewrite audit evidence to make a rollback appear clean.

## 17. Deferred work and non-goals

Deferred pending separate approval are public schema/resource publication, live MCP probing, admission enforcement, root selection/distribution, any key operation, real signed-clearance issuance, Rekor/log policy changes, public TrustShift telemetry, alerting/on-call integration, retention implementation, trust-root recovery exercises, and migration beyond `trust-stack/v1`.

Non-goals are:

- changing the ten-status taxonomy, existing health/evidence meaning, or closed v1 schemas;
- adding authentication, payment, caller identity, write tools, or upstream mutation to public DataPulse;
- turning DataPulse into a generic AI-trust platform, public chatbot, model evaluator, or semantic oracle;
- publishing private Engine policy, buyer state, traces, prompts, model output, or proprietary data;
- claiming FAIR/DCAT/DQV/Croissant/PROV/SLSA/Sigstore/Rekor/MCP conformance beyond tested mappings;
- inventing cryptography, self-authorizing roots, treating transparency inclusion as truth, or equating a signature with authorization;
- automatically resolving conflicting evidence, automatically granting human verification, or learning a security baseline from unexplained drift; and
- claiming that SetGo readiness, ContextNest integrity, F(AI)²R provenance, attested admission, or TrustShift monitoring proves semantic truth.
