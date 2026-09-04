FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: only what cryptography and its transitive dependencies need.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for layer cache.
COPY mcp/requirements.txt /app/mcp/requirements.txt
RUN pip install --upgrade pip \
 && pip install -r /app/mcp/requirements.txt

# Copy only the files required by the server at runtime.
COPY mcp/ /app/mcp/
COPY scripts/ /app/scripts/
COPY datapulse.json datapulse.schema.json mcp.schema.json /app/

# Glama probes on $MCP_PORT (default 8788).
ENV MCP_HOST=127.0.0.1 \
    MCP_PORT=8788 \
    DATA_BASE=https://www.data-pulse.my \
    PYTHONPATH=/app

EXPOSE 8788

# The initialize request is the canonical liveness signal for the HTTP server.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS -X POST "http://127.0.0.1:${MCP_PORT}/" \
       -H "Accept: application/json, text/event-stream" \
       -H "Content-Type: application/json" \
       --max-time 4 \
       --data-raw "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-06-18\",\"capabilities\":{},\"clientInfo\":{\"name\":\"healthcheck\",\"version\":\"1.0\"}}}" \
       | grep -q serverInfo || exit 1

CMD ["python", "-c", "import runpy; s=runpy.run_path('/app/mcp/server.py', run_name='datapulse_server'); s['mcp'].run(transport='http', host=s['MCP_HOST'], port=s['MCP_PORT'], path='/', json_response=True, stateless_http=True)"]
