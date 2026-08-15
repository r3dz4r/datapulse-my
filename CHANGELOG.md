# Changelog

This is the chronological project history. Live dataset state belongs in
[`health/latest.json`](health/latest.json) and generated machine-readable state
belongs in [`changelog.json`](changelog.json).

## [0.5.0](https://github.com/r3dz4r/datapulse-my/compare/v0.4.2...v0.5.0) (2026-08-15)


### Features

* **catalogue:** add 4 legal advisory datasets (JBG) to manifest ([fc23623](https://github.com/r3dz4r/datapulse-my/commit/fc23623757b792f70205b2f8bbb86f73a27c057c))
* **catalogue:** generate artifacts for legal_advisory datasets ([a9ad153](https://github.com/r3dz4r/datapulse-my/commit/a9ad1533a10a81f0ad7fd97b34ff3176b668d440))


### Bug Fixes

* **catalogue:** add expected_record_count to legal_advisory entries ([2abe022](https://github.com/r3dz4r/datapulse-my/commit/2abe0228db02996a943b5b2af397b59fd82d4e92))
* **catalogue:** register jbg custodian (Legal Aid Department) ([9481d4c](https://github.com/r3dz4r/datapulse-my/commit/9481d4c540078b687463bf8e652d3be152e7b137))
* **dashboard:** regenerate embedded data + filters for 389 datasets ([4f43b75](https://github.com/r3dz4r/datapulse-my/commit/4f43b75796aa08c5b60b1788a080bf5a91545aa2))
* **mcp:** regenerate mcp.json with 389-dataset descriptions ([5dd028d](https://github.com/r3dz4r/datapulse-my/commit/5dd028d900bb228e57ecd1491a82917d2caf7dbc))

## [0.4.2](https://github.com/r3dz4r/datapulse-my/compare/v0.4.1...v0.4.2) (2026-08-15)


### Bug Fixes

* **mcp:** _fetch_json follows redirects so tools survive DATA_BASE drift ([bf303d7](https://github.com/r3dz4r/datapulse-my/commit/bf303d7792dc8ad4a334d002b523570ecc33bb77))

## 2026-08-06

- Repaired the manifest schema and agent-discovery contracts (`c2aac5c`).
- Wired README summary generation into the 15-minute service source and made
  the summary match the current health snapshot (`606d0bb`).
- Regenerated the JSON-LD catalog with 122 dereferenceable dataset URLs and
  expanded the dashboard graph from 50 to 122 objects (`1b7359b`).
- Regenerated the entry-point and operational documentation from live sources.

## 2026-08-05

- Added dynamic PriceCatcher URLs, CSV/parquet row-count handling, failed-probe
  preservation, and more reliable browser polling.
- Added the README trust-summary generator and initial Pages invariant gate
  (`f618bba`).
- Corrected BNM 1700 freshness handling and made the dashboard display the
  declared MYT publication time (`0dc0712`).

## 2026-08-04

- Added 30 GTFS feeds—16 static and 14 realtime—bringing the catalog to 122
  datasets (`1eb668f`).
- Added namespaces, tiered `--due` probing, JSON-LD, agent discovery files,
  Plausible analytics, and deploy-on-health-workflow completion.
- Distinguished stale data from missing freshness evidence and restored the
  browser-dependent status for browser-only sources.

## 2026-08-03

- Expanded coverage from 13 to 92 datasets across economic, demographic,
  health, utilities, transport, and government-open-data sources.
- Replaced blanket health claims with the eight-status trust taxonomy
  (`0659220`).
- Deployed the read-only MCP service and added adoption issue/PR templates.

## 2026-08-02

- Added the health probe, weekly fallback workflow, badges, RSS feed, samples,
  embedded-data dashboard, GitHub Pages deployment, and agent-ready index.
- Added MET Malaysia, DOE browser-backed sources, iDengue, and initial OpenDOSM
  datasets.

## 2026-08-01

- Added PriceCatcher and four BNM publication-time datasets, growing the
  initial catalog to seven datasets.
- Added the scheduled OpenWiki refresh and corrected the fuel-price schema.

## 2026-07-31

- Created the repository, manifest, contribution model, licence, and the first
  `fuelprice` and `eperolehan-diklankan` health records.
