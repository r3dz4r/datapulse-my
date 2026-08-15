---
dataset_id: eperolehan-diklankan
last_checked: 2026-08-15T04:36:16Z
status: browser-dependent
freshness_delta: 0 days
next_expected_update: unknown
file_size_bytes: null
file_count: null
schema_version: unknown
schema_drift: none
known_quirks: []
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: MOF ePerolehan
---

# ePerolehan Tender Notices (DIIKLANKAN)

## Status

**Status:** Browser dependent

**Freshness:** 0 days

Browser check succeeded

## Last checked

2026-08-15 at 04:36:16 UTC.

## File size

The health snapshot did not report a file size.

## Coverage

The browser-rendered listing exposed 29 tender rows in the observed snapshot.
Its paginator reported 834 total results across 42 pages. Each listing exposes
six fields:

- `title`
- `agency`
- `publish_date`
- `close_date`
- `days_remaining`
- `briefing_flag`

Following a listing to its detail view exposes seven additional fields:

- `ministry`
- `estimated_value_rm`
- `kod_bidang` (array)
- `supplier_status`
- `coverage_area`
- `validity_days`
- `procurement_method`

## Health assessment

The listing and detail views are available and current, with no freshness lag.
Collection requires a browser-capable workflow because the site is rendered
with JavaScript. The public source uses the `www.eperolehan.gov.my` host; the
bare `eperolehan.gov.my` host is not publicly DNS-resolvable.

## Known quirks

- `href-dash` links require a click-flow rather than direct navigation.
- Detail pages render 8–12 seconds after a click.
- Gridcell indexes are offset by 1.

Collectors should wait for the detail content after clicking and account for
the gridcell offset when mapping values.

## Sample

- [samples/eperolehan-diklankan.json](samples/eperolehan-diklankan.json)

## Licence and attribution

Licensed under the Open Government Licence (Malaysia).

Attribution: MOF ePerolehan.
