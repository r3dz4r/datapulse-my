Workdir: /home/redza/datapulse-my
Goal: Make the rollback-safe MCP deployment sync verifier compatible with the newly deployed FastMCP 4.0.0b3 service so a valid source update is not rolled back because FastMCP 4 omits the custom `serverInfo.source_commit_sha` field from the legacy initialize result.
Failure mode: The production venv is correctly upgraded to FastMCP 4.0.0b3, but every source sync rolls back after restart with `live source SHA mismatch: live=<missing>`, leaving the public MCP endpoint on the old v3.4.7 source.
Acceptance test: The sync verifier validates the deployed FastMCP 4 source using a documented stable identity/version surface while retaining strict mismatch detection and rollback; focused shell/sync tests pass; `bash -n scripts/sync_mcp_deployment.sh` and `git diff --check` pass; no commit or push occurs in this dispatch.
Recommended execution model: luna

Implementation authority: You are the designated Codex implementer for this dispatch. The repository-level rule requiring Hermes to dispatch Codex has already been fulfilled; it does not prohibit you from editing the explicitly scoped file/test paths below. Edit the scoped files directly. Do not call `codex-run`, `codex-run-bg`, `delegate_task`, or any other agent recursively.

# FastMCP 4 MCP-sync verifier fix

## Verified incident

`sync_mcp_deployment.sh` copies the new source, restarts `datapulse-mcp.service`, then sends a legacy `initialize` request and asserts:

```jq
.result.serverInfo.source_commit_sha == $expected_source_sha
```

Under FastMCP 4.0.0b3 the service starts successfully, but the legacy initialize result omits the custom `source_commit_sha` field even though the server version includes the source marker suffix (`v4.0.0b3+<sha-prefix>`). The sync script therefore rolls back a valid deployment.

## In scope

- `scripts/sync_mcp_deployment.sh`
- Existing sync-related tests, or a narrowly scoped new test under `scripts/tests/`, if needed

Do not change:

- `mcp/server.py`
- FastMCP or MCP dependency pins
- deployment workflows
- systemd units
- health/trust-layer code
- public artifacts
- credentials

## Required behavior

1. Preserve the existing backup → copy → restart → local endpoint verification → rollback-on-failure flow.
2. Support the deployed FastMCP 4.0.0b3 runtime where custom source identity is represented by the server version string rather than `serverInfo.source_commit_sha` in the legacy initialize result.
3. Keep strict identity verification: accept only when the live response proves the expected FastMCP version and source marker, or use the documented modern discovery response if that is the authoritative surface. Do not fall back to “HTTP 200 means healthy.”
4. Preserve compatibility with the previous FastMCP 3 response shape if the verifier is intended to support rollback or mixed-era recovery.
5. Make the failure message identify which identity surface was checked and what was observed.
6. Avoid adding arbitrary retries beyond the existing bounded restart probe.

## Verification

Run at minimum:

```bash
bash -n scripts/sync_mcp_deployment.sh
python3 -m pytest scripts/tests/ -q
python3 -m pytest mcp/tests/ -q
python3 -m pytest scripts/tests/test_workflow_rewire.py -q
git diff --check
```

Use deterministic local fixtures or a local endpoint test to cover:

- FastMCP 4 legacy initialize with version suffix but no custom source field;
- previous FastMCP 3 response with explicit `source_commit_sha`;
- mismatched version/source marker causing rollback/failure;
- malformed response causing failure.

Do not commit, push, restart the production service, or invoke the sync script in this Codex dispatch. Report changed files and exact test results; `Pushed: NO`.
