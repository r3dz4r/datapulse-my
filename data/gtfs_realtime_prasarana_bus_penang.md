---
dataset_id: gtfs_realtime_prasarana_bus_penang
last_checked: 2026-08-13T03:40:12Z
status: fresh
freshness_delta: 0 days
record_count: 151
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

**Status:** Fresh

**Freshness:** 0 days

HTTP 200; valid GTFS realtime protobuf (151 vehicles)

## Last checked

2026-08-13 at 03:40:12 UTC.

## File size

The checked resource is 12,126 bytes.

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
