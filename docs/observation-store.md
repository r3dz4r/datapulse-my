# Observation store

Implementation: [`scripts/observation_store.py`](https://github.com/r3dz4r/datapulse-my/blob/main/scripts/observation_store.py) — decided 2026-09-15 (Phase 2 storage-plane decisions, sections 1–3). Tests: [`scripts/tests/test_observation_store.py`](https://github.com/r3dz4r/datapulse-my/blob/main/scripts/tests/test_observation_store.py).

## Runtime root, and why it is outside Git

The observation archive lives at `/home/redza/runtime/datapulse-observations/` on the pipeline host. It is **deliberately not inside this repository**: the archive holds third-party source content (raw response bytes, normalized projections, envelopes) that would balloon the repo and change on every capture, while the repo carries only the code and the policy that govern it. The root sits beside the existing `~/runtime/datapulse-history/` archive, on the same filesystem, which held 105 GB free when measured on 2026-09-15.

`~/runtime` is root-owned, so creating `datapulse-observations/` beneath it is a one-time operator step; the store never creates its own root.

**The root is not yet in the backup inventory.** The operator's backup script (`hermes-backup.sh`) lists its required inputs explicitly, and `~/runtime` is not among them — meaning everything this layer retains is currently unbacked. Adding the root to that inventory is a separate, later task (planned as Task 2.3); this page exists partly so that fact is on record until it happens.

Tests and verification runs never touch that root: every store function accepts an explicit `root` argument, and the test suite passes a throwaway directory. Without an explicit root, the store resolves `DATAPULSE_OBSERVATION_ROOT`, then the default above — and rejects any relative path, so an archive can never scatter across whatever directory a timer happened to run in.

## Ownership and permissions

Directories are mode **750**, files mode **640**, owned by the pipeline user. The archive holds third-party source content and has no reason to be world-readable. Both modes are set explicitly after creation (not left to the process umask), so the posture is the same regardless of who runs the pipeline. These are pinned by test.

## Directory tree

```
/home/redza/runtime/datapulse-observations/
├── blobs/sha256/<prefix>/<digest>.raw          raw source bytes, content-addressed
├── normalized/sha256/<prefix>/<digest>.json    normalized projections, canonical JSON, content-addressed
├── envelopes/<dataset_id>/<YYYY>/<MM>/<observation_id>.json   filed observation envelopes
├── indexes/observations.sqlite                 acceleration index, rebuildable from envelopes
├── policies/<dataset_id>.json                  per-dataset archive policy, projected from config
└── manifests/<YYYY-MM-DD>.json                 per-cycle manifest
```

One line each: **blobs** keeps the exact raw bytes a source returned; **normalized** keeps canonical-JSON projections derived from them; **envelopes** is this store's own record of every observation, filed by dataset and the UTC year/month of `observed_at` — it makes no claim about the upstream source's standing; **indexes** answers "which observations exist for a dataset, newest first" without walking the envelope tree; **policies** mirrors the archive policy each dataset runs under; **manifests** records what one capture cycle filed, one file per day.

## The digest convention

Every stored object's identity is a digest string: **`sha256:` followed by 64 lowercase hex characters**. The first two hex characters name the prefix directory (`blobs/sha256/ab/ab12….raw`), which fans content-addressed files across 256 directories instead of one flat listing.

This is the same string form as `source_digest` in the historical-observation envelope contract, and the same canonical-JSON convention (`sort_keys`, compact separators) as the attestation chain. **One digest convention across the product**: mixed digest string formats are how digests get mis-parsed. The store rejects any digest that does not match the form, rather than guessing.

## Envelope attachment, and what the index is

An envelope file must carry its own `observation_id` member, equal to its filename stem. A rebuild refuses any envelope that does not — the index must not paper over a misfiled envelope. This is what makes the layout self-describing: a third party can walk `envelopes/` alone and know exactly what was retained, without the live source and without trusting any index.

`indexes/observations.sqlite` is an **acceleration cache, never the authority**. It can be deleted at any time; `rebuild_index_from_envelopes` reconstructs every row from the envelope files on disk — including envelopes that were never indexed. A rebuild may therefore legitimately return *more* rows than the index previously held. If the index and the envelope tree disagree, the envelope tree wins.

## Limits in force

Defined in [`config/observation-policies.json`](https://github.com/r3dz4r/datapulse-my/blob/main/config/observation-policies.json) as of 2026-09-15:

| Limit | Value | Enforced |
|---|---|---|
| Max raw response | 25 MB (26,214,400 bytes) | Yes — oversized writes are refused, nothing written |
| Max normalized output | 25 MB (26,214,400 bytes) | Yes — same refusal behaviour |
| Per-dataset retention | 24 months | Recorded; enforcement is Task 2.2 |
| Total archive budget | 10 GB (10,737,418,240 bytes) | Recorded; enforcement is Task 2.2 |

**A dataset with no policy entry is not permitted to archive.** The config is an explicit allow list; a missing entry fails closed to health-only observation and is never treated as allowed by default.

## Rotation and size

As the archive grows, `envelopes/` fans out by dataset, year, and month; `blobs/` and `normalized/` fan out by digest prefix. There is no log rotation and no compaction — content addressing means identical bytes are stored once and never rewritten, preserving the original file's timestamp as evidence.

Expected pilot cost under the approved archive modes is ≈145 MB/year, so the 10 GB budget is roughly 60× headroom against the current plan; it exists to fail loudly if a source changes far more often than assumed, not to be approached. Today the store enforces only the two per-payload size caps; retention and total-budget enforcement, and compression-ratio anomaly detection, are deferred to Task 2.2.

## Cleanup behaviour

This layer implements **no deletion at all**. No retention pruning, no budget trim, no orphan sweep — a file written by this store is only ever added to, never removed. Any future pruning (Task 2.2, dry-run report first) must obey one invariant: **it may never remove a blob still referenced by an envelope**, because the envelope's digest claims would then describe bytes that no longer exist.

## Enforced today versus Task 2.2

| Check | Status |
|---|---|
| Per-payload size caps (raw, normalized) | **Enforced today** — refused at write, nothing written |
| Identity and placement validation (observation ids, dataset ids, digest form) | **Enforced today** |
| Atomic writes, mandated modes, no temp-file survivors | **Enforced today** |
| Index rebuildable from envelopes (envelopes are the authority) | **Enforced today** |
| Retention enforcement (24 months) | Task 2.2 |
| Total budget enforcement (10 GB) | Task 2.2 |
| Compression-ratio anomaly detection | Task 2.2 |
| Checksum verification on read | Task 2.2 |
| Safe cleanup / pruning (dry-run first, never drop referenced blobs) | Task 2.2 |

To verify the store yourself, from the repository root:

```bash
python3 -m pytest scripts/tests/test_observation_store.py -q
```

The suite runs entirely inside throwaway directories and touches no real archive.
