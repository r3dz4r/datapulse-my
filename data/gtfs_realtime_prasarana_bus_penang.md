---
dataset_id: gtfs_realtime_prasarana_bus_penang
last_checked: 2026-10-08T16:15:53Z
status: stale
freshness_delta: 0.000925925925925926 days
record_count: 10
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

**Freshness:** 0.000925925925925926 days

HTTP 200; valid GTFS realtime protobuf (10 vehicles)

## Last checked

2026-10-08 at 16:15:53 UTC.

## File size

The checked resource is 797 bytes.

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
