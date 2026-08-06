---
dataset_id: gtfs_realtime_mybas_kota_bharu
last_checked: 2026-08-06T16:31:19Z
status: degraded
freshness_delta: unknown
record_count: 1
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

**Status:** Degraded

**Freshness:** unknown

Invalid GTFS realtime protobuf: No module named 'google'

## Last checked

2026-08-06 at 16:31:19 UTC.

## File size

The checked resource is 80 bytes.

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
