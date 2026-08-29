Workdir: /home/redza/datapulse-my
Goal: Correct the private-Rekor consistency adapter so Cosign receives the proof-enriched UUID entry body after read-after-write convergence, allowing bundle creation to succeed without duplicate POST submissions.
Failure mode: The adapter currently waits until the GET inclusion proof is readable but returns the original POST response body, which lacks the proof. Cosign still fails with `not enough verified log entries: 0 < 1` even though the adapter has observed readiness.
Acceptance test: The adapter performs exactly one POST, polls the UUID GET, and returns the proof-enriched GET representation with the original successful status/appropriate headers; fake-upstream tests prove the returned body contains inclusion proof, timeout/malformed paths fail closed, and non-entry traffic remains unchanged. No production routing or lab process changes in this dispatch.
Recommended execution model: terra

Implementation authority: You are the designated Codex implementer for this dispatch. The repository rule requiring Hermes to dispatch Codex has already been fulfilled; it does not prohibit you from editing the explicitly scoped files below. Edit the scoped files directly. Do not call codex-run, codex-run-bg, delegate_task, or any other agent recursively.

## Verified live failure

The committed adapter `9d495e3b` logged:

```text
method=POST path=/api/v1/log/entries uuid=<uuid> attempts=1 outcome=ready
method=POST path=/api/v1/log/entries outcome=201
```

Yet Cosign failed inclusion verification. The upstream POST response is not the proof-enriched representation. The adapter must preserve the original POST status, but return the final successful UUID GET body after proof readiness.

## Scope

Modify only:

- `scripts/rekor_consistency_proxy.py`
- `scripts/tests/test_rekor_consistency_proxy.py`

Do not modify production MCP/attestation code, Docker/systemd files, OpenBao/Rekor lab configuration, public artifacts, credentials, or generated data. Do not start the proxy, submit Rekor entries, commit, or push in this dispatch.

## Required change

1. Make the proof wait return both attempt count and the final proof-enriched GET response body/headers needed for the downstream response.
2. On a successful intercepted POST:
   - preserve the upstream POST status (normally 201);
   - return a JSON body keyed by the submitted UUID from the final GET representation, including `verification.inclusionProof`;
   - preserve safe content-type headers but recalculate content length;
   - never return the original pre-proof POST body when the final GET body is available.
3. Keep exactly one POST submission and GET-only polling.
4. Keep timeout/malformed/UUID mismatch behavior fail-closed.
5. Keep sensitive logging exclusions.
6. Handle direct-entry and UUID-keyed GET responses consistently; return a normalized UUID-keyed body compatible with Cosign/Rekor clients.

## Tests

Update/add fake-upstream tests proving:

- delayed inclusion causes the final response body to contain the inclusion proof;
- original POST body is not returned when GET body differs;
- one POST only, multiple GET attempts allowed;
- non-2xx POST, malformed response, timeout, multiple UUIDs, and non-entry paths retain existing behavior;
- headers/body handling remains correct.

## Verification

```bash
python3 -m pytest scripts/tests/test_rekor_consistency_proxy.py -q
python3 -m pytest scripts/tests/test_attestations.py scripts/tests/test_sigstore_rekor_migration_contract.py -q
python3 -m py_compile scripts/rekor_consistency_proxy.py scripts/tests/test_rekor_consistency_proxy.py
git diff --check
```

Report exact files and tests; `Pushed: NO`.
