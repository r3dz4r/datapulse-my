# Credential-free pull-request release build

Date: 2026-10-01

## Why

The pull-request preview lane runs `bash scripts/generate.sh release-build` on a
runner that has no attestation signing key. When the published key registry
(`docs/.well-known/datapulse-probe-keys.json`) exists, the attestation stage
failed closed and the whole job stopped there with every later step skipped.
The operator decision is that the PR build is a credential-free rehearsal: the
signed release build is rehearsed in the trusted deployment lane, so the PR lane
must not require a signing key.

## What changed

- `scripts/generate.sh` — the `gen_attestations.py` stage now honours an
  explicit opt-in, `DATAPULSE_ALLOW_UNSIGNED_BUILD`. When it is exactly `1` and
  `DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE` is absent, the stage is skipped and
  prints `DATAPULSE_ALLOW_UNSIGNED_BUILD=1: WARNING: attestations were NOT
  regenerated; this release-build is UNSIGNED`. Nothing else about the branch
  changed: with the opt-in unset, a missing key plus a published registry still
  prints the original message and exits non-zero in every profile, and a key
  that is present (usable or not) is never bypassed by the opt-in.
- `scripts/verify_release_reproducible.py` — the isolated rebuilds start from a
  deliberately explicit environment. `_build` now forwards
  `DATAPULSE_ALLOW_UNSIGNED_BUILD=1` into those isolated builds only when the
  caller set it; the default (unset) is unchanged and stays fail-closed.
- `.github/workflows/preview-verify.yml` — the `Build release artifact` step
  sets `DATAPULSE_ALLOW_UNSIGNED_BUILD: "1"`. It is scoped to that step only;
  no secret reference was added, removed, or altered, and the deploy and
  served-verification steps were not touched.
- `scripts/tests/test_preview_credential_free.py` (new) — pins the fail-closed
  default, the honest skip message, that a present key is never bypassed
  (including an unusable key), the isolated-build forwarding, and the workflow
  wiring and unchanged secret references.

## What remains signed only in the trusted lane

`bash scripts/generate.sh release-build` still signs by default. The trusted
`.github/workflows/deploy-cloudflare-pages.yml` lane keeps every signing path:

- the `sign_health` job's pinned Cosign/Sigstore DSSE bundle,
- per-dataset evidence statement signing (`sign_per_dataset_receipts.py`),
- `bash scripts/refresh_chain_head.sh` before signing,
- the full-release gate that requires `attestation_state=signed`, and
- the classifier-scoped health-only `signer_down` preservation path.

The Pull-Request lane never signs and never claims to.

## PR-job steps affected by skipping attestation, and how they stay coherent

No step in the PR job is gated. Every later step still runs and can still fail;
the opt-in only removes the signer requirement.

1. `bash scripts/generate.sh release-build` — skips only the attestation stage
   (with the loud unsigned message) and runs every other generator.
2. `python3 scripts/gen_per_dataset_receipt.py` — no signing dependency; it
   generates evidence blobs and in-toto statements from `health/latest.json` and
   `datapulse.json` and can still fail on schema/identity drift.
3. `bash scripts/run_datacontract_validation.sh` — no signing dependency; the
   health/manifest contract checks run unchanged.
4. `python3 scripts/verify_release_reproducible.py --workdir-root … --output …`
   — the reproducible-release verifier in build mode re-runs the release build
   twice in isolated copies. It now forwards the explicit opt-in to those
   isolated builds, so both rebuilds are consistently unsigned and the
   byte-identical comparison of the owned public surfaces still runs and can
   fail. The verifier itself never inspects signatures.
5. `python3 scripts/verify_release_reproducible.py --verify-proof …` — validates
   the freshly generated proof against the source SHA, health timestamp and MCP
   tool count. No signing dependency; runs unchanged.
6. `bash scripts/verify_release_invariants.sh --local` — the local mode already
   models a signer-down checkout (`attestation_plane_state=signer_down`) and
   only skips the signed count-equality assertions. The committed attestation
   plane structure, JSON-LD/report presence, manifest schema, MCP runtime
   schema, trackers and README parity still run and can fail.

Because there was no genuinely signer-blocked step, the brief's gating clause is
not exercised and there is no gated check to comment on in the workflow; the
opt-in itself carries an explanatory comment.

## Residual exposure (deliberately not addressed)

The PR job still deploys the assembled `_site` to Cloudflare with
`secrets.CLOUDFLARE_API_TOKEN` and `secrets.CLOUDFLARE_ACCOUNT_ID` (the
`Deploy isolated Cloudflare Pages preview` step) and then runs
`scripts/verify_external.py` against the preview URL. That unsigned preview is
uploaded to the shared `datapulse-p4b-preview` project on a per-PR branch and
carries the committed (therefore possibly stale) attestation plane. This change
does not alter that credential posture, the preview project, or the served
verification; it only removes the signing-key requirement from the build.

## Addendum — 2026-10-02

The residual exposure recorded above has since been addressed.

- `.github/workflows/preview-verify.yml` — the `Deploy isolated Cloudflare Pages
  preview` step no longer draws `secrets.CLOUDFLARE_API_TOKEN`. It draws
  `secrets.CLOUDFLARE_PREVIEW_API_TOKEN`, a repository secret carrying one
  permission, Cloudflare Pages Write, and nothing else. The environment variable
  name stays `CLOUDFLARE_API_TOKEN`, because that is the name wrangler reads;
  only the secret on the right of the mapping changed.
- The same step is gated with
  `if: ${{ github.event.pull_request.head.repo.full_name == github.repository }}`,
  so a fork pull request never reaches a token-bearing step.
- The production deploy lane is untouched and keeps the production credential.

Two assertions in `scripts/tests/test_preview_credential_free.py` were written on
2026-10-01 to pin that *that day's* change left the Cloudflare secret references
unchanged. They hard-coded the old posture, so they failed against this change.
They were re-expressed rather than deleted and now assert the stronger property:
the reference set is `CLOUDFLARE_ACCOUNT_ID` plus
`CLOUDFLARE_PREVIEW_API_TOKEN`, and `secrets.CLOUDFLARE_API_TOKEN` appears
nowhere in the file. Their names were changed to state what they pin. The file's
other thirteen tests are unchanged, and a mutation proof — restoring the old
workflow into the path — showed both failing against it.

Evidence that the preview-scoped credential is sufficient: the lane's own run on
the pull request deployed, resolved the preview URL, verified the served preview
and passed its negative control. `Deploy isolated Cloudflare Pages preview`,
`Wait for preview deployment URL`, `Verify served preview` and the
mismatched-artifact control all succeeded.

Known limitation, unchanged in effect: three later steps consume
`steps.deploy_preview.outputs.url`, so a fork pull request now skips the deploy
and those steps receive an empty URL. A fork PR previously ran the deploy with no
secret and failed anyway, so this is not a regression. Gating those three steps
is the follow-up if fork PRs should skip the preview half entirely.
