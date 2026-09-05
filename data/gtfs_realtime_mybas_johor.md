---
dataset_id: gtfs_realtime_mybas_johor
last_checked: 2026-09-05T02:11:03Z
status: aging
freshness_delta: 0.0005902777777777778 days
record_count: 84
content_freshness_date: 2026-08-03
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: BAS.MY via data.gov.my GTFS API
---

# GTFS Realtime — BAS.MY Johor Vehicle Positions

## Status

**Status:** Aging

**Freshness:** 0.0005902777777777778 days

HTTP 200; valid GTFS realtime protobuf (84 vehicles)

## Last checked

2026-09-05 at 02:11:03 UTC.

## File size

The checked resource is 13,261 bytes.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/mybas-johor`

Licence: Creative Commons Attribution 4.0

Attribution: BAS.MY via data.gov.my GTFS API.

## Coverage

The reference snapshot contains 1 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: Johor.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: BAS.MY via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_mybas_johor.pb](../samples/gtfs-realtime/gtfs_realtime_mybas_johor.pb)
