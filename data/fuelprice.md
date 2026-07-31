# Malaysian Fuel Prices

**Dataset ID:** `fuelprice`  
**Status:** Healthy  
**Freshness:** 0 days behind  
**Refresh frequency:** Weekly

## Coverage

The dataset contains 472 weekly rows covering 30 March 2017 through 30 July
2026. It provides one date field and six numeric price fields:

- `date`
- `rous97`
- `ron95`
- `diesel`
- `diesel_euro5`
- `lpg`
- `kerosene`

## Health assessment

The published series is current and has no freshness lag. Its date range and
weekly cadence are consistent with the expected publication schedule.

## Known quirks

- The `offset` parameter is silently ignored.
- The date filter is silently ignored.

Consumers should retrieve the full dataset and apply pagination or date
filtering locally.

## Licence and attribution

Licensed under the Open Government Licence (Malaysia).

Attribution: Ministry of Finance Malaysia via data.gov.my.
