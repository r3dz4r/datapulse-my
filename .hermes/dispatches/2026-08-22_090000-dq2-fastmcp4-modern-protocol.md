Workdir: /home/redza/datapulse-my
Goal: Complete the foundational MCP upgrade by migrating the existing DataPulse server from FastMCP 3.4.7 to the exact FastMCP 4.0.0b3 prerelease, enabling MCP 2026-07-28 modern/sessionless protocol compatibility while preserving legacy clients and the existing read-only 16-tool/9-resource surface.
Failure mode: A raw SDK rewrite or incomplete FastMCP 4 migration breaks the public MCP endpoint, legacy clients, middleware, annotations, resource behavior, or the static catalogue’s generated discovery surfaces. We must not ship a beta migration based on guessed APIs or stale dq-2 assumptions.
Acceptance test: The focused MCP suite and full repository safety gates pass; FastMCP 4.0.0b3 is pinned exactly; modern and legacy client paths are exercised; public cache hints are verified; 16 tools remain annotated; generated mcp.json remains coherent; `git diff --check` passes; no push occurs in this dispatch.
Recommended execution model: terra

# dq-2 refreshed — FastMCP 4 / MCP 2026-07-28

## Why this brief replaces the two older dq-2 briefs

The older briefs conflicted:

- `2026-08-20_011600-dq2-fastmcp-2026-07-28-upgrade.md` proposed FastMCP 4 but incorrectly assumed a `Stateless=True` constructor and said 11 tool annotations were missing.
- `2026-08-20_124500-dq2-mcp-sdk-v2-spec-upgrade.md` proposed replacing FastMCP with a raw `MCPServer`, which conflicts with the repository’s FastMCP architecture and `mcp/AGENTS.md` handler-isolation rule.

Live state before this dispatch:

- `fastmcp==3.4.7`
- `mcp==1.29.0`
- `mcp.json`: 16 tools, 0 missing annotation blocks
- `mcp/server.py`: FastMCP application with existing middleware, 16 tools, 9 resources
- all four required tool annotation hints are already present and tested
- FastMCP `4.0.0b3` is available as a prerelease and must be pinned exactly

Authoritative references consulted:

- `https://gofastmcp.com/development/v4-notes/protocol-2026`
- `https://gofastmcp.com/getting-started/upgrading/from-fastmcp-3`
- `https://modelcontextprotocol.io/specification/2026-07-28/changelog`

## In scope

- `mcp/requirements.txt`
- `mcp/server.py`
- `mcp/tests/` tests and fixtures required by the migration
- `scripts/tests/` only if a generated MCP-surface contract requires a narrowly scoped expectation update
- generated `mcp.json` only as a local verification artifact; do not hand-edit it

Do not modify:

- the 10-status taxonomy;
- dataset manifests or health logic;
- the DataPulse trust-layer code just shipped in `d51d72ff`;
- Cloudflare/Tailscale/systemd configuration;
- public docs unless a generator/test contract requires it;
- deployment workflows;
- existing untracked `.hermes/` or Phase 1 notes;
- any secrets or credential files.

## Required implementation approach

1. Read the FastMCP 4 upgrade guide and inspect the actual server for every relevant migration signal before editing. Report only signals found in this repository.
2. Pin `fastmcp==4.0.0b3` exactly. Let its supported MCP SDK v2 dependency resolve according to the package metadata; do not independently rewrite the server to raw `MCPServer`.
3. Preserve the FastMCP decorator architecture and existing middleware unless the upgrade guide proves a specific API break. Do not introduce a speculative abstraction.
4. Configure the static public catalogue’s supported cache hints using the confirmed FastMCP 4 API: `cache_ttl=300` and `cache_scope="public"` where the constructor accepts them. Do not use `private`: the tool catalogue is identical for unauthenticated callers.
5. Do not add `Stateless=True` unless the installed FastMCP 4 API explicitly exposes and requires that parameter. FastMCP 4 negotiates modern/sessionless and legacy eras through its supported server/client surface; use the documented API, not the old brief’s guessed constructor.
6. Preserve all 16 tool names, schemas, descriptions, annotations, handler behavior, and all 9 resource names/behaviors. No tool-count or annotation expansion is part of this dispatch.
7. Audit compatibility-sensitive code for the upgrade guide’s actual breaks: removed context methods, camelCase field access, raw SDK access, HTTP exception types, middleware lifecycle hooks, task APIs, and error construction. Change only code paths that exist here.
8. Keep the public endpoint’s legacy handshake path working while adding a verified modern/sessionless path. Do not assume modern clients use `initialize`; test the documented discovery/negotiation behavior and preserve legacy compatibility.
9. Keep output and generated-surface ordering deterministic.

## Acceptance tests

Run at minimum:

```bash
python3 -m pytest mcp/tests/ -q
python3 -m pytest scripts/tests/ -q
python3 scripts/gen_mcp_reference.py
jq '.tools | length' mcp.json
jq '[.tools[] | select(.annotations == null)] | length' mcp.json
git diff --check
```

Add focused tests as needed for:

- exact FastMCP `4.0.0b3` pin and resolved MCP SDK compatibility;
- modern protocol negotiation/discovery through the documented FastMCP client/server path;
- legacy client compatibility through the documented legacy mode;
- cache hints on the applicable static list response(s), with `ttlMs=300000` and `cacheScope="public"`;
- unchanged 16-tool count, tool names, schemas, and four annotation hints;
- unchanged resource count and representative resource reads;
- middleware and existing in-memory client behavior;
- deterministic `mcp.json` regeneration.

If a proposed FastMCP 4 API is not confirmed in the fetched official documentation or installed package, stop and report the incompatibility instead of guessing.

## Execution boundaries

- The designated Codex implementer must edit only the scoped files directly; do not call `codex-run`, `codex-run-bg`, `delegate_task`, or another agent recursively.
- Do not commit or push in this dispatch. Report changed files, tests, exact exit statuses, and remaining risks.
- Do not regenerate the full public release cascade.
- Do not run a production service restart.
