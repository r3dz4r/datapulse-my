# P6 reconcile + contain — non-blocking deploy with failed-closed attestation

**Date:** 2026-08-28
**Operator direction:** Reconcile/contain — make the deploy chain non-blocking so the
intentional signer absence / stale attestation plane does not red full deploys; keep
attestation failed-closed; define archived-backup recovery as a separate gated path.
**Author:** Hermes (operator-approved)

---

## 1. Reconcile: live state vs 2026-08-25 recovery note

The `2026-08-25-p1-p8-openbao-recovery-resume.md` note assumed OpenBao/Rekor were running
and awaiting re-unseal. **Live host state (2026-08-28) contradicts that assumption** and
confirms the P6 stand-down (2026-08-24) was executed:

| Surface | 2026-08-25 (note) | 2026-08-28 (live) |
|---|---|---|
| OpenBao/Rekor/Trillian/MySQL containers | "running" | **absent** (docker ps -a: 18 total, none sigstore) |
| `rekor-production` / `datapulse-rekor-prod` compose project | present | **absent** from `docker compose ls -a` |
| `/etc/datapulse-sigstore` | present | **absent** |
| `/etc/datapulse-rekor` | present | **absent** |
| `real-lab-gate.passed` | absent | absent (confirmed) |
| served `attestations/latest/index.json` | — | frozen `2026-08-15` (389 attests) |
| served `attestations/latest/binding.json` | — | dated `2026-08-27` (inconsistent w/ index) |
| `datapulse-attest-daily.service` | — | `enabled` but `inactive (dead)` |
| deploy `verify_attestation_binding.py --head-only` | — | **fails** (plane inconsistent) |

**Root cause of deploy red is NOT a recoverable bug.** Per P6 (2026-08-24), the private
signer lane was deliberately stood down: "asynchronous and replaceable; its failure must
never block health publication, Pages, API, or MCP." Commit `d31f3333 chore: archive Sigstore
and attestation implementation` archived the implementation in git. The frozen 08-15 plane
with `artifact_signed:false` is the **intended fail-closed state**, and the deploy-red on
`verify_attestation_binding.py` reflects **blocked signer availability by design**, not a
corrupt/recoverable condition.

**Therefore "recovery" (re-unseal/stand-up) is the wrong default.** There is no OpenBao to
re-unseal. Re-animating a live signing lane is a **new implementation / architecture change**
(P6.2 low-risk issuer pilot), governed by the P6 promotion gate — distinct from reconciling
the deploy so it stops red-ing.

---

## 2. Containment design: non-blocking deploy, failed-closed attestation

Objective: a full release-build (`[no skip deploy]`) must complete green even when the
signer lane is intentionally down, while continuing to expose that no live signing occurred
(`artifact_signed:false` on the dashboard) and without pretending a corrupt plane is healthy.

### Principle — distinguish "signer down (P6 intended)" from "plane corrupt"

- **Signer-down (expected):** served `attestations/latest/index.json` is a well-formed,
  schema-valid envelope whose date is stale (> N days old) AND whose trust claims report
  `artifact_signed:false`. This is the P6 fail-closed posture. The deploy should **warn but
  not fail**.
- **Plane corrupt (unexpected):** attestation JSON fails schema validation, or `artifact_signed`
  claims `true` but the plane is inconsistent. The deploy should **fail** (a real regression).

### Checks to convert from hard-fail to warn-under-condition

In `verify_release_invariants.sh` (deployed mode) and `deploy-pages.yml` post-deploy:

1. `verify_attestation_binding.py --head-only` (line 138 / deploy step)
   → When the head/index/binding are schema-valid but stale-dated with `artifact_signed:false`,
   emit a `::warning title=Signer lane down (P6)` and continue. Only fail on schema-invalid or
   `artifact_signed:true` inconsistency.

2. Attestation index/head/scores internal-consistency block (lines 220-234)
   → Same conditional: schema-valid + stale + unsigned = warn; corrupt or falsely-signed = fail.

3. `deploy-pages.yml` "Preserve served attestation plane (fast path)" (`served index is invalid`,
   `served binding date is invalid`)
   → Same: a stale-but-valid plane is preserved and carried forward as the failed-closed state;
   do not treat "stale" as "invalid." Only abort on a structurally broken plane.

### Implementation shape (dispatch later, after this design approves)

- A new helper (bash function or `verify_attestation_state.py`) that classifies the plane as
  `signer_down` | `healthy` | `corrupt` based on schema-validity + `artifact_signed` + freshness.
- Call it from all three sites; branch on the classification.
- Keep the 10-status health taxonomy, dashboard trust-claim exposure (`artifact_signed:false`),
  and `verify_agent_ready.sh` unchanged.

### Guardrail

Do NOT paper over a genuine corruption by widening "stale" to swallow a bad plane. The
classification must require schema-valid + explicit `artifact_signed:false`. A planed dated
yesterday with `artifact_signed:true` that doesn't verify is still a hard fail.

---

## 3. Gated recovery path (NOT the default; separate approval)

Archived backups (age-encrypted, mode 600) available for any future re-animation decision:

| Artifact | Size | Purpose |
|---|---|---|
| `/home/redza/backups/datapulse-openbao-recovery-20260824T182546Z.tar.age` | 2.49 MB | OpenBao state (early) |
| `/home/redza/backups/datapulse-openbao-recovery-20260825T052704Z-retry.tar.age` | 2.48 MB | OpenBao state (retry) |
| `/home/redza/backups/datapulse-openbao-raw-inventory-20260825T061831Z.tar.age` | 2.49 MB | raw inventory |
| `/home/redza/backups/datapulse-rekor-preserved-20260825T063416Z.tar.age` | 210 MB | Rekor state preserved |

Re-animation is **P6.2+ territory**, not "recovery": it would re-derive a live signing lane per
the P6 promotion gate (bounded daily pilot, client/buyer need, operational/maintenance case).
No bulk replay of the 245 queued requests; no marker restoration without approval. This
runbook does **not** authorize standing the lane back up.

---

## 4. Immediate operator decisions

1. **Approve the containment design (§2)** so a well-scoped brief can be dispatched (Codex,
   likely `sol` or `terra`) to convert the three checks to warn-under-signer-down.
2. **Confirm `datapulse-attest-daily.service` posture:** it is `enabled` but `dead` (fails to
   advance against a stood-down signer). Options: leave it (harmless, signals intent) or mask it
   until the lane is re-animated. Recommend masking to avoid silent recurring failed unit noise
   — operator call.
3. **Deploy-chain now:** `15ab351f` (dashboard-marker fix) is pushed and its deploy will finish
   red at attestation. Once the §2 containment lands, full deploys go green without masking the
   failed-closed signer state.

---

## 5. Outcome / definition of done

- A full release-build deploy passes green with the signer lane intentionally down, emitting a
  `::warning` that no live signing occurred.
- A genuinely corrupt or falsely-signed plane still fails the deploy.
- The dashboard continues to expose trust claims honestly (`artifact_signed:false`).
- Recovery from archive remains a documented, operator-gated, separately-approved path.
