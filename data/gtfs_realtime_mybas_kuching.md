---
dataset_id: gtfs_realtime_mybas_kuching
last_checked: 2026-10-03T01:45:56Z
status: stale
freshness_delta: 0.0010069444444444444 days
record_count: 44
content_freshness_date: 2026-08-03
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: BAS.MY via data.gov.my GTFS API
---

# GTFS Realtime — BAS.MY Kuching Vehicle Positions

## Status

**Status:** Stale

**Freshness:** 0.0010069444444444444 days

HTTP 200; valid GTFS realtime protobuf (44 vehicles)

## Last checked

2026-10-03 at 01:45:56 UTC.

## File size

The checked resource is 4,019 bytes.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/mybas-kuching`

Licence: Creative Commons Attribution 4.0

Attribution: BAS.MY via data.gov.my GTFS API.

## Coverage

The reference snapshot contains 1 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: Kuching, Sarawak.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: BAS.MY via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_mybas_kuching.pb](../samples/gtfs-realtime/gtfs_realtime_mybas_kuching.pb)
