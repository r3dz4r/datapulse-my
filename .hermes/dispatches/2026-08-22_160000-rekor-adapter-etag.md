Workdir: /home/redza/datapulse-my
Goal: Preserve the Rekor entry identifier header so Cosign can consume the proof-enriched adapter response and complete bundle generation.
Failure mode: The adapter returns a valid proof-enriched body without the POST `ETag`; Cosign indexes the response with an empty key, receives a zero-valued entry, and panics in `GenerateTransparencyLogEntry`.
Acceptance test: The adapter sets `ETag` to the exact full Rekor entry ID on the proof-enriched response, preserves one POST/no duplicate behavior, passes regression tests, and a real disposable Cosign/OpenBao/Rekor fixture produces a complete bundle after this fix.
Recommended execution model: luna

Implementation authority: You are the designated Codex implementer for this dispatch. The repository rule requiring Hermes to dispatch Codex has already been fulfilled; it does not prohibit you from editing the explicitly scoped files below. Edit the scoped files directly. Do not call codex-run, codex-run-bg, delegate_task, or any other agent recursively.

## Verified source contract

- Rekor v1 `POST /api/v1/log/entries` returns an `ETag` header whose value is the full entry ID.
- Cosign v3.1.3 / sigstore-go v1.2.2 uses the OpenAPI client response `ETag` as the key: `resp.Payload[resp.ETag]`, then calls Rekor `GenerateTransparencyLogEntry`.
- The adapter currently replaces the POST headers with headers from the UUID GET response; the GET has no `ETag`.
- The lab response body is proof-bearing and structurally valid; the nil-pointer panic is caused by the missing header key, not missing proof fields.

## Scope

Modify only:

- `scripts/rekor_consistency_proxy.py`
- `scripts/tests/test_rekor_consistency_proxy.py`

Do not modify production MCP/attestation code, Docker/systemd files, OpenBao/Rekor configuration, credentials, public artifacts, or generated data. Do not commit or push in this dispatch.

## Required change

1. In the successful intercepted POST path, retain the exact entry ID extracted from the original POST response.
2. Return the proof-enriched normalized JSON body, with:
   - `ETag` set to the exact extracted full entry ID;
   - `Content-Type` preserved as JSON;
   - `Content-Length` recalculated;
   - hop-by-hop headers removed.
3. Do not trust an arbitrary GET header for `ETag`.
4. Keep one POST only and GET-only polling.
5. Keep timeout, malformed response, UUID mismatch, and sensitive-log behavior unchanged.
6. Add/adjust a regression test asserting `headers["ETag"] == UUID` and that the response body contains `verification.inclusionProof`.

## Verification

Run:

```bash
python3 -m pytest scripts/tests/test_rekor_consistency_proxy.py -q
python3 -m pytest scripts/tests/test_attestations.py scripts/tests/test_sigstore_rekor_migration_contract.py -q
python3 -m py_compile scripts/rekor_consistency_proxy.py scripts/tests/test_rekor_consistency_proxy.py
git diff --check
```

Report exact files and test results; `Pushed: NO`.
