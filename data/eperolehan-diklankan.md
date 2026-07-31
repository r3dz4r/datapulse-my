# ePerolehan Tender Notices (DIIKLANKAN)

**Dataset ID:** `eperolehan-diklankan`  
**Status:** Healthy  
**Freshness:** 0 days  
**Access method:** JavaScript-rendered via Camofox

## Coverage

The observed dataset contains 20 rows. Each listing exposes six fields:

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
with JavaScript.

## Known quirks

- `href-dash` links require a click-flow rather than direct navigation.
- Detail pages render 8–12 seconds after a click.
- Gridcell indexes are offset by 1.

Collectors should wait for the detail content after clicking and account for
the gridcell offset when mapping values.

## Licence and attribution

Licensed under the Open Government Licence (Malaysia).

Attribution: MOF ePerolehan.
