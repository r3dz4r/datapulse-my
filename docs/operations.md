# Operations

## Scheduling and ownership

`datapulse-health.timer` wakes every 15 minutes (`OnCalendar=*:0/15`) and starts
the root-owned unit `/etc/systemd/system/datapulse-health.service` as user
`redza`. Its durable sources are `/home/redza/dotfiles/system/` and
`deploy/systemd/`. `Persistent=true` catches up after downtime.

`scripts/check.sh --due` maps refresh frequencies to probe tiers:

| Tier | Manifest frequency | Due interval |
| --- | --- | ---: |
| realtime | `30 seconds`, `hourly` | 15 minutes |
| daily | weekday publication times | 60 minutes |
| daily | `daily` | 1 day |
| weekly-monthly | weekly, monthly, quarterly | 7 days |
| slow | annual, survey-year, as-required | 30 days |

The Sunday GitHub Actions workflow runs a full, non-tiered probe as a fallback.
Its successful completion triggers Pages via `workflow_run`, ensuring Pages
checks out the health commit rather than the pre-push workflow SHA.

## Paths and logs

- Operational repository: `/home/redza/datapulse-my`
- Health service source: `/home/redza/dotfiles/system/datapulse-health.service`
- MCP deployment: `/home/redza/.local/share/datapulse-mcp`
- Health log: `/var/log/datapulse-health.err`
- MCP log: `journalctl -u datapulse-mcp`
- Units: `/etc/systemd/system/datapulse-health.{service,timer}` and the installed
  `datapulse-mcp.service`

The health timer owns probe commits and generated health artifacts. Humans and
automation may also write `main`, so the unit pulls with `--rebase --autostash`
before probing and pulls with rebase again after its generated commit. The
second pull handles another writer winning the race; a genuine content conflict
stops the unit and must be resolved in the operational clone.

## Safe deploy and rollback

1. Validate source units with `systemd-analyze verify`.
2. Install the unit as root, run `systemctl daemon-reload`, and inspect
   `systemctl cat` before restarting the timer or MCP service.
3. Watch the appropriate log and confirm generated counts before pushing.
4. Roll back repository behavior with `git revert <commit>`; restore a prior
   unit source, reinstall it, daemon-reload, and restart. Do not reset or delete
   the operational clone to recover from a failed cycle.

The timer pushes probe commits by design. Manual regeneration work in this
repository is committed but pushed only by an operator.
