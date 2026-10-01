# DataPulse signed-response build scope

## Authority
Operator instruction: "Go build your recommendation", following the recommendation to close signature-to-response binding first, then pilot one use-specific assurance assessment. This authorises staged implementation, not production promotion, public publication, spending, secret/config changes, service stops or credential rotation. A fresh coding-lane word is still required by the dispatch gate. No implementation worker has started.

## Reconciliation
- Current-work probe on 2026-10-01 still reports DP/Engine remediation as the previous main lane. The new operator-directed build does not imply the remediation is complete.
- DataPulse main at probe: eaf56e5fc910ac380b270ff0f655adc9bd0d658e, clean tracked working tree. Production unit executes from /srv/datapulse-my.
- Existing preview branch session/dp-pr-head-sha is separate and unlanded. Scanner/configuration/preview gates remain unresolved; this instruction does not waive them.
- Production deployment 36838772458 completed successfully. Independent public checks passed sampled Ed25519 envelopes, Git parity, fuelprice receipt signature, health snapshot signature and manifest digest, and tamper rejection.
- The health signature covered a different snapshot from the fresher live health response. functions/health/[[path]].js serves independent KV artifact keys, with static fallback; no response/proof binding exists in that reader.
- Engine daily-output has four pre-existing modified generated files; preserve them. Stage 2 R2 remains an operator-decision dependency, outside this build.

## Main lane and sequencing
Build staged DataPulse response/proof coupling first, reusing existing canonicalisation and signing authority. Separate repository slices from runtime orchestration and promotion. Do not call a fixture-only implementation production adoption.

Background: existing DataPulse observation/publication/daily signer and Engine daily outputs continue unchanged. Previous preview remediation remains unresolved, not superseded. Use-specific assurance follows the signing slice; choose one dataset and one decision with a named policy before implementing it. No universal semantic-truth or completeness certification.

## Required contract
1. Enumerate designated covered endpoints and signed subjects; do not promise signing of every arbitrary HTTP error or response.
2. Freeze and canonicalise one publication version, binding payload digest, observation time, source revision, policy and relevant inputs. Assembly time is not upstream observation time.
3. Sign and verify before advertising the candidate as verified. Preserve current signing/trust primitives. No production key creation/rotation or PR-controlled signer authority.
4. Publish immutable snapshot/proof objects with an envelope or binding that cannot mix versions. Eventually-consistent pointers may expose older complete versions, never mismatched payload/proof pairs. Do not claim a globally atomic KV transaction or newest worldwide source state.
5. If proof is invalid/missing or signer unavailable, serve an explicitly aged last-verified version or unavailable on the verified path. Existing unverified publication can stay independently available with honest labels, never a borrowed signature claim.
6. Apply named consumer freshness and anti-replay policy. A signature alone does not establish latestness.
7. Derived dashboard/MCP outputs require a verifiable derivation or signature over the canonical answer. A digest is identity, not authenticity; an observation signature does not authenticate arbitrary derived output.
8. Keep source_truth_verified=false and distinguish authenticity, source availability and suitability.

## Staged acceptance
Use isolated fixtures, disposable signing material and local mock consumers; no production endpoints/KV/services/credentials as test inputs.
- Known-good offline verification; payload mutation and version mismatch rejected.
- Wrong identity/key, revoked/expired key and unsupported policy rejected.
- Partial uploads, delayed/reordered pointer propagation and interrupted publication never produce a mixed verified response.
- Signer outage retains complete last-verified data with age or returns unavailable, never newer unsigned data labelled verified.
- Stale/replayed valid snapshots rejected under the configured policy.
- Derived output mutation cannot retain an authenticity verdict without proof.
- Tests discriminate no-op implementation; negative controls must fail before green.
- Existing publisher, health Function, receipt and MCP contracts remain green. No implicit dependency, taxonomy, catalogue-count, paid-rail or public-claim changes.
- Independent review and staged end-to-end exercise precede promotion; exact public push/merge and any runtime/secret/config operations are separate gates.

## Execution model and next gate
Recommend Codex gpt-6.1-sol for the first slice: cross-system publication consistency, signer trust boundaries and consumer semantics require design. Use Terra for later bounded integrations once the protocol is fixed.

Next gate: fresh operator lane selection, e.g. codex gpt-6.1-sol. Then create worktree and the eight-header brief, measure focused acceptance, pass brief/staging gates, and dispatch once. This scope note is neither a validated dispatch brief nor implementation completion.
