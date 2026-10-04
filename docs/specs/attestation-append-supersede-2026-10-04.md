# Attestation append and supersede specification — 2026-10-04

## Scope and evidence boundary

This is an implementation specification, not an implemented migration. It permits a new signed envelope set for a UTC calendar day that already has a signed set, without replacing the earlier evidence or relaxing publication checks. Only this document is changed by this task.

Repository evidence was read locally in the supplied worktree at base commit `51fcf993b3` (`chore(health): update due dataset health (#522)`). Citations below are repository-relative `file:line` locations at that base. **Current** describes inspected source or artifacts; **Required** describes the proposed contract. Example identifiers such as `H2` are symbolic, not fabricated production hashes.

No HTTP surface, Actions log, external Rekor log, installed service, or signing key was read. Descriptions of served surfaces below mean **local workflow/client source inspection**, not a fresh live probe. The incident log supplied in the brief is operator-provided evidence; its run, merge, and exact timing were not independently retrieved. The recurring scheduled trigger is independently visible at `.github/workflows/datapulse-attest-daily.yml:5` (`17 3 * * *`). This is a schedule, not a guarantee that signing finishes at 03:17 UTC.

## Current failure and verified migration inputs

The supplied incident records:

```text
refresh_chain_head.sh: date 2026-10-04 dated attestation dir already exists; refreshing latest/chain-head from committed set (no re-sign)
refresh_chain_head.sh: refreshed chain head dataset_count (418) does not match canonical health (425)
##[error]Process completed with exit code 1.
```

The exact messages and refusal are supported by `scripts/refresh_chain_head.sh:33` and `scripts/refresh_chain_head.sh:52`. Its dated-set shortcut checks only directory/binding/head existence, copies four dated files to `latest/`, then mirrors the head and compares counts (`scripts/refresh_chain_head.sh:32`, `scripts/refresh_chain_head.sh:36`, `scripts/refresh_chain_head.sh:50`). It does not attempt generation on that branch. A missing key argument/environment value refuses even before this branch (`scripts/refresh_chain_head.sh:21`).

The generator has a stronger existing-set verification path but also enforces a single indexed head per date (`scripts/gen_attestations.py:148`, `scripts/gen_attestations.py:199`). It returns after reuse before loading new health/key inputs (`scripts/gen_attestations.py:268`). The current test explicitly expects different health and an unusable different key file to reuse the committed dated set (`scripts/tests/test_attestation_binding.py:149`). Therefore merely calling the generator from the shell shortcut would not implement supersession.

The daily workflow's envelope-generation step calls the same shell script (`.github/workflows/datapulse-attest-daily.yml:160`). It also has a separate Cosign witness step (`.github/workflows/datapulse-attest-daily.yml:68`); saying it performs no signing at all would be incorrect. It performs no independent Ed25519 envelope generation outside that script. The Pages workflow calls refresh before generating the DSSE statement (`.github/workflows/deploy-cloudflare-pages.yml:71`, `.github/workflows/deploy-cloudflare-pages.yml:86`), whose guard requires the legacy head count to match canonical health (`scripts/gen_sigstore_bundle.py:103`). Keep that guard.

Local artifact observations:

| Input | Observation and repository evidence |
|---|---|
| Canonical catalogue | 425 rows, counted from the `datasets` array at `datapulse.json:3`; existing refs can lag, e.g. `datapulse.json:5`. |
| Canonical health | 425 rows, counted independently; summary says 425 and observation time is `2026-10-04T04:10:42Z` (`health/latest.json:3`, `health/latest.json:6`). |
| Original October 4 head | Count 418; head `9a4376de7769d094ec3cc186a6d0e62130a13d728758a722197e7ad8018b1bf1`; predecessor is the October 3 head (`attestations/2026-10-04/chain_head.json:6`, `attestations/2026-10-04/chain_head.json:7`, `attestations/2026-10-04/chain_head.json:12`). |
| Original binding | Published `2026-10-04T03:20:20Z`, health count 418, observation `2026-10-04T03:05:39Z`, and dated head reference (`attestations/2026-10-04/binding.json:6`, `attestations/2026-10-04/binding.json:10`, `attestations/2026-10-04/binding.json:18`). |
| Discovery | Latest index points to the first October 4 set; chain index maps its hash to the original dated head (`attestations/latest/index.json:4`, `attestations/chain-index.json:27`). |

The brief's September 7 refusal is historical operator evidence. Its quoted refusal text was not found in this tree; do not attribute it to the current generator. A local historical note records an earlier served/source durability gap, but is not a current live measurement (`notes/2026-09-07-attestation-evidence-gap-investigation.md:26`).

## Envelope identity and signed ordering

**Required:** an envelope set is one complete head, per-dataset envelopes, index, binding, and score snapshot. Its primary identity is the head's existing lowercase SHA-256 `chain_head`, denoted `H`. Date is a UTC grouping label, not a unique identifier or sufficient ordering rule.

Preserve existing cryptography and payload schemas. Current canonical JSON and signing are at `scripts/gen_attestations.py:15` and `scripts/gen_attestations.py:21`. Current formulas at `scripts/gen_attestations.py:282` through `scripts/gen_attestations.py:284` are:

```text
dataset_link = SHA256(bytes.fromhex(parent_head) || canonical(dataset_payload))
H = SHA256(bytes.fromhex(parent_head) || canonical(head_payload))
head_payload.previous_chain_head = parent_head
dataset_payload.previous_chain_head = parent_head
head_payload.dataset_links_sha256 = SHA256(canonical(sorted_dataset_links))
```

Each superseding set uses the **current accepted global head**, not yesterday's head, as `previous_chain_head` in both its head and every dataset payload. If that parent has the same date, the child supersedes it for current-day publication. The next day's first set links to the last accepted superseding head. A second supersession links to the first supersession. Reusing yesterday's parent would create siblings, not a valid append.

