# DataPulse MY MCP server

This directory contains a read-only FastMCP server over DataPulse MY's published
`datapulse.json` manifest and `health/latest.json` health snapshot. It does not
write to the DataPulse MY data layer.

## Run locally

Python 3.11 or newer and `uv` are recommended:

```bash
uv run --with fastmcp,httpx python mcp/server.py
```

The Streamable HTTP endpoint starts at `http://127.0.0.1:8788/mcp` by default.
Copy the values from `.env.example` into your environment to override the data
base URL, host, or port.

## Test

The integration tests use FastMCP's in-memory client while fetching the live
published DataPulse MY JSON documents:

```bash
uv run --with fastmcp,httpx pytest mcp/tests/ -v
```

This directory is the server implementation only. Deployment and public
endpoint verification are separate work.
