---
dataset_id: gtfs_realtime_ktmb
last_checked: 2026-08-14T04:59:27Z
status: fresh
freshness_delta: 0 days
record_count: 0
content_freshness_date: 2026-08-03
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: KTMB via data.gov.my GTFS API
---

# GTFS Realtime — KTMB Vehicle Positions

## Status

**Status:** Fresh

**Freshness:** 0 days

HTTP 200; valid GTFS realtime protobuf (0 vehicles)

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 15 bytes.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/ktmb`

Licence: Creative Commons Attribution 4.0

Attribution: KTMB via data.gov.my GTFS API.

## Coverage

The reference snapshot contains 0 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: national.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: KTMB via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_ktmb.pb](../samples/gtfs-realtime/gtfs_realtime_ktmb.pb)
