# PR preview served verification: use the repository verifier, honestly unsigned

Date: 2026-10-01

## Defect

`.github/workflows/preview-verify.yml` built the release artifact credential-free,
assembled the Pages artifact, deployed a `pr-<number>` preview, and then ran the
last step:

```bash
python3 scripts/verify_external.py --base-url "$PREVIEW_URL"
```

`scripts/verify_external.py` verifies the *production* trust plane and its first
live check refuses any origin that is not the production site
(`scripts/verify_external.py`):

```
FAIL: public base must be exactly https://www.data-pulse.my; use --self-test for local tampering tests
```

A pull-request preview origin can never satisfy that guard, so the step was
unpassable by construction. It had not been reached before because earlier build
failures masked it.

## Change

The preview lane now verifies the deployed preview with the repository's own
served-release verifier, `scripts/verify_served_release.sh` — the same tool the
production promotion gate uses against its staging preview
(`deploy-cloudflare-pages.yml`). The step passes:

* `--base-url "$PREVIEW_URL"` — the freshly deployed preview origin;
* `--site _site` — the exact assembled artifact;
* `--sigstore-signed false` — this lane builds unsigned;
* `--health-only false` — the lane built the full release artifact, so the
  full-release proof checks apply;
* `--source-commit "$GITHUB_SHA"` — an explicit provenance commit.

The production verifier is no longer referenced anywhere in this workflow.

## The unsigned-input decision

`verify_served_release.sh` previously refused to start unless
`--sigstore-publication` was supplied, even when signing was declared false:

```bash
[[ -n "$publication_dir" && -n "$source_commit" ]] || fail "missing staged signing inputs"
```

That directory stages the signed bundle and manifest that the verifier compares
the served bytes against. It is a signing input. Demanding it for an unsigned
verification claims a signature that does not exist, so the requirement is now
conditional:

```bash
[[ -n "$source_commit" ]] || fail "missing staged signing inputs"
if [[ "$sigstore_signed" == true && -z "$publication_dir" ]]; then
  fail "missing staged signing inputs"
fi
```

`--source-commit` stays required in every mode. The signed branch, which still
needs the directory, is unchanged, and the production lane continues to pass it.
The verifier never silently skips the served comparison: with signing false it
still fetches and byte-compares the release proof, health snapshots, the
dashboard projection, trends/drift/reconciliation, `mcp.json`, `llms.txt`, the
compatibility aliases and every declared public surface. (The preview lane later
opts out of exactly the KV-backed health comparisons by name — see the next
section — only after the served health snapshot proved unsatisfiable there.)

## KV-backed health surfaces excluded by name

The preview origin's `/health/latest.json` and `/health/index.json` are served
by the Pages Function from the isolated staging KV namespace
(`functions/health/[[path]].js`), not from the assembled `_site` bytes. The
production deploy lane publishes that namespace on its own cadence (`Publish
health artifacts to isolated preview KV` in `deploy-cloudflare-pages.yml`). The
pull-request lane assembles a fresh snapshot minutes old and must hold no KV
write credential, so it cannot seed the store it is compared against; that is
the unsatisfiable `served health snapshot is older than the assembled snapshot`
failure.

The verifier now takes one explicit option,
`--kv-surfaces-published-elsewhere`. When it is passed, the verifier skips only
the served health snapshot's freshness and dataset-count comparison (including
the release proof's health cross-check against that snapshot) and the served
dashboard health projection comparison, and prints one `::warning` line naming
those surfaces and stating that they are published by another lane on its own
cadence. The default is unchanged and strict: with the option absent a stale
served snapshot still fails.

The option is not a blanket relaxation. Every static surface is still fetched
and still compared exactly as before: the landing surfaces, the register, the
dataset register, the release-verification proof (byte-for-byte `cmp` plus its
static identity fields), the compatibility aliases, `mcp.json`, `llms.txt` and
every declared public surface. Sigstore verification is unaffected and remains
gated on the signing flag. The negative control stays pointed at the static
`datapulse.json` register, so a tampered static surface still fails with the
option present, and it still requires the specific
`origin root register rows mismatch` diagnostic rather than a bare non-zero
exit.

The option is passed on the preview lane's `Verify served preview` step only.
The production promotion gate (`Verify isolated Pages preview before production
promotion` and `Verify canonical served surface` in
`deploy-cloudflare-pages.yml`) does **not** pass it: that lane seeds the KV
namespace in-lane, so it keeps the strict comparison.

The exclusion flag is argument-only. A verification relaxation must not be
environment-reachable, because runner environment state must not weaken a
lane's verification; only that lane's explicit workflow argument can opt in.

## Bounded negative control

A passing happy path only proves the comparison happened if the comparison can
also fail. The workflow runs a second, bounded step after the happy path, and it
stays pointed at the static register so it remains meaningful under the KV
exclusion:

* copies `_site` to `$RUNNER_TEMP/preview-negative-control-site`;
* appends one dataset to the copy's `datapulse.json` with `jq`;
* runs the same verifier against the same live `PREVIEW_URL` with the tampered
  site;
* requires a non-zero exit and specifically the
  `origin root register rows mismatch` diagnostic.

If the verifier skipped the served comparison, the negative control would exit 0
and the step would fail. The tamper is one local file and the failure fires on
the first fetched surface, so the control adds one fetch and one 30-second
propagation wait to the lane.

## Tests

`scripts/tests/test_preview_served_verification.py` pins:

* the workflow invocation arguments and the absence of the production verifier;
* the negative-control wiring and ordering;
* that an unsigned run needs no publication directory and reaches the terminal
  comparison (it passes against a local fixture site served through a stub
  `curl`);
* that a signed run without a publication directory still fails closed;
* that a tampered built artifact fails for the behavioural reason, not a usage
  or transport error;
* that the default still fails on a stale served snapshot and the strict run
  prints no exclusion notice;
* that with the option present the KV-backed surfaces are skipped, the single
  notice names them, and the static surfaces are still fetched and compared;
* that with the option present a tampered register or release proof still fails;
* that the preview workflow passes the option only to the served verification
  and that `deploy-cloudflare-pages.yml` never passes it.

Run them with the virtualenv on `PATH`:

```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python3 -m pytest \
  scripts/tests/test_deploy_cloudflare_pages_contract.py \
  scripts/tests/test_workflow_rewire.py \
  scripts/tests/test_staging_isolation.py \
  scripts/tests/test_verify_served_release_transport.py \
  scripts/tests/test_preview_credential_free.py \
  scripts/tests/test_preview_served_verification.py -q
```

## Limits

The proof that the lane runs green end to end can only come from the
pull-request run itself, which deploys the preview and exercises the live
origin. Nothing here weakens the deploy step, the Cloudflare secret references,
`deploy-cloudflare-pages.yml`, the production verifier's production-only guard,
or any other workflow.
