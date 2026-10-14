#!/usr/bin/env bash
# Prove the suite's imports resolve to the tree under test, not to the checkout
# that happened to host the run.
#
# Measured failure: pytest leaves the invocation's working directory at the
# front of sys.path, so `import scripts...` / `import mcp...` resolved from the
# checkout that hosted the run rather than from the checkout whose files were
# under test. Two revisions then shared one verdict, and a worker inside a
# linked worktree could not trust a red or a green produced by the suite.
#
# Each test directory's conftest.py pins the tree under test at the front of
# sys.path. This test exercises that pin through a real linked worktree and a
# foreign hosting checkout, and refuses if the pin is missing or ineffective.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
scripts_conftest="$repo_root/scripts/tests/conftest.py"
mcp_conftest="$repo_root/mcp/tests/conftest.py"

for conftest in "$scripts_conftest" "$mcp_conftest"; do
  if [[ ! -f "$conftest" ]]; then
    printf 'missing %s: the suite cannot pin imports to the tree under test\n' "$conftest" >&2
    exit 1
  fi
done

# The repository's own interpreter lives in the main worktree's .venv; a linked
# worktree does not carry one. Prefer it (and any explicit override) over a bare
# python3, which may lack pytest.
main_worktree="$(git -C "$repo_root" worktree list --porcelain | awk '/^worktree /{print substr($0, 10); exit}')"

select_python() {
  local candidate
  for candidate in \
    "${DATAPULSE_PYTEST_PYTHON:-}" \
    "${PYTEST_PYTHON:-}" \
    "$main_worktree/.venv/bin/python3" \
    "$repo_root/.venv/bin/python3" \
    "$(command -v python3 2>/dev/null || true)"; do
    if [[ -n "$candidate" && -x "$candidate" ]] && "$candidate" -c 'import pytest' >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if ! python_bin="$(select_python)"; then
  printf 'no interpreter with pytest found; set DATAPULSE_PYTEST_PYTHON\n' >&2
  exit 1
fi
printf 'interpreter: %s\n' "$python_bin"

workdir="$(mktemp -d "${TMPDIR:-/tmp}/dp-linked-worktree.XXXXXX")"
trap 'rm -rf "$workdir"' EXIT

origin="$workdir/origin"
linked="$workdir/linked"
mkdir -p "$origin/scripts/tests"

# A minimal git repository with the same import shape as the suite: a top-level
# namespace package imported from a test module under scripts/tests/.
cat > "$origin/scripts/sentinel.py" <<'PY'
"""Revision marker shipped by the checkout that hosted the run."""
MARKER = "hosting-tree"
PY

cat > "$origin/scripts/tests/test_resolution_probe.py" <<'PY'
from scripts.sentinel import MARKER


def test_import_resolves_to_the_tree_under_test() -> None:
    assert MARKER == "tree-under-test", MARKER
PY

git -C "$origin" init -q
git -C "$origin" add -A
git -C "$origin" -c user.name='linked-worktree test' -c user.email='test@example.invalid' \
  -c commit.gpgsign=false commit -qm 'seed resolution fixture'
git -C "$origin" worktree add -q --detach "$linked" HEAD

# The linked worktree is the tree under test. A linked worktree carries a .git
# file rather than a directory; assert that shape so the scenario is real.
[[ -f "$linked/.git" ]] || {
  printf 'fixture did not produce a linked worktree: %s/.git is not a file\n' "$linked" >&2
  exit 1
}

# The tree under test carries the repository's own test-directory conftest.py
# and its own revision of the imported module.
cp "$scripts_conftest" "$linked/scripts/tests/conftest.py"
cat > "$linked/scripts/sentinel.py" <<'PY'
"""Revision marker shipped only by the tree under test."""
MARKER = "tree-under-test"
PY

probe="$linked/scripts/tests/test_resolution_probe.py"

run_probe() {
  (cd "$origin" && "$python_bin" -m pytest -q -p no:cacheprovider "$probe")
}

# Positive: hosted from the origin, the linked worktree's module must win.
if ! run_probe >"$workdir/positive.log" 2>&1; then
  cat "$workdir/positive.log" >&2
  printf 'linked-worktree import did not resolve to the tree under test\n' >&2
  exit 1
fi
printf 'linked-worktree import resolves to the tree under test: PASS\n'

# Negative control: without the pin, the same run must import the wrong tree.
# This proves the probe detects the failure it claims to guard against.
rm "$linked/scripts/tests/conftest.py"
if run_probe >"$workdir/negative.log" 2>&1; then
  cat "$workdir/negative.log" >&2
  printf 'probe passed without the conftest pin; it cannot detect the failure\n' >&2
  exit 1
fi
printf 'without the pin the foreign tree is imported: PASS\n'

# The repository's own suite must also resolve against the real tree when the
# run is hosted from a foreign checkout, in both test directories.
for real_test in \
  "$repo_root/scripts/tests/test_classify_change.py" \
  "$repo_root/mcp/tests/test_mcp_source_stamp.py"; do
  if ! (cd "$origin" && "$python_bin" -m pytest -q -p no:cacheprovider "$real_test") \
      >"$workdir/real.log" 2>&1; then
    cat "$workdir/real.log" >&2
    printf 'suite did not resolve its imports from the tree under test: %s\n' "$real_test" >&2
    exit 1
  fi
done
printf 'repository suite resolves from the tree under test: PASS\n'
