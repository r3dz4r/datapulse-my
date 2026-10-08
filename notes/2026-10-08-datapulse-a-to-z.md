# DataPulse MY — A to Z

Operational reference for the whole product, not one lane. Compiled 2026-10-08 from eight
parallel read-only sweeps of the repo, the production tree, the units and git history. Every
claim carries its evidence; anything reasoned rather than read is marked INFERRED. Where a
sweep found the repo contradicting itself, that is recorded as a discrepancy rather than
smoothed over.

Source sweeps: `/home/redza/.hermes/cache/delegation/live/deleg_dabfbb2d/task-{0..7}.log`
(anatomy · pipeline · gates · MCP · release/deploy · history · managed artifacts · operate).

---

## 1. What it is, and the canon

Open-source trust layer for Malaysian public data: **425 datasets** probed continuously and
classified into a **10-status taxonomy**, published at `https://www.data-pulse.my`, with a
read-only MCP server at `https://mcp.data-pulse.my`. Repo `r3dz4r/datapulse-my`, 15,112
tracked files, MCP advertises **19 tools** (`jq '.tools | length' mcp.json`).

**Always derive counts, never quote them.** `jq '._trust_summary.datasets_total' health/latest.json`
→ 425; `jq '.tools | length' mcp.json` → 19. Hardcoded copies have already drifted and been fixed
more than once (`d48f3cbfa0` "15 → 16"; PR#585 "drop the stale 418-dataset claims").

## 2. Trees — who executes, who is edited

| Tree | Owner | Role |
|---|---|---|
| `/srv/datapulse-my` | `datapulse-observer` | **Executes.** Unit `WorkingDirectory=` and `DATAPULSE_REPO=`. The only tree the publisher pushes from. |
| `/home/redza/datapulse-dev` | `redza` | **Edited.** Never executes. `/home/redza/datapulse-my` is a symlink to it. |
| `~/.worktrees/wt-*` | `redza` | Attached to the dev clone. Scratch only; inert until landed. |

Prod pushes via the `github-observer` deploy-key alias; fetches over HTTPS.
**Trap:** `docs/operations.md` and `docs/troubleshooting.md` still describe the service as
running as `redza:redza` with cwd `/home/redza/datapulse-my`. The live unit runs as
`datapulse-observer`, cwd `/srv/datapulse-my`, logging to `/var/lib/datapulse-observer/health.err`.
**Trust the unit, not the doc.**

## 3. The pipeline

The orchestrator is **not in this repo**. It is `dotfiles/scripts/datapulse-pipeline.sh`,
installed root-owned at `/usr/local/sbin/datapulse-pipeline.sh` as a **copy, not a symlink**
(these run as root; the dotfiles checkout is redza-writable). Generators are read from a
frozen `origin/main` snapshot — `git_repo archive "$snapshot" | tar -x -C "$run_dir"`
(`datapulse-pipeline.sh:1757`) — never the working tree.

Stages (`run_pipeline()` `:1744-2050`): preflight → snapshot → probe (`check.sh --due`) →
validate → history → evidence (trends/drift/reconciliation) → deltas + 8 sub-rows → attestation-score
→ passports → dataset pages → okf (daily) → **kv-index** → publish gate → stage → swap → commit →
push `health-automation` → observation signing (failures only) → **mcp-sync** → observation capture
→ shadow health → pipeline receipt → reconcile.

Driven by **systemd, not cron**: `datapulse-health.timer` (`OnCalendar=*:0/5`, `Persistent=true`)
→ `datapulse-health.service` (`Type=oneshot`, `User=datapulse-observer`,
`SupplementaryGroups=datapulse-signer`, `TimeoutStartSec=25min` via drop-in), `ExecStartPre=… --preflight`,
`ExecStart=… flock -n 9 … --run`. Stdout goes to `append:/var/lib/datapulse-observer/health.err`,
**not the journal**. `crontab -l` → no crontab for redza.

Scheduled work that *is* GitHub Actions: `datapulse-attest-daily` (03:17 UTC), `pipeline-freshness`
(hourly), `provenance-drift` (hourly :17), `main-consistency-audit` (:23), `openwiki-update` (Mon 08:00),
`pipeline-audit` (Sun 00:00).

Publish is **not** to main: `git push --force-with-lease origin HEAD:health-automation` (`:415`), then
`health-automation-merge.yml` opens and auto-merges the `health-automation → main` PR. Until it merges,
main is frozen by design.

## 4. The signed lane (append), end to end

1. **Candidate built privately** — `datapulse-attest-daily.yml:44-47` runs `refresh_chain_head.sh`,
   which refuses if the head's `dataset_count` disagrees with the binding's observed count.
2. **Rekor witness** — pinned cosign v3.1.3 → `attestations/rekor/<day>/reference.<digest>.json`;
   `bind_candidate_witness.py` sets `claims.rekor_witnessed=true` and re-signs.
3. **Submit** — `submit_attestation_append.sh` in order: verify against HEAD (`:5`) → refuse unless
   witnessed (`:6-11`, override `DATAPULSE_ALLOW_UNWITNESSED_PUBLICATION=1`) → discard unless the
   candidate descends from `origin/main` (`:12-16`) → **create branch `attestation/append-<current_head>`**
   (`:19`, `:22`) → stage only immutable evidence (`:26-29`) → exit 0 if nothing new (`:30`) → commit →
   merge (never rebase) if main moved (`:34-39`) → re-resolve the day after alignment (`:40-48`) →
   `promote()` rebuilds projections (`:49-60`) → stage projections **after** the refresh (`:64-67`) →
   force-push the branch (`:68-71`) → open the PR (`:72-74`).
4. **Accepted when** the required check `deterministic-safety-net` passes its step
   `Verify immutable attestation append against accepted base` (`ci.yml:136-140`, `--base ${{ github.event.pull_request.base.sha }}`).

**A red deploy run is the normal state of the lane.** `deploy-cloudflare-pages.yml:226-236` submits the
candidate and then **`exit 1` by design** while the append is unmerged — contractual, pinned by
`verify_attestation_workflow_contract.py:142-143`. **Read the candidate's required check, never the
deploy run's conclusion.**

**The 2026-10-06 → 10-08 stall (37 hours):** five candidates failed with `legacy mirror disagrees with
current head` while the verifier passed whenever run alone. Cause: `_shadow_checkout()` in
`scripts/tests/test_release_invariant_retry.py:76` omitted `.attestations` from its mutable copies and
**symlinked** it, so the test suite — which CI runs *before* the verifier — overwrote the checkout's
`.attestations/chain_head.json` with a 62,424-byte test document. Second cause, compounding: the mirror
clause's guard read `document["schema"]` (which `discovery()` **upgrades v1→v2 in memory**) instead of
the committed file's schema. Fixes: guard reads the file (`#809`), `.attestations` copied not symlinked
(`#812`), append merged (`#811`). Full chapter in `notes/2026-10-08-datapulse-attestation-lane.md`.

## 5. Gates — what can refuse a change

**Required check:** exactly one, `deterministic-safety-net` (the job **id**; there is no `name:` —
do not rename it without updating ruleset `20884049`). Ruleset on `refs/heads/main`: deletion blocked,
non-fast-forward blocked, `required_status_checks: [deterministic-safety-net]`, `bypass_actors: []`
(current user **cannot** bypass), `required_approving_review_count: 0`. Classic protection: none (404).
The job is gated `pull_request || workflow_dispatch` (`ci.yml:41`) — **it is skipped on push**, so only
a PR (or dispatch) can turn it green.

**22 steps in `ci.yml`**, all required (no `continue-on-error` anywhere; `:57-61` explicitly warns against
adding one): checkout `fetch-depth: 0` → checkout **dotfiles** via `CROSS_REPO_TOKEN` → Python 3.11 →
Pandoc 3.1.3 → `requirements-dev.txt` → `bash -n` all shell → jsonschema on manifest+health → release-proof
format → `gen_readme.py` → `pytest -q scripts/tests/ mcp/tests/` → agent-ready → repository contract →
attestation workflow contract → public internal refs → distribution sync → release identity → chain
linearity → OpenWiki → URL drift → release invariants → `fact_lint` → `verify_documentation --report-only`
(**the only step that cannot refuse**).

**Test suite:** `scripts/tests/` (168 files) + `mcp/tests/` (13). **No coverage floor of any kind** —
no `pyproject.toml`/`pytest.ini`/`--cov`/`fail-under`. `sg/tests/` exists but **no workflow runs it**.

**No local gate protects DataPulse.** `core.hooksPath` unset; the `pre-push` hook is an *enumeration*
guard scoped to `r3dz4r/dotfiles` only and prints
`publish-set rule does not apply here, allowing push` for datapulse-my. There is no pre-commit and no
commit-msg hook. All refusals originate in Actions + the ruleset.

**Refusals worth recognising:**
`Repository contract verification failed (N invariant(s)):` · `Public internal-reference verification failed`
· `Failures (N):` · `ChainLinearityError` · `Invalid probe policy: <path>` ·
`Required status check "deterministic-safety-net" is expected` · `Cannot force-push to a protected branch`.

## 6. Managed artifacts and cross-repo wiring

In `dotfiles/scripts/datapulse-pipeline.sh`:

```
:57  ARTIFACT_PATHS=(health badges feed.xml changelog.json catalog-snapshot.json catalog-graph.json
                     datapulse_summary.json README.md record-evidence deltas data/passports
                     docs/okf docs/datasets observation-receipts)
:58  MANAGED_ARTIFACT_PATHS=("${ARTIFACT_PATHS[@]}" "$ATTESTATION_SCORE_PATH")   # + attestations/latest/scores.json
:222 path_is_pipeline_managed()   # deliberately BROADER: accepts docs/* , not just docs/okf + docs/datasets
:234 assert_managed_commits()     # every local commit above base must be pipeline-managed
```

`assert_managed_commits` fails the run with
`control-plane degraded: local-only commit is not pipeline-managed: <sha> (<subject>)`, accepting only
three subjects: `chore(health): update due dataset health`, `chore(health): heartbeat <ts>`,
`chore(observation): sign observation <ts>`.

**The three lists are deliberately not equal, and the code says why** (`:222-225`): the commit validator
and the recovery's discard decision read one predicate so they cannot drift. But `:264-281` records the
cost of the narrow list: *"a pipeline-managed path outside that list … passes the guard and still wedges
the reset. That is the 2026-10-05 lock … the same reset refused on 210 consecutive cycles."* Fix:
`clear_managed_reset_obstructions()` (`:282-310`) uses the broad predicate.

**Cross-repo:** canonical scripts are installed as **root-owned copies** (not symlinks) precisely because
they run as root while the dotfiles checkout is redza-writable; auxiliary scripts *are* symlinks into
dotfiles. `hermes/config.yaml:405` registers the MCP endpoint; `opencode/run.sh` and the codex wrappers
refuse dispatch unless `/srv/datapulse-my` is on `main` and not diverged.

## 7. Known bugs, recurring classes, fixes that failed

**Datable incidents** (each with its fix): fuelprice schema T32 (`d075009`) · 155/335 datasets reported
`unknown-freshness` because manifest additions landed without matching `probe-policy` entries (`7563634`)
· stale `.git/rebase-merge` made every 15-min tick exit 128 while the timer read `active (waiting)`
(`56af356`) · Pages deploy raced the health timer (`f80d690345`) · **a withdrawn paid price survived on a
generated OpenWiki page for three weeks and passed every gate** (`0a71375c6d`, `c93a7c63f2`) · release PR
blocked 5 days because release-please ran as `GITHUB_TOKEN` (`d292a32ac9`) · `passports` stage in the
emitter but not the summariser → every run receipt failed from cycle 2026-09-10T06:30 while the unit
exited 0 (`bb01f54580`) · `browser-dependent` evaluated before freshness, mis-rating 4 datasets
(`69d156e01b`) · README gate *regenerated before asserting*, normalising the mismatch it existed to catch
(`87fc01e808`).

**Recurring classes:** manifest≠policy drift · **HTTP 200 ≠ fresh** (`notes/failure-corpus/`) ·
generated-vs-hand-authored drift and stale hardcoded counts · duplicate allowlists that must move together
(telemetry `STAGES`; MCP annotations) · races against a churning `main` · attestation ref/directory
resolution · silent non-fatal failures (telemetry receipts, kv-index, OpenWiki 429).

**Fixes that did not resolve the problem:** the eight-correction attestation chain `#783→#792→#795→#799→#802→#805→#809→#812`,
where `9afd60fd91`'s own body states *"this commit does not claim to resolve the reported CI-state mismatch"*;
a self-labelled "PROBE" release credential (`f702381f06`, reverted by `0d7b975534`); same-day correction
(`30837b3663`, "Known gap … still fails the fast path"); the DOSM re-land where a clean re-merge silently
dropped 6 hand-authored and 15 deleted files, with failures *misattributed to the absent signing key*.

## 8. Quirks and traps

- **`[skip deploy]` is a convention, not a gate.** Deploy mode comes from `classify_change.py` classifying
  **paths**; no workflow reads the trailer (`AGENTS.md:124`, `docs/release-process.md:48`).
- **`classify_change.py` fails open to the full release:** any unrecognised path forces `release-build`
  ("Unknown paths deliberately select the source/release profile", `:5-7`). Measured: `health/latest.json`
  + `observation-receipts/chain_head.json` → **full release**, not health-only.
- **Deploy `paths:` allowlist excludes `health/**` and `badges/**`** — such a commit never triggers a deploy.
- **Two attestation directories:** `attestations/` (11,022 files, the real chain) vs `.attestations/`
  (2 files: `AGENTS.md` + the `chain_head.json` mirror).
- **`changelog.json` is a byte-identical alias** of `catalog-snapshot.json`; `gen_changelog.py` is a
  deprecated shim.
- **`discovery()` upgrades a v1 chain index to v2 in memory.** Any guard written against `document["schema"]`
  behaves differently from one written against the file — this class cost a day.
- **`health/history.jsonl` is gitignored but is a serving input** for deltas/trends/drift/as_of, so a clean
  clone cannot regenerate them.
- **`catalog-graph.json` lives at repo root**, though `scripts/AGENTS.md:49` documents it as `data/catalog-graph.json`.
- **`gen_anomaly.py` is a stdin→stdout filter**, not the file writer `scripts/AGENTS.md:47` claims.
- **Positional release-proof checks** (`verify_served_release.sh:243`, `verify_release_invariants.sh:329`)
  fail from any non-deployed commit.
- **MCP:** `grep -c '@mcp.tool'` returns 6 but there are 19 tools — 13 are registered via
  `FunctionTool.from_function` + `mcp.add_tool`. Every tool's four read-only hints are enforced at
  generation, at deploy, and by tests.

## 9. Operate and diagnose

```bash
# reproduce CI locally
PATH="$HOME/.venvs/datapulse-dev/bin:$PATH" TMPDIR=/tmp \
  ~/.venvs/datapulse-dev/bin/python -m pytest -q scripts/tests/ mcp/tests/ -p no:randomly
```

Interpreter must be 3.11 (matches CI); venv `bin` **first** on PATH (24 modules spawn bare `python3`);
`TMPDIR=/tmp` keeps churn out of the 24h-pruned Hermes scratch dir. Production is different again:
`/opt/datapulse/venv/bin/python`.

**Read a candidate honestly** — `gh pr checks <n>` shows `pass | fail | skipping` per run; a skipped
required check is **not** a pass. Then, if it failed:
`gh run view <run-id> --log-failed > /tmp/dl.txt` (the job-logs API returned empty) and grep for
`env:`, `##ERROR`, `ACCEPTED_BASE`, `legacy mirror`, `mirror=`, `expected=`.

**Triage "not publishing", in order:** (1) KV projection `checked_at` fresh? → if stale, the data layer;
(2) `systemctl show datapulse-health.service -p Result` — system scope, `--user` returns nothing;
(3) `git log --oneline -3 origin/health-automation` in `/srv/datapulse-my`, and tail
`/var/lib/datapulse-observer/health.err`; (4) if the data plane is green but the site is frozen, read the
**newest** deploy run regardless of status — never `--status success`. **One-line discriminator:** KV fresh
+ site frozen ⇒ signed/deploy lane; KV frozen too ⇒ data layer.

**Recovery order is load-bearing:** append path → daily lane → merge its append PR → then ordinary PRs.
Never force a re-sign across the immutable chain. Always-ask: stopping timer/services, rotating
credentials, touching ruleset `20884049` or trust roots, deleting evidence.

## 10. Discrepancies the sweeps found (unfixed, flagged not buried)

1. `docs/mcp-deploy.md:110` says the expected tool count is **18**; the same file's generated block says 19.
2. `docs/mcp-deploy.md:38` and `docs/operations.md:78` cite the MCP deploy path as
   `/home/redza/.local/share/datapulse-mcp`; the running unit uses `/srv/datapulse-mcp`.
3. nginx CORS allowlist admits `datapulse.my`; the canonical website origin is `www.data-pulse.my`.
4. `health_policy.py:65-75` defines **9** statuses (no `discontinued`) while the schema, the shell
   classifier, the dashboard and 8 generators define **10** — so `derive_trust_summary` builds `by_status`
   over 9 and a `discontinued` row would be counted in the total but absent from that map.
5. `scripts/AGENTS.md:19` says pipeline outputs are gitignored; 15,112 tracked files are overwhelmingly
   generated output.
6. `scripts/AGENTS.md:47` documents `gen_anomaly.py` as writing `health/anomalies.json`; it writes nothing.
7. `scripts/AGENTS.md:49` documents `data/catalog-graph.json`; the file is at repo root.
8. `sg/tests/` is not run by any workflow.
9. The append PR's merge step is **not encoded in the tree** — no auto-merge arming for
   `attestation/append-*` exists; it relies on repository settings or an operator (INFERRED).

Each of these is a candidate for a follow-up fix; none has been actioned in this pass, and none was
changed by it. This document records state, not repairs.
