# DataPulse MY

**Live dashboard:** https://www.data-pulse.my

**Open in Google Colab:** [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/r3dz4r/datapulse-my/blob/main/docs/trust-layer-notebook.ipynb)

[![M8ven Verified](https://m8ven.ai/badge/mcp/r3dz4r-datapulse-my-fsfgq3)](https://m8ven.ai/mcp/r3dz4r-datapulse-my-fsfgq3)
[![mcpgrade](https://img.shields.io/badge/mcpgrade-100%2F100%20(Grade%20A)-success?style=flat&logo=anthropic)](https://www.npmjs.com/package/mcpgrade)
<!-- m8ven-verify: d1505f0f7e0429963789e95995216ca3 -->

> **🤖 AI-agent-ready** — Wire DataPulse MY into Claude Desktop, Cursor, Cline, or
> any MCP-compatible client with one config block. Your agent gets **389 official
> Malaysian datasets** — including **30 GTFS transit feeds (KTMB, Prasarana,
> BAS.MY)** — with declared licences and an honest nine-status trust taxonomy
> instead of a blanket green checkmark.
>
> → [Connect your AI agent in 30 seconds](#ai-agent-ready--what-it-means-for-you)

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
- **Pipeline health gate:** fail the build when a required dataset probe has
  remained unavailable for more than 24 hours.
- **RAG knowledge base:** consume the JSON envelopes as structured context for
  a chatbot answering "what's the latest BNM rate?"

## Dataset health

Health is reported as `fresh`, `aging`, `stale`, `discontinued`, `degraded`,
`browser-dependent`, `unreachable`, `unknown`, `unknown-freshness`, or
`reference`. Unknown freshness means the URL and content shape work, but neither
a Last-Modified header nor a parseable content date proves when the data was
updated. Reference means versioned lookup data is reachable and its record count
is measured, while date-based freshness does not apply. The public
[`_trust_summary`](health/latest.json) shows the distribution and explicitly
counts missing freshness and row-count signals.

**Discontinued** — The source has stopped publishing new data. The data is
frozen at the last known content date. This is not a freshness failure — it's a
publisher decision.

Current distribution (`_trust_summary`): [92 fresh](badges/status-fresh.svg) · [126 aging](badges/status-aging.svg) · [154 stale](badges/status-stale.svg) · [1 discontinued](badges/status-discontinued.svg) · [5 browser-dependent](badges/status-browser-dependent.svg) · [11 reference](badges/status-reference.svg)

<!--
Statuses with zero count are omitted. Full per-dataset health is in
[health/latest.json](health/latest.json) and per-dataset badges live in
[badges/](badges/).
-->

**Subscribe:** [RSS feed](feed.xml) — get notified when dataset health changes.

> **⚠️ Status: active development.** Dashboards and health snapshots update as
> probes complete. Per-dataset reports under `data/{id}.md` may briefly lag
> behind the live health snapshot in `health/latest.json` (a regeneration gap
> that is being closed). Coverage and quality improve with each tagged release;
> expect rough edges. Track progress via the [GitHub Releases](../../releases)
> page — `v0.4.0` is the current milestone.

### Browser-dependent datasets

Five sources (currently 1.4% of the catalogue) require a real browser to probe because their
source pages render client-side JavaScript: `eperolehan-diklankan`,
`doe_apims`, `doe_rqims`, `doe_mqims`, and `kkm_idengue`.

DataPulse uses **[Camofox](https://github.com/jo-inc/camofox-browser)**, a
self-hosted patched headless-Chromium sidecar, to probe these. The probe path
is [`check.sh`](scripts/check.sh) → Camofox sidecar → DOM snapshot →
content-date extraction.

**To enable browser probing:**

1. Run the Camofox Docker sidecar on a reachable address (default
   `http://localhost:9377`). The probe script and the GitHub Actions
   workflow pick this up from the `CAMOFOX_BASE_URL` environment
   variable; nothing in this repo encodes a public IP.
2. Set `CAMOFOX_BASE_URL` to that address.
3. Restart the timer with `systemctl restart datapulse-health.timer`.

Without Camofox, those five datasets will sit at `browser-dependent` — the
**honest** status: DataPulse cannot probe them without a browser, so it says
so rather than failing silently. See
[`scripts/smoke_browser_probes.sh`](scripts/smoke_browser_probes.sh) for
isolated smoke tests.

### Legal

DataPulse probes publicly-published open-data sources. We do not bypass
authentication, CAPTCHAs, or terms-of-service restrictions. Every source we
probe is publicly available without login; the data is aggregate/non-personal;
and the probe respects each dataset's declared refresh frequency.

All scraping is rate-limited (5-minute cadence, dataset-tier cadence applied)
and identifies itself via User-Agent. Sources we cannot probe without
authentication, CAPTCHA bypass, or ToS violation are marked `unreachable` or
`browser-dependent` — never silently scraped through a workaround.

If you are a data source maintainer and would like DataPulse to adjust its probe
cadence, exclude a dataset, or remove it from the manifest, please open a GitHub
issue or contact the maintainers.

## AI-agent-ready — what it means for you

Give your organisation's AI tools current, licensed, and verified Malaysian
public data without first building a custom integration. DataPulse MY makes the
full portfolio discoverable from one self-describing index, ready for agents,
RAG systems, and internal knowledge tools to consume.

**What being AI-ready gives you**

- **Zero integration work:** an AI agent or LLM/RAG system fetches one
  [`llms.txt`](https://r3dz4r.github.io/datapulse-my/llms.txt) and can use the
  entire portfolio immediately — no scraping, API-key setup, or data-format
  reverse-engineering.
- **Honest freshness signals:** a 5-minute timer probes datasets when their
  cadence tier is due, separating HTTP
  reachability, browser dependency, schema validity, and source freshness so
  missing evidence is visible instead of being labelled healthy.
  Consumers can also use `anomaly_detected` as an explainable, orthogonal
  freshness-delta signal without changing the ten-status taxonomy.
- **Machine-readable and licence-clear:** every dataset has a JSON envelope with
  its schema, licence, and refresh cadence, giving legal and engineering teams
  the information they need to approve and integrate it.
- **Trustworthy for AI:** verified official sources and explicit licences let
  agents cite and use the data without permission ambiguity.
- **RAG and knowledge-base ready:** drop the envelopes into a retrieval pipeline
  to ground chatbots and AI tools in current Malaysian public data.

**Every manifest dataset declares either CC BY 4.0 or OGL licensing and is
assessed with the honest ten-status trust taxonomy.** Each entry retains its
human-readable `steward` and supplies a stable `custodian` ID resolved through
[`custodians.json`](custodians.json) for publisher-level provenance.

### MCP server (read-only)

DataPulse MY also exposes an AI-ready, read-only MCP server so agents can query
the catalogue natively:

- Endpoint: `https://mcp.data-pulse.my/mcp` (Streamable HTTP, no auth)
Verified by mcpgrade: 100/100 (Grade A), 16 tools, last audited 2026-08-17.
<!-- BEGIN mcp-tools -->
- 16 tools: `search_datasets`, `get_dataset`, `find_stale`, `find_anomalies`, `find_deteriorating`, `find_recovering`, `find_unreliable`, `find_schema_drift`, `check_reconciliation`, `get_provenance`, `get_evidence`, `verify_evidence`, `trust_verdict`, `verify_attestation`, `find_by_licence`, `usage_summary`

The public endpoint is live and serves all 16 read-only tools over the
389-dataset catalogue.
<!-- END mcp-tools -->
- 8 resources plus 1 resource template, including `datapulse://attestations` and the signed daily probe-attestation index.

`get_evidence` exposes pipeline receipts; `verify_evidence` performs cached
transport-only live checks and does not update health.

Connect from Claude Desktop:

```json
{
  "mcpServers": {
    "datapulse-my": {
      "transport": "streamable-http",
      "url": "https://mcp.data-pulse.my/mcp"
    }
  }
}
```

See [`llms.txt`](https://r3dz4r.github.io/datapulse-my/llms.txt) for the full
discovery index, and [`docs/mcp-deploy.md`](./docs/mcp-deploy.md) for the
deployment architecture.

### Authenticated buyer API

Paying integrations use the separate, versioned `/api/v1/` buyer API. It uses
`X-API-Key` authentication, durable per-key request limits, and audit logs;
the public MCP endpoint above remains intentionally unauthenticated. See the
[buyer API reference](./docs/buyer-api-reference.md) for endpoint and operator
details.

### How to consume the data

Verify access:

```sh
curl -s https://r3dz4r.github.io/datapulse-my/llms.txt
```

- [`llms.txt`](https://r3dz4r.github.io/datapulse-my/llms.txt) — curated dataset index
- [`datapulse.json`](https://r3dz4r.github.io/datapulse-my/datapulse.json) — manifest with a declared `$schema`
- [`health/latest.json`](https://r3dz4r.github.io/datapulse-my/health/latest.json) — latest freshness snapshot
- [`health/trends.json`](https://r3dz4r.github.io/datapulse-my/health/trends.json) — published freshness trends and publish-reliability evidence
- [`health/drift.json`](https://r3dz4r.github.io/datapulse-my/health/drift.json) — published structural and record-count drift evidence
- [`health/reconciliation.json`](https://r3dz4r.github.io/datapulse-my/health/reconciliation.json) — cross-source publication differences requiring human review, not proof either source is wrong
- [`feed.xml`](https://r3dz4r.github.io/datapulse-my/feed.xml) — dataset health change feed
- [`datapulse.schema.json`](https://r3dz4r.github.io/datapulse-my/datapulse.schema.json) — manifest schema

To consume the portfolio:

1. Fetch [`llms.txt`](https://r3dz4r.github.io/datapulse-my/llms.txt) for the curated index.
2. Fetch [`datapulse.json`](https://r3dz4r.github.io/datapulse-my/datapulse.json)
   for the machine-readable manifest, including licence, refresh cadence, and
   geographic coverage.
3. Fetch [`health/latest.json`](https://r3dz4r.github.io/datapulse-my/health/latest.json)
   to check freshness before use.
4. Fetch [`health/trends.json`](https://r3dz4r.github.io/datapulse-my/health/trends.json) for published trend and reliability evidence.
5. Fetch [`health/reconciliation.json`](https://r3dz4r.github.io/datapulse-my/health/reconciliation.json) for cross-source differences; treat discrepancies as requiring human review, not proof either source is wrong.
6. Cite each dataset according to its licence and attribution requirements.

[`robots.txt`](https://r3dz4r.github.io/datapulse-my/robots.txt) allows all agents;
[`scripts/verify_agent_ready.sh`](https://github.com/r3dz4r/datapulse-my/blob/main/scripts/verify_agent_ready.sh)
is the agent-consumer self-test.

**For humans wiring their own agents:** see the [MCP server](#mcp-server-read-only)
section below for the Claude Desktop / Cursor / Cline config block, or the full
integration guide at [`docs/mcp-deploy.md`](./docs/mcp-deploy.md).

**Wire it into Claude Desktop** via `claude_desktop_config.json` (30 seconds, no
API key):

```json
{
  "mcpServers": {
    "datapulse-my": {
      "transport": "streamable-http",
      "url": "https://mcp.data-pulse.my/mcp"
    }
  }
}
```

Restart Claude Desktop, confirm the hammer icon shows "datapulse-my" with 13
tools in the runtime order above. Cursor / Cline use the same JSON in their MCP config panel.

## Included datasets

- [Malaysian Fuel Prices](data/fuelprice.md) — Samples:
  [CSV](samples/fuelprice.csv), [JSON](samples/fuelprice.json)
- [ePerolehan Tender Notices (DIIKLANKAN)](data/eperolehan-diklankan.md) —
  [Sample JSON](samples/eperolehan-diklankan.json)
- [PriceCatcher (Grocery Prices)](data/pricecatcher.md) — Samples:
  [main CSV](samples/pricecatcher.csv),
  [item lookup](samples/pricecatcher_lookup_item.csv),
  [premise lookup](samples/pricecatcher_lookup_premise.csv)

### Daily reference data

Daily-published reference datasets from official Malaysian sources. Each
agency publishes on its own schedule, declared in `refresh_frequency`; the
dashboard combines the date-only source value with the publication time and
does not infer a time from midnight or UTC conversion.

#### Bank Negara Malaysia (BNM)

- [BNM Daily Exchange Rates (0900)](data/exchangerates_daily_0900.md) —
  [Sample JSON](samples/exchangerates_daily_0900.json)
- [BNM Daily Exchange Rates (1130)](data/exchangerates_daily_1130.md) —
  [Sample JSON](samples/exchangerates_daily_1130.json)
- [BNM Daily Exchange Rates (1200)](data/exchangerates_daily_1200.md) —
  [Sample JSON](samples/exchangerates_daily_1200.json)
- [BNM Daily Exchange Rates (1700)](data/exchangerates_daily_1700.md) —
  [Sample JSON](samples/exchangerates_daily_1700.json)
- [Overnight Policy Rate (OPR)](data/bnm_opr.md)
- [Base Rates / BLR / Effective LR](data/bnm_base_rate.md)
- [Kuala Lumpur USD/MYR Reference Rate](data/bnm_kl_usd_myr.md)
- [Interest Rates: Banking Institutions](data/bnm_interest_rate.md)
- [Interest Volume: Banking Institutions](data/bnm_interest_volume.md)
- [Interbank Swap](data/bnm_interbank_swap.md)
- [Kijang Emas (Gold Reference Price)](data/bnm_kijang_emas.md)
- [Malaysia Overnight Rate (MYOR)](data/bnm_myor.md)

#### MET Malaysia

- [MET Malaysia Weather Forecast](data/met_weather.md) — Samples:
  [CSV](samples/met_weather.csv), [JSON](samples/met_weather.json)

#### Department of Environment (DOE)

- [DOE APIMS Air Quality (Hourly)](data/doe_apims.md) —
  [Sample JSON](samples/doe_apims.json)
- [DOE RQIMS River Water Quality (Continuous)](data/doe_rqims.md) —
  [Sample JSON](samples/doe_rqims.json)
- [DOE MQIMS Marine Water Quality (Monthly)](data/doe_mqims.md) —
  [Sample JSON](samples/doe_mqims.json)

#### KKM (Ministry of Health)

- [KKM iDengue Weekly Dengue Cases](data/kkm_idengue.md) —
  [Sample JSON](samples/kkm_idengue.json)

#### OpenDOSM (DOSM open data portal)

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
- [OpenDOSM Annual Births by State](data/dosm_birth_state.md) —
  [Sample JSON](samples/dosm_birth_state.json)
- [OpenDOSM Annual Deaths by State](data/dosm_death_state.md) —
  [Sample JSON](samples/dosm_death_state.json)
- [OpenDOSM Annual Maternal Deaths by State](data/dosm_death_maternal_state.md) —
  [Sample JSON](samples/dosm_death_maternal_state.json)
- [OpenDOSM Annual Marriages by State and Sex](data/dosm_marriages_state.md) —
  [Sample JSON](samples/dosm_marriages_state.json)
- [OpenDOSM Household Income, Malaysia](data/dosm_hh_income.md) —
  [Sample JSON](samples/dosm_hh_income.json)
- [OpenDOSM Household Income by State](data/dosm_hh_income_state.md) —
  [Sample JSON](samples/dosm_hh_income_state.json)
- [OpenDOSM Household Income by District](data/dosm_hh_income_district.md) —
  [Sample JSON](samples/dosm_hh_income_district.json)
- [OpenDOSM Poverty, Malaysia](data/dosm_hh_poverty.md) —
  [Sample JSON](samples/dosm_hh_poverty.json)
- [OpenDOSM Poverty by State](data/dosm_hh_poverty_state.md) —
  [Sample JSON](samples/dosm_hh_poverty_state.json)
- [OpenDOSM Poverty by District](data/dosm_hh_poverty_district.md) —
  [Sample JSON](samples/dosm_hh_poverty_district.json)
- [OpenDOSM Income Inequality, Malaysia](data/dosm_hh_inequality.md) —
  [Sample JSON](samples/dosm_hh_inequality.json)
- [OpenDOSM Income Inequality by State](data/dosm_hh_inequality_state.md) —
  [Sample JSON](samples/dosm_hh_inequality_state.json)
- [OpenDOSM Income Inequality by District](data/dosm_hh_inequality_district.md) —
  [Sample JSON](samples/dosm_hh_inequality_district.json)
- [OpenDOSM Household Expenditure by DUN](data/dosm_hh_expenditure_dun.md) —
  [Sample JSON](samples/dosm_hh_expenditure_dun.json)
- [OpenDOSM Household Expenditure by Parliamentary Constituency](data/dosm_hh_expenditure_parlimen.md) —
  [Sample JSON](samples/dosm_hh_expenditure_parlimen.json)
- [OpenDOSM Annual Population, Malaysia](data/dosm_population_malaysia.md) —
  [Sample JSON](samples/dosm_population_malaysia.json)
- [OpenDOSM Annual Population by Parliamentary Constituency](data/dosm_population_parlimen.md) —
  [Sample JSON](samples/dosm_population_parlimen.json)
- [OpenDOSM Annual Deaths by District and Sex](data/dosm_death_district_sex.md) —
  [Sample JSON](samples/dosm_death_district_sex.json)
- [OpenDOSM Annual Marriages by State, Age, and Sex](data/dosm_marriages_state_age.md) —
  [Sample JSON](samples/dosm_marriages_state_age.json)
- [OpenDOSM Annual Fertility](data/dosm_fertility.md) —
  [Sample JSON](samples/dosm_fertility.json)
- [OpenDOSM Annual Maternal Deaths, Malaysia](data/dosm_death_maternal.md) —
  [Sample JSON](samples/dosm_death_maternal.json)

#### data.gov.my

- [data.gov.my Monthly Interest Rates](data/dgm_interest_rates.md) —
  [Sample JSON](samples/dgm_interest_rates.json)
- [data.gov.my Quarterly Federal Government Revenue](data/federal_finance_qtr_revenue.md) —
  [Sample JSON](samples/federal_finance_qtr_revenue.json)
- [data.gov.my Quarterly Federal Operating Expenditure](data/federal_finance_qtr_oe.md) —
  [Sample JSON](samples/federal_finance_qtr_oe.json)
- [data.gov.my Monthly Money Aggregates](data/dgm_money_aggregates.md) —
  [Sample JSON](samples/dgm_money_aggregates.json)
- [data.gov.my Monthly Payment Systems](data/dgm_payments_systems.md) —
  [Sample JSON](samples/dgm_payments_systems.json)
- [data.gov.my Monthly Payment Instruments](data/dgm_payments_instruments.md) —
  [Sample JSON](samples/dgm_payments_instruments.json)
- [data.gov.my Monthly Payment Channels](data/dgm_payments_channels.md) —
  [Sample JSON](samples/dgm_payments_channels.json)
- [data.gov.my Annual Interest Rates](data/dgm_interest_rates_annual.md) —
  [Sample JSON](samples/dgm_interest_rates_annual.json)
- [data.gov.my Annual EPF Dividend Rates](data/epf_dividend.md) —
  [Sample JSON](samples/epf_dividend.json)
- [data.gov.my Monthly Vehicle Registrations by Type and Fuel](data/dgm_vehicle_registrations_type_fuel.md) —
  [Sample JSON](samples/dgm_vehicle_registrations_type_fuel.json)
- [data.gov.my Daily FPX Transactions](data/dgm_payments_transactions_fpx.md) —
  [Sample JSON](samples/dgm_payments_transactions_fpx.json)
- [data.gov.my Healthcare Staff by State and Staff Type](data/healthcare_staff.md) —
  [Sample JSON](samples/healthcare_staff.json)
- [data.gov.my Daily Blood Donations by Blood Group and State](data/blood_donations_state.md) —
  [Sample JSON](samples/blood_donations_state.json)
- [data.gov.my Infant Immunisation Coverage](data/infant_immunisation.md) —
  [Sample JSON](samples/infant_immunisation.json)
- [data.gov.my Sexually Transmitted Diseases by State](data/std_state.md) —
  [Sample JSON](samples/std_state.json)
- [data.gov.my Daily PeKaB40 Health Screenings by State](data/pekab40_screenings_state.md) —
  [Sample JSON](samples/pekab40_screenings_state.json)
- [data.gov.my Malaysian National Health Accounts Expenditure](data/mnha.md) —
  [Sample JSON](samples/mnha.json)
- [data.gov.my Monthly Electricity Supply](data/electricity_supply.md) —
  [Sample JSON](samples/electricity_supply.json)
- [data.gov.my Water Production by State](data/water_production.md) —
  [Sample JSON](samples/water_production.json)
- [data.gov.my Access to Treated Water by State and Strata](data/water_access.md) —
  [Sample JSON](samples/water_access.json)
- [data.gov.my Monthly KTMB Ridership](data/dgm_ktmb_ridership_monthly.md) —
  [Sample JSON](samples/dgm_ktmb_ridership_monthly.json)
- [data.gov.my Cellular Subscribers by Plan Type](data/cellular_subscribers.md) —
  [Sample JSON](samples/cellular_subscribers.json)
- [data.gov.my Prisoners by State and Sex](data/prisoners_state.md) —
  [Sample JSON](samples/prisoners_state.json)
- [data.gov.my Drug Addicts by State and Age Group](data/drug_addicts_age.md) —
  [Sample JSON](samples/drug_addicts_age.json)
- [data.gov.my Female Representation in Local Authorities](data/local_authority_sex.md) —
  [Sample JSON](samples/local_authority_sex.json)
- [data.gov.my Female Representation in Parliament](data/parliament_sex.md) —
  [Sample JSON](samples/parliament_sex.json)
- [data.gov.my Monthly Marine Fish Landings by State](data/fish_landings.md) —
  [Sample JSON](samples/fish_landings.json)
- [data.gov.my Crop Area and Production by State](data/crops_state.md) —
  [Sample JSON](samples/crops_state.json)
- [data.gov.my Public Education Institutions by District](data/schools_district.md) —
  [Sample JSON](samples/schools_district.json)
### GTFS transit feeds

The transport namespace adds 16 GTFS Static schedule ZIPs and 14 GTFS Realtime
vehicle-position protobuf feeds for KTMB, Prasarana, and BAS.MY services. Static
samples are under [`samples/gtfs-static/`](samples/gtfs-static/) and realtime
snapshots are under [`samples/gtfs-realtime/`](samples/gtfs-realtime/).

DataPulse MY currently tracks the portfolio declared in `datapulse.json`.

## Current coverage

### Refresh cadence

| Dataset | Refresh cadence |
| --- | --- |
| Malaysian Fuel Prices (`fuelprice`) | Weekly |
| ePerolehan Tender Notices (`eperolehan-diklankan`) | Hourly |
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
| data.gov.my Federal Revenue (`federal_finance_qtr_revenue`) | Quarterly |
| data.gov.my Federal Operating Expenditure (`federal_finance_qtr_oe`) | Quarterly |
| data.gov.my Money Aggregates (`dgm_money_aggregates`) | Monthly |
| data.gov.my Payment Systems (`dgm_payments_systems`) | Monthly |
| data.gov.my Payment Instruments (`dgm_payments_instruments`) | Monthly |
| data.gov.my Payment Channels (`dgm_payments_channels`) | Monthly |
| data.gov.my Annual Interest Rates (`dgm_interest_rates_annual`) | Annual |
| data.gov.my EPF Dividend Rates (`epf_dividend`) | Annual |
| data.gov.my Vehicle Registrations by Type and Fuel (`dgm_vehicle_registrations_type_fuel`) | Monthly |
| data.gov.my FPX Transactions (`dgm_payments_transactions_fpx`) | Daily |
| OpenDOSM Births by State (`dosm_birth_state`) | Annual |
| OpenDOSM Deaths by State (`dosm_death_state`) | Annual |
| OpenDOSM Maternal Deaths by State (`dosm_death_maternal_state`) | Annual |
| OpenDOSM Marriages by State and Sex (`dosm_marriages_state`) | Annual |
| data.gov.my Healthcare Staff (`healthcare_staff`) | Annual |
| data.gov.my Blood Donations by State (`blood_donations_state`) | Daily |
| data.gov.my Infant Immunisation (`infant_immunisation`) | Annual |
| data.gov.my Sexually Transmitted Diseases by State (`std_state`) | Annual |
| data.gov.my PeKaB40 Screenings by State (`pekab40_screenings_state`) | Daily |
| data.gov.my Malaysian National Health Accounts (`mnha`) | Annual |
| data.gov.my Electricity Supply (`electricity_supply`) | Monthly |
| data.gov.my Water Production (`water_production`) | Annual |
| data.gov.my Treated Water Access (`water_access`) | Annual |
| data.gov.my KTMB Ridership (`dgm_ktmb_ridership_monthly`) | Monthly |
| data.gov.my Cellular Subscribers (`cellular_subscribers`) | Annual |
| data.gov.my Prisoners by State and Sex (`prisoners_state`) | Annual |
| data.gov.my Drug Addicts by State and Age (`drug_addicts_age`) | Annual |
| data.gov.my Female Representation in Local Authorities (`local_authority_sex`) | Annual |
| data.gov.my Female Representation in Parliament (`parliament_sex`) | Annual |
| data.gov.my Marine Fish Landings (`fish_landings`) | Monthly |
| data.gov.my Crops by State (`crops_state`) | Annual |
| data.gov.my Schools by District (`schools_district`) | Annual |
| OpenDOSM Household Income, Malaysia (`dosm_hh_income`) | Biennial to triennial (survey years) |
| OpenDOSM Household Income by State (`dosm_hh_income_state`) | Biennial to triennial (survey years) |
| OpenDOSM Household Income by District (`dosm_hh_income_district`) | Biennial to triennial (survey years) |
| OpenDOSM Poverty, Malaysia (`dosm_hh_poverty`) | Biennial to triennial (survey years) |
| OpenDOSM Poverty by State (`dosm_hh_poverty_state`) | Biennial to triennial (survey years) |
| OpenDOSM Poverty by District (`dosm_hh_poverty_district`) | Biennial to triennial (survey years) |
| OpenDOSM Income Inequality, Malaysia (`dosm_hh_inequality`) | Biennial to triennial (survey years) |
| OpenDOSM Income Inequality by State (`dosm_hh_inequality_state`) | Biennial to triennial (survey years) |
| OpenDOSM Income Inequality by District (`dosm_hh_inequality_district`) | Biennial to triennial (survey years) |
| OpenDOSM Household Expenditure by DUN (`dosm_hh_expenditure_dun`) | Biennial to triennial (survey years) |
| OpenDOSM Household Expenditure by Parliament (`dosm_hh_expenditure_parlimen`) | Biennial to triennial (survey years) |
| OpenDOSM Population, Malaysia (`dosm_population_malaysia`) | Annual |
| OpenDOSM Population by Parliament (`dosm_population_parlimen`) | Annual |
| OpenDOSM Deaths by District and Sex (`dosm_death_district_sex`) | Annual |
| OpenDOSM Marriages by State, Age, and Sex (`dosm_marriages_state_age`) | Annual |
| OpenDOSM Fertility (`dosm_fertility`) | Annual |
| OpenDOSM Maternal Deaths, Malaysia (`dosm_death_maternal`) | Annual |

## How to use it

Start with [`datapulse.json`](datapulse.json) to discover datasets and their
official sources. Follow each `health_report` link for a plain-language
assessment, or consume the matching file under `data/json/` in an automated
workflow.

For example, a data pipeline can inspect `status`, `content_freshness_date`, and
`freshness_signal_source` before processing a source, while a researcher can
review the known quirks before designing a collection method.

## Monitoring

- The VPS `datapulse-health.timer` wakes every 5 minutes and runs only the
  datasets whose cadence tier is due.
- GitHub Actions performs a full weekly probe as a fallback and republishes the
  generated health, badge, feed, README, catalog snapshot, and delta artifacts.
- RSS feed — available.
- Status badges — available.
- More datasets — planned.

## Adopt a dataset

Know a Malaysian public dataset that deserves dependable health metadata?
Adopt it: verify its source and licence, document its schema and quirks, and
submit a health report. See [CONTRIBUTING.md](CONTRIBUTING.md) for the expected
three-file contribution model.

New contributors can start with the repository's
[Good first issues](https://github.com/r3dz4r/datapulse-my/issues?q=is%3Aissue%20is%3Aopen%20label%3A%22good%20first%20issue%22)
or propose a dataset through the GitHub issue forms. Maintainers use
`good first issue` (yellow), `adopt-a-dataset` (blue), `freshness-check`
(blue), `bug` (red), `documentation` (blue), `question` (purple), and
`wontfix` (gray) to route contributions.

## Licence

DataPulse MY is released under the [MIT License](LICENSE). Source datasets
remain subject to the licences and attribution requirements stated in their
individual health reports.
