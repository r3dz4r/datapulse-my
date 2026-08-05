# Changelog

This is the chronological project history. Live dataset state belongs in
[`health/latest.json`](health/latest.json) and generated machine-readable state
belongs in [`changelog.json`](changelog.json).

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
