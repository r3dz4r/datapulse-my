"""Reproduce the publisher stall measured on 2026-11-04 (frozen since 2026-11-02).

Mechanism. ``publisher_post_publish`` in ``scripts/datapulse-pipeline.sh``
guards its detach-to-artifact step with ``HEAD == fetched_origin`` and dies with
"publisher post-push recovery refused: checkout moved unexpectedly" otherwise.
That assumes the checkout always sits exactly on origin/main when a pushed
observation is recovered. ``preflight`` breaks the assumption on purpose: while
``var/log/publication-in-flight.sha`` names a commit, a HEAD that is merely an
ancestor of origin/main returns early without the fast-forward, so the checkout
stays behind. Nothing moved the checkout; origin/main moved forward (release
and attestation merges #2991..#2998) after the publisher's last restore.

Measured on the host:

* ``/srv/datapulse-my`` HEAD on ``main`` = 4edbb02bc6 (release 3.60.1), the
  last reflog entry being the publisher's own restore at 2026-11-02 22:51:49
  +08; refs/remotes/origin/main = ca71bc61c1, 15 commits ahead, and HEAD is an
  ancestor of it.
* ``var/log/publication-in-flight.sha`` = 223b432d13 (chore(health)), which is
  not an ancestor of HEAD, so the guard is reached.
* ``health.err`` repeats "recovered pushed observation cycle=2026-11-02T03:45"
  then "checkout moved unexpectedly" 590 times. The same spool item is retried
  every activation and never retired, so no new artifact reaches the bot
  branch, and Health Automation Merge (run 41821839662) reports success with
  "No health commits to promote; branch tip was already merged."

Being behind origin/main is not movement. reconcile_after_publish already
fast-forwards such a checkout after the post-publish stages, so the guard should
refuse only a HEAD that is not on origin/main's history.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "scripts" / "datapulse-pipeline.sh"

# Builds a real repository and remote, parks HEAD as the measured host had it,
# then runs publisher_post_publish with the live-service stages stubbed (the
# same stubs as test_pipeline_checkout_restore.sh).
HARNESS = r"""
set -Eeuo pipefail
source "$PIPELINE"
fixture="$1"; scenario="$2"
origin="$fixture/origin.git"; repo="$fixture/repo"; run_dir="$fixture/run"
git init -q --bare --initial-branch=main "$origin"
git init -q --initial-branch=main "$repo"
git -C "$repo" config user.name 'Stall test'
git -C "$repo" config user.email stall@example.invalid
git -C "$repo" remote add origin "$origin"
mkdir -p "$repo/health" "$repo/observation-receipts"
printf 'initial\n' > "$repo/health/latest.json"
git -C "$repo" add .
git -C "$repo" commit -qm initial
git -C "$repo" push -q -u origin main
# The pushed observation (223b432d13 on the host): never an ancestor of HEAD.
git -C "$repo" checkout -qb artifact
printf 'published artifact\n' > "$repo/health/latest.json"
git -C "$repo" commit -qam "$COMMIT_MESSAGE"
artifact="$(git -C "$repo" rev-parse HEAD)"
git -C "$repo" checkout -q main
# origin/main advances elsewhere (the attestation and release merges).
git clone -q "$origin" "$fixture/other"
git -C "$fixture/other" -c user.name=o -c user.email=o@example.invalid \
  commit -q --allow-empty -m 'chore(attestations): refresh accepted projections'
git -C "$fixture/other" push -q origin main
git -C "$repo" fetch -q origin main
if [[ "$scenario" == moved ]]; then
  # A genuinely moved checkout: a local commit absent from origin/main.
  git -C "$repo" commit -q --allow-empty -m 'foreign local commit'
fi
fetched_origin="$(git -C "$repo" rev-parse refs/remotes/origin/main)"
parked="$(git -C "$repo" rev-parse HEAD)"
[[ "$parked" != "$fetched_origin" ]]
mkdir -p "$run_dir/.handoff"
printf '%s\n' "$artifact" > "$run_dir/.handoff/artifact-commit"
source_snapshot="$parked"; probe_finished_at=fixture; cycle=2026-11-02T03:45
stage() {
  [[ "$(git_repo rev-parse HEAD)" == "$artifact" ]] || die "stage ran on the wrong commit"
  printf 'stage:%s\n' "$1"
}
run_shadow_snapshot() { stage snapshot; }
clear_publish_deferral_state() { stage deferral; }
run_observation_signing() { stage signing; }
run_mcp_sync() { stage mcp; }
run_observation_capture() { stage capture; }
run_shadow_health_publication() { stage shadow; }
run_pipeline_receipt() { stage receipt; }
reconcile_after_publish() { stage reconcile; }
spool_control() { printf 'spool:%s\n' "$1"; }
publisher_post_publish
printf 'returned:%s@%s\n' "$(git_repo symbolic-ref --short -q HEAD)" \
  "$([[ "$(git_repo rev-parse HEAD)" == "$parked" ]] && echo parked || echo other)"
"""


def run_post_publish(tmp_path: Path, scenario: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PIPELINE": str(PIPELINE),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_ALLOW_PROTOCOL": "file",
        "DATAPULSE_FETCH_ATTEMPTS": "1",
        "DATAPULSE_FETCH_RETRY_BASE_SECONDS": "0",
    }
    return subprocess.run(
        ["bash", "-c", HARNESS, "bash", str(tmp_path), scenario],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_recovery_proceeds_when_origin_main_advanced_past_the_parked_checkout(
    tmp_path: Path,
) -> None:
    result = run_post_publish(tmp_path, "behind")
    output = result.stdout + result.stderr
    assert "checkout moved unexpectedly" not in output, output
    assert result.returncode == 0, output
    stages = [line.removeprefix("stage:") for line in result.stdout.splitlines() if line.startswith("stage:")]
    assert stages == ["snapshot", "deferral", "signing", "mcp", "capture", "shadow", "receipt", "reconcile"]
    # The spool item is retired, so the next activation can publish a new cycle.
    assert "spool:retire" in result.stdout, output
    assert "returned:main@parked" in result.stdout, output


def test_recovery_still_refuses_a_checkout_that_left_origin_main_history(
    tmp_path: Path,
) -> None:
    result = run_post_publish(tmp_path, "moved")
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "publisher post-push recovery refused: checkout moved unexpectedly" in output
    assert "stage:" not in result.stdout, output
