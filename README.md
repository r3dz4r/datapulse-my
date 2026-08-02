# DataPulse MY

**Live dashboard:** https://r3dz4r.github.io/datapulse-my/

> **🤖 AI-ready** — Point your AI agent at [`https://r3dz4r.github.io/datapulse-my/llms.txt`](https://r3dz4r.github.io/datapulse-my/llms.txt) to consume all 40 datasets (manifest, freshness, licences) in one request.

DataPulse MY is an open-source trust layer for Malaysian public data. It makes
official datasets easier to assess and reuse by publishing a small manifest,
human-readable health reports, and machine-readable health envelopes.

It does not replace the official source. It documents what is available,
whether it is fresh, how its schema behaves, and which collection quirks users
need to handle.

## Who it is for

- Journalists and researchers checking whether a public dataset is usable.
- Civic technologists building reproducible data pipelines.
- Public servants improving the discoverability and reliability of open data.
- Developers who need stable, machine-readable dataset health metadata.

## Use this for

- **Journalist fact-check:** before citing a fuel price figure, check fuelprice
  freshness to make sure it's current.
- **Pipeline health gate:** fail the build if data.gov.my has been down for
  more than 24 hours.
- **RAG knowledge base:** consume the JSON envelopes as structured context for
  a chatbot answering "what's the latest BNM rate?"

## Dataset health

![fuelprice](badges/fuelprice.svg)
![eperolehan-diklankan](badges/eperolehan-diklankan.svg)
![pricecatcher](badges/pricecatcher.svg)
![exchangerates_daily_0900](badges/exchangerates_daily_0900.svg)
![exchangerates_daily_1130](badges/exchangerates_daily_1130.svg)
![exchangerates_daily_1200](badges/exchangerates_daily_1200.svg)
![exchangerates_daily_1700](badges/exchangerates_daily_1700.svg)
![met_weather](badges/met_weather.svg)
![doe_apims](badges/doe_apims.svg)
![doe_rqims](badges/doe_rqims.svg)
![doe_mqims](badges/doe_mqims.svg)
![kkm_idengue](badges/kkm_idengue.svg)
![dosm_crime_district](badges/dosm_crime_district.svg)
![dosm_cpi_state](badges/dosm_cpi_state.svg)
![dosm_gdp_state_real_supply](badges/dosm_gdp_state_real_supply.svg)

**Subscribe:** [RSS feed](feed.xml) — get notified when dataset health changes.

## For AI agents

DataPulse MY is AI-agent-friendly. Agents can discover and consume the full
dataset portfolio from a single self-describing index.

Verify access:

```sh
curl -s https://r3dz4r.github.io/datapulse-my/llms.txt
```

- [`llms.txt`](https://r3dz4r.github.io/datapulse-my/llms.txt) — curated dataset index
- [`datapulse.json`](https://r3dz4r.github.io/datapulse-my/datapulse.json) — manifest with a declared `$schema`
- [`health/latest.json`](https://r3dz4r.github.io/datapulse-my/health/latest.json) — latest freshness snapshot
- [`feed.xml`](https://r3dz4r.github.io/datapulse-my/feed.xml) — dataset health change feed
- [`datapulse.schema.json`](https://r3dz4r.github.io/datapulse-my/datapulse.schema.json) — manifest schema

To consume the portfolio:

1. Fetch [`llms.txt`](https://r3dz4r.github.io/datapulse-my/llms.txt) for the curated index.
2. Fetch [`datapulse.json`](https://r3dz4r.github.io/datapulse-my/datapulse.json)
   for the machine-readable manifest, including licence, refresh cadence, and
   geographic coverage.
3. Fetch [`health/latest.json`](https://r3dz4r.github.io/datapulse-my/health/latest.json)
   to check freshness before use.
4. Cite each dataset according to its licence and attribution requirements.

[`robots.txt`](https://r3dz4r.github.io/datapulse-my/robots.txt) allows all agents;
[`scripts/verify_agent_ready.sh`](https://github.com/r3dz4r/datapulse-my/blob/main/scripts/verify_agent_ready.sh)
is the agent-consumer self-test.

## Included datasets

- [Malaysian Fuel Prices](data/fuelprice.md) — Samples:
  [CSV](samples/fuelprice.csv), [JSON](samples/fuelprice.json)
- [ePerolehan Tender Notices (DIIKLANKAN)](data/eperolehan-diklankan.md) —
  [Sample JSON](samples/eperolehan-diklankan.json)
- [PriceCatcher (Daily Grocery Prices)](data/pricecatcher.md) — Samples:
  [main CSV](samples/pricecatcher.csv),
  [item lookup](samples/pricecatcher_lookup_item.csv),
  [premise lookup](samples/pricecatcher_lookup_premise.csv)

### Daily Reference Data (Bank Negara Malaysia)

These four BNM reference-rate datasets are updated on weekdays at fixed MYT
publication times:

- [BNM Daily Exchange Rates (0900)](data/exchangerates_daily_0900.md) —
  [Sample JSON](samples/exchangerates_daily_0900.json)
- [BNM Daily Exchange Rates (1130)](data/exchangerates_daily_1130.md) —
  [Sample JSON](samples/exchangerates_daily_1130.json)
- [BNM Daily Exchange Rates (1200)](data/exchangerates_daily_1200.md) —
  [Sample JSON](samples/exchangerates_daily_1200.json)
- [BNM Daily Exchange Rates (1700)](data/exchangerates_daily_1700.md) —
  [Sample JSON](samples/exchangerates_daily_1700.json)

- [MET Malaysia Weather Forecast](data/met_weather.md) — Samples:
  [CSV](samples/met_weather.csv), [JSON](samples/met_weather.json)
- [DOE APIMS Air Quality (Hourly)](data/doe_apims.md) —
  [Sample JSON](samples/doe_apims.json)
- [DOE RQIMS River Water Quality (Continuous)](data/doe_rqims.md) —
  [Sample JSON](samples/doe_rqims.json)
- [DOE MQIMS Marine Water Quality (Monthly)](data/doe_mqims.md) —
  [Sample JSON](samples/doe_mqims.json)
- [KKM iDengue Weekly Dengue Cases](data/kkm_idengue.md) —
  [Sample JSON](samples/kkm_idengue.json)
- [OpenDOSM Crime by District (Annual)](data/dosm_crime_district.md) —
  [Sample JSON](samples/dosm_crime_district.json)
- [OpenDOSM Monthly CPI by State](data/dosm_cpi_state.md) —
  [Sample JSON](samples/dosm_cpi_state.json)
- [OpenDOSM Annual Real GDP by State](data/dosm_gdp_state_real_supply.md) —
  [Sample JSON](samples/dosm_gdp_state_real_supply.json)
- [OpenDOSM Quarterly Real GDP](data/dosm_gdp_qtr_real.md) —
  [Sample JSON](samples/dosm_gdp_qtr_real.json)
- [OpenDOSM Annual Real GDP by Supply Sector](data/dosm_gdp_annual_real_supply.md) —
  [Sample JSON](samples/dosm_gdp_annual_real_supply.json)
- [OpenDOSM Monthly Trade Headline](data/dosm_trade_headline.md) —
  [Sample JSON](samples/dosm_trade_headline.json)
- [OpenDOSM Monthly CPI Inflation by Division](data/dosm_cpi_inflation.md) —
  [Sample JSON](samples/dosm_cpi_inflation.json)
- [OpenDOSM Monthly Trade by End Use (BEC)](data/dosm_trade_enduse_bec.md) —
  [Sample JSON](samples/dosm_trade_enduse_bec.json)
- [OpenDOSM Quarterly Labour Force Statistics](data/dosm_lfs_qtr.md) —
  [Sample JSON](samples/dosm_lfs_qtr.json)
- [OpenDOSM Quarterly Labour Force Statistics by State](data/dosm_lfs_qtr_state.md) —
  [Sample JSON](samples/dosm_lfs_qtr_state.json)
- [OpenDOSM Annual Employment by Sector and Sex](data/dosm_employment_sector.md) —
  [Sample JSON](samples/dosm_employment_sector.json)
- [OpenDOSM Annual Population by State](data/dosm_population_state.md) —
  [Sample JSON](samples/dosm_population_state.json)
- [OpenDOSM Annual Nominal GDP by Supply Sector](data/dosm_gdp_annual_nominal_supply.md) —
  [Sample JSON](samples/dosm_gdp_annual_nominal_supply.json)
- [OpenDOSM Quarterly Nominal GDP](data/dosm_gdp_qtr_nominal.md) —
  [Sample JSON](samples/dosm_gdp_qtr_nominal.json)
- [OpenDOSM Quarterly Real GDP (Seasonally Adjusted)](data/dosm_gdp_qtr_real_sa.md) —
  [Sample JSON](samples/dosm_gdp_qtr_real_sa.json)
- [OpenDOSM Annual Nominal GDP and GNI](data/dosm_gdp_gni_annual_nominal.md) —
  [Sample JSON](samples/dosm_gdp_gni_annual_nominal.json)
- [OpenDOSM Monthly Core CPI Inflation by Division](data/dosm_cpi_core_inflation.md) —
  [Sample JSON](samples/dosm_cpi_core_inflation.json)
- [OpenDOSM Monthly CPI Inflation by State and Division](data/dosm_cpi_state_inflation.md) —
  [Sample JSON](samples/dosm_cpi_state_inflation.json)
- [OpenDOSM Monthly Producer Price Index](data/dosm_ppi.md) —
  [Sample JSON](samples/dosm_ppi.json)
- [OpenDOSM Annual Labour Force Statistics](data/dosm_lfs_year.md) —
  [Sample JSON](samples/dosm_lfs_year.json)
- [OpenDOSM Monthly Labour Force Statistics](data/dosm_lfs_month.md) —
  [Sample JSON](samples/dosm_lfs_month.json)
- [OpenDOSM Monthly Trade by SITC Section](data/dosm_trade_sitc_1d.md) —
  [Sample JSON](samples/dosm_trade_sitc_1d.json)
- [OpenDOSM IPI for Export-Oriented Divisions](data/dosm_ipi_export.md) —
  [Sample JSON](samples/dosm_ipi_export.json)
- [OpenDOSM IPI for Domestic-Oriented Divisions](data/dosm_ipi_domestic.md) —
  [Sample JSON](samples/dosm_ipi_domestic.json)
- [data.gov.my Monthly Interest Rates](data/dgm_interest_rates.md) —
  [Sample JSON](samples/dgm_interest_rates.json)
- [data.gov.my Quarterly Federal Government Revenue](data/dgm_federal_finance_qtr_revenue.md) —
  [Sample JSON](samples/dgm_federal_finance_qtr_revenue.json)
- [data.gov.my Quarterly Federal Operating Expenditure](data/dgm_federal_finance_qtr_oe.md) —
  [Sample JSON](samples/dgm_federal_finance_qtr_oe.json)
- [data.gov.my State Government Expenditure](data/dgm_state_finance_expenditure.md) —
  [Sample JSON](samples/dgm_state_finance_expenditure.json)

DataPulse MY currently tracks forty datasets in total.

## Current coverage

### Refresh cadence

| Dataset | Refresh cadence |
| --- | --- |
| Malaysian Fuel Prices (`fuelprice`) | Weekly |
| ePerolehan Tender Notices (`eperolehan-diklankan`) | Daily |
| PriceCatcher (`pricecatcher`) | Monthly |
| BNM Daily Exchange Rates (`exchangerates_daily_0900`) | Daily on weekdays at 0900 MYT |
| BNM Daily Exchange Rates (`exchangerates_daily_1130`) | Daily on weekdays at 1130 MYT |
| BNM Daily Exchange Rates (`exchangerates_daily_1200`) | Daily on weekdays at 1200 MYT |
| BNM Daily Exchange Rates (`exchangerates_daily_1700`) | Daily on weekdays at 1700 MYT |
| MET Malaysia Weather Forecast (`met_weather`) | Daily |
| DOE APIMS Air Quality (`doe_apims`) | Hourly |
| DOE RQIMS River Water Quality (`doe_rqims`) | Hourly |
| DOE MQIMS Marine Water Quality (`doe_mqims`) | Monthly |
| KKM iDengue (`kkm_idengue`) | Daily |
| OpenDOSM Crime by District (`dosm_crime_district`) | Annual |
| OpenDOSM CPI by State (`dosm_cpi_state`) | Monthly |
| OpenDOSM GDP by State (`dosm_gdp_state_real_supply`) | Annual |
| OpenDOSM Quarterly Real GDP (`dosm_gdp_qtr_real`) | Quarterly |
| OpenDOSM Annual Real GDP by Supply Sector (`dosm_gdp_annual_real_supply`) | Annual |
| OpenDOSM Trade Headline (`dosm_trade_headline`) | Monthly |
| OpenDOSM CPI Inflation by Division (`dosm_cpi_inflation`) | Monthly |
| OpenDOSM Trade by End Use (`dosm_trade_enduse_bec`) | Monthly |
| OpenDOSM Labour Force Statistics (`dosm_lfs_qtr`) | Quarterly |
| OpenDOSM Labour Force Statistics by State (`dosm_lfs_qtr_state`) | Quarterly |
| OpenDOSM Employment by Sector and Sex (`dosm_employment_sector`) | Annual |
| OpenDOSM Population by State (`dosm_population_state`) | Annual |
| OpenDOSM Nominal GDP by Supply Sector (`dosm_gdp_annual_nominal_supply`) | Annual |
| OpenDOSM Quarterly Nominal GDP (`dosm_gdp_qtr_nominal`) | Quarterly |
| OpenDOSM Seasonally Adjusted Real GDP (`dosm_gdp_qtr_real_sa`) | Quarterly |
| OpenDOSM Annual Nominal GDP and GNI (`dosm_gdp_gni_annual_nominal`) | Annual |
| OpenDOSM Core CPI Inflation (`dosm_cpi_core_inflation`) | Monthly |
| OpenDOSM State CPI Inflation (`dosm_cpi_state_inflation`) | Monthly |
| OpenDOSM Producer Price Index (`dosm_ppi`) | Monthly |
| OpenDOSM Annual Labour Force Statistics (`dosm_lfs_year`) | Annual |
| OpenDOSM Monthly Labour Force Statistics (`dosm_lfs_month`) | Monthly |
| OpenDOSM Trade by SITC Section (`dosm_trade_sitc_1d`) | Monthly |
| OpenDOSM Export-Oriented IPI (`dosm_ipi_export`) | Monthly |
| OpenDOSM Domestic-Oriented IPI (`dosm_ipi_domestic`) | Monthly |
| data.gov.my Interest Rates (`dgm_interest_rates`) | Monthly |
| data.gov.my Federal Revenue (`dgm_federal_finance_qtr_revenue`) | Quarterly |
| data.gov.my Federal Operating Expenditure (`dgm_federal_finance_qtr_oe`) | Quarterly |
| data.gov.my State Government Expenditure (`dgm_state_finance_expenditure`) | Annual |

## How to use it

Start with [`datapulse.json`](datapulse.json) to discover datasets and their
official sources. Follow each `health_report` link for a plain-language
assessment, or consume the matching file under `data/json/` in an automated
workflow.

For example, a data pipeline can inspect `status` and `freshness_days` before
processing a source, while a researcher can review the known quirks before
designing a collection method.

## Roadmap

- Scheduled health checks — weekly.
- RSS feed — available.
- Status badges — available.
- More datasets — planned.

## Adopt a dataset

Know a Malaysian public dataset that deserves dependable health metadata?
Adopt it: verify its source and licence, document its schema and quirks, and
submit a health report. See [CONTRIBUTING.md](CONTRIBUTING.md) for the expected
three-file contribution model.

## Licence

DataPulse MY is released under the [MIT License](LICENSE). Source datasets
remain subject to the licences and attribution requirements stated in their
individual health reports.
