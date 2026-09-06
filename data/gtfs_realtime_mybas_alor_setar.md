---
dataset_id: gtfs_realtime_mybas_alor_setar
last_checked: 2026-09-06T13:01:21Z
status: stale
freshness_delta: 0.001261574074074074 days
record_count: 35
content_freshness_date: 2026-08-03
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: BAS.MY via data.gov.my GTFS API
---

# GTFS Realtime — BAS.MY Alor Setar Vehicle Positions

## Status

**Status:** Stale

**Freshness:** 0.001261574074074074 days

HTTP 200; valid GTFS realtime protobuf (35 vehicles)

## Last checked

2026-09-06 at 13:01:21 UTC.

## File size

The checked resource is 2,664 bytes.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/mybas-alor-setar`

Licence: Creative Commons Attribution 4.0

Attribution: BAS.MY via data.gov.my GTFS API.

## Coverage

The reference snapshot contains 8 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: Alor Setar, Kedah.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: BAS.MY via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_mybas_alor_setar.pb](../samples/gtfs-realtime/gtfs_realtime_mybas_alor_setar.pb)