Use these immutable locations:

```text
attestations/<day>/                         # first set; historical paths retained
attestations/<day>/revisions/<H>/            # second and later complete sets
  chain_head.json
  index.json
  binding.json
  scores.json
  <dataset_id>.json
```

Compute and verify the complete candidate before naming its final directory with `H`. The first set's paths remain unchanged. Each later index and binding carries its exact immutable references under its own revision directory. The binding's existing `ed25519.chain_head_ref` string changes value, not type or schema; it is already inside the signed binding payload (`scripts/gen_attestations.py:42`).

Ordering authority is the signed parent hash. A per-day sequence is derived for discovery: first set is 1, a same-day child is parent sequence + 1, a new day's first set is 1. Sequence is not added to any signed payload and is never accepted as evidence without checking parent linkage. Do not sort by publication time, JSON map insertion order, or highest filename. Dates cannot move backwards; preserve the existing older-day rejection (`scripts/gen_attestations.py:265`).

## Ledger immutability and publication boundary

**Invariant: nothing committed to the evidence ledger is ever rewritten or deleted, only appended.** Every existing dated envelope, dated index/binding/scores file, witness file, head-to-path mapping, and accepted ledger entry keeps its original bytes or value. Supersession changes what is current; it does not revoke the historical signature or erase the earlier claim.

Distinguish ledger from projections explicitly. `attestations/latest/*`, `.attestations/chain_head.json`, and the discovery document's current-head field are derived mutable views. Updating them in a new Git commit is necessary to implement `latest`; it is not permission to amend old commits or replace immutable evidence. A literal prohibition on changing *any* committed filename would make the requested latest semantics impossible. The existing code already rebuilds latest and mirrors the legacy pointer (`scripts/gen_attestations.py:288`, `scripts/refresh_chain_head.sh:50`). The proposed guarantee applies to committed evidence and append-only ledger entries, with only the named projections allowed to move.

An implementation gate must compare candidate against its accepted source revision: all pre-existing immutable paths remain byte-identical, every existing `heads`/envelope/anchor entry is retained, new immutable paths are additions, and current-head movement is a verified descendant append. Reject a deletion, mapping replacement, fork, incomplete set, or unexplained pointer rollback. Do not repair corrupt committed evidence by overwriting it.

Acceptance of an append and promotion of its views must share a compare-and-swap boundary: expected source revision plus expected parent head must still be current. The full accepted append must become durable in the authoritative Git source before it is advertised as current. Otherwise the next checkout can build a sibling from an older parent and the external verifier's source-parity claim cannot hold. Currently Pages signs with read-only repository permissions and copies generated evidence into an artifact, while the daily workflow commits through a PR (`.github/workflows/deploy-cloudflare-pages.yml:59`, `.github/workflows/deploy-cloudflare-pages.yml:145`, `.github/workflows/datapulse-attest-daily.yml:175`, `.github/workflows/datapulse-attest-daily.yml:259`). Extending that existing commit-back interface to accepted deploy appends is required implementation work; this spec neither grants additional write credentials nor performs a push.

## Chain index and latest semantics

**Required:** introduce `datapulse/v2/chain-index` at the existing `attestations/chain-index.json` path. Retain the existing `heads` hash-to-exact-head-path map and `anchors` map unchanged for old entries. Current production maps are visible at `attestations/chain-index.json:2`, `attestations/chain-index.json:3`, and `attestations/chain-index.json:29`.

The v2 document has these normative fields:

| Field | Meaning |
|---|---|
| `schema` | `datapulse/v2/chain-index`; declares new discovery semantics, not new signed head payloads. |
| `heads` | Append-only map `H -> immutable chain_head.json reference`; never remap an existing hash. |
| `anchors` | Existing Git tag/commit evidence; preserve historical entries and verify additions. |
| `envelopes` | Append-only map `H -> {date, sequence, parent_head, index_ref, binding_ref, scores_ref}`. Existing sets receive descriptors without changing their files. |
| `days` | Map UTC day to append-only ordered list of its accepted head hashes. First hash names the legacy root set; later hashes name revision sets. |
| `current_head` | One mutable selector `H`, advanced only when a complete descendant is accepted. |

The document is a discovery index, not a substitute for signatures. Verify every descriptor against the signed head and binding, actual files, exact path grammar, and derived sequence. Same-day multiplicity is valid only as one parent-linked run. Unknown schema, duplicate hash/path, missing parent, repeated hash, sibling heads, cycle, changed mapping, and inconsistent day lists fail closed in the accepted forward lineage. Upgrade legacy v1 by deriving descriptors only for entries whose referenced evidence verifies. Retain every original `heads` entry, including unresolved historical entries, but never promote an unresolved entry into a verified descriptor/day list or use it as evidence. A replay encountering one fails explicitly. Do not retroactively demand a single historical genesis chain: the current linearity verifier explicitly excludes such a historical guarantee (`scripts/verify_chain_linearity.py:2`). Establish the existing accepted October 4 head as the migration boundary and require every subsequent append to extend it; historical traversal gaps remain explicit.

A current verifier reads `current_head`, resolves `heads[H]` and `envelopes[H]`, verifies signatures, head/link digests, binding, and day sequence, then requires the four latest files to be byte-identical to that exact set. `.attestations/chain_head.json` must also mirror that head. Dataset refs come from that set's index, not from its date. For historical reads, find the containing head by its indexed immutable directory and verify membership; retain every superseded set as addressable evidence.

Current means exactly `H == current_head`. The terminal hash of `days[day]` is the selected head for that day; earlier entries are superseded for selection. Once a later day is current, the earlier day's terminal set is historical. No status field on an old envelope is edited. A head that verifies cryptographically is not necessarily the current head, and an unsigned index alone cannot prove that a reader has the freshest publication. Retain Git/served parity and freshness checks; readers can pin an accepted source revision/head to detect rollback.

