---
dataset_id: kkm_idengue
last_checked: 2026-08-10T10:07:26Z
status: browser-dependent
freshness_delta: unknown
next_expected_update: 2026-08-02
record_count: null
date_range: 2026-08-01
schema_version: 1.0
schema_drift: none
known_quirks: ["JavaScript-rendered and requires Camofox", "state names are published in Bahasa Malaysia", "death count is supplementary and appears in an iframe chart"]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: KKM via iDengue portal (MYSA hosted)
---

# KKM iDengue Weekly Dengue Cases

## Status

**Status:** Browser dependent

**Freshness:** unknown

Browser check succeeded

## Last checked

2026-08-10 at 10:07:26 UTC.

## File size

The health snapshot did not report a file size.

## Coverage

The table contains 16 rows: 14 states, `WILAYAH PERSEKUTUAN`,
`WILAYAH PERSEKUTUAN LABUAN`, and a `MALAYSIA` total. State names are
published in Bahasa Malaysia and should be preserved as-is.

The portal also reported 36 dengue deaths year-to-date as of 26 July 2026 in
a supplementary iframe chart. Deaths are not part of the state-table schema
documented here.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | State or national-total label in Bahasa Malaysia. |
| `daily_cases` | integer | Dengue cases reported for the displayed day. |
| `cumulative_cases` | integer | Year-to-date cumulative dengue cases. |
| `as_of_date` | date | Date represented by the table, in `YYYY-MM-DD` format. |

## Known quirks

- The portal is JavaScript-rendered; direct HTTP requests return only the SPA
  shell, so collection requires Camofox and a 12-second rendering wait.
- The site and state labels are in Bahasa Malaysia.
- The supplementary death count appears in an iframe chart rather than the
  state table.

## Breaking changes

None observed.

## Reproducibility

Open `https://idengue.mysa.gov.my/` in Camofox, wait 12 seconds for the state
table to render, capture the accessibility snapshot, and close the tab.

## Provenance note

The portal footer identifies MYSA and KKM's Bahagian Kawalan Penyakit as the
source and steward of the published information. DataPulse attributes this
dataset to KKM via the MYSA-hosted iDengue portal.

## Licence

Licensed under the Open Government Licence (Malaysia).

Attribution: KKM via iDengue portal (MYSA hosted).

## Sample

- [samples/kkm_idengue.csv](../samples/kkm_idengue.csv)
- [samples/kkm_idengue.json](../samples/kkm_idengue.json)
