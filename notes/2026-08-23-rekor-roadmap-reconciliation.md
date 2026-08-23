# Sigstore/Rekor roadmap reconciliation — 2026-08-23

## Roadmap reconciliation: COMPLETE

**Main lane:** Sigstore/Rekor adoption — operator-directed continuation after the private Rekor/OpenBao infrastructure and first production anchor were verified.

**Background:** Phase 1 longitudinal evidence collection and the five-minute DataPulse health pipeline continue independently.

**Deferred:** dq-1 through dq-8 and the other sourcing tracks remain queued/deferred; this lane does not silently reprioritise them.

**Research plan status:** The design/fixture work is shipped; the private Rekor infrastructure and first anchor are shipped; automatic daily dual-publish remains queued.

**Phase justification:** operator-directed continuation of the existing src-1 lane.

**Next gate:** a bounded Codex implementation must wire a VPS-side publisher for a fresh canonical daily artifact to the private Rekor boundary, preserve the legacy Ed25519 path, fail the new path closed, and prove read-after-write inclusion before any consumer cutover.

## Reconciled live state

| Track | Evidence | Live classification | Next action |
|---|---|---|---|
| Legacy Ed25519 attestation chain | `.attestations/chain_head.json`, generator, public key registry | shipped/background | retain unchanged; generate fresh heads through the existing controlled key path |
| Private Rekor/OpenBao/Trillian/MySQL boundary | runtime Compose, live Rekor API, tree ID `3406645411023811912`, LogID `3cd689f8e16c7b228b84ded418d257c27b764f7fce2e9e13275eee4f09f3c8fe` | shipped | preserve identity; monitor token renewal and backup/restore |
| First production Rekor anchor | verified Rekor `rekord` entry at log index `0` for the signed 2026-08-20 chain-head envelope | shipped | retain as historical anchor; do not duplicate |
| Daily dual-publish integration | `scripts/rekor_consistency_proxy.py` and fixture contract exist; no pipeline invocation | queued/blocked | implement the VPS-side publisher and additive bundle/reference contract |
| Fresh artifact signing custody | current Ed25519 private key is GitHub Actions-only; OpenBao ECDSA path is available but no daily publisher is wired | blocked | resolve exact signer/publisher boundary in the implementation brief |
| Other roadmap dispatches | `todos.md`, dispatch queue, recent git history | queued/deferred/background | leave untouched |

## Non-goals for the next implementation

- no changes to `scripts/gen_attestations.py` legacy semantics unless the brief explicitly scopes an additive output;
- no consumer cutover or removal of Ed25519/Git-tag verification;
- no public Rekor/Fulcio/OIDC/TUF route;
- no new key generation, rotation, export, or deletion;
- no push, release, or public publication without separate authorization;
- no edits to existing unrelated dirty files or `.hermes/` artifacts.