Keep `datapulse/v1/attestation-index` and its existing field types. Its exact head/binding/dataset refs select one set. Keep `attestations/latest/{index,chain_head,binding,scores}.json` as the four-file projection, never a mixture of sets. Publish the chain index, immutable set, latest views, manifest refs, canonical health, and matching Sigstore inputs in one release artifact. Readers fetching across an artifact switch must reject inconsistent snapshots and may retry the read; they must not infer a successful append from partial files.

Old-verifier behaviour is a compatibility break in **path/discovery assumptions**, not in signature serialization:

| Existing consumer | Precise failure after a same-day append |
|---|---|
| `scripts/verify_external.py:275` | Reconstructs the old dataset path, then raises `latest attestation index: selected reference is not canonical` at `scripts/verify_external.py:277`. If only that check were updated, root/latest head parity would fail at `scripts/verify_external.py:289`. |
| `scripts/verify_attestation_binding.py:428` | The bound verifier first rejects the revision head ref as `Ed25519 binding does not match the latest daily head` (`scripts/verify_attestation_binding.py:432`). Its legacy-plane helper separately rejects the index ref as `latest attestation index is invalid` (`scripts/verify_attestation_binding.py:202`); date duplicate checks also reject two heads as `duplicate-date attestation ambiguity detected` (`scripts/verify_attestation_binding.py:384`, `scripts/verify_attestation_binding.py:443`). |
| `scripts/verify_chain_linearity.py:65` | Scans only root dated heads and raises `latest chain head does not match newest dated head` when latest is the child (`scripts/verify_chain_linearity.py:77`). |
| `mcp/server.py:2369` | Rejects revision refs as `Unknown dataset id or unsafe attestation reference`. If that regex alone were widened, replay still starts at the old root head and returns unsatisfied L2 membership (`mcp/server.py:2425`, `mcp/server.py:2429`). |
| `datapulse.schema.json:212` | Existing manifest validator rejects the revision `attestation_ref` regex; validation is performed at `scripts/verify_repository_contract.py:391`. |

Deploy upgraded consumers with the first append. Preserve historical paths; do not make old date URLs silently return new bytes to accommodate old verifiers.

## Required refresh behaviour by branch

The shell remains an orchestration entry point. `scripts/gen_attestations.py` owns construction, signing, set validation, index advancement, and projections. The current division is visible at `scripts/refresh_chain_head.sh:40`, `scripts/gen_attestations.py:262`. Avoid maintaining a weaker independent shell decision rule.

| Branch | Required outcome |
|---|---|
| Signing key absent | Refuse before modifying anything, preserving the current missing-key failure (`scripts/refresh_chain_head.sh:21`). An unreadable, malformed, mismatched, expired, inactive, or wrong-purpose key also refuses when signing is required; current signing checks are at `scripts/gen_attestations.py:271`. No unsigned fallback. |
| Day absent | Preserve first-of-day signing and root dated layout. Take the verified current global head as parent; generate the complete set, append its discovery entries, and publish projections. Current fresh generation uses previous latest and signs all datasets (`scripts/gen_attestations.py:277`, `scripts/gen_attestations.py:280`). |
| Day present; current selected set agrees | Validate the complete selected set and current key registry, then copy its four existing files byte-for-byte to latest and mirror the legacy head. No signing, timestamp refresh, new sequence, or witness upload merely because the deploy reran. This retains the no-re-sign outcome of `scripts/refresh_chain_head.sh:33`, now selecting the indexed revision instead of always the day root. |
| Day present; current selected set differs | Validate the old set as historical evidence, validate new canonical inputs and signing key, freeze the expected parent, construct and sign a complete same-day child under `revisions/<H>/`, then accept and advance views through the publication boundary. Do not require the old binding to match new health as a condition of verifying its historical integrity. |
| Day present but incomplete/corrupt/ambiguous | Refuse without moving latest, index, or legacy mirror. Directory existence is not proof of a complete set. Preserve incomplete/corrupt-set refusal tests, not the old duplicate-date blanket ban (`scripts/gen_attestations.py:161`, `scripts/tests/test_attestations.py:289`). |
| Attempted day older than current head | Refuse, retaining the current monotonic-day contract (`scripts/tests/test_attestation_binding.py:195`). Midnight during a candidate operation requires rechecking UTC day before acceptance; never mislabel a new day's append. |

Agreement is stronger than count equality: exact health byte digest, unique dataset ID set/hash/count, observed time, catalogue IDs and signed source URLs, head/index membership, and authorized signer identity must agree. Health binding already commits to exact bytes/IDs/time (`scripts/gen_attestations.py:23`); dataset payloads bind catalogue URL and observation fields (`scripts/gen_attestations.py:282`); the verifier requires the exact health claim (`scripts/verify_attestation_binding.py:467`). Compare catalogue signing inputs without treating generated `attestation_ref` values as new catalogue changes. Reuse still validates freshness; do not refresh `published_at` to conceal stale observations.

This necessarily supports changes to canonical health bytes even when the count remains equal. A count-only append trigger would miss dataset replacement, URL changes, or changed probe results and would still fail the exact binding contract. A newly available witness for an otherwise identical set is an explicit evidence upgrade, handled by an append rather than an edit; ordinary reruns without an upgrade reuse the selected set.

After either reuse or signing, retain the count check at `scripts/refresh_chain_head.sh:52` and the statement guard at `scripts/gen_sigstore_bundle.py:110`. Also verify ID-set agreement and the complete binding before exposing changed views. Generation must not leave a mismatched legacy mirror behind if a later validation fails; today the mirror is copied before the shell count guard (`scripts/refresh_chain_head.sh:50`).

## Consumer inventory: code, schemas, and published projections

