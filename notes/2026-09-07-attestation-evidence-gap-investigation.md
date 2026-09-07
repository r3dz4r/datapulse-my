# Longitudinal attestation evidence — root-cause investigation (2026-09-07)

## What Redza asked
"How's our longitudinal evidence collection going along?" → prompted a deep dive because
served-vs-git divergence surfaced. Redza: "valuable artefacts that has no room for errors, investigate and fix."

## Confirmed live facts (all probed, not from memory)

### Served surface (www.data-pulse.my) — HEALTHY and advancing daily
- `attestations/latest/chain_head.json` → date **2026-09-07**, count **418**
- `attestations/latest/index.json` → date 2026-09-07
- `attestations/latest/scores.json` → 418 dataset rows
- Per-dataset signed envelopes served for 2026-09-07: `fuelprice.json`, `air_pollution.json` HTTP 200, schema `datapulse/v1/probe-attestation-envelope`, signature present
- Sigstore path healthy: `/signatures/datapulse.json`, `/record-evidence/`, `/per-dataset/` all HTTP 200

### Git source repo (r3dz4r/datapulse-my) — FROZEN at 2026-08-15 for dated chain
- Only git-tracked dated envelope dir: `attestations/2026-08-15/` (392 files)
- `attestations/latest/chain_head.json` committed = date **2026-08-15**, count **389** (e27b1e82d alpha)
- `.attestations/chain_head.json` committed (release anchor) = **2026-09-06**, count **412**
- Git check-ignore: `attestations/2026-09-07/fuelprice.json` = **NOT ignored** (committable by design)
- Last git commit that ADDED a dated envelope dir: `e27b1e82d` (the alpha)

## Root cause (Phase 1 complete)
There are TWO attestation systems, and the dated-chain one has a git-commit-back gap:

1. **`gen_attestations.py` (Ed25519 dated chain, `attestations/YYYY-MM-DD/`)** — regenerated fresh each deploy/Pages build, producing dated per-dataset signed envelopes up to the CURRENT date (served 09-07/418). BUT only the alpha-era snapshot (2026-08-15) was ever committed. The deploy generates + serves these but never `git commit`s the regenerated dated dirs back to source.
2. **`gen_sigstore_bundle.py` + `gen_per_dataset_receipt.py` (Sigstore/DSSE/Rekor, per-deploy)** — the current separate proof path; also served fresh each deploy.

**Net durability issue:** the reproducible git-source-of-truth dated attestation trail stops at 2026-08-15, while the *served* (deploy-artifact-only) evidence advances to 2026-09-07. The provenance evidence a consumer can verify TODAY (served, signed, fresh) is healthy, but the versioned source record behind it has a ~3-week gap. Everything generated 08-16..09-07 exists only in the last Cloudflare build, not in git history — so a rebuild from source would NOT reproduce it, and the git trail cannot independently substantiate the served claims.

## Why not already a "fix"
- The dated dir is NOT gitignored → architected to be committable.
- `release-please.yml` lists `attestations/**` in a paths filter → attestation changes are expected in commits/releases.
- But the deploy build steps that generate the fresh dated dirs don't appear to push them back (only stage for Cloudflare Pages).
- Anchor workflow only commits `.attestations/chain_head.json` (the pointer), not the full dated envelope trees.

## Candidate fixes (for operator decision — NOT yet applied; no room for error)
A. Add a commit-back step to the deploy/release path: after `gen_attestations.py` generates a new dated dir, `git add attestations/YYYY-MM-DD*` + commit + push so source git tracks each day's full signed envelope set. Must dedupe against auto-health commits / avoid clobbering origin/main races.
B. Explicitly decide the dated per-DS envelope trail is deploy-artifact-only (not git-source) and document that the durable provenance record is the Sigstore/rekor path, retiring the expectation that git holds dated Ed25519 envelopes per day. Purely a documentation/contract decision — lower risk but reduces the git-substantive moat.
C. Hybrid: keep serving freshness via deploy artifact (fast) but commit dated envelopes on a slower cadence (e.g. daily or per-release anchor) so the git trail stays within ~1 day, not 3 weeks.

Recommendation: A or C. B is a retreat of the "dated evidence history in git" moat claim.
