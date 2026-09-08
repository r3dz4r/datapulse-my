# DataPulse

**Live dashboard:** https://www.data-pulse.my

**Open in Google Colab:** [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/r3dz4r/datapulse-my/blob/main/docs/trust-layer-notebook.ipynb)

[![datapulse-my MCP server](https://glama.ai/mcp/servers/r3dz4r/datapulse-my/badges/score.svg)](https://glama.ai/mcp/servers/r3dz4r/datapulse-my)
[![M8ven Verified](https://m8ven.ai/badge/mcp/r3dz4r-datapulse-my-fsfgq3?variant=verified)](https://m8ven.ai/mcp/r3dz4r-datapulse-my-fsfgq3)
[![mcpgrade](https://img.shields.io/badge/mcpgrade-100%2F100%20(Grade%20A)-success?style=flat&logo=anthropic)](https://www.npmjs.com/package/mcpgrade)
<!-- m8ven-verify: d1505f0f7e0429963789e95995216ca3 -->

> **🤖 AI-agent-ready** — Wire DataPulse into Claude Desktop, Cursor, Cline, or
> any MCP-compatible client with one config block. Your agent gets
> <!-- BEGIN readme-hero -->
**418 official Malaysian datasets** — including **30 GTFS transit feeds (KTMB,
Prasarana, BAS.MY)** — with declared licences and an honest ten-status trust
taxonomy instead of a blanket green checkmark.
<!-- END readme-hero -->
>
> → [Connect your AI agent in 30 seconds](#connect-an-ai-agent)

## This is DataPulse

When an AI quote is wrong, it is often wrong because the **underlying data was
stale, mis-licensed, or unverifiable** — not because the model hallucinated.
An official-looking page does not tell an agent when the dataset behind it last
updated, who published it, whether it may legally be reused, or whether the
observation can be reproduced by a second party.

DataPulse exists to make that uncertainty explicit. It is an open, read-only
**verification layer for Malaysian public data**: it continuously probes
<!-- BEGIN readme-cover -->**418 official datasets**<!-- END readme-cover -->,
and publishes — for each one — machine-readable *evidence* about whether the
source is reachable, how fresh the content is, what licence applies, how the
schema behaves, and when the observation was signed.

It does **not** replace the official source. It documents, on an honest and
reproducible basis, what the official portal states and whether that material is
current, so you know what you are reusing or citing. The verification speaks
for itself: every claim here is a live, checkable artefact, not a promise.

## What we do, simply

- **We watch the sources.** A scheduled probe revisits each dataset under its
  declared cadence and records what it actually finds — reachability, an honest
  freshness signal, schema shape, record counts, and collection quirks.
- **We state the truth plainly.** Instead of a blanket green checkmark, each
  dataset carries one of ten honest health statuses (`fresh`, `aging`, `stale`,
  `discontinued`, `degraded`, `browser-dependent`, `unreachable`, `unknown`,
  `unknown-freshness`, `reference`). A dataset that cannot be proven fresh is
  labelled `unknown-freshness` — not silently treated as healthy.
- **We publish evidence, not just claims.** Each dated observation is signed
  and recorded to an immutable public log, so you can verify *when* DataPulse
  observed the source and that the record has not been altered.
- **We make it machine-readable first.** The whole portfolio is discoverable
  from one index and queryable over a read-only MCP server, so an agent receives
  the same freshness, licence, and provenance signal a careful human reviewer
  would.

## Who this serves

- **AI builders and agent developers**, who want a model to check a Malaysian
  figure's freshness and licence before it cites the number — without building a
  bespoke integration or trusting a scraping pipeline.
- **Researchers, analysts, and journalists**, who need to ground coursework,
  a thesis, a dashboard, or a published figure in data whose currency and licence
  they can actually verify.
- **Compliance and regulatory-monitoring teams**, who must keep a tamper-evident
  trail that an official figure was checked at a known time before it reached a
  product or a public statement.
- **Civic technologists and public servants**, who want a transparent,
  reproducible view of how discoverable and reliably described public data is.

## Why you can trust the verification

Three independent, checkable layers. You do not have to take DataPulse's word —
you can verify each with the published public key, the public Git source record,
and the public transparency log:

| Layer | What it proves | How to check it yourself |
|---|---|---|
| **Signed envelope** | Each per-dataset observation is **Ed25519-signed** over its exact content by a key in the published registry | `python3 scripts/verify_external.py` |
| **Source of record** | The served observation **byte-matches** the versioned Git source | `python3 scripts/verify_external.py` |
| **Temporal witness** | The health statement carries a **Rekor/Sigstore public-log inclusion proof** | `python3 scripts/verify_external.py` |

Run it yourself, from anywhere, with no checkout and no DataPulse code:

```bash
curl -fsSLO https://raw.githubusercontent.com/r3dz4r/datapulse-my/main/scripts/verify_external.py
python3 verify_external.py
```

See [Verify DataPulse externally](docs/verify-datapulse-externally.md) for the
full guide, and [our methodology](#dataset-health) below for how health is judged.

A verification layer is only as honest as its method, so DataPulse deliberately
tells you **when it cannot be sure** — a source that cannot be proven current is
labelled accordingly, never silently marked healthy. That is the boundary we
hold: the platform proves the integrity and timing of its *observations*, not
that an upstream government figure is semantically true. That distinction is the
whole point of an evidence layer, and we do not blur it.

## Dataset health

Health is reported as `fresh`, `aging`, `stale`, `discontinued`, `degraded`,
`browser-dependent`, `unreachable`, `unknown`, `unknown-freshness`, or
`reference`. Unknown freshness means the URL and content shape work, but neither
a Last-Modified header nor a parseable content date proves when the data was
updated. Reference means versioned lookup data is reachable and its record count
is measured, while date-based freshness does not apply. Within the catalogue,
`data_type` refines the reference family without changing the status: `policy-reference`
rows (policy state that stays valid until superseded — BNM OPR is current while
unchanged, not stale) and `reference-current` rows (lookups that must still pass
freshness, such as a bank-rate table that can itself go stale) are judged by their
declared policy, while plain `reference` rows are static. The public
[`_trust_summary`](health/latest.json) shows the distribution and explicitly
counts missing freshness and row-count signals.

**Discontinued** — The source has stopped publishing new data. The data is
frozen at the last known content date. This is not a freshness failure — it's a
publisher decision.

<!-- BEGIN readme-health -->
Current distribution (`_trust_summary`): [94 fresh](badges/status-fresh.svg) · [104 aging](badges/status-aging.svg) · [189 stale](badges/status-stale.svg) · [1 discontinued](badges/status-discontinued.svg) · [4 degraded](badges/status-degraded.svg) · [5 browser-dependent](badges/status-browser-dependent.svg) · [7 unknown-freshness](badges/status-unknown-freshness.svg) · [14 reference](badges/status-reference.svg)
<!-- END readme-health -->

**Subscribe:** [RSS feed](feed.xml) — get notified when dataset health changes.

> **⚠️ Status: active development.** Dashboards and health snapshots update as
> probes complete. Per-dataset reports under `data/{id}.md` may briefly lag
> behind the live health snapshot in `health/latest.json` (a regeneration gap
> that is being closed). Coverage and quality improve with each tagged release;
> expect rough edges. Track progress via the [GitHub Releases](../../releases)
> page.

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

## Methodology

| Topic | DataPulse's position |
|---|---|
| **Health status** | Ten-status taxonomy, judged by reachability + an honest freshness signal (`Last-Modified`, parseable content date, or declared policy) — never a fabricated green checkmark. A series that stopped publishing is `discontinued` (a publisher decision, frozen data), not a freshness failure. |
| **Licence** | Every dataset declares its licence machine-readably. <!-- BEGIN readme-licences -->Creative Commons Attribution 4.0 (285); MBPP Government Open Data Terms (attribution required) (1); MIT License (8); Open Government Licence (Malaysia) (115); Publisher licence not stated; portal disclaimer applies (4); Singapore Open Data Licence v1.0 (attribution required) (5).<!-- END readme-licences --> A second party can reproduce this from `datapulse.json` → `.datasets[].licence`. |
| **Freshness cadence** | Each dataset is probed on its own tiered schedule (5-minute timer, cadence-aware) — `daily` references, `weekly` fuel prices, `monthly` surveys, etc. Always with the human-readable `steward` and a stable `custodian` ID for publisher provenance. |
| **Provenance** | Stable `custodian` per dataset; signed probe attestations per observation |
| **Observed claim** | The platform proves what an official source was *observed to be at a known time* — it does not claim upstream data is semantically true |
| **Read-only + lawful** | Publicly available, authenticated sources only — never bypassed; rate-limited; identifies itself to sources |
| **Verification** | Fresh days are Rekor-witnessed; signed envelopes + Git source-of-record + public-log inclusion, checkable by anyone |

## Connect an AI agent

DataPulse exposes an AI-ready, read-only MCP server so agents can query the
catalogue natively. It provides the same freshness, licence, schema-drift, and
provenance evidence available to a human reviewer.

- Endpoint: `https://mcp.data-pulse.my/mcp` (Streamable HTTP, no auth)
Graded by [mcpgrade](https://www.npmjs.com/package/mcpgrade) — replay with `bash scripts/audit_mcpgrade.sh` (pinned version, writes `artifacts/mcpgrade/`). The canonical tool count lives in `mcp.json` / `agent.json`.

<!-- BEGIN mcp-tools -->
- 18 tools: `search_datasets`, `get_dataset`, `find_stale`, `find_anomalies`, `find_deteriorating`, `find_recovering`, `find_unreliable`, `find_schema_drift`, `check_reconciliation`, `get_provenance`, `get_evidence`, `verify_dataset`, `get_freshness_summary`, `verify_evidence`, `trust_verdict`, `verify_attestation`, `find_by_licence`, `usage_summary`

The public endpoint serves all 18 read-only tools over the
418-dataset catalogue.
<!-- END mcp-tools -->

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

See [`llms.txt`](https://www.data-pulse.my/llms.txt) for the full
discovery index, and [`docs/mcp-deploy.md`](./docs/mcp-deploy.md) for the
deployment architecture.

<!-- BEGIN public-discovery -->
- [LLM index](https://www.data-pulse.my/llms.txt)
- [Agent manifest](https://www.data-pulse.my/agent.json)
- [MCP advertisement](https://www.data-pulse.my/mcp.json)
- [Sitemap](https://www.data-pulse.my/sitemap.xml)
- [MCP endpoint](https://mcp.data-pulse.my/mcp)
<!-- END public-discovery -->

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

Restart Claude Desktop, confirm the hammer icon shows "datapulse-my" with the
read-only tools listed above. Cursor / Cline use the same JSON in their MCP config panel.

## Included datasets

<!-- BEGIN readme-inventory -->
Dataset inventory is grouped by stable `custodian` publisher ID; unknown IDs fall back to the ID itself.

### National Anti-Drugs Agency (`aadk`)

- [data.gov.my Drug Addicts by State & Age Group](data/drug_addicts_age.md) (`drug_addicts_age`) · [sample](samples/drug_addicts_age.csv)
- [Drug Addicts by State & Drug Type](data/drug_addicts_drugtype.md) (`drug_addicts_drugtype`)
- [Drug Addicts by Highest Education Level](data/drug_addicts_education.md) (`drug_addicts_education`)
- [Drug Addicts by State & Occupation](data/drug_addicts_occupation.md) (`drug_addicts_occupation`)

### Accountant General's Department of Malaysia (`agc`)

- [Quarterly Federal Government Finance](data/federal_finance_qtr.md) (`federal_finance_qtr`)
- [data.gov.my Quarterly Federal Operating Expenditure](data/federal_finance_qtr_oe.md) (`federal_finance_qtr_oe`) · [sample](samples/federal_finance_qtr_oe.csv)
- [data.gov.my Quarterly Federal Government Revenue](data/federal_finance_qtr_revenue.md) (`federal_finance_qtr_revenue`) · [sample](samples/federal_finance_qtr_revenue.csv)
- [Annual Federal Government Finance](data/federal_finance_year.md) (`federal_finance_year`)
- [Annual Federal Government Development Expenditure by Function](data/federal_finance_year_de.md) (`federal_finance_year_de`)
- [Annual Federal Government Operating Expenditure by Object](data/federal_finance_year_oe.md) (`federal_finance_year_oe`)
- [Lookup Table: Federal Finance](data/lookup_federal_finance.md) (`lookup_federal_finance`)

### Agensi Pengangkutan Awam Darat (APAD) (`apad`)

- [GTFS Realtime — BAS.MY Alor Setar Vehicle Positions](data/gtfs_realtime_mybas_alor_setar.md) (`gtfs_realtime_mybas_alor_setar`)
- [GTFS Realtime — BAS.MY Ipoh Vehicle Positions](data/gtfs_realtime_mybas_ipoh.md) (`gtfs_realtime_mybas_ipoh`)
- [GTFS Realtime — BAS.MY Johor Vehicle Positions](data/gtfs_realtime_mybas_johor.md) (`gtfs_realtime_mybas_johor`)
- [GTFS Realtime — BAS.MY Kangar Vehicle Positions](data/gtfs_realtime_mybas_kangar.md) (`gtfs_realtime_mybas_kangar`)
- [GTFS Realtime — BAS.MY Kota Bharu Vehicle Positions](data/gtfs_realtime_mybas_kota_bharu.md) (`gtfs_realtime_mybas_kota_bharu`)
- [GTFS Realtime — BAS.MY Kuala Terengganu Vehicle Positions](data/gtfs_realtime_mybas_kuala_terengganu.md) (`gtfs_realtime_mybas_kuala_terengganu`)
- [GTFS Realtime — BAS.MY Kuching Vehicle Positions](data/gtfs_realtime_mybas_kuching.md) (`gtfs_realtime_mybas_kuching`)
- [GTFS Realtime — BAS.MY Melaka Vehicle Positions](data/gtfs_realtime_mybas_melaka.md) (`gtfs_realtime_mybas_melaka`)
- [GTFS Realtime — BAS.MY Seremban A Vehicle Positions](data/gtfs_realtime_mybas_seremban_a.md) (`gtfs_realtime_mybas_seremban_a`)
- [GTFS Realtime — BAS.MY Seremban B Vehicle Positions](data/gtfs_realtime_mybas_seremban_b.md) (`gtfs_realtime_mybas_seremban_b`)
- [GTFS Static — BAS.MY Alor Setar Bus Schedule](data/gtfs_static_mybas_alor_setar.md) (`gtfs_static_mybas_alor_setar`)
- [GTFS Static — BAS.MY Ipoh Bus Schedule](data/gtfs_static_mybas_ipoh.md) (`gtfs_static_mybas_ipoh`)
- [GTFS Static — BAS.MY Johor Bus Schedule](data/gtfs_static_mybas_johor.md) (`gtfs_static_mybas_johor`)
- [GTFS Static — BAS.MY Kangar Bus Schedule](data/gtfs_static_mybas_kangar.md) (`gtfs_static_mybas_kangar`)
- [GTFS Static — BAS.MY Kota Bharu Bus Schedule](data/gtfs_static_mybas_kota_bharu.md) (`gtfs_static_mybas_kota_bharu`)
- [GTFS Static — BAS.MY Kuala Terengganu Bus Schedule](data/gtfs_static_mybas_kuala_terengganu.md) (`gtfs_static_mybas_kuala_terengganu`)
- [GTFS Static — BAS.MY Kuching Bus Schedule](data/gtfs_static_mybas_kuching.md) (`gtfs_static_mybas_kuching`)
- [GTFS Static — BAS.MY Melaka Bus Schedule](data/gtfs_static_mybas_melaka.md) (`gtfs_static_mybas_melaka`)
- [GTFS Static — BAS.MY Seremban A Bus Schedule](data/gtfs_static_mybas_seremban_a.md) (`gtfs_static_mybas_seremban_a`)
- [GTFS Static — BAS.MY Seremban B Bus Schedule](data/gtfs_static_mybas_seremban_b.md) (`gtfs_static_mybas_seremban_b`)

### Bank Negara Malaysia (`bnm`)

- [Base Rates / BLR / Effective LR](data/bnm_base_rate.md) (`bnm_base_rate`)
- [Interbank Swap](data/bnm_interbank_swap.md) (`bnm_interbank_swap`)
- [Interest Rates: Banking Institutions](data/bnm_interest_rate.md) (`bnm_interest_rate`)
- [Interest Volume: Banking Institutions](data/bnm_interest_volume.md) (`bnm_interest_volume`)
- [Kijang Emas (Gold Reference Price)](data/bnm_kijang_emas.md) (`bnm_kijang_emas`)
- [Kuala Lumpur USD/MYR Reference Rate](data/bnm_kl_usd_myr.md) (`bnm_kl_usd_myr`)
- [Malaysia Overnight Rate (MYOR)](data/bnm_myor.md) (`bnm_myor`)
- [Overnight Policy Rate (OPR)](data/bnm_opr.md) (`bnm_opr`)
- [Monthly Currency in Circulation](data/currency_in_circulation.md) (`currency_in_circulation`)
- [Annual Currency in Circulation](data/currency_in_circulation_annual.md) (`currency_in_circulation_annual`)
- [data.gov.my Monthly Interest Rates](data/dgm_interest_rates.md) (`dgm_interest_rates`) · [sample](samples/dgm_interest_rates.csv)
- [data.gov.my Annual Interest Rates](data/dgm_interest_rates_annual.md) (`dgm_interest_rates_annual`) · [sample](samples/dgm_interest_rates_annual.csv)
- [data.gov.my Monthly Money Aggregates](data/dgm_money_aggregates.md) (`dgm_money_aggregates`) · [sample](samples/dgm_money_aggregates.csv)
- [data.gov.my Monthly Payment Channels](data/dgm_payments_channels.md) (`dgm_payments_channels`) · [sample](samples/dgm_payments_channels.csv)
- [data.gov.my Monthly Payment Instruments](data/dgm_payments_instruments.md) (`dgm_payments_instruments`) · [sample](samples/dgm_payments_instruments.csv)
- [data.gov.my Monthly Payment Systems](data/dgm_payments_systems.md) (`dgm_payments_systems`) · [sample](samples/dgm_payments_systems.csv)
- [data.gov.my Daily FPX Transactions](data/dgm_payments_transactions_fpx.md) (`dgm_payments_transactions_fpx`) · [sample](samples/dgm_payments_transactions_fpx.csv)
- [Monthly Exchange Rates](data/exchangerates.md) (`exchangerates`)
- [BNM Daily Exchange Rates (0900)](data/exchangerates_daily_0900.md) (`exchangerates_daily_0900`) · [sample](samples/exchangerates_daily_0900.json)
- [BNM Daily Exchange Rates (1130)](data/exchangerates_daily_1130.md) (`exchangerates_daily_1130`) · [sample](samples/exchangerates_daily_1130.json)
- [BNM Daily Exchange Rates (1200)](data/exchangerates_daily_1200.md) (`exchangerates_daily_1200`) · [sample](samples/exchangerates_daily_1200.json)
- [BNM Daily Exchange Rates (1700)](data/exchangerates_daily_1700.md) (`exchangerates_daily_1700`) · [sample](samples/exchangerates_daily_1700.json)
- [Monthly Interest Rates](data/interestrates.md) (`interestrates`)
- [Annual Interest Rates](data/interestrates_annual.md) (`interestrates_annual`)
- [Lookup Table: Money & Banking](data/lookup_money_banking.md) (`lookup_money_banking`)
- [Monthly Monetary Aggregates](data/monetary_aggregates.md) (`monetary_aggregates`)
- [Monthly Payment Channels](data/payment_channels.md) (`payment_channels`)
- [Monthly Payment Instruments](data/payment_instruments.md) (`payment_instruments`)
- [Monthly Payment Systems](data/payment_systems.md) (`payment_systems`)

### Department of Agriculture Malaysia (`doa`)

- [data.gov.my Crop Area and Production by State](data/crops_state.md) (`crops_state`) · [sample](samples/crops_state.csv)
- [Crop Area by District](data/dosm_crops_district_area.md) (`dosm_crops_district_area`)
- [Crop Production by District](data/dosm_crops_district_production.md) (`dosm_crops_district_production`)

### Department of Environment Malaysia (`doe`)

- [Air Pollutant Concentrations](data/air_pollution.md) (`air_pollution`)
- [DOE APIMS Air Quality (Hourly API)](data/doe_apims.md) (`doe_apims`) · [sample](samples/doe_apims.csv)
- [DOE MQIMS Marine Water Quality (Manual)](data/doe_mqims.md) (`doe_mqims`) · [sample](samples/doe_mqims.csv)
- [DOE RQIMS River Water Quality (Continuous)](data/doe_rqims.md) (`doe_rqims`) · [sample](samples/doe_rqims.csv)
- [River Basin Pollution Monitoring](data/water_pollution_basin.md) (`water_pollution_basin`)

### Department of Fisheries Malaysia (`dof`)

- [data.gov.my Monthly Landings of Marine Fish by State](data/fish_landings.md) (`fish_landings`) · [sample](samples/fish_landings.csv)

### Department of Statistics Malaysia (`dosm`)

- [Balance of Payments by Account](data/bop_balance.md) (`bop_balance`)
- [Monthly CPI by Group](data/cpi_3d.md) (`cpi_3d`)
- [Monthly CPI by Class](data/cpi_4d.md) (`cpi_4d`)
- [Monthly CPI by Subclass](data/cpi_5d.md) (`cpi_5d`)
- [Monthly Core Consumer Price Index](data/cpi_core.md) (`cpi_core`)
- [Monthly Core CPI Inflation](data/cpi_core_inflation.md) (`cpi_core_inflation`)
- [Monthly CPI by Division (2-digit)](data/cpi_headline.md) (`cpi_headline`)
- [Monthly CPI by State & Division (2-digit)](data/cpi_state.md) (`cpi_state`)
- [Monthly CPI Inflation by State & Division (2-digit)](data/cpi_state_inflation.md) (`cpi_state_inflation`)
- [DOSM's Advance Release Calendar](data/dosm_arc_dosm.md) (`dosm_arc_dosm`)
- [Broad Economic Categories (BEC)](data/dosm_bec.md) (`dosm_bec`)
- [OpenDOSM Annual Births by State](data/dosm_birth_state.md) (`dosm_birth_state`) · [sample](samples/dosm_birth_state.csv)
- [Annual CPI by Division (2-digit)](data/dosm_cpi_annual.md) (`dosm_cpi_annual`)
- [Annual CPI Inflation by Division (2-digit)](data/dosm_cpi_annual_inflation.md) (`dosm_cpi_annual_inflation`)
- [OpenDOSM Monthly Core CPI Inflation by Division](data/dosm_cpi_core_inflation.md) (`dosm_cpi_core_inflation`) · [sample](samples/dosm_cpi_core_inflation.csv)
- [Monthly CPI Inflation by Division (2-digit)](data/dosm_cpi_headline_inflation.md) (`dosm_cpi_headline_inflation`)
- [OpenDOSM Monthly CPI Inflation by Division](data/dosm_cpi_inflation.md) (`dosm_cpi_inflation`) · [sample](samples/dosm_cpi_inflation.csv)
- [Monthly CPI for Low-Income Households](data/dosm_cpi_lowincome.md) (`dosm_cpi_lowincome`)
- [OpenDOSM Monthly CPI by State & Division](data/dosm_cpi_state.md) (`dosm_cpi_state`) · [sample](samples/dosm_cpi_state.csv)
- [OpenDOSM Monthly CPI Inflation by State and Division](data/dosm_cpi_state_inflation.md) (`dosm_cpi_state_inflation`) · [sample](samples/dosm_cpi_state_inflation.csv)
- [Monthly CPI by Strata & Division (2-digit)](data/dosm_cpi_strata.md) (`dosm_cpi_strata`)
- [OpenDOSM Crime by District & Type (Annual)](data/dosm_crime_district.md) (`dosm_crime_district`) · [sample](samples/dosm_crime_district.csv)
- [OpenDOSM Annual Deaths by District and Sex](data/dosm_death_district_sex.md) (`dosm_death_district_sex`) · [sample](samples/dosm_death_district_sex.csv)
- [OpenDOSM Annual Maternal Deaths, Malaysia](data/dosm_death_maternal.md) (`dosm_death_maternal`) · [sample](samples/dosm_death_maternal.csv)
- [OpenDOSM Annual Maternal Deaths by State](data/dosm_death_maternal_state.md) (`dosm_death_maternal_state`) · [sample](samples/dosm_death_maternal_state.csv)
- [OpenDOSM Annual Deaths by State](data/dosm_death_state.md) (`dosm_death_state`) · [sample](samples/dosm_death_state.csv)
- [OpenDOSM Annual Employment by Sector and Sex](data/dosm_employment_sector.md) (`dosm_employment_sector`) · [sample](samples/dosm_employment_sector.csv)
- [OpenDOSM Annual Fertility](data/dosm_fertility.md) (`dosm_fertility`) · [sample](samples/dosm_fertility.csv)
- [TFR and ASFR by State](data/dosm_fertility_state.md) (`dosm_fertility_state`)
- [Annual Nominal GDP by Expenditure Type](data/dosm_gdp_annual_nominal_demand.md) (`dosm_gdp_annual_nominal_demand`)
- [Annual Nominal GDP by Expenditure Subtype](data/dosm_gdp_annual_nominal_demand_granular.md) (`dosm_gdp_annual_nominal_demand_granular`)
- [Annual Nominal GDP by Income Component](data/dosm_gdp_annual_nominal_income.md) (`dosm_gdp_annual_nominal_income`)
- [OpenDOSM Annual Nominal GDP by Supply Sector](data/dosm_gdp_annual_nominal_supply.md) (`dosm_gdp_annual_nominal_supply`) · [sample](samples/dosm_gdp_annual_nominal_supply.csv)
- [Annual Nominal GDP by Economic Subsector](data/dosm_gdp_annual_nominal_supply_granular.md) (`dosm_gdp_annual_nominal_supply_granular`)
- [Annual Real GDP by Expenditure Type](data/dosm_gdp_annual_real_demand.md) (`dosm_gdp_annual_real_demand`)
- [Annual Real GDP by Expenditure Subtype](data/dosm_gdp_annual_real_demand_granular.md) (`dosm_gdp_annual_real_demand_granular`)
- [OpenDOSM Annual Real GDP by Supply Sector](data/dosm_gdp_annual_real_supply.md) (`dosm_gdp_annual_real_supply`) · [sample](samples/dosm_gdp_annual_real_supply.csv)
- [Annual Real GDP by Economic Subsector](data/dosm_gdp_annual_real_supply_granular.md) (`dosm_gdp_annual_real_supply_granular`)
- [Annual Real GDP by District & Economic Sector](data/dosm_gdp_district_real_supply.md) (`dosm_gdp_district_real_supply`)
- [OpenDOSM Annual Nominal GDP and GNI](data/dosm_gdp_gni_annual_nominal.md) (`dosm_gdp_gni_annual_nominal`) · [sample](samples/dosm_gdp_gni_annual_nominal.csv)
- [Annual Real GDP & GNI: 1970 to Present](data/dosm_gdp_gni_annual_real.md) (`dosm_gdp_gni_annual_real`)
- [Lookup Table: GDP](data/dosm_gdp_lookup.md) (`dosm_gdp_lookup`)
- [OpenDOSM Quarterly Nominal GDP](data/dosm_gdp_qtr_nominal.md) (`dosm_gdp_qtr_nominal`) · [sample](samples/dosm_gdp_qtr_nominal.csv)
- [Quarterly Nominal GDP by Expenditure Type](data/dosm_gdp_qtr_nominal_demand.md) (`dosm_gdp_qtr_nominal_demand`)
- [Quarterly Nominal GDP by Expenditure Subtype](data/dosm_gdp_qtr_nominal_demand_granular.md) (`dosm_gdp_qtr_nominal_demand_granular`)
- [Quarterly Nominal GDP by Economic Sector](data/dosm_gdp_qtr_nominal_supply.md) (`dosm_gdp_qtr_nominal_supply`)
- [Quarterly Nominal GDP by Economic Subsector](data/dosm_gdp_qtr_nominal_supply_granular.md) (`dosm_gdp_qtr_nominal_supply_granular`)
- [OpenDOSM Quarterly Real GDP](data/dosm_gdp_qtr_real.md) (`dosm_gdp_qtr_real`) · [sample](samples/dosm_gdp_qtr_real.csv)
- [Quarterly Real GDP by Expenditure Type](data/dosm_gdp_qtr_real_demand.md) (`dosm_gdp_qtr_real_demand`)
- [Quarterly Real GDP by Expenditure Subtype](data/dosm_gdp_qtr_real_demand_granular.md) (`dosm_gdp_qtr_real_demand_granular`)
- [OpenDOSM Quarterly Real GDP (Seasonally Adjusted)](data/dosm_gdp_qtr_real_sa.md) (`dosm_gdp_qtr_real_sa`) · [sample](samples/dosm_gdp_qtr_real_sa.csv)
- [Quarterly Real GDP (Seasonally Adjusted) by Expenditure Type](data/dosm_gdp_qtr_real_sa_demand.md) (`dosm_gdp_qtr_real_sa_demand`)
- [Quarterly Real GDP (Seasonally Adjusted) by Economic Sector](data/dosm_gdp_qtr_real_sa_supply.md) (`dosm_gdp_qtr_real_sa_supply`)
- [Quarterly Real GDP by Economic Sector](data/dosm_gdp_qtr_real_supply.md) (`dosm_gdp_qtr_real_supply`)
- [Quarterly Real GDP by Economic Subsector](data/dosm_gdp_qtr_real_supply_granular.md) (`dosm_gdp_qtr_real_supply_granular`)
- [OpenDOSM Annual Real GDP by State & Sector](data/dosm_gdp_state_real_supply.md) (`dosm_gdp_state_real_supply`) · [sample](samples/dosm_gdp_state_real_supply.csv)
- [Access to Basic Amenities by State & District](data/dosm_hh_access_amenities.md) (`dosm_hh_access_amenities`)
- [OpenDOSM Household Expenditure by DUN](data/dosm_hh_expenditure_dun.md) (`dosm_hh_expenditure_dun`) · [sample](samples/dosm_hh_expenditure_dun.csv)
- [OpenDOSM Household Expenditure by Parliamentary Constituency](data/dosm_hh_expenditure_parlimen.md) (`dosm_hh_expenditure_parlimen`) · [sample](samples/dosm_hh_expenditure_parlimen.csv)
- [OpenDOSM Household Income, Malaysia](data/dosm_hh_income.md) (`dosm_hh_income`) · [sample](samples/dosm_hh_income.csv)
- [OpenDOSM Household Income by District](data/dosm_hh_income_district.md) (`dosm_hh_income_district`) · [sample](samples/dosm_hh_income_district.csv)
- [Household Income by DUN](data/dosm_hh_income_dun.md) (`dosm_hh_income_dun`)
- [Household Income by Parliament](data/dosm_hh_income_parlimen.md) (`dosm_hh_income_parlimen`)
- [OpenDOSM Household Income by State](data/dosm_hh_income_state.md) (`dosm_hh_income_state`) · [sample](samples/dosm_hh_income_state.csv)
- [OpenDOSM Income Inequality, Malaysia](data/dosm_hh_inequality.md) (`dosm_hh_inequality`) · [sample](samples/dosm_hh_inequality.csv)
- [OpenDOSM Income Inequality by District](data/dosm_hh_inequality_district.md) (`dosm_hh_inequality_district`) · [sample](samples/dosm_hh_inequality_district.csv)
- [Income Inequality by DUN](data/dosm_hh_inequality_dun.md) (`dosm_hh_inequality_dun`)
- [Income Inequality by Parliament](data/dosm_hh_inequality_parlimen.md) (`dosm_hh_inequality_parlimen`)
- [OpenDOSM Income Inequality by State](data/dosm_hh_inequality_state.md) (`dosm_hh_inequality_state`) · [sample](samples/dosm_hh_inequality_state.csv)
- [OpenDOSM Poverty, Malaysia](data/dosm_hh_poverty.md) (`dosm_hh_poverty`) · [sample](samples/dosm_hh_poverty.csv)
- [OpenDOSM Poverty by District](data/dosm_hh_poverty_district.md) (`dosm_hh_poverty_district`) · [sample](samples/dosm_hh_poverty_district.csv)
- [Poverty by DUN](data/dosm_hh_poverty_dun.md) (`dosm_hh_poverty_dun`)
- [Poverty by Parliament](data/dosm_hh_poverty_parlimen.md) (`dosm_hh_poverty_parlimen`)
- [OpenDOSM Poverty by State](data/dosm_hh_poverty_state.md) (`dosm_hh_poverty_state`) · [sample](samples/dosm_hh_poverty_state.csv)
- [Number of Households and Living Quarters](data/dosm_hh_profile.md) (`dosm_hh_profile`)
- [Number of Households and Living Quarters by State](data/dosm_hh_profile_state.md) (`dosm_hh_profile_state`)
- [Household Income and Expenditure: Administrative Districts](data/dosm_hies_district.md) (`dosm_hies_district`)
- [Household Income by Percentile](data/dosm_hies_malaysia_percentile.md) (`dosm_hies_malaysia_percentile`)
- [Household Income and Expenditure: States](data/dosm_hies_state.md) (`dosm_hies_state`)
- [Household Income by State & Percentile](data/dosm_hies_state_percentile.md) (`dosm_hies_state_percentile`)
- [Headline Wholesale & Retail Trade](data/dosm_iowrt.md) (`dosm_iowrt`)
- [Wholesale & Retail Trade by Division (2 digit)](data/dosm_iowrt_2d.md) (`dosm_iowrt_2d`)
- [Wholesale & Retail Trade by Group (3 digit)](data/dosm_iowrt_3d.md) (`dosm_iowrt_3d`)
- [Industrial Production Index (IPI)](data/dosm_ipi.md) (`dosm_ipi`)
- [IPI by Section (1 digit)](data/dosm_ipi_1d.md) (`dosm_ipi_1d`)
- [OpenDOSM IPI for Domestic-Oriented Divisions](data/dosm_ipi_domestic.md) (`dosm_ipi_domestic`) · [sample](samples/dosm_ipi_domestic.csv)
- [OpenDOSM IPI for Export-Oriented Divisions](data/dosm_ipi_export.md) (`dosm_ipi_export`) · [sample](samples/dosm_ipi_export.csv)
- [Annual Principal Labour Force Statistics by District](data/dosm_lfs_district.md) (`dosm_lfs_district`)
- [Annual Principal Labour Force Statistics by DUN](data/dosm_lfs_dun.md) (`dosm_lfs_dun`)
- [OpenDOSM Monthly Labour Force Statistics](data/dosm_lfs_month.md) (`dosm_lfs_month`) · [sample](samples/dosm_lfs_month.csv)
- [Monthly Unemployment by Duration](data/dosm_lfs_month_duration.md) (`dosm_lfs_month_duration`)
- [Monthly Principal Labour Force Statistics, Seasonally Adjusted](data/dosm_lfs_month_sa.md) (`dosm_lfs_month_sa`)
- [Monthly Employment by Status in Employment](data/dosm_lfs_month_status.md) (`dosm_lfs_month_status`)
- [Monthly Youth Unemployment](data/dosm_lfs_month_youth.md) (`dosm_lfs_month_youth`)
- [Annual Principal Labour Force Statistics by Parliament](data/dosm_lfs_parlimen.md) (`dosm_lfs_parlimen`)
- [OpenDOSM Quarterly Labour Force Statistics](data/dosm_lfs_qtr.md) (`dosm_lfs_qtr`) · [sample](samples/dosm_lfs_qtr.csv)
- [Quarterly Skills-Related Underemployment by Age](data/dosm_lfs_qtr_sru_age.md) (`dosm_lfs_qtr_sru_age`)
- [Quarterly Skills-Related Underemployment by Sex](data/dosm_lfs_qtr_sru_sex.md) (`dosm_lfs_qtr_sru_sex`)
- [OpenDOSM Quarterly Labour Force Statistics by State](data/dosm_lfs_qtr_state.md) (`dosm_lfs_qtr_state`) · [sample](samples/dosm_lfs_qtr_state.csv)
- [Quarterly Time-Related Underemployment by Age](data/dosm_lfs_qtr_tru_age.md) (`dosm_lfs_qtr_tru_age`)
- [Quarterly Time-Related Underemployment by Sex](data/dosm_lfs_qtr_tru_sex.md) (`dosm_lfs_qtr_tru_sex`)
- [Annual Principal Labour Force Statistics by State & Sex](data/dosm_lfs_state_sex.md) (`dosm_lfs_state_sex`)
- [OpenDOSM Annual Labour Force Statistics](data/dosm_lfs_year.md) (`dosm_lfs_year`) · [sample](samples/dosm_lfs_year.csv)
- [Annual Principal Labour Force Statistics by Sex](data/dosm_lfs_year_sex.md) (`dosm_lfs_year_sex`)
- [Annual Marriages](data/dosm_marriages.md) (`dosm_marriages`)
- [Annual Marriage by Age Group](data/dosm_marriages_age.md) (`dosm_marriages_age`)
- [OpenDOSM Annual Marriages by State and Sex](data/dosm_marriages_state.md) (`dosm_marriages_state`) · [sample](samples/dosm_marriages_state.csv)
- [OpenDOSM Annual Marriages by State, Age, and Sex](data/dosm_marriages_state_age.md) (`dosm_marriages_state_age`) · [sample](samples/dosm_marriages_state_age.csv)
- [MCOICOP](data/dosm_mcoicop.md) (`dosm_mcoicop`)
- [MSIC](data/dosm_msic.md) (`dosm_msic`)
- [OpenDOSM Annual Population, Malaysia](data/dosm_population_malaysia.md) (`dosm_population_malaysia`) · [sample](samples/dosm_population_malaysia.csv)
- [OpenDOSM Annual Population by Parliamentary Constituency](data/dosm_population_parlimen.md) (`dosm_population_parlimen`) · [sample](samples/dosm_population_parlimen.csv)
- [OpenDOSM Annual Population by State](data/dosm_population_state.md) (`dosm_population_state`) · [sample](samples/dosm_population_state.csv)
- [OpenDOSM Monthly Producer Price Index](data/dosm_ppi.md) (`dosm_ppi`) · [sample](samples/dosm_ppi.csv)
- [Monthly PPI by Section (1 digit)](data/dosm_ppi_1d.md) (`dosm_ppi_1d`)
- [Monthly PPI by SITC Section (1 digit)](data/dosm_ppi_sitc.md) (`dosm_ppi_sitc`)
- [Annual Productivity by Economic Sector](data/dosm_productivity_annual.md) (`dosm_productivity_annual`)
- [Annual Productivity for Priority Subsectors](data/dosm_productivity_annual_priority.md) (`dosm_productivity_annual_priority`)
- [Lookup Table: Labour Productivity](data/dosm_productivity_lookup.md) (`dosm_productivity_lookup`)
- [Quarterly Productivity by Economic Sector](data/dosm_productivity_qtr.md) (`dosm_productivity_qtr`)
- [SITC](data/dosm_sitc.md) (`dosm_sitc`)
- [SITC: Stage of Processing](data/dosm_sitc_sop.md) (`dosm_sitc_sop`)
- [Headline Services Producer Price Index (SPPI)](data/dosm_sppi.md) (`dosm_sppi`)
- [SPPI by Section (1 digit)](data/dosm_sppi_1d.md) (`dosm_sppi_1d`)
- [SPPI by Division (2 digits)](data/dosm_sppi_2d.md) (`dosm_sppi_2d`)
- [OpenDOSM Monthly Trade by End Use (BEC)](data/dosm_trade_enduse_bec.md) (`dosm_trade_enduse_bec`) · [sample](samples/dosm_trade_enduse_bec.csv)
- [OpenDOSM Monthly Trade Headline](data/dosm_trade_headline.md) (`dosm_trade_headline`) · [sample](samples/dosm_trade_headline.csv)
- [OpenDOSM Monthly Trade by SITC Section](data/dosm_trade_sitc_1d.md) (`dosm_trade_sitc_1d`) · [sample](samples/dosm_trade_sitc_1d.csv)
- [Malaysian Economic Indicators](data/economic_indicators.md) (`economic_indicators`)
- [Employment by MSIC Sector and Sex](data/employment_sector.md) (`employment_sector`)
- [Foreign Direct Investment Flows](data/fdi_flows.md) (`fdi_flows`)
- [TFR and ASFR](data/fertility.md) (`fertility`)
- [Annual Nominal GDP by Economic Sector](data/gdp_annual_nominal_supply.md) (`gdp_annual_nominal_supply`)
- [Annual Real GDP by Economic Sector](data/gdp_annual_real_supply.md) (`gdp_annual_real_supply`)
- [Annual Nominal GDP & GNI: 1947 to Present](data/gdp_gni_annual_nominal.md) (`gdp_gni_annual_nominal`)
- [OpenDOSM Quarterly Nominal GDP](data/gdp_qtr_nominal.md) (`gdp_qtr_nominal`)
- [OpenDOSM Quarterly Real GDP](data/gdp_qtr_real.md) (`gdp_qtr_real`)
- [Quarterly Real GDP (Seasonally Adjusted)](data/gdp_qtr_real_sa.md) (`gdp_qtr_real_sa`)
- [Annual Real GDP by State & Economic Sector](data/gdp_state_real_supply.md) (`gdp_state_real_supply`)
- [Household Expenditure by DUN](data/hh_expenditure_dun.md) (`hh_expenditure_dun`)
- [Household Expenditure by Parliament](data/hh_expenditure_parlimen.md) (`hh_expenditure_parlimen`)
- [Household Income](data/hh_income.md) (`hh_income`)
- [Household Income by Administrative District](data/hh_income_district.md) (`hh_income_district`)
- [Household Income by State](data/hh_income_state.md) (`hh_income_state`)
- [Income Inequality](data/hh_inequality.md) (`hh_inequality`)
- [Income Inequality by District](data/hh_inequality_district.md) (`hh_inequality_district`)
- [Income Inequality by State](data/hh_inequality_state.md) (`hh_inequality_state`)
- [Poverty](data/hh_poverty.md) (`hh_poverty`)
- [Poverty by Administrative District](data/hh_poverty_district.md) (`hh_poverty_district`)
- [Poverty by State](data/hh_poverty_state.md) (`hh_poverty_state`)
- [Monthly Industrial Production Index by Division](data/ipi_2d.md) (`ipi_2d`)
- [Monthly Industrial Production Index by Group](data/ipi_3d.md) (`ipi_3d`)
- [Monthly Industrial Production Index by Item](data/ipi_5d.md) (`ipi_5d`)
- [Monthly IPI for Domestic-Oriented Divisions](data/ipi_domestic.md) (`ipi_domestic`)
- [Monthly IPI for Export-Oriented Divisions](data/ipi_export.md) (`ipi_export`)
- [OpenDOSM Monthly Labour Force Statistics](data/lfs_month.md) (`lfs_month`)
- [Quarterly Principal Labour Force Statistics](data/lfs_qtr.md) (`lfs_qtr`)
- [Quarterly Principal Labour Force Statistics by State](data/lfs_qtr_state.md) (`lfs_qtr_state`)
- [Annual Principal Labour Force Statistics](data/lfs_year.md) (`lfs_year`)
- [Annual Marriages by State](data/marriages_state.md) (`marriages_state`)
- [Annual Marriage by State & Age Group](data/marriages_state_age.md) (`marriages_state_age`)
- [OpenDOSM Annual Population by Administrative District](data/population_district.md) (`population_district`)
- [Annual Population by State Constituency](data/population_dun.md) (`population_dun`)
- [OpenDOSM Annual Population, Malaysia](data/population_malaysia.md) (`population_malaysia`)
- [Annual Population by Parliamentary Constituency](data/population_parlimen.md) (`population_parlimen`)
- [OpenDOSM Annual Population by State](data/population_state.md) (`population_state`)
- [Monthly Producer Price Index (PPI)](data/ppi.md) (`ppi`)
- [Monthly Producer Price Index by Division](data/ppi_2d.md) (`ppi_2d`)
- [Monthly Producer Price Index by Group](data/ppi_3d.md) (`ppi_3d`)
- [Monthly PPI by Stage of Processing](data/ppi_sop.md) (`ppi_sop`)
- [SDG 04-6-1: Proficiency in Functional Literacy and Numeracy](data/sdg_04-6-1.md) (`sdg_04-6-1`)
- [SDG 10-C-1: Remittance Costs as a % of the Amount Remitted](data/sdg_10-c-1.md) (`sdg_10-c-1`)
- [Quarterly Services Producer Price Index by Group](data/sppi_3d.md) (`sppi_3d`)
- [OpenDOSM Monthly Trade Headline](data/trade_headline.md) (`trade_headline`)
- [Monthly Trade by SITC Section (1 digit)](data/trade_sitc_1d.md) (`trade_sitc_1d`)

### Energy Commission (`energy_commission`)

- [Households with Access to Electricity](data/electricity_access.md) (`electricity_access`)
- [data.gov.my Electricity Supply](data/electricity_supply.md) (`electricity_supply`) · [sample](samples/electricity_supply.csv)
- [Co-Generators — Malaysia](data/st_cogenerators.md) (`st_cogenerators`)
- [Number of Electricity Consumers — Malaysia](data/st_consumers.md) (`st_consumers`)
- [Current Co-Generation Licensees — Malaysia](data/st_current_cogen_licensees.md) (`st_current_cogen_licensees`)
- [Current Independent Power Producer Licensees — Malaysia](data/st_current_ipp_licensees.md) (`st_current_ipp_licensees`)
- [Current Large-Scale Solar Licensees — Malaysia](data/st_current_lss_licensees.md) (`st_current_lss_licensees`)
- [Current Renewable Energy Licensees — Malaysia](data/st_current_re_licensees.md) (`st_current_re_licensees`)
- [Electrical Competency Certificates Issued — Malaysia](data/st_elesca.md) (`st_elesca`)
- [National Energy Balance (Malaysia, annual PDF)](data/st_energy_balance_pdf.md) (`st_energy_balance_pdf`)
- [Generation Mix (GWh) — Malaysia](data/st_generation_mix_gwh.md) (`st_generation_mix_gwh`)
- [Installed Generation Capacity (MW) — Malaysia](data/st_installed_capacity_mw.md) (`st_installed_capacity_mw`)
- [Independent Power Producers — Malaysia](data/st_ipps.md) (`st_ipps`)
- [Maximum Demand (MW) — Malaysia](data/st_max_demand_mw.md) (`st_max_demand_mw`)
- [Renewable Energy Projects — Malaysia](data/st_re_projects.md) (`st_re_projects`)
- [Electricity Sales by Unit (GWh) — Malaysia](data/st_sales_unit_gwh.md) (`st_sales_unit_gwh`)
- [Electricity Sales by Value (RM million) — Malaysia](data/st_sales_value_rm_million.md) (`st_sales_value_rm_million`)

### Employees Provident Fund (`epf`)

- [data.gov.my Annual EPF Dividend Rates](data/epf_dividend.md) (`epf_dividend`) · [sample](samples/epf_dividend.csv)

### Forestry Department (`forestry_department`)

- [Area of Permanent Forest Reserves](data/dosm_forest_reserve.md) (`dosm_forest_reserve`)
- [Area of Permanent Forest Reserves by State](data/dosm_forest_reserve_state.md) (`dosm_forest_reserve_state`)
- [Production of Major Timber Products by State](data/dosm_timber_production.md) (`dosm_timber_production`)

### Immigration Department of Malaysia (`immigration`)

- [Monthly Arrivals by Nationality & Sex](data/arrivals.md) (`arrivals`)
- [Monthly Arrivals by State of Entry, Nationality & Sex](data/arrivals_soe.md) (`arrivals_soe`)
- [Monthly Passport Issuances by State and Branch](data/passports.md) (`passports`)

### Legal Aid Department (`jbg`)

- [Legal Advisory Services by Branch](data/legal_advisory_branch.md) (`legal_advisory_branch`)
- [Legal Advisory Services by Branch & Case Type](data/legal_advisory_case_type.md) (`legal_advisory_case_type`)
- [Legal Advisory Services by Branch & Category](data/legal_advisory_category.md) (`legal_advisory_category`)
- [Legal Advisory Services by Branch & Subcategory](data/legal_advisory_subcategory.md) (`legal_advisory_subcategory`)

### National Digital Department (`jdn`)

- [Currency Codes (ISO 4217)](data/currency_codes.md) (`currency_codes`)
- [List of Datasets on data.gov.my](data/datasets.md) (`datasets`)
- [Transactional Data: Official Government Mobile Applications](data/government_apps.md) (`government_apps`)
- [Number of Active Government Mobile Applications](data/government_apps_active.md) (`government_apps_active`)
- [Downloads of Government Mobile Applications](data/government_apps_downloads.md) (`government_apps_downloads`)
- [Transactional Data: User Reviews of Government Mobile Applications](data/government_apps_reviews.md) (`government_apps_reviews`)
- [Number of Datasets on data.gov.my](data/metrics_content.md) (`metrics_content`)
- [Cumulative Views and Downloads by Dataset](data/metrics_dataset_cumul.md) (`metrics_dataset_cumul`)
- [Daily Usage Metrics for data.gov.my](data/usage_metrics.md) (`usage_metrics`)
- [Daily OpenAPI Hits by Endpoint](data/usage_metrics_openapi.md) (`usage_metrics_openapi`)
- [Cumulative OpenAPI Hits by Endpoint](data/usage_metrics_openapi_cumul.md) (`usage_metrics_openapi_cumul`)

### Department of Mineral and Geoscience (`jmg`)

- [Extraction of Minerals by State and Commodity](data/dosm_mineral_extraction.md) (`dosm_mineral_extraction`)

### Road Transport Department Malaysia (`jpj`)

- [data.gov.my Monthly Vehicle Registrations by Type and Fuel](data/dgm_vehicle_registrations_type_fuel.md) (`dgm_vehicle_registrations_type_fuel`) · [sample](samples/dgm_vehicle_registrations_type_fuel.csv)
- [Vehicle Registration Transactions](data/registration_transactions_all.md) (`registration_transactions_all`)
- [Car Registration Transactions](data/registration_transactions_car.md) (`registration_transactions_car`)
- [Motorcycle Registration Transactions](data/registration_transactions_motorcycle.md) (`registration_transactions_motorcycle`)
- [Monthly Vehicle Registrations by Vehicle and Fuel Type](data/registrations_type_fuel.md) (`registrations_type_fuel`)

### National Registration Department (`jpn`)

- [Daily Live Births](data/births.md) (`births`)
- [Annual Deaths](data/deaths.md) (`deaths`)
- [Annual Live Births](data/dosm_births_annual.md) (`dosm_births_annual`)
- [Annual Live Births by Sex & Ethnicity](data/dosm_births_annual_sex_ethnic.md) (`dosm_births_annual_sex_ethnic`)
- [Annual Live Births by State, Sex, & Ethnicity](data/dosm_births_annual_sex_ethnic_state.md) (`dosm_births_annual_sex_ethnic_state`)
- [Annual Live Births by State](data/dosm_births_annual_state.md) (`dosm_births_annual_state`)
- [Annual Live Births by District & Sex](data/dosm_births_district_sex.md) (`dosm_births_district_sex`)
- [Annual Deaths by District & Sex](data/dosm_deaths_district_sex.md) (`dosm_deaths_district_sex`)
- [Annual Early Childhood Deaths](data/dosm_deaths_early_childhood.md) (`dosm_deaths_early_childhood`)
- [Annual Early Childhood Deaths by Sex](data/dosm_deaths_early_childhood_sex.md) (`dosm_deaths_early_childhood_sex`)
- [Annual Early Childhood Deaths by State](data/dosm_deaths_early_childhood_state.md) (`dosm_deaths_early_childhood_state`)
- [Annual Early Childhood Deaths by State & Sex](data/dosm_deaths_early_childhood_state_sex.md) (`dosm_deaths_early_childhood_state_sex`)
- [Annual Maternal Deaths](data/dosm_deaths_maternal.md) (`dosm_deaths_maternal`)
- [Annual Maternal Deaths by State](data/dosm_deaths_maternal_state.md) (`dosm_deaths_maternal_state`)
- [Annual Deaths by Sex & Ethnicity](data/dosm_deaths_sex_ethnic.md) (`dosm_deaths_sex_ethnic`)
- [Annual Deaths by State, Sex, & Ethnicity](data/dosm_deaths_sex_ethnic_state.md) (`dosm_deaths_sex_ethnic_state`)
- [Annual Deaths by State](data/dosm_deaths_state.md) (`dosm_deaths_state`)

### Ministry of Health Malaysia (`kkm`)

- [Daily COVID-19 Cases by State](data/covid_cases.md) (`covid_cases`)
- [Daily COVID-19 Cases by Age Group & State](data/covid_cases_age.md) (`covid_cases_age`)
- [Daily COVID-19 Cases by Vaccination Status & State](data/covid_cases_vaxstatus.md) (`covid_cases_vaxstatus`)
- [COVID-19 Deaths Line List](data/covid_deaths_linelist.md) (`covid_deaths_linelist`)
- [Annual Stillbirths](data/dosm_stillbirths.md) (`dosm_stillbirths`)
- [Annual Stillbirths by State](data/dosm_stillbirths_state.md) (`dosm_stillbirths_state`)
- [data.gov.my Healthcare Staff by State and Staff Type](data/healthcare_staff.md) (`healthcare_staff`) · [sample](samples/healthcare_staff.csv)
- [Hospital Beds by State and Hospital Type](data/hospital_beds.md) (`hospital_beds`)
- [data.gov.my Infant Immunisation Coverage](data/infant_immunisation.md) (`infant_immunisation`) · [sample](samples/infant_immunisation.csv)
- [KKM iDengue Weekly Dengue Cases](data/kkm_idengue.md) (`kkm_idengue`) · [sample](samples/kkm_idengue.csv)
- [KKMNOW Hospital Bed Utilisation by Facility/State](data/kkmnow_bedutil.md) (`kkmnow_bedutil`)
- [KKMNOW Daily Blood Donations and Stock](data/kkmnow_blood.md) (`kkmnow_blood`)
- [KKMNOW Weekly COVID-19 Epidemiological Surveillance](data/kkmnow_covidepid.md) (`kkmnow_covidepid`)
- [KKMNOW COVID-19 Daily Cases](data/kkmnow_covidnow.md) (`kkmnow_covidnow`)
- [KKMNOW COVID-19 Vaccine Registrations](data/kkmnow_covidvax.md) (`kkmnow_covidvax`)
- [KKMNOW Healthcare Resources/Facilities Directory](data/kkmnow_facilities.md) (`kkmnow_facilities`)
- [KKMNOW Organ Donation Pledges and Deaths](data/kkmnow_organ.md) (`kkmnow_organ`)
- [KKMNOW PeKa B40 Daily Health Screenings by State](data/kkmnow_pekab40.md) (`kkmnow_pekab40`)
- [data.gov.my MNHA: Total (TEH) and Current (CHE) Expenditure on Health](data/mnha.md) (`mnha`) · [sample](samples/mnha.csv)
- [MNHA: MOH Expenditure on Health](data/mnha_moh.md) (`mnha_moh`)
- [Nutritional Status of Children Under 5 by Sex](data/nutrition_children_sex.md) (`nutrition_children_sex`)
- [Nutritional Status of Children Under 5 by Strata](data/nutrition_children_strata.md) (`nutrition_children_strata`)
- [Access to Sanitary Latrines by State](data/sanitation_access.md) (`sanitation_access`)
- [SDG 03-3-1: HIV Incidence per 1,000 Uninfected Population](data/sdg_03-3-1.md) (`sdg_03-3-1`)
- [data.gov.my Sexually Transmitted Diseases (STDs) by State](data/std_state.md) (`std_state`) · [sample](samples/std_state.csv)
- [Daily COVID-19 Vaccine Registrations by State](data/vaxreg_covid.md) (`vaxreg_covid`)
- [COVID-19 Vaccination Registrations by Demographic Group](data/vaxreg_covid_demog.md) (`vaxreg_covid_demog`)

### Ministry of Domestic Trade and Cost of Living (`kpdn`)

- [PriceCatcher: Item Lookup](data/dosm_lookup_item.md) (`dosm_lookup_item`)
- [PriceCatcher: Premise Lookup](data/dosm_lookup_premise.md) (`dosm_lookup_premise`)
- [PriceCatcher (Grocery Prices)](data/pricecatcher.md) (`pricecatcher`) · [sample](samples/pricecatcher.csv)

### Keretapi Tanah Melayu Berhad (`ktmb`)

- [data.gov.my Monthly KTMB Ridership](data/dgm_ktmb_ridership_monthly.md) (`dgm_ktmb_ridership_monthly`) · [sample](samples/dgm_ktmb_ridership_monthly.csv)
- [GTFS Realtime — KTMB Vehicle Positions](data/gtfs_realtime_ktmb.md) (`gtfs_realtime_ktmb`)
- [GTFS Static — KTMB Rail Schedule](data/gtfs_static_ktmb.md) (`gtfs_static_ktmb`)
- [Daily KTMB Ridership](data/ridership_ktmb_daily.md) (`ridership_ktmb_daily`)
- [Monthly KTMB Ridership](data/ridership_ktmb_monthly.md) (`ridership_ktmb_monthly`)
- [KTMB ETS Origin-Destination Ridership](data/ridership_od_ets.md) (`ridership_od_ets`)
- [KTMB Intercity Origin-Destination Ridership](data/ridership_od_intercity.md) (`ridership_od_intercity`)
- [KTMB Komuter Origin-Destination Ridership](data/ridership_od_komuter.md) (`ridership_od_komuter`)
- [KTMB Komuter Utara Origin-Destination Ridership](data/ridership_od_komuter_utara.md) (`ridership_od_komuter_utara`)
- [KTMB Shuttle Tebrau Origin-Destination Ridership](data/ridership_od_shuttle_tebrau.md) (`ridership_od_shuttle_tebrau`)

### Majlis Bandaraya Pulau Pinang (`mbpp`)

- [MBPP Weather Station Observations](data/mbpp_weather_stations.md) (`mbpp_weather_stations`)

### Malaysian Communications and Multimedia Commission (`mcmc`)

- [data.gov.my Cellular Subscribers by Plan Type](data/cellular_subscribers.md) (`cellular_subscribers`) · [sample](samples/cellular_subscribers.csv)
- [Postcode Dataset](data/poskod.md) (`poskod`)

### Malaysian Meteorological Department (`met`)

- [Astronomy Almanac](data/almanak_astronomi.md) (`almanak_astronomi`)
- [MET Malaysia Weather Forecast](data/met_weather.md) (`met_weather`) · [sample](samples/met_weather.csv)

### Ministry of Home Affairs Malaysia (`mha`)

- [SDG 16-2-2: Victims of Human Trafficking](data/sdg_16-2-2.md) (`sdg_16-2-2`)

### Ministry of Housing and Local Government (`mhlg`)

- [data.gov.my Female Representation in Local Authorities](data/local_authority_sex.md) (`local_authority_sex`) · [sample](samples/local_authority_sex.csv)

### Ministry of Education Malaysia (`moe`)

- [School Completion Rates by State](data/completion_school_state.md) (`completion_school_state`)
- [Enrolment in Government Schools by District](data/enrolment_school_district.md) (`enrolment_school_district`)
- [data.gov.my Public Education Institutions by District](data/schools_district.md) (`schools_district`) · [sample](samples/schools_district.csv)
- [Teachers in Government Schools by District](data/teachers_district.md) (`teachers_district`)

### Ministry of Finance Malaysia (`mof`)

- [ePerolehan Tender Notices (DIIKLANKAN)](data/eperolehan-diklankan.md) (`eperolehan-diklankan`) · [sample](samples/eperolehan-diklankan.json)
- [Annual Budget Allocation for the Ministry of Education](data/federal_budget_moe.md) (`federal_budget_moe`)
- [Annual Budget Allocation for the Ministry of Health](data/federal_budget_moh.md) (`federal_budget_moh`)
- [Quarterly Federal Development Expenditure](data/federal_finance_qtr_de.md) (`federal_finance_qtr_de`)
- [Annual Federal Government Revenue](data/federal_finance_year_revenue.md) (`federal_finance_year_revenue`)
- [Malaysian Fuel Prices](data/fuelprice.md) (`fuelprice`) · [sample](samples/fuelprice.csv)

### Ministry of Higher Education Malaysia (`mohe`)

- [Lecturers in Public Universities by Citizenship & Sex](data/lecturers_uni.md) (`lecturers_uni`)

### Ministry of Transport Malaysia (`mot`)

- [data.gov.my Daily Public Transport Ridership](data/ridership_headline.md) (`ridership_headline`)

### MYNIC (`mynic`)

- [Number of Registered .MY Domains](data/domains.md) (`domains`)
- [Number of Registered .MY Domains with DNSSEC](data/domains_dnssec.md) (`domains_dnssec`)
- [Number of Registered Internationalised .MY Domains](data/domains_idn.md) (`domains_idn`)
- [Number of Registered .MY Domains with IPv6 DNS](data/domains_ipv6.md) (`domains_ipv6`)

### National Audit Department Malaysia (`national_audit`)

- [State Government Expenditure](data/state_finance_expenditure.md) (`state_finance_expenditure`)
- [State Government Revenue](data/state_finance_revenue.md) (`state_finance_revenue`)

### National Blood Centre (`national_blood_centre`)

- [Daily Blood Donations by Blood Group](data/blood_donations.md) (`blood_donations`)
- [data.gov.my Daily Blood Donations by Blood Group & State](data/blood_donations_state.md) (`blood_donations_state`) · [sample](samples/blood_donations_state.csv)

### National Pharmaceutical Regulatory Agency (`npra`)

- [Cosmetic Product Notifications](data/cosmetic_notifications.md) (`cosmetic_notifications`)
- [Cancelled Cosmetic Product Notifications](data/cosmetic_notifications_cancelled.md) (`cosmetic_notifications_cancelled`)
- [Approved Manufacturers of Cosmetic Products](data/cosmetics_manufacturers.md) (`cosmetics_manufacturers`)
- [Licensed Pharmaceutical Importers](data/pharmaceutical_importers.md) (`pharmaceutical_importers`)
- [Licensed Pharmaceutical Manufacturers](data/pharmaceutical_manufacturers.md) (`pharmaceutical_manufacturers`)
- [Registered Pharmaceutical Products](data/pharmaceutical_products.md) (`pharmaceutical_products`)
- [Cancelled Pharmaceutical Product Registrations](data/pharmaceutical_products_cancelled.md) (`pharmaceutical_products_cancelled`)
- [Licensed Pharmaceutical Wholesalers](data/pharmaceutical_wholesalers.md) (`pharmaceutical_wholesalers`)

### Ministry of Natural Resources and Environmental Sustainability (`nres`)

- [Greenhouse Gas Emissions](data/ghg_emissions.md) (`ghg_emissions`)

### National Transplant Resource Centre (`ntrc`)

- [Daily Organ Donation Pledges](data/organ_pledges.md) (`organ_pledges`)
- [Daily Organ Donation Pledges by State](data/organ_pledges_state.md) (`organ_pledges_state`)

### Parliament of Malaysia (`parliament`)

- [Malaysian Parliament Hansard MPs](data/hansard_mps.md) (`hansard_mps`)
- [Malaysian Parliamentary Terms](data/hansard_parliamentary_terms.md) (`hansard_parliamentary_terms`)
- [Malaysian Parliament Hansard Sitting Catalogue](data/hansard_sittings.md) (`hansard_sittings`)
- [data.gov.my Female Representation in Parliament](data/parliament_sex.md) (`parliament_sex`) · [sample](samples/parliament_sex.csv)

### Payments Network Malaysia (`paynet`)

- [Daily DirectDebit Transactions](data/trnsc_daily_directdebit.md) (`trnsc_daily_directdebit`)
- [Daily FPX Transactions](data/trnsc_daily_fpx.md) (`trnsc_daily_fpx`)
- [Daily JomPAY Transactions](data/trnsc_daily_jompay.md) (`trnsc_daily_jompay`)
- [Daily Shared ATM Network (SAN) Transactions](data/trnsc_daily_san.md) (`trnsc_daily_san`)

### Royal Malaysia Police (`pdrm`)

- [Drug Arrests by Sex & Age](data/drug_arrests_age.md) (`drug_arrests_age`)
- [Drug Arrests by Sex & Ethnicity](data/drug_arrests_ethnicity.md) (`drug_arrests_ethnicity`)
- [SDG 16-1-1: Victims of Intentional Homicide](data/sdg_16-1-1.md) (`sdg_16-1-1`)

### Prasarana Malaysia Berhad (`prasarana`)

- [GTFS Realtime — Rapid KL Bus Vehicle Positions](data/gtfs_realtime_prasarana_bus_kl.md) (`gtfs_realtime_prasarana_bus_kl`)
- [GTFS Realtime — MRT Feeder Bus Vehicle Positions](data/gtfs_realtime_prasarana_bus_mrtfeeder.md) (`gtfs_realtime_prasarana_bus_mrtfeeder`)
- [GTFS Realtime — Rapid Penang Bus Vehicle Positions](data/gtfs_realtime_prasarana_bus_penang.md) (`gtfs_realtime_prasarana_bus_penang`)
- [GTFS Static — Rapid KL Bus Schedule](data/gtfs_static_prasarana_bus_kl.md) (`gtfs_static_prasarana_bus_kl`)
- [GTFS Static — Rapid Kuantan Bus Schedule](data/gtfs_static_prasarana_bus_kuantan.md) (`gtfs_static_prasarana_bus_kuantan`)
- [GTFS Static — MRT Feeder Bus Schedule](data/gtfs_static_prasarana_bus_mrtfeeder.md) (`gtfs_static_prasarana_bus_mrtfeeder`)
- [GTFS Static — Rapid Penang Bus Schedule](data/gtfs_static_prasarana_bus_penang.md) (`gtfs_static_prasarana_bus_penang`)
- [GTFS Static — Rapid KL Rail Schedule](data/gtfs_static_prasarana_rail_kl.md) (`gtfs_static_prasarana_rail_kl`)
- [Daily Origin-Destination Ridership: BRT Sunway Line](data/ridership_od_brt_daily.md) (`ridership_od_brt_daily`)
- [Daily Origin-Destination Ridership: Rapid Rail (KV)](data/ridership_od_rapidrail_daily.md) (`ridership_od_rapidrail_daily`)

### Prisons Department of Malaysia (`prisons`)

- [Prisoners by Prison Centre and Sex](data/prisoners_prison.md) (`prisoners_prison`)
- [data.gov.my Prisoners by State and Sex](data/prisoners_state.md) (`prisoners_state`) · [sample](samples/prisoners_state.csv)

### ProtectHealth Corporation (`protecthealth`)

- [Daily PeKaB40 Health Screenings](data/pekab40_screenings.md) (`pekab40_screenings`)
- [data.gov.my Daily PeKaB40 Health Screenings by State](data/pekab40_screenings_state.md) (`pekab40_screenings_state`) · [sample](samples/pekab40_screenings_state.csv)

### Singapore Government Data.gov.sg (`sg-datagov`)

- [COE Bidding Results (SG)](data/sg_datagov_coe_bidding.md) (`sg_datagov_coe_bidding`)
- [HDB Dataset Metadata (SG)](data/sg_datagov_hdb_metadata.md) (`sg_datagov_hdb_metadata`)
- [HDB Resale Flat Prices Jan-2017 onwards (SG)](data/sg_datagov_hdb_resale_prices.md) (`sg_datagov_hdb_resale_prices`)
- [Taxi Availability real-time (SG)](data/sg_datagov_taxi_availability.md) (`sg_datagov_taxi_availability`)
- [Weather Readings real-time (SG)](data/sg_datagov_weather_readings.md) (`sg_datagov_weather_readings`)

### National Water Services Commission (`span`)

- [data.gov.my Access to Treated Water by State & Strata](data/water_access.md) (`water_access`) · [sample](samples/water_access.csv)
- [Water Consumption by State and Sector](data/water_consumption.md) (`water_consumption`)
- [data.gov.my Water Production by State](data/water_production.md) (`water_production`) · [sample](samples/water_production.csv)

### Tenaga Nasional Berhad (`tnb`)

- [Monthly Electricity Consumption](data/electricity_consumption.md) (`electricity_consumption`)
<!-- END readme-inventory -->

## Current coverage

### Refresh cadence

<!-- BEGIN readme-cadence -->
| Dataset | Refresh cadence |
| --- | --- |
| `air_pollution` | monthly |
| `almanak_astronomi` | daily |
| `arrivals` | monthly |
| `arrivals_soe` | monthly |
| `births` | daily |
| `blood_donations` | daily |
| `blood_donations_state` | daily |
| `bnm_base_rate` | monthly |
| `bnm_interbank_swap` | daily (weekdays) |
| `bnm_interest_rate` | monthly |
| `bnm_interest_volume` | monthly |
| `bnm_kijang_emas` | daily |
| `bnm_kl_usd_myr` | daily (weekdays) |
| `bnm_myor` | daily |
| `bnm_opr` | monthly |
| `bop_balance` | quarterly |
| `cellular_subscribers` | annual |
| `completion_school_state` | annual |
| `cosmetic_notifications` | monthly |
| `cosmetic_notifications_cancelled` | monthly |
| `cosmetics_manufacturers` | daily |
| `covid_cases` | daily |
| `covid_cases_age` | daily |
| `covid_cases_vaxstatus` | daily |
| `covid_deaths_linelist` | annual |
| `cpi_3d` | monthly |
| `cpi_4d` | monthly |
| `cpi_5d` | monthly |
| `cpi_core` | monthly |
| `cpi_core_inflation` | monthly |
| `cpi_headline` | monthly |
| `cpi_state` | monthly |
| `cpi_state_inflation` | monthly |
| `crops_state` | annual |
| `currency_codes` | as-required |
| `currency_in_circulation` | monthly |
| `currency_in_circulation_annual` | annual |
| `datasets` | monthly |
| `deaths` | annual |
| `dgm_interest_rates` | monthly |
| `dgm_interest_rates_annual` | annual |
| `dgm_ktmb_ridership_monthly` | monthly |
| `dgm_money_aggregates` | monthly |
| `dgm_payments_channels` | monthly |
| `dgm_payments_instruments` | monthly |
| `dgm_payments_systems` | monthly |
| `dgm_payments_transactions_fpx` | daily |
| `dgm_vehicle_registrations_type_fuel` | monthly |
| `doe_apims` | hourly |
| `doe_mqims` | monthly |
| `doe_rqims` | hourly |
| `domains` | monthly |
| `domains_dnssec` | monthly |
| `domains_idn` | monthly |
| `domains_ipv6` | monthly |
| `dosm_arc_dosm` | daily |
| `dosm_bec` | as-required |
| `dosm_birth_state` | annual |
| `dosm_births_annual` | annual |
| `dosm_births_annual_sex_ethnic` | annual |
| `dosm_births_annual_sex_ethnic_state` | annual |
| `dosm_births_annual_state` | annual |
| `dosm_births_district_sex` | annual |
| `dosm_cpi_annual` | annual |
| `dosm_cpi_annual_inflation` | annual |
| `dosm_cpi_core_inflation` | monthly |
| `dosm_cpi_headline_inflation` | monthly |
| `dosm_cpi_inflation` | monthly |
| `dosm_cpi_lowincome` | monthly |
| `dosm_cpi_state` | monthly |
| `dosm_cpi_state_inflation` | monthly |
| `dosm_cpi_strata` | monthly |
| `dosm_crime_district` | annual |
| `dosm_crops_district_area` | annual |
| `dosm_crops_district_production` | annual |
| `dosm_death_district_sex` | annual |
| `dosm_death_maternal` | annual |
| `dosm_death_maternal_state` | annual |
| `dosm_death_state` | annual |
| `dosm_deaths_district_sex` | annual |
| `dosm_deaths_early_childhood` | annual |
| `dosm_deaths_early_childhood_sex` | annual |
| `dosm_deaths_early_childhood_state` | annual |
| `dosm_deaths_early_childhood_state_sex` | annual |
| `dosm_deaths_maternal` | annual |
| `dosm_deaths_maternal_state` | annual |
| `dosm_deaths_sex_ethnic` | annual |
| `dosm_deaths_sex_ethnic_state` | annual |
| `dosm_deaths_state` | annual |
| `dosm_employment_sector` | annual |
| `dosm_fertility` | annual |
| `dosm_fertility_state` | annual |
| `dosm_forest_reserve` | annual |
| `dosm_forest_reserve_state` | annual |
| `dosm_gdp_annual_nominal_demand` | annual |
| `dosm_gdp_annual_nominal_demand_granular` | annual |
| `dosm_gdp_annual_nominal_income` | annual |
| `dosm_gdp_annual_nominal_supply` | annual |
| `dosm_gdp_annual_nominal_supply_granular` | annual |
| `dosm_gdp_annual_real_demand` | annual |
| `dosm_gdp_annual_real_demand_granular` | annual |
| `dosm_gdp_annual_real_supply` | annual |
| `dosm_gdp_annual_real_supply_granular` | annual |
| `dosm_gdp_district_real_supply` | annual |
| `dosm_gdp_gni_annual_nominal` | annual |
| `dosm_gdp_gni_annual_real` | annual |
| `dosm_gdp_lookup` | as-required |
| `dosm_gdp_qtr_nominal` | quarterly |
| `dosm_gdp_qtr_nominal_demand` | quarterly |
| `dosm_gdp_qtr_nominal_demand_granular` | quarterly |
| `dosm_gdp_qtr_nominal_supply` | quarterly |
| `dosm_gdp_qtr_nominal_supply_granular` | quarterly |
| `dosm_gdp_qtr_real` | quarterly |
| `dosm_gdp_qtr_real_demand` | quarterly |
| `dosm_gdp_qtr_real_demand_granular` | quarterly |
| `dosm_gdp_qtr_real_sa` | quarterly |
| `dosm_gdp_qtr_real_sa_demand` | quarterly |
| `dosm_gdp_qtr_real_sa_supply` | quarterly |
| `dosm_gdp_qtr_real_supply` | quarterly |
| `dosm_gdp_qtr_real_supply_granular` | quarterly |
| `dosm_gdp_state_real_supply` | annual |
| `dosm_hh_access_amenities` | annual |
| `dosm_hh_expenditure_dun` | biennial to triennial (survey years) |
| `dosm_hh_expenditure_parlimen` | biennial to triennial (survey years) |
| `dosm_hh_income` | biennial to triennial (survey years) |
| `dosm_hh_income_district` | biennial to triennial (survey years) |
| `dosm_hh_income_dun` | annual |
| `dosm_hh_income_parlimen` | annual |
| `dosm_hh_income_state` | biennial to triennial (survey years) |
| `dosm_hh_inequality` | biennial to triennial (survey years) |
| `dosm_hh_inequality_district` | biennial to triennial (survey years) |
| `dosm_hh_inequality_dun` | annual |
| `dosm_hh_inequality_parlimen` | annual |
| `dosm_hh_inequality_state` | biennial to triennial (survey years) |
| `dosm_hh_poverty` | biennial to triennial (survey years) |
| `dosm_hh_poverty_district` | biennial to triennial (survey years) |
| `dosm_hh_poverty_dun` | annual |
| `dosm_hh_poverty_parlimen` | annual |
| `dosm_hh_poverty_state` | biennial to triennial (survey years) |
| `dosm_hh_profile` | annual |
| `dosm_hh_profile_state` | annual |
| `dosm_hies_district` | annual |
| `dosm_hies_malaysia_percentile` | annual |
| `dosm_hies_state` | annual |
| `dosm_hies_state_percentile` | annual |
| `dosm_iowrt` | monthly |
| `dosm_iowrt_2d` | monthly |
| `dosm_iowrt_3d` | monthly |
| `dosm_ipi` | monthly |
| `dosm_ipi_1d` | monthly |
| `dosm_ipi_domestic` | monthly |
| `dosm_ipi_export` | monthly |
| `dosm_lfs_district` | annual |
| `dosm_lfs_dun` | annual |
| `dosm_lfs_month` | monthly |
| `dosm_lfs_month_duration` | monthly |
| `dosm_lfs_month_sa` | monthly |
| `dosm_lfs_month_status` | monthly |
| `dosm_lfs_month_youth` | monthly |
| `dosm_lfs_parlimen` | annual |
| `dosm_lfs_qtr` | quarterly |
| `dosm_lfs_qtr_sru_age` | quarterly |
| `dosm_lfs_qtr_sru_sex` | quarterly |
| `dosm_lfs_qtr_state` | quarterly |
| `dosm_lfs_qtr_tru_age` | quarterly |
| `dosm_lfs_qtr_tru_sex` | quarterly |
| `dosm_lfs_state_sex` | annual |
| `dosm_lfs_year` | annual |
| `dosm_lfs_year_sex` | annual |
| `dosm_lookup_item` | as-required |
| `dosm_lookup_premise` | as-required |
| `dosm_marriages` | annual |
| `dosm_marriages_age` | annual |
| `dosm_marriages_state` | annual |
| `dosm_marriages_state_age` | annual |
| `dosm_mcoicop` | as-required |
| `dosm_mineral_extraction` | monthly |
| `dosm_msic` | as-required |
| `dosm_population_malaysia` | annual |
| `dosm_population_parlimen` | annual |
| `dosm_population_state` | annual |
| `dosm_ppi` | monthly |
| `dosm_ppi_1d` | monthly |
| `dosm_ppi_sitc` | monthly |
| `dosm_productivity_annual` | annual |
| `dosm_productivity_annual_priority` | annual |
| `dosm_productivity_lookup` | as-required |
| `dosm_productivity_qtr` | quarterly |
| `dosm_sitc` | as-required |
| `dosm_sitc_sop` | as-required |
| `dosm_sppi` | quarterly |
| `dosm_sppi_1d` | quarterly |
| `dosm_sppi_2d` | quarterly |
| `dosm_stillbirths` | annual |
| `dosm_stillbirths_state` | annual |
| `dosm_timber_production` | annual |
| `dosm_trade_enduse_bec` | monthly |
| `dosm_trade_headline` | monthly |
| `dosm_trade_sitc_1d` | monthly |
| `drug_addicts_age` | annual |
| `drug_addicts_drugtype` | annual |
| `drug_addicts_education` | annual |
| `drug_addicts_occupation` | annual |
| `drug_arrests_age` | annual |
| `drug_arrests_ethnicity` | annual |
| `economic_indicators` | monthly |
| `electricity_access` | annual |
| `electricity_consumption` | monthly |
| `electricity_supply` | monthly |
| `employment_sector` | monthly |
| `enrolment_school_district` | annual |
| `eperolehan-diklankan` | hourly |
| `epf_dividend` | annual |
| `exchangerates` | monthly |
| `exchangerates_daily_0900` | daily (weekdays, 0900 MYT) |
| `exchangerates_daily_1130` | daily (weekdays, 1130 MYT) |
| `exchangerates_daily_1200` | daily (weekdays, 1200 MYT) |
| `exchangerates_daily_1700` | daily (weekdays, 1700 MYT) |
| `fdi_flows` | quarterly |
| `federal_budget_moe` | annual |
| `federal_budget_moh` | annual |
| `federal_finance_qtr` | quarterly |
| `federal_finance_qtr_de` | quarterly |
| `federal_finance_qtr_oe` | quarterly |
| `federal_finance_qtr_revenue` | quarterly |
| `federal_finance_year` | annual |
| `federal_finance_year_de` | quarterly |
| `federal_finance_year_oe` | annual |
| `federal_finance_year_revenue` | annual |
| `fertility` | monthly |
| `fish_landings` | monthly |
| `fuelprice` | weekly |
| `gdp_annual_nominal_supply` | annual |
| `gdp_annual_real_supply` | annual |
| `gdp_gni_annual_nominal` | annual |
| `gdp_qtr_nominal` | quarterly |
| `gdp_qtr_real` | quarterly |
| `gdp_qtr_real_sa` | quarterly |
| `gdp_state_real_supply` | annual |
| `ghg_emissions` | annual |
| `government_apps` | monthly |
| `government_apps_active` | monthly |
| `government_apps_downloads` | monthly |
| `government_apps_reviews` | monthly |
| `gtfs_realtime_ktmb` | 30 seconds |
| `gtfs_realtime_mybas_alor_setar` | 30 seconds |
| `gtfs_realtime_mybas_ipoh` | 30 seconds |
| `gtfs_realtime_mybas_johor` | 30 seconds |
| `gtfs_realtime_mybas_kangar` | 30 seconds |
| `gtfs_realtime_mybas_kota_bharu` | 30 seconds |
| `gtfs_realtime_mybas_kuala_terengganu` | 30 seconds |
| `gtfs_realtime_mybas_kuching` | 30 seconds |
| `gtfs_realtime_mybas_melaka` | 30 seconds |
| `gtfs_realtime_mybas_seremban_a` | 30 seconds |
| `gtfs_realtime_mybas_seremban_b` | 30 seconds |
| `gtfs_realtime_prasarana_bus_kl` | 30 seconds |
| `gtfs_realtime_prasarana_bus_mrtfeeder` | 30 seconds |
| `gtfs_realtime_prasarana_bus_penang` | 30 seconds |
| `gtfs_static_ktmb` | daily |
| `gtfs_static_mybas_alor_setar` | as-required |
| `gtfs_static_mybas_ipoh` | as-required |
| `gtfs_static_mybas_johor` | as-required |
| `gtfs_static_mybas_kangar` | as-required |
| `gtfs_static_mybas_kota_bharu` | as-required |
| `gtfs_static_mybas_kuala_terengganu` | as-required |
| `gtfs_static_mybas_kuching` | as-required |
| `gtfs_static_mybas_melaka` | as-required |
| `gtfs_static_mybas_seremban_a` | as-required |
| `gtfs_static_mybas_seremban_b` | as-required |
| `gtfs_static_prasarana_bus_kl` | as-required |
| `gtfs_static_prasarana_bus_kuantan` | as-required |
| `gtfs_static_prasarana_bus_mrtfeeder` | as-required |
| `gtfs_static_prasarana_bus_penang` | as-required |
| `gtfs_static_prasarana_rail_kl` | as-required |
| `hansard_mps` | as-required |
| `hansard_parliamentary_terms` | as-required |
| `hansard_sittings` | as-required |
| `healthcare_staff` | annual |
| `hh_expenditure_dun` | monthly |
| `hh_expenditure_parlimen` | monthly |
| `hh_income` | monthly |
| `hh_income_district` | monthly |
| `hh_income_state` | monthly |
| `hh_inequality` | monthly |
| `hh_inequality_district` | monthly |
| `hh_inequality_state` | monthly |
| `hh_poverty` | monthly |
| `hh_poverty_district` | monthly |
| `hh_poverty_state` | monthly |
| `hospital_beds` | annual |
| `infant_immunisation` | annual |
| `interestrates` | monthly |
| `interestrates_annual` | annual |
| `ipi_2d` | monthly |
| `ipi_3d` | monthly |
| `ipi_5d` | monthly |
| `ipi_domestic` | monthly |
| `ipi_export` | monthly |
| `kkm_idengue` | daily |
| `kkmnow_bedutil` | daily |
| `kkmnow_blood` | daily |
| `kkmnow_covidepid` | weekly |
| `kkmnow_covidnow` | daily |
| `kkmnow_covidvax` | daily |
| `kkmnow_facilities` | annual |
| `kkmnow_organ` | daily |
| `kkmnow_pekab40` | daily |
| `lecturers_uni` | annual |
| `legal_advisory_branch` | monthly |
| `legal_advisory_case_type` | monthly |
| `legal_advisory_category` | monthly |
| `legal_advisory_subcategory` | monthly |
| `lfs_month` | monthly |
| `lfs_qtr` | quarterly |
| `lfs_qtr_state` | quarterly |
| `lfs_year` | annual |
| `local_authority_sex` | annual |
| `lookup_federal_finance` | as-required |
| `lookup_money_banking` | as-required |
| `marriages_state` | annual |
| `marriages_state_age` | annual |
| `mbpp_weather_stations` | hourly |
| `met_weather` | daily |
| `metrics_content` | monthly |
| `metrics_dataset_cumul` | daily |
| `mnha` | annual |
| `mnha_moh` | annual |
| `monetary_aggregates` | monthly |
| `nutrition_children_sex` | annual |
| `nutrition_children_strata` | annual |
| `organ_pledges` | daily |
| `organ_pledges_state` | daily |
| `parliament_sex` | annual |
| `passports` | monthly |
| `payment_channels` | monthly |
| `payment_instruments` | monthly |
| `payment_systems` | monthly |
| `pekab40_screenings` | daily |
| `pekab40_screenings_state` | daily |
| `pharmaceutical_importers` | monthly |
| `pharmaceutical_manufacturers` | monthly |
| `pharmaceutical_products` | monthly |
| `pharmaceutical_products_cancelled` | monthly |
| `pharmaceutical_wholesalers` | monthly |
| `population_district` | annual |
| `population_dun` | annual |
| `population_malaysia` | annual |
| `population_parlimen` | annual |
| `population_state` | annual |
| `poskod` | as-required |
| `ppi` | monthly |
| `ppi_2d` | monthly |
| `ppi_3d` | monthly |
| `ppi_sop` | monthly |
| `pricecatcher` | monthly |
| `prisoners_prison` | annual |
| `prisoners_state` | annual |
| `registration_transactions_all` | daily |
| `registration_transactions_car` | daily |
| `registration_transactions_motorcycle` | daily |
| `registrations_type_fuel` | monthly |
| `ridership_headline` | daily |
| `ridership_ktmb_daily` | daily |
| `ridership_ktmb_monthly` | monthly |
| `ridership_od_brt_daily` | daily |
| `ridership_od_ets` | daily |
| `ridership_od_intercity` | daily |
| `ridership_od_komuter` | daily |
| `ridership_od_komuter_utara` | daily |
| `ridership_od_rapidrail_daily` | daily |
| `ridership_od_shuttle_tebrau` | daily |
| `sanitation_access` | annual |
| `schools_district` | annual |
| `sdg_03-3-1` | annual |
| `sdg_04-6-1` | annual |
| `sdg_10-c-1` | annual |
| `sdg_16-1-1` | annual |
| `sdg_16-2-2` | annual |
| `sg_datagov_coe_bidding` | monthly |
| `sg_datagov_hdb_metadata` | monthly |
| `sg_datagov_hdb_resale_prices` | monthly |
| `sg_datagov_taxi_availability` | daily |
| `sg_datagov_weather_readings` | daily |
| `sppi_3d` | monthly |
| `st_cogenerators` | annual |
| `st_consumers` | monthly |
| `st_current_cogen_licensees` | as-required |
| `st_current_ipp_licensees` | as-required |
| `st_current_lss_licensees` | as-required |
| `st_current_re_licensees` | as-required |
| `st_elesca` | annual |
| `st_energy_balance_pdf` | annual |
| `st_generation_mix_gwh` | annual |
| `st_installed_capacity_mw` | monthly |
| `st_ipps` | annual |
| `st_max_demand_mw` | monthly |
| `st_re_projects` | annual |
| `st_sales_unit_gwh` | monthly |
| `st_sales_value_rm_million` | monthly |
| `state_finance_expenditure` | annual |
| `state_finance_revenue` | annual |
| `std_state` | annual |
| `teachers_district` | annual |
| `trade_headline` | monthly |
| `trade_sitc_1d` | monthly |
| `trnsc_daily_directdebit` | daily |
| `trnsc_daily_fpx` | daily |
| `trnsc_daily_jompay` | daily |
| `trnsc_daily_san` | daily |
| `usage_metrics` | daily |
| `usage_metrics_openapi` | daily |
| `usage_metrics_openapi_cumul` | daily |
| `vaxreg_covid` | daily |
| `vaxreg_covid_demog` | annual |
| `water_access` | annual |
| `water_consumption` | annual |
| `water_pollution_basin` | annual |
| `water_production` | annual |
<!-- END readme-cadence -->

DataPulse currently tracks the portfolio declared in `datapulse.json`.

## How to use it

Start with [`datapulse.json`](datapulse.json) to discover datasets and their
official sources. Follow each `health_report` link for a plain-language
assessment, or consume the matching file under `data/json/` in an automated
workflow.

For example, a data pipeline can inspect `status`, `content_freshness_date`, and
`freshness_signal_source` before processing a source, while a researcher can
review the known quirks before designing a collection method.

## External verification

For a clone-less, independent check of the published Ed25519 dataset envelope,
GitHub source parity, and Rekor/Sigstore health witness, see
[Verify DataPulse externally](docs/verify-datapulse-externally.md).

Every dataset in this catalogue ships with a **publicly-signed Sigstore
DSSE evidence receipt** that an agent can verify offline, without trusting
the DataPulse server. An agent (human or MCP) can obtain, for any dataset,
the full health row + evidence + signed-receipt-verification in **three MCP
tool calls or fewer**: `verify_dataset` → `get_freshness_summary`. The standard
offline path is the `verify_external.py` command above.

For the portfolio-level health bundle, verify
`/signatures/health.latest.sigstore.json` with the exact companion manifest
at `/signatures/datapulse.json`. That signed-manifest snapshot is distinct
from `/datapulse.json`, the current discovery manifest: the latter can change
when generated metadata is refreshed. A valid signature proves the integrity
of DataPulse's attested observation, not that upstream data is semantically
true. Every refresh publishes signed bundles to the public Rekor log.

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

DataPulse is released under the [MIT License](LICENSE). Source datasets
remain subject to the licences and attribution requirements stated in their
individual health reports.

## Privacy

See [PRIVACY.md](PRIVACY.md) for what DataPulse collects (transient operational
logs for rate limiting and usage aggregation) and what it does not collect
(no credentials, no accounts, no personal data).

## Legal

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
