#!/usr/bin/env bash
# audit_mcpgrade.sh — pinned, documented replay of the mcpgrade score
# asserted by the README badge. Writes artifacts/mcpgrade/*.json.
#
# Usage:
#   bash scripts/audit_mcpgrade.sh [ENDPOINT]
#   MCPGRADE_VERSION=0.5.0 bash scripts/audit_mcpgrade.sh
#
# Exit codes:
#   0 — parsed successfully, summary printed
#   1 — mcpgrade execution failed
#   3 — could not parse output (UNKNOWN)

set -euo pipefail

MCPGRADE_VERSION="${MCPGRADE_VERSION:-0.4.0}"
ENDPOINT="${1:-https://mcp.data-pulse.my/mcp}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${REPO_ROOT}/artifacts/mcpgrade"
mkdir -p "${ARTIFACT_DIR}"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_FILE="${ARTIFACT_DIR}/mcpgrade-${TIMESTAMP}.json"
LATEST_FILE="${ARTIFACT_DIR}/latest.json"

# ---------------------------------------------------------------------------
# Run mcpgrade via npx (pinned version, no repo dep install)
# ---------------------------------------------------------------------------
echo "Running mcpgrade@${MCPGRADE_VERSION} against ${ENDPOINT} ..."
if ! npx --yes "mcpgrade@${MCPGRADE_VERSION}" --json "${ENDPOINT}" > "${OUTPUT_FILE}" 2>/dev/null; then
  echo "FAIL: mcpgrade@${MCPGRADE_VERSION} exited non-zero against ${ENDPOINT}" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Parse the JSON output — try jq first, fall back to python3
# ---------------------------------------------------------------------------
parse_json() {
  local file="$1"
  if command -v jq >/dev/null 2>&1; then
    jq -r '{grade: .grade, total_score: .totalScore, tools: .snapshot.toolCount}' "$file"
  else
    python3 -c "
import json, sys
with open('${file}') as f:
    d = json.load(f)
print(json.dumps({
    'grade': d.get('grade'),
    'total_score': d.get('totalScore'),
    'tools': d.get('snapshot', {}).get('toolCount')
}))
"
  fi
}

PARSED="$(parse_json "${OUTPUT_FILE}")"

# Extract fields
if command -v jq >/dev/null 2>&1; then
  GRADE="$(echo "${PARSED}" | jq -r '.grade')"
  TOTAL_SCORE="$(echo "${PARSED}" | jq -r '.total_score')"
  TOOLS="$(echo "${PARSED}" | jq -r '.tools')"
else
  GRADE="$(echo "${PARSED}" | python3 -c "import json,sys; print(json.load(sys.stdin)['grade'])")"
  TOTAL_SCORE="$(echo "${PARSED}" | python3 -c "import json,sys; print(json.load(sys.stdin)['total_score'])")"
  TOOLS="$(echo "${PARSED}" | python3 -c "import json,sys; print(json.load(sys.stdin)['tools'])")"
fi

# ---------------------------------------------------------------------------
# Validate parsed fields
# ---------------------------------------------------------------------------
if [[ "${GRADE}" == "null" || "${TOTAL_SCORE}" == "null" || "${TOOLS}" == "null" || -z "${GRADE}" || -z "${TOTAL_SCORE}" || -z "${TOOLS}" ]]; then
  echo "UNKNOWN: could not parse mcpgrade output — inspect ${OUTPUT_FILE}" >&2
  exit 3
fi

# ---------------------------------------------------------------------------
# Write stable latest.json copy
# ---------------------------------------------------------------------------
cp "${OUTPUT_FILE}" "${LATEST_FILE}"

# ---------------------------------------------------------------------------
# Summary line
# ---------------------------------------------------------------------------
echo "OK: mcpgrade grade=${GRADE} score=${TOTAL_SCORE} tools=${TOOLS} version=${MCPGRADE_VERSION} endpoint=${ENDPOINT}"
exit 0
