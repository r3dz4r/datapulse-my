# P1–P8 / OpenBao recovery resume anchor — 2026-08-25

## Authority

This note supersedes stale roadmap summaries in `~/.hermes/memories/todos.md` and the older generated `STATE.md` snapshot for the current recovery thread.

Interrupted session: `@session:default/20260824_060307_f4fee650`

## Actual stopping point

The active work was finishing the DataPulse P1–P8 remediation sequence, with the immediate task narrowed to OpenBao recovery-token generation. Recovery had been initialized and was waiting for the original OpenBao recovery/unseal-key shares to be entered locally, one at a time, until the response reports `complete: true`.

Required material is the original recovery/unseal-key quorum from the OpenBao initialization or an encrypted/operator recovery record. There is no install key. Do not paste keys, tokens, nonce, OTP, or encoded recovery token into chat.

Do not run `bao operator init`; that risks creating a new identity/state over the existing OpenBao data.

## Verified live state at resume

- `datapulse-prod-openbao`: running; image `openbao/openbao:2.6.2`; Docker restart count `0`.
- `datapulse-openbao-recovery`: absent. The accidental `docker stop datapulse-openbao-recovery 2>/dev/null || true` therefore did nothing.
- `docker start datapulse-prod-openbao` started the normal container; no data deletion or container recreation was performed.
- Production Rekor/Trillian/MySQL containers are running; the consistency proxy is active.
- `datapulse-sigstore-publish-dispatch.timer`, `datapulse-openbao-token-renew.timer`, and `datapulse-rekor-log-signer-token-renew.timer` are disabled/inactive.
- `/etc/datapulse-sigstore/real-lab-gate.passed` is absent.
- No publisher replay or new production signing is authorized.
- The production compose inspection command currently cannot interpolate because `REKOR_DB_SECRET_GID` is missing; do not infer that the already-running containers are down from that compose error.

## Next safe gate

1. Re-derive the current recovery-container/endpoint command from the canonical production compose and OpenBao deployment files; do not reuse an old guessed command.
2. Locate the original recovery/unseal-key quorum through the operator’s secure backup/password-manager/offline record.
3. Run the recovery-token procedure locally without exposing key material in chat.
4. Verify OpenBao health, seal/recovery state, token-generation result, Transit key metadata, and audit path read-only.
5. Only after explicit approval, decide whether/when to restore publisher/renewal timers and the real-lab gate.

P1–P8 status must be re-derived from live commits, served artifacts, deployment state, and this recovery thread before any new roadmap action. Do not use the old todo list as the current phase authority.
