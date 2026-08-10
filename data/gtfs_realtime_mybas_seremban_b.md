---
dataset_id: gtfs_realtime_mybas_seremban_b
last_checked: 2026-08-10T15:30:42Z
status: fresh
freshness_delta: 0 days
record_count: 2
content_freshness_date: 2026-08-03
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: BAS.MY via data.gov.my GTFS API
---

# GTFS Realtime — BAS.MY Seremban B Vehicle Positions

## Status

**Status:** Fresh

**Freshness:** 0 days

HTTP 200; valid GTFS realtime protobuf (2 vehicles)

## Last checked

2026-08-10 at 15:30:42 UTC.

## File size

The checked resource is 282 bytes.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/mybas-seremban-b`

Licence: Creative Commons Attribution 4.0

Attribution: BAS.MY via data.gov.my GTFS API.

## Coverage

The reference snapshot contains 0 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: Seremban, Negeri Sembilan.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: BAS.MY via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_mybas_seremban_b.pb](../samples/gtfs-realtime/gtfs_realtime_mybas_seremban_b.pb)
