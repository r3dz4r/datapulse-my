# Changelog

This is the chronological project history. Live dataset state belongs in
[`health/latest.json`](health/latest.json) and generated machine-readable state
belongs in [`changelog.json`](changelog.json).

## [0.9.1](https://github.com/r3dz4r/datapulse-my/compare/v0.9.0...v0.9.1) (2026-08-20)


### Bug Fixes

* **ci:** use github token for anchor attestation ([#20](https://github.com/r3dz4r/datapulse-my/issues/20)) ([83fa749](https://github.com/r3dz4r/datapulse-my/commit/83fa7499845552e7f75939f7f44afafd57f869d1))
* **nginx:** correct MCP vhost hostname ([#19](https://github.com/r3dz4r/datapulse-my/issues/19)) ([1fbe7db](https://github.com/r3dz4r/datapulse-my/commit/1fbe7db4483c1b9c1ebb80c3a703dec6439590ae))

## [0.9.0](https://github.com/r3dz4r/datapulse-my/compare/v0.8.0...v0.9.0) (2026-08-18)


### Features

* **attestation:** publish real Ed25519 key registry + first daily digests ([05081da](https://github.com/r3dz4r/datapulse-my/commit/05081da271dabc632ea3dbb804ca16ea13839f2c))
* **attestation:** signed probe attestation chain + trust_verdict + verify_attestation (the alpha) ([e27b1e8](https://github.com/r3dz4r/datapulse-my/commit/e27b1e82d1bf58c8300f42b53af02e11ad4d816d))
* **drift:** add schema/content drift detection, expose via MCP ([280ddef](https://github.com/r3dz4r/datapulse-my/commit/280ddefaa96b5ca1d0e4a94fc013fe8fa4db2d00))
* **embed:** self-heal changelog-strip in docs/index.html ([d7c9381](https://github.com/r3dz4r/datapulse-my/commit/d7c9381a49151b8925217025502661965dc33a3a))
* **evidence:** evidence receipts + verify_evidence live check — completes trust-layer moat plan ([c01aaf0](https://github.com/r3dz4r/datapulse-my/commit/c01aaf0f88811b27ca7b0176a3f81913eb730a90))
* **generator:** own MCP inventory in llms.txt, README.md, agent.json, docs/mcp-deploy.md ([b39e728](https://github.com/r3dz4r/datapulse-my/commit/b39e728c0a67b06bb2985133dfdd61e92c34a3bc))
* **mcp:** observability foundation — per-buyer JSONL usage sink + usage_summary tool ([4ee851a](https://github.com/r3dz4r/datapulse-my/commit/4ee851a5847ad198179d2cfd8acae2a1edb41900))
* **mcp:** polish tool descriptions and publish score ([79f586c](https://github.com/r3dz4r/datapulse-my/commit/79f586c62e377835b3c027061d1b6475e47e8ec0))
* **methodology:** self-healing page — extract from code, keep prose ([babc03b](https://github.com/r3dz4r/datapulse-my/commit/babc03b9e5c04eeaf18df34e9f409d2ced3c51c9))
* **nav:** self-healing site nav from assets/site-nav.html partial ([8b4877f](https://github.com/r3dz4r/datapulse-my/commit/8b4877fe05602b37eebc391f81f6023a08003cf1))
* **reconciliation:** cross-source duplicate detection + MCP exposure ([2aba9ec](https://github.com/r3dz4r/datapulse-my/commit/2aba9ec869a613c1eaa5b60e7a4310db3e666f4b))
* **reliability:** expose reliability scoring — find_unreliable + min_reliability filter + resource ([9b6b732](https://github.com/r3dz4r/datapulse-my/commit/9b6b7323cad834160962aeaae757524f724f3d6e))
* **scoring:** methodology v2 — missing-signal weighting + reference cap ([be3fcae](https://github.com/r3dz4r/datapulse-my/commit/be3fcae5d38389907358b55694f95a83ae0d0e3c))
* **scoring:** methodology_version 3 with explicit component availability ([57002f1](https://github.com/r3dz4r/datapulse-my/commit/57002f1fcd085203d27185ea786651aaf0ce54c3))
* **theme:** uniform prose typography across all pages ([6b61e1c](https://github.com/r3dz4r/datapulse-my/commit/6b61e1cb915eb324a2771ad0ebacee68a8193a24))


### Bug Fixes

* **ci:** bind DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE secret to deploy step ([d8af2f1](https://github.com/r3dz4r/datapulse-my/commit/d8af2f1871143170963ab4e707c7f7327814e2da))
* **ci:** copy .attestations/ to _site for chain_head.json access ([ada4ca1](https://github.com/r3dz4r/datapulse-my/commit/ada4ca1f16620b1fd268b8d10781b7c47930188c))
* **ci:** deterministic-safety-net green — archives dir + history fixture ([eaab5a6](https://github.com/r3dz4r/datapulse-my/commit/eaab5a608336ea752e6676430eec93869bb486d8))
* **ci:** freshness workflow checks pipeline-liveness, not data freshness ([2c68852](https://github.com/r3dz4r/datapulse-my/commit/2c6885247c3c3daf1af6fcf35e4d3129b42fc07f))
* **ci:** release-please concurrency block — cancel in-flight runs on new push ([aa72932](https://github.com/r3dz4r/datapulse-my/commit/aa72932781fc66ce7d759f868ba89d75c32caa1f))
* **ci:** use GITHUB_TOKEN for attestation anchor injection ([677218e](https://github.com/r3dz4r/datapulse-my/commit/677218e49efe4f7b15748753bb5b6fe99be7b151))
* **ci:** wire DATAPULSE_ARCHIVES_DIR through harness + defensive generate.sh fallback ([36ce9e6](https://github.com/r3dz4r/datapulse-my/commit/36ce9e6d23018454280a0346b444fa91f6c87317))
* **ci:** write the attestation key to a temp file before gen runs ([eaa2cc2](https://github.com/r3dz4r/datapulse-my/commit/eaa2cc2cc83589864958e44a82eeb26a1902fbea))
* **dashboard:** clarify ODIN [#1](https://github.com/r3dz4r/datapulse-my/issues/1) claim with freshness gap framing ([0af9882](https://github.com/r3dz4r/datapulse-my/commit/0af98825022d4e8aec66e790eda821add6dce951))
* **generator:** substitute dataset count in agent.json description ([e85e6c4](https://github.com/r3dz4r/datapulse-my/commit/e85e6c43d0f4ef710a11f8f9d0cd953dcce2d478))
* **health:** audit + reduce 32 unknown-freshness to 0 ([371bf43](https://github.com/r3dz4r/datapulse-my/commit/371bf432d8ac18df3bd5ed7ab4d12e1c5f0f6096))
* **invariants:** include tool annotations in MCP expected_tools ([988f29d](https://github.com/r3dz4r/datapulse-my/commit/988f29db77c2c92d82d9d5624854c588f5b86a20))
* **llms.txt:** correct tool count 15 → 16 in prose paragraph ([d48f3cb](https://github.com/r3dz4r/datapulse-my/commit/d48f3cbfa0a0fb7df3196475feb00d8bf66aed67))
* **mcp:** serialize tool annotations into mcp.json; add PRIVACY.md ([16cfe7b](https://github.com/r3dz4r/datapulse-my/commit/16cfe7b1b83e966130a4738d3834046362bf2853))
* **methodology:** defensive timer read for CI / non-systemd environments ([40fdc81](https://github.com/r3dz4r/datapulse-my/commit/40fdc816f2f81050dc7d645c962a7ef9ecece6a7))
* **methodology:** render with shared datapulse.css + site-nav ([2f1956f](https://github.com/r3dz4r/datapulse-my/commit/2f1956f8b09311a8f169c63a26f6318f3a45390f))
* **migrations:** trim-history single-pass partition (was O(n²)) ([5ad1225](https://github.com/r3dz4r/datapulse-my/commit/5ad1225bad91bc0019718c911ea5b0838728de5a))
* **nav:** eliminate wrapped-row gap between nav links on mobile ([1aa7578](https://github.com/r3dz4r/datapulse-my/commit/1aa75782c91cea85c58dc2fa79f934bc5d5bfa93))
* **telemetry:** add attestation-score to allowed stages ([38bb5dd](https://github.com/r3dz4r/datapulse-my/commit/38bb5dde5bfea27113867ef662fb0617b0356a05))
* **workflow:** suppress Pages deploy on heartbeat-only pushes ([d15dda2](https://github.com/r3dz4r/datapulse-my/commit/d15dda20292479a94ca81db053ac1055f2b88615))

## [0.8.0](https://github.com/r3dz4r/datapulse-my/compare/v0.7.0...v0.8.0) (2026-08-15)


### Features

* **attestation:** publish real Ed25519 key registry + first daily digests ([cf738fd](https://github.com/r3dz4r/datapulse-my/commit/cf738fd506ad20e998011b20d02ef6a22b6676fe))
* **attestation:** signed probe attestation chain + trust_verdict + verify_attestation (the alpha) ([11ec455](https://github.com/r3dz4r/datapulse-my/commit/11ec455b2ca24bce91398159ff1f991aac4cc509))


### Bug Fixes

* **ci:** bind DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE secret to deploy step ([5d60a56](https://github.com/r3dz4r/datapulse-my/commit/5d60a56b8f304b504c6849a393d55fbe2100df25))
* **ci:** copy .attestations/ to _site for chain_head.json access ([a55b3ad](https://github.com/r3dz4r/datapulse-my/commit/a55b3ad0995ced853960529a02f4be93275e74dd))
* **ci:** write the attestation key to a temp file before gen runs ([77f42a7](https://github.com/r3dz4r/datapulse-my/commit/77f42a79b5090a41a0b841cb4b704e7d690ab439))

## [0.7.0](https://github.com/r3dz4r/datapulse-my/compare/v0.6.0...v0.7.0) (2026-08-15)


### Features

* **evidence:** evidence receipts + verify_evidence live check — completes trust-layer moat plan ([8fbc66c](https://github.com/r3dz4r/datapulse-my/commit/8fbc66c9baccb49253dc75e7fe1e150a0251803f))
* **reconciliation:** cross-source duplicate detection + MCP exposure ([b00fd1a](https://github.com/r3dz4r/datapulse-my/commit/b00fd1a0fb669443c4ad36e9b08881e615326b42))
* **reliability:** expose reliability scoring — find_unreliable + min_reliability filter + resource ([105e178](https://github.com/r3dz4r/datapulse-my/commit/105e1786d199d2fc10ccf80153cc1fc22b177989))

## [0.6.0](https://github.com/r3dz4r/datapulse-my/compare/v0.5.0...v0.6.0) (2026-08-15)


### Features

* **anomaly:** calibrate detection — 12/14 rolling tolerance + strict &gt;3x cadence fallback ([e1cfab3](https://github.com/r3dz4r/datapulse-my/commit/e1cfab3fe6e4ea96060aa30e7de7268f67450da6))
* **drift:** add schema/content drift detection, expose via MCP ([859b1bd](https://github.com/r3dz4r/datapulse-my/commit/859b1bd0760f9f063a6ab45e93a15bda1380f048))
* **mcp:** expose anomaly detection — find_anomalies tool + datapulse://anomalies resource ([de3f084](https://github.com/r3dz4r/datapulse-my/commit/de3f084add4e0e3a087edfd5ee208eb3d3fa88c4))
* **trends:** add dataset trend tracking + reliability scoring, expose via MCP ([5706ca6](https://github.com/r3dz4r/datapulse-my/commit/5706ca6a1ed698dc08b0cc1ee35af2972e41763a))


### Bug Fixes

* **docs:** add find_anomalies to llms.txt tool table ([a36ccd9](https://github.com/r3dz4r/datapulse-my/commit/a36ccd97f334415ece0fdc62542938286455d800))

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
