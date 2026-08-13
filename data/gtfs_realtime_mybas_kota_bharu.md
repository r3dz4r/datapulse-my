---
dataset_id: gtfs_realtime_mybas_kota_bharu
last_checked: 2026-08-13T03:40:12Z
status: fresh
freshness_delta: 0 days
record_count: 62
content_freshness_date: 2026-08-03
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: BAS.MY via data.gov.my GTFS API
---

# GTFS Realtime — BAS.MY Kota Bharu Vehicle Positions

## Status

**Status:** Fresh

**Freshness:** 0 days

HTTP 200; valid GTFS realtime protobuf (62 vehicles)

## Last checked

2026-08-13 at 03:40:12 UTC.

## File size

The checked resource is 4,917 bytes.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/mybas-kota-bharu`

Licence: Creative Commons Attribution 4.0

Attribution: BAS.MY via data.gov.my GTFS API.

## Coverage

The reference snapshot contains 1 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: Kota Bharu, Kelantan.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: BAS.MY via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_mybas_kota_bharu.pb](../samples/gtfs-realtime/gtfs_realtime_mybas_kota_bharu.pb)