Disposition means **must change**, **can stay as-is**, or **must be verified as tolerant** in the later implementation. This inventory includes direct readers and indirect consumers of their results. Repository-wide source searches covered scripts, workflows, MCP, schemas, and rendered-client inputs; generated evidence is not a second implementation.

| Consumer and evidence | Disposition and requirement |
|---|---|
| `scripts/gen_attestations.py:148`, `scripts/gen_attestations.py:218`, `scripts/gen_attestations.py:262` | **Must change:** select by index, replace reuse/duplicate-date bans with verified append logic, resolve manifest refs from the selected set, and publish transactionally. Its current direct-write helper is at `scripts/gen_attestations.py:19`. |
| `scripts/refresh_chain_head.sh:32`, `scripts/refresh_chain_head.sh:50` | **Must change:** implement the branch contract above through the generator, retaining missing-key and head-count checks. |
| `scripts/verify_external.py:167`, `scripts/verify_external.py:270` | **Must change:** validate explicit safe revision refs, discover selected immutable head, verify same-day chain selection, and compare served/source bytes at those refs. Retain parity and public-proof checks. No live surface was fetched for this spec. |
| `scripts/verify_attestation_binding.py:166`, `scripts/verify_attestation_binding.py:358`, `scripts/verify_attestation_binding.py:388` | **Must change:** both bound and unbound paths must accept only a validated linear multi-set day, exact selected refs and copies; preserve signatures, ID membership, freshness, health digest, key, and proof checks. |
| `scripts/verify_chain_linearity.py:50`, `scripts/verify_chain_linearity.py:75` | **Must change:** select the indexed terminal envelope and verify post-migration parent continuity, including same-day edges. Do not silently redefine historical guarantee. |
| `scripts/verify_attestation_plane_state.py:83`, `scripts/verify_attestation_plane_state.py:121` | **Must change:** date-derived fail-closed binding/head paths must resolve to the selected immutable set; corruption and signer-down classifications retain their current meanings. |
| `scripts/gen_sigstore_bundle.py:103`, `scripts/gen_sigstore_bundle.py:157` | **Can stay as-is:** existing payload/count guard and legacy pointer interface consume the selected mirrored head. No count bypass or predicate change. |
| `scripts/verify_sigstore_bundle.py:133`, `scripts/verify_sigstore_bundle.py:172` | **Can stay as-is:** regenerates the exact statement from supplied canonical inputs; keep parity and signature/proof verification. |
| `scripts/verify_release_invariants.sh:143`, `scripts/verify_release_invariants.sh:164`, `scripts/verify_release_invariants.sh:288` | **Must change:** fetch selected immutable refs and required discovery ancestry; replace date-root assertion. Its Rekor regex currently accepts only files directly under `attestations/<day>/` (`scripts/verify_release_invariants.sh:168`), unlike the committed `attestations/rekor/<day>/` evidence. Correct the fetch validator without moving witness paths or weakening proof checks. |
| `scripts/verify_agent_ready.sh:158`, `scripts/verify_agent_ready.sh:171` | **Must be verified as tolerant:** uses index-selected first ref and current schemas/counts, not a reconstructed date path. Exercise a revision fixture. |
| `scripts/verify_local_public_parity.py:233` | **Must be verified as tolerant:** checks latest head subject presence, not dated layout; retain that limited claim, do not treat it as chain validation. |
| `scripts/verify_served_release.sh:157` | **Must be verified as tolerant:** supplies sign-time publication head and signed manifest to bundle verification. Same-day selected bytes must survive assembly. Observation-receipt checks at `scripts/verify_served_release.sh:126` concern a different chain. |
| `scripts/embed_dashboard_data.py:459`, `scripts/embed_dashboard_data.py:660` | **Must be verified as tolerant:** uses latest map and strict contract results; upgraded verifier must validate revision sets, and the renderer must retain false claims when validation fails. UI links use map refs (`scripts/embed_dashboard_data.py:483`). |
| `scripts/gen_dataset_passports.py:158`, `scripts/gen_dataset_passports.py:190` | **Must be verified as tolerant:** passes through the selected chain reference and attestation map, including longer paths. |
| `scripts/gen_quality_profile.py:172` | **Can stay as-is:** checks declared manifest reference availability and explicitly does not verify it. |
| `datapulse.schema.json:210`, `scripts/verify_repository_contract.py:391` | **Must change schema path grammar:** retain legacy refs and allow only the exact `<day>/revisions/<64 lowercase hex>/<safe dataset id>.json` form. The validator can stay as-is after schema update; do not allow arbitrary nesting/traversal. |
| `mcp/server.py:970`, `mcp/server.py:2333`, `mcp/server.py:2674` | **Must be verified as tolerant:** latest loader, trust verdict, and attestation resource already read latest index/head/scores and pass through map refs. Preserve schemas and test coherent sets. |
| `mcp/server.py:2367`, `mcp/server.py:2424` | **Must change:** safe-ref grammar and L2 containing-head selection. Replay the exact envelope's indexed head before following hash-map parents; a historical explicit ref must not be forced into the current day's terminal set. |
| `mcp/server.py:2378`, `mcp/server.py:2390` | **Can stay as-is:** head signature/hash algorithm and Git-tag legacy anchor comparison remain valid for same-date parent edges. Verify traversal budgets with the longer chain (`mcp/server.py:2439`). |
| `scripts/attestation_commit_back.py:11` | **Must be verified as tolerant:** its dated-prefix test includes nested revision files already; add nested-path coverage. |
| `scripts/classify_change.py:36`, `scripts/classify_change.py:51` | **Can stay as-is:** new dated revisions/chain-index paths remain outside the health-only output allowlist, so committed append changes take the full release route. Do not broaden it just to avoid signing. |
| `scripts/generate.sh:111`, `scripts/generate.sh:154`, `scripts/generate.sh:324` | **Must change its output contract description** at `scripts/generate.sh:127` and `scripts/generate.sh:187`; **must verify** both generator profiles select/reuse exactly the accepted append. Retain key boundary and generation call. |
| `scripts/verify_release_reproducible.py:453` | **Must be verified as tolerant:** indirect consumer runs release-build twice. Both builds must reuse accepted set bytes, not independently append or mint new publication timestamps. |
| `scripts/verify_attestation_workflow_contract.py:17`, `scripts/verify_attestation_workflow_contract.py:96` | **Must change/add invariants:** retain canonical DSSE arguments, key and signer boundaries; assert shared writer coordination, digest-aware witness reuse, and immutable append publication. |
| `scripts/sigstore_rekor_publisher.py:310`, `scripts/sigstore_rekor_publisher.py:373` | **Can stay as-is:** additive publisher operates on `health-<digest>` and caller-selected output refs, not date uniqueness. Preserve no-clobber and ambiguity handling. |
| `scripts/observation_evidence_link.py:252`, `historical-observation.schema.json:207` | **Can stay as-is:** opaque aggregate attestation ref passes through; no date regex. Observation capture initializes unresolved refs (`scripts/observation_capture.py:684`); it does not resolve this ledger. |
| `scripts/observation_receipt.py:599`, `scripts/observation_verify.py:76` | **Can stay as-is:** separate observation-receipt chain, not consumers of this attestation head despite similarly named files. |
| `scripts/run_openwiki_snapshot.sh:17` | **Can stay as-is:** excludes latest generated evidence from a wiki snapshot; it is an indexing filter, not a trust verifier. |

