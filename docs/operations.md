# Operations

## Scheduling and ownership

`datapulse-health.timer` wakes every 5 minutes (`OnCalendar=*:0/5`) and starts
the root-owned `/etc/systemd/system/datapulse-health.service`. The service
acquires `/tmp/datapulse-health.lock`, probes due datasets with
`scripts/check.sh --due`, validates the temporary snapshot, and atomically
moves it to `health/latest.json`. A successful probe then invokes
`bash scripts/generate.sh health-cycle`.

The release-build signs daily probe facts with the protected Ed25519 key referenced by
`DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE`; private keys remain outside the checkout.
It publishes immutable dated envelopes plus `attestations/latest/` and a public key
registry at `.well-known/datapulse-probe-keys.json`.

The additive attestation binding signs the exact `health/latest.json` SHA-256,
dataset count and identifier-set hash, observation time, publication time, active key,
and daily chain head. A Rekor reference may be attached only when its Cosign bundle
names that same health digest and carries a matching LogID, index, UUID, inclusion
proof, and signed entry timestamp. These are three separate claims: an Ed25519
signature proves the published artifact binding, Rekor proves transparency-log
witnessing, and neither proves that an upstream source is true.

Sigstore/Rekor remains additive. If no complete Rekor evidence is available, legacy
health publication continues and the public contract reports `rekor_witnessed: false`.
If metadata claims `rekor_witnessed: true`, generation and postdeploy verification fail
closed on a missing or invalid proof. A fast health-only deploy may publish a newer
snapshot without a matching binding only when the dashboard exposes all three trust
claims as false; even in that mode, a malformed legacy signature, superseded key, or
ambiguous daily head remains a deployment failure. Full release builds require current
health/signature/key/count/time parity.

`scripts/check.sh --due` maps refresh frequencies to probe tiers:

| Tier | Manifest frequency | Due interval |
| --- | --- | ---: |
| realtime | `30 seconds`, `hourly` | 5 minutes |
| daily | weekday publication times | 60 minutes |
| daily | `daily` | 1 day |
| weekly-monthly | weekly, monthly, quarterly | 7 days |
| slow | annual, survey-year, as-required | 30 days |

The Sunday 00:00 UTC GitHub Actions workflow runs a full, non-tiered probe and
the same `health-cycle` profile as a fallback. Its successful completion
triggers Pages via `workflow_run`, ensuring Pages checks out the health commit
rather than the pre-push workflow SHA.

The Pages workflow owns the broader release surface. On a relevant push to
`main`, manual dispatch, or successful weekly-health `workflow_run`,
`.github/workflows/deploy-pages.yml` invokes
`bash scripts/generate.sh release-build`, embeds current data, and deploys the
assembled Pages artifact. The always-on `datapulse-mcp.service` user unit is a
separate read-only runtime owned by `redza`. Its installed command uses
`/home/redza/.local/share/datapulse-mcp/venv/bin/python` to run
`/home/redza/.local/share/datapulse-mcp/server.py`, with `Restart=on-failure`.
The separate system-installed `datapulse-api.service` runs the authenticated
buyer API on `127.0.0.1:8791`; the public API origin is
`https://api.data-pulse.my`. Its durable key, rate-limit, entitlement, and audit state is under
`/home/redza/datapulse-my/var/`.

The NPRA Pro control plane verifies Paddle signatures over the raw webhook body,
uses an inter-process lock plus atomic replacement for durable entitlement state,
and forwards only its internal engine credential to `127.0.0.1:8001`. No public
route exposes that engine directly. The webhook secret and internal credential
remain environment-only and must never be logged or copied into page assets.
The browser's checkout nonce is its single-use redemption token; webhook state
stores only its hash and webhook responses never include it.

## Paths and logs

- Operational repository: `/home/redza/datapulse-my`
- Health service source: `/home/redza/dotfiles/system/datapulse-health.service`
- MCP deployment: `/home/redza/.local/share/datapulse-mcp`
- Health log (unchanged): `/var/log/datapulse-health.err`
- MCP log: `journalctl --user -u datapulse-mcp.service`
- Health units: `/etc/systemd/system/datapulse-health.{service,timer}`
- MCP user unit source: `deploy/systemd/datapulse-mcp.service`
- Release profile invocation: `.github/workflows/deploy-pages.yml`

The health timer owns probe commits and generated health artifacts. Humans and
automation may also write `main`, so the unit pulls with `--rebase --autostash`
before probing and pulls with rebase again after its generated commit. The
second pull handles another writer winning the race; a genuine content conflict
stops the unit and must be resolved in the operational clone.

## Safe deploy and rollback

**Three operational units, distinct responsibilities:**

1. **`datapulse-health.timer` / `.service`** — owned by root.
   Atomic probe writes + `health-cycle` artifacts. Pushes
   `chore(health): ...` commits automatically when artifacts change.
   Failure here manifests as missing/old `health/latest.json`, `health/trends.json`, `health/drift.json`, `health/reconciliation.json`, or
   absent artifacts in `badges/`, `feed.xml`, `catalog-snapshot.json`, or `deltas/`.

2. **`deploy-pages.yml` workflow** — owned by GH Actions.
   Runs `release-build` then embed then deploy. Failure here
   manifests as a Pages deploy failure, a post-deploy invariant
   failure, or stale public surfaces. Roll back by reverting the
   triggering commit on `main` and re-running the workflow (or
   `gh workflow run deploy-pages.yml`).

