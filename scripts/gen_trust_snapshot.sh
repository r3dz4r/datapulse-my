#!/usr/bin/env bash
set -euo pipefail

repo_root="${DATAPULSE_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DATAPULSE_REPO_ROOT="$repo_root" python3 "$repo_root/scripts/gen_trust_snapshot.py"
