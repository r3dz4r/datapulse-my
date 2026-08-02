---
dataset_id: dgm_parliament_sex
last_checked: 2026-08-03T02:00:00Z
status: stale
freshness_delta: 677 days since file update
next_expected_update: overdue
record_count: 14
date_range: 2016-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January and represent composition at the start of the year.", "Percentages use filled seats as the denominator and exclude vacancies.", "The two parliamentary houses are reported separately."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Parliament of Malaysia via data.gov.my
---

# data.gov.my Female Representation in Parliament

## Provenance

Parliament of Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/publicadmin/parliament_sex.csv`
- `https://storage.data.gov.my/publicadmin/parliament_sex.parquet`

Catalogue description: [Proportion of women and men in Malaysian Parliament, covering both the House of Representatives (Dewan Rakyat) and the Senate (Dewan Negara).](https://data.gov.my/data-catalogue/parliament_sex).

## Status

**Status:** Stale

**Freshness:** File last updated 2024-09-25; observations end on 2022-01-01

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 541-byte file. It
contains 14 data rows.

## Last checked

2026-08-03 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (Dewan Rakyat and Dewan Negara) from 2016-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `house` | string | Either House of Representatives (Dewan Rakyat) or Senate (Dewan Negara) |
| `date` | date | The date in YYYY-MM-DD format, with MM-DD set to 01-01 as the data is at annual frequency. |
| `female` | number | Women as a percentage of total filled seats |
| `male` | number | Men as a percentage of total filled seats |

## Known quirks

- Annual dates use 1 January and represent composition at the start of the year.
- Percentages use filled seats as the denominator and exclude vacancies.
- The two parliamentary houses are reported separately.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/publicadmin/parliament_sex.csv" \
  -o /tmp/parliament_sex.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Parliament of Malaysia via data.gov.my.

## Sample

- [samples/dgm_parliament_sex.csv](../samples/dgm_parliament_sex.csv)
- [samples/dgm_parliament_sex.json](../samples/dgm_parliament_sex.json)
