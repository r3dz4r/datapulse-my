# Architecture

DataPulse MY is a read-only trust layer. Official publishers remain the source
of record; this repository stores metadata, observations, small samples, and
generated discovery surfaces rather than replacing upstream datasets.

## System boundaries

```text
official sources
  data.gov.my / OpenDOSM / BNM / MET / DOE / KKM / KPDN
       |
       v
scripts/check.sh + extractors + GTFS helper + Camofox
       |
       v
health/latest.json (merge with prior snapshot in --due mode)
       |
       +--> badges/ + feed.xml + README summary + changelog.json
       +--> data/jsonld/catalog.json + dashboard JSON-LD
       |
       v
GitHub Pages artifact --------------------> data-pulse.my
       |
       +--> manifest, reports, health, samples, agent discovery

mcp/server.py --fetches published manifest + health--> read-only MCP tools
```

## Sources and probes

`datapulse.json` is the registry and scheduling contract. Direct sources use
HEAD or GET probes; GTFS feeds use `scripts/probe_gtfs.py`; JavaScript-rendered
DOE, iDengue, and ePerolehan pages use Camofox. Content-date extractors provide
freshness evidence when HTTP headers do not.

## Health merge and artifacts

The 15-minute service calls `scripts/check.sh --due`. Only due rows are probed,
then their results are merged with preserved rows from the prior snapshot in
manifest order. A successful snapshot drives badges, RSS, README counts, and
the machine-readable changelog. JSON-LD is regenerated separately from the
manifest plus health state.

## Publication and MCP

`.github/workflows/deploy-pages.yml` assembles the static Pages artifact and
injects the current manifest and health snapshot into the dashboard. The MCP
service runs independently on the VPS, but reads the published Pages manifest
and health documents; it cannot write upstream data or repository state.