## Consumer inventory: workflow and release boundaries

| Consumer and evidence | Disposition and requirement |
|---|---|
| `.github/workflows/deploy-cloudflare-pages.yml:71` | **Must change coordination/durability interface:** refresh selects or appends through the authoritative writer; full releases use exactly that accepted set. Existing production concurrency at `.github/workflows/deploy-cloudflare-pages.yml:22` serializes this workflow, not the separate daily workflow. |
| `.github/workflows/deploy-cloudflare-pages.yml:137`, `.github/workflows/deploy-cloudflare-pages.yml:145` | **Must be verified as tolerant:** sign-time head/manifest/evidence-tree packaging supports nested files. Ensure the accepted current selector and all referenced immutable evidence are included. |
| `.github/workflows/deploy-cloudflare-pages.yml:386` through `.github/workflows/deploy-cloudflare-pages.yml:405` | **Must change:** preservation fetches must resolve indexed revision refs and necessary ancestry; root-path assertions and dataset regex are incompatible. Existing same-day Rekor sibling-file regex can tolerate digest-named files. |
| `.github/workflows/deploy-cloudflare-pages.yml:314`, `.github/workflows/deploy-cloudflare-pages.yml:443`, `.github/workflows/deploy-cloudflare-pages.yml:454` | **Must change full-path set handoff/verify assembly:** isolated release-build and sign-time build must reuse identical accepted bytes. Currently sign-time evidence overwrites assembly only on the signed health-only path; it must not leave a full release serving a different generated append from its signed head. |
| `.github/workflows/datapulse-attest-daily.yml:40`, `.github/workflows/datapulse-attest-daily.yml:78`, `.github/workflows/datapulse-attest-daily.yml:163` | **Must change:** shared writer serialization, digest-aware witness selection, and prepare-head-before-DSSE ordering. A changed-count prior committed head cannot pass the statement guard used before today's refresh. |
| `.github/workflows/datapulse-attest-daily.yml:182`, `.github/workflows/datapulse-attest-daily.yml:233`, `.github/workflows/datapulse-attest-daily.yml:242` | **Must change publication checks:** nested paths fit its prefixes already, but accepted-parent CAS and append-only diff checks are required. Rebase alone does not validate a signed parent. Per-day branch replacement at `.github/workflows/datapulse-attest-daily.yml:225` and `.github/workflows/datapulse-attest-daily.yml:247` must not discard a concurrent accepted append. Latest scores/manifest are deliberately excluded at `.github/workflows/datapulse-attest-daily.yml:210`; preserve ownership while deriving them from the selected immutable set in the release artifact. |
| `.github/workflows/anchor-release-attestation.yml:35`, `.github/workflows/anchor-release-attestation.yml:47` | **Must be verified as tolerant:** fetches served latest and stamps legacy pointer. Validate the selected accepted hash/source revision before anchoring; do not fall back to a date-root head. Surface described from local workflow source only. |
| `.github/workflows/release-please.yml:97` | **Can stay as-is:** release anchor reads the tagged legacy pointer's exact hash. No additional date ordering assumption here. |
| `.github/workflows/ci.yml:130`, `.github/workflows/ci.yml:142`, `.github/workflows/ci.yml:179` | **Can stay as-is as gate entry points:** upgraded workflow-contract and linearity verifiers must still run and fail on invalid appends. No silencing deterministic-safety-net failures. |

## Consumer inventory: tests and compatibility assertions

