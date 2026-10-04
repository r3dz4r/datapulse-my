---
dataset_id: gtfs_realtime_prasarana_bus_kl
last_checked: 2026-10-04T03:05:39Z
status: aging
freshness_delta: 0.0005902777777777778 days
record_count: 81
content_freshness_date: 2026-08-03
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API
---

# GTFS Realtime — Rapid KL Bus Vehicle Positions

## Status

**Status:** Aging

**Freshness:** 0.0005902777777777778 days

HTTP 200; valid GTFS realtime protobuf (81 vehicles)

## Last checked

2026-10-04 at 03:05:39 UTC.

## File size

The checked resource is 8,895 bytes.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana?category=rapid-bus-kl`

Licence: Creative Commons Attribution 4.0

Attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API.

## Coverage

The reference snapshot contains 0 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: Klang Valley.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_prasarana_bus_kl.pb](../samples/gtfs-realtime/gtfs_realtime_prasarana_bus_kl.pb)
