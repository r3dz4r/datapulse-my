# DataPulse MY — Privacy Policy

_Last updated: 2026-08-17_

## Scope

DataPulse MY ("DataPulse") publishes a continuously verified catalogue of Malaysian public-sector datasets and exposes them through a read-only Model Context Protocol (MCP) endpoint at `mcp.data-pulse.my`.

This policy covers:

1. What DataPulse collects when you use the public endpoint or the MCP server.
2. What DataPulse does not collect.
3. How collected information is used, stored, and retained.
4. Your rights and contact information.

## 1. Data DataPulse collects

### 1.1 Source data (published datasets)

DataPulse mirrors and verifies metadata about **Malaysian public-sector datasets** sourced from government publishers (data.gov.my, Bank Negara Malaysia, Department of Statistics Malaysia, Ministry of Health, and other public agencies). This data is **already published by the relevant government bodies** and is not personal data belonging to DataPulse.

### 1.2 Operational logs (when you call the MCP endpoint)

When a client connects to `mcp.data-pulse.my/mcp`, DataPulse may record:

- The **IP address** of the caller, retained transiently for rate limiting and abuse prevention.
- The **tool name and sanitised arguments** of each tool call, retained in an aggregated usage ledger.
- A **buyer identifier** you supply when calling tools such as `usage_summary` (e.g. `"pro-default"` or `"anonymous"`).

Arguments are passed through a sanitisation layer that strips credential-shaped values (API keys, tokens, secrets) before logging.

### 1.3 Environment variables (self-hosted deployments)

If you self-host the DataPulse MCP server, configuration values such as `DATAPULSE_MCP_SOURCE_SHA`, `DATAPULSE_MCP_SOURCE_DATE`, `DATA_BASE`, `MCP_HOST`, `MCP_PORT`, `DATAPULSE_REPO_ROOT`, and `FAKE_DATE` are read from your local environment and stay on your machine. The server does not transmit these values anywhere.

## 2. What DataPulse does NOT collect

- **No account creation.** You do not need an account to use the public MCP endpoint.
- **No cookies, tracking pixels, or advertising identifiers.**
- **No credentials.** DataPulse does not ask for or store API keys, passwords, or tokens for the public endpoint.
- **No personal data about Malaysian citizens.** The catalogue covers published government datasets; it does not collect personal information about individuals.

## 3. How collected information is used

- **IP address:** rate limiting and abuse prevention only.
- **Tool usage ledger:** operational monitoring, EU AI Act–style usage transparency, and aggregated reporting (via `usage_summary`). Aggregates are released only in forms that do not identify individual callers.
- **Buyer identifier:** lets you group your own usage records; DataPulse does not map identifiers to personal identities.

## 4. Storage and retention

- Logs are stored on DataPulse's infrastructure (a single VPS in the Asia/Kuala_Lumpur region) and are not sold or shared with third parties except as required by law.
- Usage ledger entries are retained for a rolling window; aggregate statistics may be retained longer after removing identifiers.
- The published dataset catalogue and verification evidence are public by design and retained as part of the open-source repository at [github.com/r3dz4r/datapulse-my](https://github.com/r3dz4r/datapulse-my).

## 5. Open source

The DataPulse MCP server source code is MIT-licensed and published at [github.com/r3dz4r/datapulse-my](https://github.com/r3dz4r/datapulse-my). You can inspect exactly what the server does with your requests.

## 6. Your rights and contact

You may contact the operator with privacy questions at the repository's issue tracker. If you believe the public endpoint has mishandled your data, open an issue and DataPulse will respond promptly.

## 7. Changes to this policy

Material changes will be noted in the repository changelog and this document's "Last updated" date will be bumped.

---

_© 2026 DataPulse MY. This document is provided for transparency; it does not create contractual obligations beyond the MIT license of the software._
