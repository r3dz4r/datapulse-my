# Troubleshooting

Start with `/var/log/datapulse-health.err`, `health/latest.json`, and the exact
`message`, `access_method`, `request_url`, and `http_status` for the dataset.

## Profile / ownership failures

| Symptom | Owner check | Action |
|---|---|---|
| `health/latest.json` stale or missing | `datapulse-health.timer` | `systemctl status datapulse-health.timer`, `tail -n 100 /var/log/datapulse-health.err` |
| Badges / RSS / changelog not updated after a probe | `health-cycle` profile | Run `bash scripts/generate.sh health-cycle --list`, then `bash scripts/generate.sh health-cycle`. If a step fails, the profile stops on first failure — check that step's error. |
| Pages deploy fails post-deploy invariant | `deploy-pages.yml` workflow | Check the workflow run, compare deployed SHA to repo HEAD, see "Pages still shows old state" below. |
| `verify_mcp_deployment.py` reports `MISMATCH` | MCP service | Redeploy per `docs/mcp-deploy.md`. |
| `verify_mcp_deployment.py` reports `UNREACHABLE` | Network / Cloudflare / nginx | Verify `curl https://mcp.data-pulse.my/mcp` from VPS, check nginx + cloudflared status. |

| Symptom or message | Likely cause | Action |
| --- | --- | --- |
| `Camofox unavailable; browser check required` | Browser service cold, unreachable, or timed out | Check Camofox health/network, retry one browser smoke test, then wait for the next due cycle. |
| `Camofox returned no tab id` | Invalid/partial open response | Inspect Camofox logs and response shape; do not reclassify as direct. |
| `Camofox snapshot failed` / `returned no snapshot` | Render did not settle before deadline | Verify the source in a browser, then tune per-dataset wait only with evidence. |
| `curl HEAD request failed` / `curl request failed` | DNS, TLS, routing, or timeout | Run curl against `request_url` from the VPS and inspect verbose output. |
| `HTTP 404` | Moved or discontinued upstream path | Confirm against the official catalog; update URL or record `real_status: discontinued` with evidence. |
| `Internal error: expected … results, wrote …` | A probe process exited without emitting one row | Run the selected tier directly, identify the missing ID, and inspect its helper stderr. |
| Old `last_checked` | Dataset is not due, or a failed probe preserved prior evidence | Compare `refresh_frequency`, tier interval, timer status, and recent service log. |
| Schema validation failure | Manifest field/type drift | Run `python3 -m jsonschema -i datapulse.json datapulse.schema.json` and fix the reported row. |
| Pages still shows old state | Deploy pending, failed, or used wrong SHA | Inspect Deploy Pages, confirm `workflow_run` conclusion, deployed SHA, and post-deploy gate. |
| MCP initialize works but calls fail | Missing session header or Accept types | Send `Accept: application/json, text/event-stream`, retain `Mcp-Session-Id`, and use it on later requests. |

For a direct source check, preserve redirects and status:

```sh
curl -L -sS -D - -o /dev/null https://example.gov.my/dataset
```

For service state:

```sh
systemctl status datapulse-health.timer datapulse-health.service
tail -n 100 /var/log/datapulse-health.err
journalctl --user -u datapulse-mcp.service -n 100 --no-pager
```

## Rebase-collision: timer runs, service fails, dashboard stale (2026-08-12)

**Diagnostic signature:** `health/latest.json` mtime is >1 h old at the same time that `datapulse-health.timer` is `active (waiting)` AND `datapulse-health.service` last exited with `Result: exit-code` (typically 128). A pull/rebase process is the failure point but the timer thread is still signalling success.

**Cause:** the systemd `ExecStartPre` step runs `git pull --rebase --autostash`. If a previous tick was interrupted mid-rebase (typical trigger: a skip-deploy GitHub Actions push to `main` landing in the same window the VPS pull runs), a stale `.git/rebase-merge` directory is left behind. Every subsequent 15 min tick exits 128 before the probe ever runs, so the timeline looks like:

1. `health/latest.json` mtime freezes while the timer keeps ticking.
2. `git status` (from the repo directory) reports `Your branch is ahead of origin/main by N commit` plus `You are currently rebasing. (all conflicts fixed: run "git rebase --continue")` or `(no commits, rebase in progress)`.
3. `tail -n 50 /var/log/datapulse-health.err` shows repeating `fatal: It seems that there is already a rebase-merge directory, and I wonder if you are in the middle of another rebase.` lines.

**Fix (verified 2026-08-12, recovered commit 56af356):**

```sh
sudo systemctl stop datapulse-health.timer
cd /home/redza/datapulse-my
rm -fr .git/rebase-merge .git/rebase-apply
git rebase --continue   # or `git rebase --abort` if it loops
git push origin main
sudo systemctl start datapulse-health.timer
sudo systemctl start datapulse-health.service
```

After `systemctl start datapulse-health.service`, the `health/latest.json` mtime will refresh within the next probe cycle (the service runs immediately on start, not waiting for the next 15-min tick).

**Prevention (long-term, pending):** switch the `ExecStartPre` step from `git pull --rebase --autostash` to `git fetch origin main && git merge --ff-only origin/main || true` (or move VPS-managed commits to a separate branch). Eliminate the rebase step entirely so neither writer can collide. Track at the `system/datapulse-health.service` unit in `r3dz4r/dotfiles`.

<!-- deploy-trigger: 2026-08-11T23:32:55Z -->