| Existing test consumer | Disposition for implementation |
|---|---|
| `scripts/tests/test_attestations.py:108`, `scripts/tests/test_attestations.py:235`, `scripts/tests/test_attestations.py:242` | **Keep existing first-day/signature/next-day tests; add** same-day signed child and next-day-after-child tests. Existing payload cryptography must remain valid. |
| `scripts/tests/test_attestations.py:248`, `scripts/tests/test_attestations.py:269`, `scripts/tests/test_attestations.py:298` | **Must extend:** selected revision manifest-ref repair and corrupt/forked-index cases. Duplicate mapping to the same root is still invalid; a verified linear second head is valid. |
| `scripts/tests/test_attestation_binding.py:133`, `scripts/tests/test_attestation_binding.py:149`, `scripts/tests/test_attestation_binding.py:276` | **Must change assumptions:** exact-input rerun remains byte-idempotent; changed health/key cannot blindly reuse; blanket duplicate-date rejection becomes invalid-parent/fork/mapping rejection. Preserve corruption and backwards-day tests at `scripts/tests/test_attestation_binding.py:169` and `scripts/tests/test_attestation_binding.py:195`. |
| `scripts/tests/test_attestation_binding.py:365`, `scripts/tests/test_attestation_binding.py:421` | **Must change expectations:** valid requested witness upgrade appends while preserving old binding; invalid requested evidence refuses and never becomes a true claim. Old bytes stay immutable. |
| `scripts/tests/test_refresh_chain_head.sh:50`, `scripts/tests/test_refresh_chain_head.sh:62`, `scripts/tests/test_refresh_chain_head.sh:71` | **Must change mismatch case:** valid mismatched canonical inputs invoke append/sign, then pass unchanged guard. Retain equal-input no-sign and day-absent cases; add missing-key, equal-count ID/URL changes, bad key, partial-set, and post-validation failure cases. |
| `scripts/tests/test_verify_chain_linearity.py:25`, `scripts/tests/test_verify_attestation_plane_state.py:50` | **Must extend:** selected revision head and binding, next-day parent, stale/signer-down handling, and rejection of fork/rollback/mixed projections. |
| `scripts/tests/test_attestation_rekor_wiring.py:29`, `scripts/tests/test_attestation_rekor_wiring.py:160` | **Must change existence-only witness guard assertions:** same date/different digest witnesses again, exact evidence rerun reuses, missing/invalid proof refuses claims. Retain proof-binding tests at `scripts/tests/test_attestation_rekor_wiring.py:44`. |
| `mcp/tests/test_server.py:264`, `mcp/tests/test_server.py:270` | **Must extend:** first-set and revision safe refs, historical containing-head membership, same-day L2 replay, source anchor and budget outcomes. |
| `scripts/tests/test_deploy_cloudflare_pages_contract.py:586`, `scripts/tests/test_deploy_cloudflare_pages_contract.py:863`, `scripts/tests/test_workflow_rewire.py:415` | **Must change/add:** exact revision fetch grammar, sign/assemble same-head handoff, preserved-plane ancestry and full-release durability. Retain missing-key refusal at `scripts/tests/test_deploy_cloudflare_pages_contract.py:921`. |
| `scripts/tests/test_verify_attestation_workflow_contract.py:1` | **Must extend:** coordination, head preparation order, digest guard and append-only acceptance invariants. |
| `scripts/tests/test_attestation_commit_back.py:12`, `scripts/tests/test_classify_change.py:30` | **Must be verified as tolerant:** nested revisions trigger commit selection and full release classification; retain existing latest-only/health-output distinctions. |
| `scripts/tests/test_gen_sigstore_bundle.py:26`, `scripts/tests/test_verify_sigstore_bundle.py:22` | **Must be verified as tolerant:** new mirrored head with unchanged v1 payload passes; 418 head with 425 health still fails. |
| `scripts/tests/test_verify_agent_ready.sh:47`, `scripts/tests/test_gen_dataset_passports.py:25`, `scripts/tests/test_gen_quality_profile.py:43` | **Must be verified as tolerant:** selected revision refs retain discoverability and projection shape. |
| `scripts/tests/test_embed_dashboard_data.py:157`, `scripts/tests/test_dashboard.py:167` | **Must be verified as tolerant:** revision fixtures preserve verification claims and exact proof links; no false signed state for a mixed set. |
| `scripts/tests/test_release_invariant_retry.py:189`, `scripts/tests/test_website_publisher_retirement.py:55` | **Must be verified as tolerant:** existing missing-binding/fail-closed publication handling must remain intact after ref resolution changes. |
| `scripts/tests/test_historical_observation_schema.py:64`, `scripts/tests/test_validate_historical_observation.py:36`, `scripts/tests/test_observation_receipt.py:639` | **Can stay as-is:** opaque old attestation refs and separate receipt-chain fixtures do not assert this ledger's one-set-per-day model. |

The standalone external verifier's offline self-test is at `scripts/verify_external.py:300`; keep it and add explicit revision/discovery/parity cases in the implementation. No standalone external-verifier test file was found in the scoped source inventory. Generic Sigstore publisher tests concern unchanged witness transport; the new digest-aware workflow tests must exercise its interface without live uploads.

## Migration of the committed October 4 set

Let `H1` be `9a4376de7769d094ec3cc186a6d0e62130a13d728758a722197e7ad8018b1bf1` from `attestations/2026-10-04/chain_head.json:12`.

1. Verify the complete existing dated set and original signatures as historical evidence. Retain all its bytes, original head mapping, and original witness references (`attestations/2026-10-04/binding.json:30`). Do not try to make its 418-dataset health claim match the 425-dataset current health.
2. Bootstrap v2 discovery from verified existing v1 entries without re-signing any old envelope. Preserve unresolved historical mappings without asserting they verify. October 4's original entry is sequence 1; establish `H1` as the accepted forward boundary.
3. Freeze current canonical 425-dataset health and catalogue signing inputs. Sign a complete sequence-2 set with `previous_chain_head = H1`, including all 425 datasets rather than only the seven additions. Its new head is `H2`; write only new immutable files under `attestations/2026-10-04/revisions/<H2>/`. Its binding commits to current exact health digest and points to its own head. Never reuse the earlier 418-dataset witness as evidence for this health.
4. Accept the child by CAS, append both discovery and any new witness evidence, and atomically publish its latest projections, manifest refs, health and verified DSSE inputs. The legacy mirror now contains `H2` and count 425. Both count guards still run. No wait for October 5 is involved.

