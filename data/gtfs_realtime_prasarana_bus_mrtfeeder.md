---
dataset_id: gtfs_realtime_prasarana_bus_mrtfeeder
last_checked: 2026-08-09T05:15:50Z
status: unknown-freshness
freshness_delta: unknown
record_count: 103
content_freshness_date: 2029-10-06
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot.", "The sampled vehicle timestamp is ahead of the feed header timestamp; freshness follows the required maximum-timestamp rule."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API
---

# GTFS Realtime — MRT Feeder Bus Vehicle Positions

## Status

**Status:** Unknown freshness

**Freshness:** unknown

HTTP 200; valid GTFS realtime protobuf (103 vehicles)

## Last checked

2026-08-09 at 05:15:50 UTC.

## File size

The checked resource is 8,180 bytes.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana?category=rapid-bus-mrtfeeder`

Licence: Creative Commons Attribution 4.0

Attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API.

## Coverage

The reference snapshot contains 1 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: Klang Valley.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.
- The sampled vehicle timestamp is ahead of the feed header timestamp; freshness follows the required maximum-timestamp rule.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_prasarana_bus_mrtfeeder.pb](../samples/gtfs-realtime/gtfs_realtime_prasarana_bus_mrtfeeder.pb)
