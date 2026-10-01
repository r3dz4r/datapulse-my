# 2026-10-01 signed-health operational integration

This note records the opt-in operational integration above the reviewed
signed-publication foundation (`c3d47ef33569bbe6aae919f2098d913e6518b0c6`,
on top of public `eaf56e5fc910ac380b270ff0f655adc9bd0d658e`). It is source
implementation plus a local, isolated Pages/workerd rehearsal. It is **not** a
deployed Cloudflare preview, not a public registry, and not a production
adoption. The production site is not signed.

## Contract added by this slice

- `scripts/signed_health_integration.py`
  - `KVRestTransport`: a real Cloudflare-KV-REST-shaped values transport. API
    base, account, namespace and credential are all explicitly injected. Only a
    loopback host may use plaintext HTTP; any other host must be explicit HTTPS.
    Credentials embedded in the URL are rejected. Redirects are never followed,
    so the bearer credential can only travel to the configured host. Responses
    are byte-bounded; timeouts, connection resets and oversized or
    error-enveloped responses fail with a bounded reason. A 200 body shaped like
    a Cloudflare API envelope is never accepted as stored value bytes.
  - `WriterLock`: one explicit destination-bound `flock` file. `serialized_publish`
    refuses to freeze, sign, write, read back or advance the pointer without the
    matching held lock, and refuses a lock bound to another destination.
  - `serialized_publish`: single frozen health input, explicit observation /
    assembly / signing clocks, injected signer, registry window check,
    independent verification, immutable object, exact verified read-back, then
    pointer. Pointer regression (authoritative pointer names a strictly later
    observation) is rejected while authoritative state is available.
  - Acknowledgement outcomes are reported distinctly: `acknowledged`, `failed`,
    `unknown`. An ambiguous write acknowledgement is never described as a
    rollback or a no-write. A lost pointer acknowledgement is `unknown` even
    though the object write is already proven.
  - `validate_registry_bytes` / `build_pages_artifact`: independent trusted
    registry validation and a reproducible isolated Pages artifact carrying the
    fixed static trust asset plus the scoped Functions. The manifest records the
    registry digest and source commit, `signature_authority: false`, and lives
    outside the served directory.
  - `quick_test` and `runtime_rehearsal` drivers and an opt-in CLI.
- `functions/_lib/signed-health-trust.js`: bounded trusted-registry delivery from
  the fixed same-deployment asset path `/.well-known/datapulse-probe-keys.json`.
  It never accepts a package-supplied URL and never reads a registry from KV.
- `functions/_lib/signed-health.js`: uses the trust helper. Independent trust and
  every existing verification rule are unchanged; the existing route
  `functions/health/verified/[[path]].js` and all unsigned routes are untouched.

## Local evidence (actual)

- Baseline focused selection before this change: `191 passed in 49.29s`.
- Final acceptance, exact brief command:
  `234 collected` / `234 passed` (see delivery report for raw output).
- Control is artifact presence only:
  - pre-change: the baseline tree has no `scripts/signed_health_integration.py`
    (`git cat-file -e HEAD:scripts/signed_health_integration.py` exits 128, so the
    `test -f` Control exits 1);
  - post-change: `CONTROL_EXIT=0`.
- Behavioral RED proof: the coordination gate `lock.assert_held(destination)`
  was temporarily replaced with `pass`. The named test
  `test_wrong_destination_lock_is_refused_before_any_write` failed for the
  behavioral reason (`Failed: DID NOT RAISE ...`), not a syntax or import error.
  The source was restored byte-exactly in a `finally` block;
  `RESTORED_BYTE_EXACT=true`,
  `RESTORED_SOURCE_SHA256=323b4efbf17a0587c2835e585aeb229625417d964706a8500a58f5e59c96c166`,
  and the test then passed green.
- Quick-test (bounded, no key material, signatures or payload bodies):

  ```json
  {"age_seconds":60.0,"consumer_verified":true,"fixture_only":true,"handler_status":200,"ok":true,"pointer_outcome":"acknowledged","publisher":"serialized_kv_rest_verified_readback_before_pointer","source_truth_verified":false,"writes":2}
  ```

- Runtime rehearsal (real local Wrangler 4.145.0 / workerd, fresh generated
  directory under `health/staging-signed-health/`, loopback ephemeral port, only
  local `DATAPULSE_HEALTH_INDEX` bound, ~16-22 s):

  ```json
  {"consumer_verified":true,"deployed":false,"elapsed_seconds":21.5,"fixture_only":true,"ok":true,"publication_sha256":"a10948f6c23e8901abfc1364afabb4fc36e86d4d0ce63abe723cfe2c22e5dfeb","registry_sha256":"ffcd2edc68215bb08ee466d225bc810a077898f41060701607752204a85549ae","routes":{"content_type":"application/json","digest":"200_verified","floor":"503","latest":"200_verified","missing_object":"503","non_get":"405","unknown_path":"404"},"runtime":"local_wrangler_workerd_pages","source_commit":"0000000000000000000000000000000000000000","source_truth_verified":false,"trust":{"old_deployment_gap":"asset rebuild proves delivery to the refreshed runtime only","refresh_forward":"200","revocation_is_live_asset_swap":true,"revoked":"503","wrong_purpose":"503"},"unsigned_fallback":"not_served"}
  ```

  The rehearsal performs real HTTP routing, the `ASSETS` trust lookup, native
  workerd Ed25519 verification, and independent Python consumer verification of
  the returned bytes through the actual Pages Functions. Revocation and
  wrong-purpose trust changes are delivered by rewriting the static asset and
  observing the running runtime fail closed, then refresh back to a valid
  registry and observe success again. Both verified routes are exercised and
  return `Content-Type: application/json`. A seeded unsigned KV
  `health/latest.json` is never served: the returned bytes are exactly the
  signed health.

