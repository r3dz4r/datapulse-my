Workdir: /home/redza/datapulse-my
Goal: Unblock the post-deploy and CI release-invariant checks for the FastMCP 4 migration by making the runtime MCP annotation comparison use the same wire-format aliases as generated `mcp.json`.
Failure mode: The FastMCP 4 server and generated MCP advertisement are correct, but `verify_release_invariants.sh` rejects the deployment because runtime `ToolAnnotations.model_dump()` returns snake_case while `mcp.json` carries camelCase wire keys. The Pages deploy is uploaded but fails its final invariant gate.
Acceptance test: The invariant comparison serializes annotations with `by_alias=True` and remains compatible with the current FastMCP 3/4 transition; a focused regression test or deterministic fixture check proves runtime and advertised tool records compare equal; `git diff --check` passes; the relevant scripts/MCP tests pass; no commit or push occurs in this dispatch.
Recommended execution model: luna

# Scoped fix

## Verified root cause

FastMCP 4 migration commit `3347a660` correctly changed `scripts/gen_mcp_reference.py` to serialize tool annotations with:

```python
model_dump(by_alias=True, exclude_none=True)
```

However, `scripts/verify_release_invariants.sh` still constructs its expected runtime tool records with:

```python
tool.annotations.model_dump(exclude_none=True)
```

The post-deploy failure is the assertion `advertised_tools == expected_tools` in the inline Python verifier. This is a serialization-alias mismatch, not a server or generated-surface mismatch.

## In scope

- `scripts/verify_release_invariants.sh`
- A narrowly scoped test/fixture under `scripts/tests/` if needed to prevent regression

Do not change:

- `mcp/server.py`
- FastMCP version pins
- `mcp.json` by hand
- deployment workflow behavior
- health/trust-layer code
- public data or generated health artifacts
- credentials, services, or infrastructure

## Required change

Update only the runtime-side annotation serialization in the invariant comparison to use the Pydantic wire aliases, matching `scripts/gen_mcp_reference.py`:

```python
tool.annotations.model_dump(by_alias=True, exclude_none=True)
```

Inspect the surrounding code first. If FastMCP 3/4 compatibility requires a narrowly bounded fallback, use the smallest documented compatibility helper and test both shapes; do not add a broad abstraction.

## Verification

Run:

```bash
bash -n scripts/verify_release_invariants.sh
python3 -m pytest scripts/tests/ -q
python3 -m pytest mcp/tests/ -q
python3 -m pytest scripts/tests/test_workflow_rewire.py -q
python3 -m py_compile scripts/gen_mcp_reference.py
python3 scripts/gen_mcp_reference.py
jq '.tools | length' mcp.json
jq '[.tools[] | select(.annotations == null)] | length' mcp.json
git diff --check
```

The full release reproducibility check remains allowed to report the known unreadable VPS certificate blocker; do not widen this dispatch to solve it. Do not commit or push. Report changed files, exact test outcomes, and `Pushed: NO`.
