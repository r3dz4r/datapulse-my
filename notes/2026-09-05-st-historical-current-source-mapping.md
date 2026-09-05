# ST MyEnergyStats: current-source mapping and historical retention

Date: 2026-09-05 (Asia/Kuala_Lumpur)

## Decision

Retain the existing legacy ST datasets as historical/reference vintages. Do not delete or relabel them as current merely because the legacy endpoint returns HTTP 200.

Use the current `myenergystats.st.gov.my` portal for new current-source datasets only where the semantics match. Do not force a one-for-one replacement where the current portal exposes a different measure or no equivalent.

## Evidence

Current portal:

- Dashboard: https://myenergystats.st.gov.my/dashboard
- HTTP 200; live page contains `System Generation and Demand for 2025`, 2025 Peninsular/Sabah cards, and Sarawak data for 2024.
- Current dashboard evidence observed: Peninsular highest demand 21,049 MW on 28 May 2025; installed capacity 27,333 MW; reserved margin 29%. Sabah highest demand 1,221.36 MW on 1 Aug 2025; installed capacity 1,751.03 MW; reserved margin 27%. Sarawak data is labelled 2024.
- Dashboard Sankey JSON: https://myenergystats.st.gov.my/documents/d/guest/dashboard-sankey-v2 — HTTP 200, application/json, 94,220 bytes, Last-Modified: 2026-07-09; contains annual energy-balance years beginning at 1990 and current 2024 data.

Current downloadable CSV resources:

| Concept | URL | Observed response |
|---|---|---|
| IPP licensees | https://myenergystats.st.gov.my/documents/d/guest/csv-senarai-lesen-ipp | HTTP 200, text/csv, 5,613 bytes, 27 rows, fields include Installed Capacity (MW), Issued Date, Expired Date; Last-Modified 2026-05-11 |
| Electricity distributors | https://myenergystats.st.gov.my/documents/d/guest/csv-senarai-lesen-distributors | HTTP 200, text/csv, 405,420 bytes, 2,577 rows, fields include Installed Capacity (MW), Issued Date, Expiry Date; Last-Modified 2026-05-11 |
| Co-generation licensees | https://myenergystats.st.gov.my/documents/d/guest/csv-senarai-lesen-cogen | HTTP 200, text/csv, 7,855 bytes, 45 rows, fields include capacity and issued/expiry dates; Last-Modified 2026-05-11 |
| Renewable-energy licensees | https://myenergystats.st.gov.my/documents/d/guest/csv-senarai-lesen-re | HTTP 200, text/csv, 110,147 bytes, 800 rows, fields include installed capacity and issued/expiry dates; Last-Modified 2026-05-11 |
| Large-scale solar licensees | https://myenergystats.st.gov.my/documents/d/guest/csv-senarai-lesen-lss | HTTP 200, text/csv, 12,391 bytes, 80 rows, fields include installed capacity and issued/expiry dates; Last-Modified 2026-08-19 |

Current PDF resources also exist for licensee categories, but the CSV resources are preferable for structured ingestion.

## Mapping of existing legacy rows

| Existing ID | Legacy observation | Current-source decision |
|---|---|---|
| `st_installed_capacity_mw` | Annual installed generation capacity table through 2021 | Current dashboard has installed capacity cards, but only current regional snapshot semantics. Retain legacy series; consider a new regional current snapshot dataset rather than replacing this ID. |
| `st_max_demand_mw` | Annual maximum-demand table through 2021 | Current dashboard has 2025 system-demand cards and monthly JavaScript arrays. New current snapshot/time-series dataset may be justified; do not overwrite historical ID until the shape is formalized. |
| `st_generation_mix_gwh` | Annual generation-mix table through 2021 | Current dashboard's visible energy-balance data is not the same as electricity generation mix. Retain historical ID; no exact replacement confirmed. |
| `st_sales_unit_gwh` | Annual electricity sales by sector through 2021 | No current one-for-one equivalent found on the current dashboard/database page. Retain historical ID. |
| `st_sales_value_rm_million` | Annual electricity sales value through 2021 | No current one-for-one equivalent found. Retain historical ID. |
| `st_consumers` | Annual electricity consumers by sector through 2021 | No current one-for-one equivalent found. Retain historical ID. |
| `st_ipps` | Historical year-specific IPP PDF page | Current CSV licensee register exists, is structured, live, and carries capacity/issued/expiry fields. Strong candidate for a new current dataset; preserve legacy historical ID. |
| `st_re_projects` | Historical year-specific renewable-energy PDF page | Current renewable-energy CSV register exists with 800 rows and capacity/issued/expiry fields. Strong candidate for a new current dataset; preserve legacy historical ID. |
| `st_cogenerators` | Historical year-specific co-generator PDF page | Current co-generation CSV register exists with 45 rows and capacity/issued/expiry fields. Strong candidate for a new current dataset; preserve legacy historical ID. |
| `st_elesca` | Historical electrical competency certificates table through 2011 | No current equivalent found on the current dashboard/database page. Retain historical ID. |

## Product meaning

Historical rows still create value when they are explicitly represented as historical vintages:

- baseline and trend comparison;
- policy/market-history evidence;
- reproducibility of past analysis;
- detection of revisions or structural breaks;
- benchmarking current observations against the prior system state.

They do not support claims about current conditions without a current source or a clear observation-period label.

## Recommended next implementation boundary

Do not replace the 10 legacy IDs in place. Add a small current ST lane with new IDs for:

1. current regional system generation and demand / installed-capacity snapshots;
2. current IPP licensee CSV;
3. current co-generation licensee CSV;
4. current renewable-energy licensee CSV;
5. optionally current large-scale-solar licensee CSV.

Then mark the existing 10 rows with explicit historical-vintage semantics in a later controlled manifest change, preserving their IDs and envelopes. First implementation should onboard the structured current CSVs, because they are semantically clear and easier to probe than the dashboard's embedded JavaScript.

## Access and freshness cautions

- The legacy `meih.st.gov.my` protocol is stateful and technically probeable, but its visible report tables end at 2021 and its PDF pages expose historical documents through 2023.
- The current portal is a separate Liferay surface at `myenergystats.st.gov.my`; a 200 response alone is not enough. Current CSVs have verifiable Last-Modified headers and fixed structured content.
- The current dashboard's embedded JavaScript values are current snapshots, not necessarily downloadable time series. Treat the observation period and retrieval/check date separately.
