#!/usr/bin/env bash
# Compatibility entry point; README ownership lives exclusively in gen_readme.py.
set -euo pipefail

exec python3 "$(dirname "$0")/gen_readme.py"
