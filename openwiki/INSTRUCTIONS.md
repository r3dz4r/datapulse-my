# DataPulse MY OpenWiki generation contract

Generate derivative documentation only from the current repository sources of record:
`config/public-surfaces.json`, `datapulse.json`, `health/latest.json`, `mcp.json`,
`README.md`, `llms.txt`, and the checked-in workflow files.

The canonical human website origin is `https://www.data-pulse.my`; the MCP
endpoint remains `https://mcp.data-pulse.my/mcp`. Treat the manifest, health
snapshot, MCP catalogue, and workflows as sources of record. This documentation
does not establish or override any of them.

REQUIRED VERBATIM FACTS — each generated page MUST include all three of the
following literal strings (they are derived from `config/public-surfaces.json`,
the current `datapulse.json` dataset count, and the current `mcp.json` tool
count, and are enforced by `scripts/verify_openwiki.py`):

- The canonical website origin: `https://www.data-pulse.my` (NOT the apex
  `https://data-pulse.my`).
- The current dataset count: read `datapulse.json`'s `datasets` array length and
  include the literal `<N> datasets` (currently `389 datasets`) in any page that
  discusses discovery or the manifest.
- The current tool count: read `mcp.json`'s `tools` array length and include the
  literal `<N> read-only tools` (currently `16 read-only tools`) in any page
  that discusses the MCP server.

These counts and the URL MUST be derived from the live sources of record at the
time of generation; never substitute a value remembered from prior context. Do
not paraphrase them.

You may generate only `quickstart.md`, `datasets.md`, `mcp.md`,
`operations.md`, and `.last-update.json` in this directory. OpenWiki may also
update only its managed marker/pointer blocks in `AGENTS.md` or `CLAUDE.md`;
all other changes to those files are forbidden. Do not edit source code,
workflows, configuration, manifests, public HTML, or any files outside those
outputs and managed marker/pointer blocks.

Describe observed published facts with dates or source links where useful. Do
not claim universal trust, payment capability, reputation, certification, or
guaranteed availability. Preserve DataPulse's read-only posture and state that
upstream sources remain authoritative for substantive data.
