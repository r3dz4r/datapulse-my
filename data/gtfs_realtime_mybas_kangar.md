---
dataset_id: gtfs_realtime_mybas_kangar
last_checked: 2026-08-07T07:25:52Z
status: fresh
freshness_delta: 0 days
record_count: 1
content_freshness_date: 2026-08-03
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: BAS.MY via data.gov.my GTFS API
---

# GTFS Realtime — BAS.MY Kangar Vehicle Positions

## Status

**Status:** Fresh

**Freshness:** 0 days

HTTP 200; valid GTFS realtime protobuf (21 vehicles)

## Last checked

2026-08-07 at 07:25:52 UTC.

## File size

The checked resource is 1,693 bytes.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/mybas-kangar`

Licence: Creative Commons Attribution 4.0

Attribution: BAS.MY via data.gov.my GTFS API.

## Coverage

The reference snapshot contains 1 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: Kangar, Perlis.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: BAS.MY via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_mybas_kangar.pb](../samples/gtfs-realtime/gtfs_realtime_mybas_kangar.pb)
