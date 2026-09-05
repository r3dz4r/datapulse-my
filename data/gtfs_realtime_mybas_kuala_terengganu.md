---
dataset_id: gtfs_realtime_mybas_kuala_terengganu
last_checked: 2026-09-05T02:11:03Z
status: aging
freshness_delta: 0.000787037037037037 days
record_count: 27
content_freshness_date: 2026-08-03
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: BAS.MY via data.gov.my GTFS API
---

# GTFS Realtime — BAS.MY Kuala Terengganu Vehicle Positions

## Status

**Status:** Aging

**Freshness:** 0.000787037037037037 days

HTTP 200; valid GTFS realtime protobuf (27 vehicles)

## Last checked

2026-09-05 at 02:11:03 UTC.

## File size

The checked resource is 2,341 bytes.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/mybas-kuala-terengganu`

Licence: Creative Commons Attribution 4.0

Attribution: BAS.MY via data.gov.my GTFS API.

## Coverage

The reference snapshot contains 1 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: Kuala Terengganu, Terengganu.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: BAS.MY via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_mybas_kuala_terengganu.pb](../samples/gtfs-realtime/gtfs_realtime_mybas_kuala_terengganu.pb)
