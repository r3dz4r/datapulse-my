---
audience: agent and application builder, analyst
canonical: true
volatility: stable
owner: operator
review_trigger: when a tool name, the MCP endpoint, or the first-call workflow changes
last_verified: 2026-09-26
---

# Quickstart

Authorise-first is the pattern this page teaches: **find the dataset, check it, then answer with the status attached.** Five minutes, no account, no API key, no DataPulse installation.

## Prerequisite

An MCP-capable client (Claude Desktop, Cursor, Cline, or any client that speaks Streamable HTTP). Nothing else: the server is read-only and requires no authentication.

## 1. Add the server

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

Restart the client and confirm the server is listed with its read-only tools. This is the canonical configuration block for this product; other pages link here rather than repeating it.

## 2. Find the dataset

Ask your agent, or call `search_datasets` directly with a query. A query for air quality returns a ranked list:

```text
{"id": "doe_apims", "title": "DOE APIMS Air Quality (Hourly API)", "source": "DOE MyEQMS portal (Camofox-rendered)", "licence": "Open Government Licence (Malaysia)", "status": "fresh", "score": 25}
{"id": "air_pollution", "title": "Air Pollutant Concentrations", "source": "data.gov.my", "licence": "Creative Commons Attribution 4.0", "status": "stale", "score": 5}
```

The status is already visible at discovery time. That is deliberate: you should be able to choose a different source before you have written any answer.

## 3. Inspect, then check before you cite

`get_dataset` returns the full record for one id — custodian, steward, licence, declared `refresh_frequency`, `expected_record_count`, the source URL, `last_checked`, and the status with its reason.

`verify_dataset` is the pre-citation check. It returns the observation, the receipt digest, and a `signed` boolean derived from actually verifying the receipt. Observed fields for `air_pollution` on 2026-09-26:

```text
dataset_id = air_pollution
signed = True
verifier_output = Verified OK
receipt_digest = sha256:fa718a37643a396c9fdbc1019be0b166b53b0b3f00badda1387cca723c66549e
certificate_identity = https://github.com/r3dz4r/datapulse-my/.github/workflows/deploy-cloudflare-pages.yml@refs/heads/main
```

When `include_proof_steps` is set, the response also carries a `verification_hint`: a runnable command that reproduces the check yourself. Run it if you want proof rather than a boolean — the command and its expected output are in [Verify a DataPulse claim](verify.md).

## 4. Answer with the status attached

A correctly qualified answer states the figure, the source, the observation time, the status, and what the status permits. The rule is in [Status semantics](status-semantics.md): never replace the status with a colour or a score.

```text
Malaysia's air pollutant concentrations (source: Department of Environment via
data.gov.my, licence CC BY 4.0). DataPulse status: stale — the content date is
1395 days older than the monthly cadence at the observation on 2026-09-26.
Usable for historical context; do not present as current.
```

## 5. When the answer must be a refusal

The same call, answered honestly, looks like this:

```text
I can't give you current air pollutant concentrations from this dataset. The
source is reachable and the licence permits reuse, but DataPulse classifies it
as stale: the newest content it could observe is 1395 days old against a monthly
refresh cadence, as of 2026-09-26. For current readings, use doe_apims (status:
fresh), or treat the figures above as historical only.
```

A refusal that names the reason, the date, and the alternative is the product working. An agent that reports a stale figure as current has failed the check it was given.

## When a call fails

| Symptom | Meaning | What to do |
|---|---|---|
| `Unknown dataset id: <id>` | The id is not in the catalogue | Re-run `search_datasets`; ids are stable and returned by discovery |
| Receipt path returns HTTP 404 | No receipt is published for that observation | Treat the claim as unverified rather than assuming an error |
| A tool returns an empty list | The filter matched nothing | Widen the query; an empty result is not evidence of absence |

## Next

- [Agent workflows](agent-workflows.md) — complete jobs, including failure branches
- [Malaysia public-data workflow](agent-workflow-malaysia-public-data.md) — the bounded four-call path
- [MCP reference](mcp-reference.md) — every tool, generated from the server
- [Verify a DataPulse claim](verify.md) — the independent verification path
