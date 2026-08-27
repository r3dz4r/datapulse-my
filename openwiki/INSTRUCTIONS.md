# DataPulse MY OpenWiki generation contract

Generate derivative documentation only from the current repository sources of record:
`config/public-surfaces.json`, `datapulse.json`, `health/latest.json`, `mcp.json`,
`README.md`, `llms.txt`, and the checked-in workflow files.

The canonical human website origin is `https://www.data-pulse.my`; the MCP
endpoint remains `https://mcp.data-pulse.my/mcp`. Treat the manifest, health
snapshot, MCP catalogue, and workflows as sources of record. This documentation
does not establish or override any of them.

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
