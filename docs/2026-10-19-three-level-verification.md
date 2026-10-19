# Three-level verification walkthrough — one fresh dataset, one dead one

**Captured:** 2026-10-19, 12:29–12:32 UTC
**Surface:** public MCP server at `https://mcp.data-pulse.my/mcp`
**Purpose:** show how a consumer verifies a published dataset end to end, and what each level does and does not prove.

This note records one live session. Values are observations from that window, not permanent facts: re-running the same calls later will produce different numbers, and that is expected — the catalogue is probed continuously.

## Method

Three read-only tools, always in this order:

| Level | Tool | Question it answers |
|---|---|---|
| 1 | `verify_dataset(dataset_id)` | What does the published record say, and does the published receipt reference resolve? |
| 2 | `verify_attestation(reference, replay_chain=true)` | Is the signed attestation intact, and does its chain replay to a Git-tagged anchor? |
| 3 | `verify_evidence(dataset_id)` | Does the upstream source answer the same way right now? |

Levels 1 and 2 read published artifacts. Level 3 makes a fresh, rate-limited live request. They are separate on purpose: a valid signature and a live source are different claims.

## Case A — `fuelprice` (healthy)

| Check | Result |
|---|---|
| Status | `fresh` |
| Last recorded probe | 2026-10-17T11:55:36Z, HTTP 200 |
| Content freshness date | 2026-10-15, staleness 4 days |
| Record count | 965 against an expected 945, within tolerance |
| Shape | unchanged, 10 columns |
| L1 signature | satisfied — signature valid, key registry match, key time valid, chain link valid |
| Key id | `ed25519-a829715828ba0f88` |
| L2 replay | satisfied — anchored to tag `v3.48.4` at commit `f53f7f5e` |
| L3 live transport | `match` — URL, HTTP 200 and 209,283-byte content length all matched |

Readiness profile returned `ready`. Note what that means: the quality-readiness profile checks that declared metadata is structurally present and consistent. It is not a freshness verdict and not a liveness verdict.

## Case B — `bnm_base_rate` (stale, and now unreachable)

| Check | Result |
|---|---|
| Status | `stale` |
| Last recorded probe | 2026-10-17T11:55:36Z, HTTP 200 |
| Content freshness date | 2020-08-06, staleness 2,265 days |
| Record count | 35 against an expected 12, reported within tolerance |
| L1 signature | satisfied — signature valid, key registry match, key time valid, chain link valid |
| L2 replay | satisfied — same tag `v3.48.4` |
| L3 live transport | `unreachable` — live HTTP 404 against a recorded 200; 2,491 bytes against a recorded 5,952 |

The signed digest itself records `last_status: stale` at 2,256 days staleness. The chain attests to a bad state rather than hiding it.

## The point of the two together

Case B has a perfect cryptographic chain and a dead source. Levels 1 and 2 pass; level 3 fails. That is the failure mode a signature cannot catch, and the reason the levels are reported separately instead of collapsed into one badge:

- L1 proves the attestation is intact and was signed by the registered key inside its validity window.
- L2 proves the daily heads chain back to a tagged, verifiable anchor.
- L3 proves the source answered the same way a moment ago — and says nothing about whether the content is correct.

A trust layer that only ever demonstrates healthy examples has not shown how it behaves when reality is bad. Case B is the honest demonstration.

## Known limits

- `verify_evidence` compares transport receipts only. Content date, record count and first-row hash are returned as unverified because they require the canonical probe pipeline; the tool reports them as `null` rather than estimating.
- A 404 establishes that this live request did not match the recorded transport. It does not establish why: endpoint retirement, path change, or transient blocking all produce the same verdict.
- Record-count tolerance can hold while content is years old. `bnm_base_rate` returns 35 records against an expected 12 and still reports tolerance as satisfied, because tolerance checks magnitude, not recency.
- Catalogue counts move between snapshots. The freshness summary returns a `checked_at`; two calls minutes apart can legitimately differ. Quote the timestamp with the numbers.

## Reproducing this

Any MCP client can repeat it. No API key is required, and the edge limits clients to roughly one request per second with a small burst.

```text
verify_dataset(dataset_id="fuelprice")
verify_attestation(reference="fuelprice", replay_chain=true)
verify_evidence(dataset_id="fuelprice")
```

Then substitute `bnm_base_rate` for the second case.

## Citation

If you quote these results, cite them as observations from 2026-10-19 12:29–12:32 UTC against `https://mcp.data-pulse.my/mcp`, and re-run before relying on them. The published artifacts are the authority; this note is a recording of one reading of them.
