#!/usr/bin/env bash
# Run the repository test suite in the same pinned dependency set on every machine.
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="$REPO_ROOT/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
MARKER="$VENV_DIR/.datapulse-requirements.sha256"

requirements_hash() {
  "$VENV_PYTHON" - "$REPO_ROOT/requirements.txt" \
    "$REPO_ROOT/mcp/requirements.txt" "$REPO_ROOT/requirements-dev.txt" <<'PY'
import hashlib
import pathlib
import sys

digest = hashlib.sha256()
for filename in sys.argv[1:]:
    path = pathlib.Path(filename)
    digest.update(path.name.encode())
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")
print(digest.hexdigest())
PY
}

venv_is_python_312() {
  test -x "$VENV_PYTHON" && "$VENV_PYTHON" -c \
    'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))'
}

create_venv() {
  if command -v uv >/dev/null 2>&1; then
    uv venv --python python3.12 "$VENV_DIR"
  else
    if ! command -v python3.12 >/dev/null 2>&1; then
      echo "error: Python 3.12 is required (install python3.12 or uv)" >&2
      exit 1
    fi
    python3.12 -m venv "$VENV_DIR"
  fi
}

if test -e "$VENV_DIR" && ! venv_is_python_312; then
  echo "Recreating $VENV_DIR because it is not a Python 3.12 virtual environment."
  rm -rf "$VENV_DIR"
fi

if ! test -x "$VENV_PYTHON"; then
  create_venv
fi

EXPECTED_HASH=$(requirements_hash)
INSTALLED_HASH=$(test -f "$MARKER" && tr -d '\r\n' < "$MARKER" || true)

if test "$EXPECTED_HASH" != "$INSTALLED_HASH"; then
  echo "Installing test dependencies."
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$VENV_PYTHON" --prerelease=allow \
      -r "$REPO_ROOT/requirements.txt" \
      -r "$REPO_ROOT/mcp/requirements.txt" \
      -r "$REPO_ROOT/requirements-dev.txt"
  else
    "$VENV_PYTHON" -m pip install --pre \
      -r "$REPO_ROOT/requirements.txt" \
      -r "$REPO_ROOT/mcp/requirements.txt" \
      -r "$REPO_ROOT/requirements-dev.txt"
  fi
  printf '%s\n' "$EXPECTED_HASH" > "$MARKER"
fi

cd "$REPO_ROOT"
printf 'Python: '
"$VENV_PYTHON" --version
printf 'fastmcp: '
"$VENV_PYTHON" -c 'import fastmcp; print(fastmcp.__version__)'

if test "$#" -eq 0; then
  set -- scripts/tests/ mcp/tests/
fi

exec "$VENV_PYTHON" -m pytest -q "$@"
