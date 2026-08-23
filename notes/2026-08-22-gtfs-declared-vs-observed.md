# GTFS Realtime: declared cadence vs observed trust

Date: 2026-08-22
Status: internal research note; not a public product page
Scope: Rapid KL bus and Rapid Penang vehicle-position feeds

## Executive conclusion

The official declaration is simple: Malaysia's Open API documentation says GTFS Realtime vehicle-position feeds update every 30 seconds, and that feed-specific validation errors were generated with the GTFS Realtime Validator.[3]

DataPulse adds a different layer of evidence. At the latest local probe snapshot (`2026-08-21T16:51:23Z`), both selected feeds returned HTTP 200 and valid GTFS Realtime protobuf responses.[15] Rapid KL had zero vehicles; Rapid Penang had four. Both were classified `fresh`, with content-date freshness on the probe date and no detected content-shape change.[15]

The important result is not that the feeds are always healthy. It is that DataPulse makes the distinction between **fresh and empty**, **fresh and populated**, and **unavailable** explicit.[15] A zero-vehicle response is not automatically treated as a dead feed.[15]

## Declared by the source

The official documentation establishes three relevant expectations:

1. Vehicle-position feeds are updated every 30 seconds.[3]
2. Validation errors are generated using the GTFS Realtime Validator.[3]
3. The feed can still expose operational defects. The documentation records missing or mismatched trip IDs, legacy systems that cannot yet support compliant tracking, and manual matching requirements between realtime and static trip IDs.[3]

The government also states that it does not modify the incoming feed to solve the known trip-ID problem because of performance concerns; a deeper fix is deferred.[3]

**Interpretation:** official validation is real, but it is scoped to the GTFS domain and does not equal a portfolio-wide trust verdict.

## Observed by DataPulse

Live local evidence from `/home/redza/datapulse-my/health/latest.json`:

| Feed | Checked | HTTP | Parsed result | DataPulse status | Shape change | Freshness signal |
|---|---:|---:|---:|---|---|---|
| Rapid KL bus | 2026-08-21 16:51:23Z | 200 | 0 vehicles | `fresh` | false | content date |
| Rapid Penang bus | 2026-08-21 16:51:23Z | 200 | 4 vehicles | `fresh` | false | content date |

The Rapid KL row is the useful test case. A consumer that equates `record_count = 0` with failure would produce a false alarm. DataPulse preserves the distinction: the protobuf is valid, the endpoint responded, freshness evidence exists, and zero vehicles is treated as a valid transient observation.

The KL attestation envelope dated 2026-08-15 contains signature and chain fields and records 486 probes in the prior 14 days, 173 probes in the prior 24 hours, a fresh last status, and zero days of observed staleness.[16] Cryptographic signature verification was not rerun in this task. The envelope is not a complete reliability score, but it is stronger than a single successful request because it records repeated observation and chain metadata.[16][unverified]

## Critical deployment caveat

The local and public artifacts are not the same snapshot. The local health file records `2026-08-21T16:51:23Z`, while the public GitHub Pages health artifact last observed in this research was `2026-08-21T16:31:14Z`.[11][15]

The generated dataset markdown pages are older still: the committed Rapid KL page is dated 2026-08-16 and describes an older 88-vehicle reference snapshot; the Rapid Penang page is also dated 2026-08-16 and describes an older 150-vehicle snapshot. Those pages are historical reference pages, not the current live observation.[unverified]

This creates a useful trust-layer finding: **the observation pipeline can be newer than the published documentation surface**.[11][15] DataPulse should not present generated reference pages as if they were current health state.[unverified] The live health envelope must remain the operational source of truth.[15]

## What this proves

### Confirmed

- The official source publishes a declared 30-second vehicle-position cadence.[3]
- The official source documents validator use and known operational defects.[3]
- DataPulse can distinguish a valid empty feed from an unavailable feed using direct observations.[15]
- DataPulse records freshness signal type, HTTP result, parsed result, shape-change state, and observation time in one health envelope.[15]
- Repeated signed attestation evidence exists for at least the Rapid KL feed.[16]

### Not proven yet

- That the feed remains reliable across a longer longitudinal window.[unverified]
- That zero-vehicle periods correlate correctly with off-peak operation in every agency/feed.[unverified]
- That DataPulse's public generated surfaces are refreshed at the same speed as the local health snapshot.[11][15]
- That the official validator catches every semantic problem relevant to downstream agents.[3][unverified]

## Product implication

The case study supports the narrower DataPulse positioning.[3][15][16]

> Official GTFS validation tells consumers whether the feed conforms to selected transport rules. DataPulse tells consumers what was observed recently, what evidence exists, what changed, and how much confidence to place in the current response.

The next product work should not be another broad GTFS expansion. It should be a longitudinal evidence pack for two or three feeds:

1. declared cadence;
2. observed response cadence;
3. vehicle-count distribution;
4. empty-feed frequency;
5. parser/schema failures;
6. timestamp freshness;
7. static/realtime ID reconciliation issues;
8. signed observation history;
9. public-surface publication lag.[11][15]

That turns the case study from a claim into a repeatable trust artifact.

## Sources

[3] https://developer.data.gov.my/realtime-api/gtfs-realtime
[11] https://r3dz4r.github.io/datapulse-my/health/latest.json
[15] file:///home/redza/datapulse-my/health/latest.json
[16] file:///home/redza/datapulse-my/attestations/2026-08-15/gtfs_realtime_prasarana_bus_kl.json

## Local evidence

- `/home/redza/datapulse-my/health/latest.json`
- `/home/redza/datapulse-my/attestations/2026-08-15/gtfs_realtime_prasarana_bus_kl.json`
- `/home/redza/datapulse-my/data/gtfs_realtime_prasarana_bus_kl.md` (historical reference snapshot; not current live state)
- `/home/redza/datapulse-my/data/gtfs_realtime_prasarana_bus_penang.md` (historical reference snapshot; not current live state)