3. **`datapulse-mcp.service` user unit** — owned by `redza`.
   Independent runtime that reads the published manifest + health.
   Failure here manifests as MCP endpoint errors or
   `verify_mcp_deployment.py` reporting `MISMATCH` /
   `UNREACHABLE`. Roll back by re-running the redeploy script
   (copy `mcp/server.py` to `/home/redza/.local/share/datapulse-mcp/`
   + `systemctl --user restart datapulse-mcp.service`).

**General rollback principles:**

- Prefer `git revert <commit>` over `git reset`. The operational
  clone at `/home/redza/datapulse-my` must be preserved.
- For systemd unit changes, restore the prior source, reinstall,
  `systemctl daemon-reload`, and restart the timer/MCP service.
- Manual regeneration work in this repository is committed but
  pushed only by an operator.

## Ownership matrix

| Path | Generated by | Owned by | When |
|---|---|---|---|
| `health/latest.json` | `scripts/check.sh --due` | `datapulse-health.timer` | Every 5 min (after probe) |
| `health/trends.json` | `scripts/gen_trends.py` | `datapulse-health.timer` | Every successful health cycle; powers trend and reliability MCP surfaces |
| `data/<id>.md` | `scripts/gen_data_reports.sh` | `datapulse-health.timer` | After every successful probe |
| `badges/<id>.svg`, `badges/status-*.svg`, `badges/index.svg` | `scripts/gen_badges.sh` | `datapulse-health.timer` | After every successful probe |
| `README.md` (trust-summary block only) | `scripts/gen_readme_summary.sh` | `datapulse-health.timer` | After every successful probe |
| `feed.xml` | `scripts/gen_rss.sh` | `datapulse-health.timer` | After every successful probe |
| `catalog-snapshot.json` + deprecated `changelog.json` alias | `scripts/gen_catalog_snapshot.py` | `datapulse-health.timer` | After every successful probe |
| `health/history.jsonl`, `health/history_daily.json` | `scripts/gen_health_history.py --compact` | `datapulse-health.timer` | After every successful probe |
| `health/trends.json` | `scripts/gen_trends.py` after history | `datapulse-health.timer` | After every successful probe |
| `health/drift.json` | `scripts/gen_drift.py` after trends | `datapulse-health.timer` | After every successful probe |
| `health/reconciliation.json` | `scripts/gen_reconciliation.py` after drift | `datapulse-health.timer` | After every successful probe |
| `deltas/<cycle>.json` | `scripts/gen_dataset_deltas.py` | `datapulse-health.timer` | After history generation for each probe cycle |
| `data/json/<id>.json` (non-GTFS) | `scripts/gen_json_envelope.py --force` | `deploy-pages.yml` (release-build Step 6) | On every Pages deploy |
| `data/jsonld/<id>.json`, `data/jsonld/catalog.json` | `scripts/gen_jsonld_catalog.py` | `deploy-pages.yml` (release-build Step 7) | On every Pages deploy |
| `docs/mcp-reference.md`, `mcp.json` | `scripts/gen_mcp_reference.py` | `deploy-pages.yml` (release-build Step 8) | On every Pages deploy |
| `docs/.dashboard_filters.json` | `scripts/gen_dashboard_filters.py` | `deploy-pages.yml` (release-build Step 9) | On every Pages deploy |
| `docs/trust-snapshot-<date>.{md,json}` | `scripts/gen_trust_snapshot.py` | `deploy-pages.yml` (release-build Step 11) | On the weekly release build |

`verify_evidence` uses a process-local 10-minute cache and global serialization;
the cache is cleared when the MCP process restarts. Monitor `mcp-tool` logs for
verification volume and external timeout rates. Replace this with shared
limiting/cache before adding workers or replicas.
| `mcp/server.py` `SOURCE_COMMIT_SHA` constant | `scripts/bump_mcp_source_version.py` | `deploy-pages.yml` (release-build Step 0) | On every Pages deploy |
| Deployed `/home/redza/.local/share/datapulse-mcp/server.py` | Manual redeploy | `datapulse-mcp.service` | After any MCP code change |
| `/etc/systemd/system/datapulse-health.{service,timer}` | Manual install | Root | When timer source changes |

## URL drift invariant

For every dataset, the dashboard URL, health probe URL, manifest URL, JSON
envelope URL, and JSON-LD `sameAs` URL must be identical. This keeps the URL a
consumer sees in the dashboard equal to the URL the probe actually fetched.

Verify the invariant locally with:

```sh
python3 scripts/check_url_drift.py
```

The check exits 1 and names each affected dataset when drift or a missing
surface is found. Cadence findings are reported for operators but do not mask
URL failures; `release-build` runs this audit before producing the release.

## Verification

The 7-gate check covers the post-deploy invariants. For pre-deploy
verification:

```bash
# Verify source units parse cleanly
systemd-analyze verify deploy/systemd/datapulse-health.service
systemd-analyze verify deploy/systemd/datapulse-mcp.service

# Verify generated artifacts are deterministic
bash scripts/generate.sh health-cycle --list
bash scripts/generate.sh release-build --list

# Verify MCP source matches deployed service
python3 scripts/verify_mcp_deployment.py

# Run the test suite
python3 -m pytest -q scripts/tests/
```