Before promotion, readers see the prior coherent release; a checkout already containing new health and old binding remains detectably inconsistent and must not be published as verified. During preparation, unreferenced candidates are not current. After promotion, upgraded readers select `H2`, can replay `H2 -> H1 -> October 3`, and can still fetch `H1` by its original URL. Old verifiers fail as named above. During an HTTP artifact switch, mixed reads fail closed and retry against one accepted revision; the design promises consistency detection, not multi-request HTTP transactions.

Keep historical anchor mappings. A read-only audit of all 24 indexed head files verified head-payload and dataset-link digests, but returned exit 1 because the August 15 map key at `attestations/chain-index.json:4` does not equal the head in its referenced file at `attestations/2026-08-15/chain_head.json:12`. This is a verified pre-existing discovery inconsistency, not a signature-verification result; the audit did not verify signatures. Preserve that mapping and file, report the unresolved historical entry, and refuse replay evidence through that mapping. Correcting historical discovery is a separately scoped reconciliation, not a prerequisite to accepting a verified descendant of `H1`. Neither this migration nor a new same-day edge repairs pre-existing missing historical ancestry; replay must report such a gap instead of inventing an anchor. The first append is an additional claim at 425 datasets, not a correction to the earlier signature at 418 datasets.

## Failure modes, concurrency, and idempotency

| Situation | Required behaviour |
|---|---|
| Two deploys for the same day | Serialize the attestation-producing/publication work of daily and Pages workflows through one shared non-canceling writer lane, using the existing production coordination mechanism where possible. Local concurrent invocations also require a repository-scoped exclusive writer lock. Recheck accepted source revision/head and canonical input snapshot at acceptance; a filesystem lock alone cannot coordinate different runners. |
| Same parent; competing candidates | Only one child can be accepted. A loser with identical inputs adopts the accepted bytes after full validation; a loser with still-needed different inputs recomputes from the winner as parent. Never merge sibling entries, blindly rebase a signed child, force a stale pointer, or overwrite a candidate with the same final hash and different bytes. Unaccepted losing candidates are not advertised ledger entries. |
| Rerun after a successful append | Resolve indexed current revision and compare its signed health/catalogue/key/evidence inputs. Copy accepted bytes; do not append because the clock changed. Do not regenerate scores or binding timestamps inside that immutable set. Determinism is for frozen inputs and accepted bytes, not arbitrary execution times; current generation uses `now` in probe windows/publication time (`scripts/gen_attestations.py:276`, `scripts/gen_attestations.py:281`). |
| Signing/validation fails after partial write | Prepare in an unadvertised temporary location; verify all signatures, links, refs, binding, evidence and counts before no-clobber installation and pointer movement. Discard only uncommitted temporary work owned by that attempt. A partial committed set is corruption and requires explicit reconciliation; never fill or replace committed bytes automatically. Current writes are not transactional (`scripts/gen_attestations.py:19`, `scripts/gen_attestations.py:283`). |
| Complete set installed; pointers not advanced | On recovery, validate candidate inputs/parent and all bytes, then finish the same acceptance only if expected parent remains current. No fresh signature or second sequence for the same accepted request. A commit/artifact publication failure leaves old current views in service. |
| Key unavailable or invalid | Refuse append and publication requiring it. Reuse cannot conceal changed inputs. No key rotation/provisioning fallback and no weakened guard. |
| Health/catalogue changes while preparing | Abort acceptance and prepare from the new canonical snapshot. Check signed manifest identity and exact health bytes again at promotion; do not combine the old signature with new data. |
| Invalid discovery or historical set | Fail closed. A superseding head is not a repair mechanism for corrupted old signatures, substituted paths, missing parent, or a fork. |
| Later day attempts to reuse a stale root | Select the current terminal hash, including revisions, as predecessor. Verify that next-day append extends it; date ordering alone is insufficient. |

Shared workflow concurrency is necessary but insufficient: accepted source lineage and exact-byte handoff are still required. The current Pages lane exists (`.github/workflows/deploy-cloudflare-pages.yml:22`), but daily starts a separate job without that concurrency declaration (`.github/workflows/datapulse-attest-daily.yml:13`). No cross-workflow/source CAS guarantee was established in this tree.

## Rekor witnessing for repeated days

**Keep the witness path and trust mechanism:** public Sigstore/Cosign DSSE over canonical health, existing workflow identities/OIDC issuer, subject digest, inclusion verification, and `DATAPULSE_REKOR_REFERENCE` remain the interface (`.github/workflows/datapulse-attest-daily.yml:84`, `.github/workflows/datapulse-attest-daily.yml:90`, `.github/workflows/datapulse-attest-daily.yml:95`, `scripts/verify_attestation_binding.py:301`). This is not a new transparency service, a private-log migration, or a signature-algorithm change.

Keep the storage namespace `attestations/rekor/<day>/`. Existing `reference.json`, `health.statement.json`, and `health.sigstore.bundle.json` stay immutable. For an additional distinct witnessed statement, append sibling files:

```text
attestations/rekor/<day>/health.<statement_sha256>.statement.json
attestations/rekor/<day>/health.<statement_sha256>.sigstore.bundle.json
attestations/rekor/<day>/reference.<statement_sha256>.json
```

Here `statement_sha256` hashes the exact generated statement bytes, including its existing legacy head, signed-manifest digest and source commit fields (`scripts/gen_sigstore_bundle.py:151`, `scripts/gen_sigstore_bundle.py:153`, `scripts/gen_sigstore_bundle.py:157`). It distinguishes proofs even when health bytes are unchanged but statement inputs differ. Keep reference schema and `run_id = health-<health_digest>` unchanged (`scripts/verify_attestation_binding.py:301`). The binding points to the exact new reference and bundle; no date-global file is overwritten. Sibling digest filenames already fit the Pages witness fetch grammar (`.github/workflows/deploy-cloudflare-pages.yml:403`). This is additive storage in the existing witness path, not relocation of old proof URLs.