## Tooling confinement

Wrangler honours `HOME`, `TMPDIR`, `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`,
`XDG_DATA_HOME`, `CLOUDFLARE_TELEMETRY_DISABLED`, `WRANGLER_SEND_METRICS`,
`WRANGLER_SEND_ERROR_REPORTS`, `WRANGLER_WRITE_LOGS` and
`CLOUDFLARE_LOAD_DEV_VARS_FROM_DOT_ENV` (verified from the installed
`wrangler-dist/cli.js`; `WRANGLER_HOME` is **not** honoured). The rehearsal
passes a minimal allowlisted environment with a generated worktree home, disables
dotenv loading and telemetry, runs `wrangler pages dev` with `--cwd` on the
generated project only (never the repository `wrangler.toml`, its real namespace
IDs or any remote mode), and starts the child in its own process group so the
whole group is shut down on every exit path. `wrangler pages dev` and
`wrangler kv key put` help output were read before use.

## Threat boundary and honest limits

- **Same-host cooperating serialization only.** The writer lock proves
  serialization between cooperating publishers on one host. It is not globally
  exclusive writer authority. Cloudflare KV GET-then-PUT is not atomic creation.
  A safe distributed creation guarantee would require a new coordinator; none is
  provisioned here, and unsafe automatic use is refused (publish requires the
  lock). Mandatory external promotion gate: designate one sole writer host and
  restrict the write credential to it.
- **Acknowledgement ambiguity.** A remote write can succeed before the response
  is lost. The code reports `unknown` and keeps sanitized phase/request/response
  digest evidence; it never claims rollback.
- **Trust delivery is the deployment's asset, not a global revocation feed.** A
  refreshed local artifact proves delivery to the refreshed runtime only. A
  still-running old deployment, an offline consumer or a CDN cache can retain a
  previously valid key. A `no-store` header or a static asset is not globally
  current revocation.
- **Freshness is consumer-clock policy, not a cryptographic clock.** Expiry and
  replay floors are enforced independently by each consumer. Equal observation
  times have no total order; no globally-newest claim is made.
- **`source_truth_verified` remains false.** This slice signs an exact frozen
  snapshot; it does not assert upstream truth, completeness or suitability.
- **Signer authority is separate.** The observation-receipt socket is not used
  and its purpose is not reused. The operator signer seam reads only an explicit
  key document/file descriptor; no discovery, default socket, rotation or new
  trust root is added. No real key is read in this task.

## Integration point and runnable operations plan (operator, not yet authorised)

1. After final health assembly (`health/latest.json` is complete and immutable
   for the cycle), read it exactly once into bytes.
2. Supply explicit inputs: destination identifier, `--api-base`, `--account-id`,
   `--namespace-id`, `--credential-file`/`--credential-fd`,
   `--signer-key-file`/`--signer-key-fd`, `--source-commit`, `--assembled-at`,
   `--signed-at`, `--now` and `--lock-dir`. Nothing is drawn from dotenv,
   process environment, runtime key paths or repository config.
3. Publish with `--publish`. It validates the signer key against the separately
   authoritative registry, purpose and validity window before any write, holds
   the destination lock across freeze/sign/object/read-back/pointer, and refuses
   on collision, read-back mismatch or pointer regression.
4. Deliver trust by deploying the generated Pages artifact (registry asset at
   the fixed path plus the scoped Functions). The artifact manifest records the
   registry digest and source commit and is explicitly not signature authority.
5. Verify independently with `--verify-response` using each consumer's own
   registry, clock and retained floors.

Dry-run (`--dry-run`), plan (`--plan`) and offline verification
(`--verify-response`) are available. With no arguments the CLI signs nothing and
opens no network connection.

## Approval gates and promotion checklist (all still required)

- Independent review of this module, the trust helper and the artifact builder.
- Preview-scoped credential and environment approval; a hosted preview remains a
  separate, explicitly authorised gate and is not replaced by the local run.
- Sole-writer-host and write-credential restriction documented and enforced.
- Remote immutable storage / distributed-creation decision (provision a
  coordinator or accept the single-writer restriction).
- Trusted-registry refresh and revocation delivery to old deployments, CDNs and
  offline consumers; monitoring for stale trust and expiry.
- Object retention and KV write budget; monitoring for signer, object, pointer
  and trust failures; alerting on stale verified availability and consumer
  rejection.
- Rollback capability to unavailable, or to an acceptable older complete
  snapshot, never unsigned bytes with borrowed proof.
- Public push, merge and deploy authorisation (operator-only). No production
  validation of any kind was performed here.
