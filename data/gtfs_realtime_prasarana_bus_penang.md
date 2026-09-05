---
dataset_id: gtfs_realtime_prasarana_bus_penang
last_checked: 2026-09-05T02:11:03Z
status: stale
freshness_delta: 0.0011342592592592593 days
record_count: 147
content_freshness_date: 2026-08-03
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API
---

# GTFS Realtime — Rapid Penang Bus Vehicle Positions

## Status

**Status:** Stale

**Freshness:** 0.0011342592592592593 days

HTTP 200; valid GTFS realtime protobuf (147 vehicles)

## Last checked

2026-09-05 at 02:11:03 UTC.

## File size

The checked resource is 11,798 bytes.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana?category=rapid-bus-penang`

Licence: Creative Commons Attribution 4.0

Attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API.

## Coverage

The reference snapshot contains 0 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: Penang.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_prasarana_bus_penang.pb](../samples/gtfs-realtime/gtfs_realtime_prasarana_bus_penang.pb)
