# Changelog

All notable changes to DataPulse MY are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release with 7 monitored datasets across 3 agencies (MOF, KPDN, BNM)
- Weekly GitHub Actions workflow for openwiki auto-refresh
- Health report + JSON envelope schema (OKF v0.1 aligned)

### Known issues
- Public outreach not yet attempted; first feedback collection pending

## [0.1.0] - 2026-07-31

### Added
- Project scaffold (MIT license, README, CONTRIBUTING, .gitignore)
- `datapulse.json` manifest schema for dataset registry
- Health report format: `data/<id>.md` with frontmatter + body
- Machine-readable envelope format: `data/json/<id>.json` with checks + quirks
- "Adopt a dataset" contribution model documented in CONTRIBUTING.md

### Datasets
- `fuelprice` — Weekly fuel prices (MOF via data.gov.my)
- `eperolehan-diklankan` — ePerolehan tender notices, DIIKLANKAN tab (MOF, scraped via Camofox)
- `pricecatcher` — Daily grocery prices (KPDN via data.gov.my, parquet download)
- `exchangerates_daily_0900` — BNM daily FX rates (0900 MYT)
- `exchangerates_daily_1130` — BNM daily FX rates (1130 MYT)
- `exchangerates_daily_1200` — BNM daily FX rates (1200 MYT, noon reference rate)
- `exchangerates_daily_1700` — BNM daily FX rates (1700 MYT, end-of-day)