Change the guard from file existence to verified artifact/statement identity. Currently nonempty same-day reference/bundle files skip upload without checking digest and the missing-evidence branch deletes the day directory (`.github/workflows/datapulse-attest-daily.yml:46`, `.github/workflows/datapulse-attest-daily.yml:54`). The new guard must retain existing evidence, reuse an exact verified witness if present, and witness a new distinct statement once. A 418-dataset proof cannot witness the new 425-dataset health; current proof validation already rejects wrong digest (`scripts/verify_attestation_binding.py:304`, `scripts/verify_attestation_binding.py:318`).

Head construction must precede statement generation when the count changes. Prepare the new Ed25519 head/set privately, expose its validated candidate through the unchanged legacy-head argument, generate and verify DSSE, then sign the final binding with that witness before accepting the complete set. Do not publish an intermediate binding or regenerate the head in release-build. This resolves the current daily ordering problem where DSSE generation consumes the prior head before refresh (`.github/workflows/datapulse-attest-daily.yml:78`, `.github/workflows/datapulse-attest-daily.yml:163`). Only this prepare/accept artifact interface is specified; staging-environment architecture is a non-goal.

A same-day second witness is another immutable proof for its own statement/health digest, not replacement of the first log entry. Exact reruns reuse verified proof bytes. If an upload outcome is ambiguous, preserve available evidence and reconcile before any repeat upload; do not assert exactly-once external insertion. The generic publisher already distinguishes ambiguity and operator reconciliation (`scripts/sigstore_rekor_publisher.py:83`, `scripts/sigstore_rekor_publisher.py:355`) and uses no-clobber creation (`scripts/sigstore_rekor_publisher.py:238`). Actual public Rekor duplicate-response behaviour was not exercised; it is an implementation integration-test gap, not an assumed API guarantee.

Retain the existing trust-policy boundaries. A supplied proof must verify before its claim is true (`scripts/gen_attestations.py:59`, `scripts/verify_attestation_binding.py:477`). An unwitnessed binding remains honestly unwitnessed; the classifier requires verified signing evidence for a healthy current plane (`scripts/verify_attestation_plane_state.py:152`). Full-release signed evidence remains required. This design does not expand signer-down allowances or let an optional daily witness failure authorize a verified full release.

## Contracts that must not change

Preserve the existing probe/head/binding signed payload schemas, canonical JSON bytes, Ed25519 signature algorithm, head/link hash formulas, field types, and `source_truth_verified: false`. Existing payload construction is at `scripts/gen_attestations.py:42`, `scripts/gen_attestations.py:282`, `scripts/gen_attestations.py:284`; proof claims are checked at `scripts/verify_attestation_binding.py:480`. Supersession uses existing signed `previous_chain_head`; no sequence field, extra payload salt, or renamed hash is needed. A new discovery schema and stricter path validation are explicit compatibility changes, not permission to change signed payload shape.

Preserve key provisioning, secret/environment interface, ephemeral-file handling, registry purpose/status/validity checks and existing key identity. Do not generate, rotate, print, commit or persist private keys as part of append logic. Current provisioning and cleanup are at `.github/workflows/datapulse-attest-daily.yml:26`, `.github/workflows/datapulse-attest-daily.yml:165`; signing authorization is at `scripts/gen_attestations.py:272`. Signing-key absence remains refusal, including when a dated set exists.

Preserve Rekor witness mechanism, verification requirements, workflow identity, health subject, existing proof URLs and namespace. Append new proof files when necessary; never point an old binding at replacement proof bytes. Preserve dataset-count/ID/digest/freshness checks, deterministic-safety-net, read-only upstream posture, release tag anchors, and the evidence immutability invariant. Do not bypass a check to make October 4 publishable.

## Implementation acceptance and unresolved evidence

The later implementation must demonstrate these behaviours with isolated fixtures, without production signing or witness uploads:

1. Start with a valid October 4-shaped 418-dataset set and matching old witness. Move canonical catalogue/health to 425 datasets; append a valid same-day child, keep all original evidence bytes, and pass existing count guards with the selected 425 head.
2. Replay signed `H2 -> H1`, then append October 5 from `H2`. All head/dataset/binding signatures, membership, exact health binding and selected refs verify. Old explicit refs still verify as historical evidence.
3. Same-day exact rerun changes no immutable bytes or index entries; equal-count ID/URL/health changes append rather than silently reuse. Evidence upgrade appends; invalid proof/key refuses.
4. Competing identical and different candidates produce one accepted linear history through CAS. Fault injection at file/signing/index/view/commit/artifact boundaries never exposes a partial current set or rewrites committed evidence.
5. Two witnessed statements in one day retain both proofs and references; exact witness rerun reuses; ambiguous external outcome does not trigger blind upload. Existing DSSE predicate and proof validation remain intact.
6. Current external, MCP, schema, release, dashboard, passport, preservation and linearity consumers accept revision refs and reject unsafe refs, forks, pointer rollback, mismatched binding, stale health, and mixed projections. Old-verifier failures match the compatibility table.
7. Both isolated release-build passes reuse identical accepted bytes; sign-time head, signed manifest, served artifact and authoritative Git revision agree. Run focused attestation/workflow tests, the full deterministic-safety-net and required release invariants when implementing. Preserve complete failure output.

This specification's own acceptance is file existence plus `## ` section count; it does not prove an implemented chain. Do not run artifact generators for this read-and-specify task: they would violate its one-file write boundary.

Unresolved from repository-only evidence: exact incident Actions run/log and merge identity; current HTTP deployment/CDN state; deployed verifier versions; installed daily service wrappers; availability of signing credentials; Rekor duplicate/ambiguous network responses; and authorization/mechanics for durable deploy append commit-back. Source evidence establishes the need for those interfaces, not their live availability. Implementation must settle them before declaring publication complete. No new staging environment, infrastructure optimization, upstream mutation, credential change, or weakened gate is specified.
