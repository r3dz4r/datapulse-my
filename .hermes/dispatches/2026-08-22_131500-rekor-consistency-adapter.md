Workdir: /home/redza/datapulse-my
Goal: Implement and test a consistency-aware private-Rekor adapter so Cosign receives a successful submission response only after the UUID entry and inclusion proof are readable.
Failure mode: Cosign submits a valid entry to private Rekor, receives HTTP 201, then immediately reads before Trillian/search convergence and fails bundle creation. Blind retries can create duplicate log entries and cannot be used in production.
Acceptance test: A bounded reverse-proxy adapter intercepts only Rekor `POST /api/v1/log/entries`, waits for the returned UUID to become readable with an inclusion proof, preserves the original successful response, fails closed on timeout/malformed responses, forwards non-entry traffic transparently, and passes deterministic fake-upstream tests. No production service, OpenBao key, public endpoint, or generated artifact changes in this dispatch.
Recommended execution model: terra

Implementation authority: You are the designated Codex implementer for this dispatch. The repository rule requiring Hermes to dispatch Codex has already been fulfilled; it does not prohibit you from editing the explicitly scoped files below. Edit the scoped files directly. Do not call codex-run, codex-run-bg, delegate_task, or any other agent recursively.

## Verified live contract

Private Rekor behavior observed in the disposable lab:

- `POST /api/v1/log/entries` returns HTTP 201 and a JSON object keyed by entry UUID.
- `GET /api/v1/log/entries/{uuid}` returns the stored entry with `verification.inclusionProof` after Trillian convergence.
- Cosign fails if that UUID lookup is not readable immediately after POST.
- The existing lab endpoints are `127.0.0.1:9300` and `127.0.0.1:9820`; do not hardcode them into production code.

## Scope

Allowed files:

- `scripts/rekor_consistency_proxy.py`
- `scripts/tests/test_rekor_consistency_proxy.py`
- a small internal README/brief under `notes/` if needed

Do not modify:

- `mcp/server.py`
- `scripts/gen_attestations.py`
- OpenBao, Rekor, Trillian, Docker, systemd, Cloudflare, or deployment files
- production configuration or credentials
- public artifacts or generated health data

## Required behavior

1. Implement a small, dependency-light HTTP reverse proxy suitable for a private lab sidecar.
2. Configure upstream URL, listen host/port, poll interval, timeout, and maximum response size through explicit arguments/environment; no hardcoded production endpoints.
3. Intercept only `POST /api/v1/log/entries`:
   - forward the request unchanged to the upstream Rekor server;
   - preserve non-2xx upstream failures without polling;
   - parse the 201 JSON response and extract exactly one UUID key;
   - poll `GET /api/v1/log/entries/{uuid}` with bounded exponential backoff;
   - accept only when the returned JSON contains a valid `verification.inclusionProof` and matching UUID/log metadata;
   - return the original POST response only after the inclusion proof is readable;
   - on timeout, malformed response, or inconsistent UUID, return a clear 502/504 and never claim success.
4. Forward all other methods/paths without polling and preserve status/body/content type.
5. Do not retry POST submission. Polling must be GET-only after one submission.
6. Do not log request bodies, signatures, tokens, or artifact payloads. Log only method/path, UUID, attempt count, and outcome.
7. Keep the proxy fail-closed and deterministic. No background queue, no persistence, no duplicate-submission recovery logic.

## Tests

Use a local fake HTTP upstream in pytest. Cover:

- 201 POST followed by delayed GET inclusion: proxy returns original 201 only after proof appears;
- multiple delayed GET attempts with bounded backoff;
- POST non-2xx passes through without GET polling;
- malformed POST response fails closed;
- multiple UUID keys fail closed;
- inclusion proof absent until timeout returns 504;
- non-entry GET/POST paths forward unchanged;
- request bodies and sensitive headers are not emitted in logs;
- no second POST occurs during polling.

Do not use the real lab Rekor endpoint inside the Codex test suite and do not create live entries in this dispatch.

## Verification

Run:

```bash
python3 -m pytest scripts/tests/test_rekor_consistency_proxy.py -q
python3 -m py_compile scripts/rekor_consistency_proxy.py scripts/tests/test_rekor_consistency_proxy.py
python3 -m pytest scripts/tests/test_attestations.py scripts/tests/test_sigstore_rekor_migration_contract.py -q
git diff --check
```

Report exact changed files, test results, and `Pushed: NO`. The parent operator will separately decide whether to run one real lab write through the proxy after reviewing the implementation.
