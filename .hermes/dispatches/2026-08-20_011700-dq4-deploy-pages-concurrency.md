Workdir: /home/redza/datapulse-my
Goal: Stop deploy-pages queue stacking by adding safe concurrency control, preserving skip-deploy heartbeat behavior, and removing the paused redispatch workaround after the PR lands.
Failure mode: Incorrect concurrency cancels release deploys or leaves the stuck cron workaround creating duplicate deploy runs.
Acceptance test: Add and verify the concurrency policy, preserve path semantics, use a test branch and PR (never direct main push), remove cron a369885b3a4c only after merge, and report exact verification results.
Recommended execution model: terra

## Scope

The current bug is that `actions/deploy-pages@v4` hangs on `workflow_dispatch` for ~8h36m in queue state; this has accumulated 30+ stuck runs since 2026-08-18. The `on.push.paths` list is 23 entries long and includes `mcp/server.py` + `mcp/requirements.txt`, which causes every agent-driven MCP edit to enqueue a full dashboard deploy.

Apply the same cancel-in-progress pattern that commit `aa729327` shipped for release-please. After this lands, remove the paused cron workaround `a369885b3a4c` (`datapulse-pages-redispatch`). Do not resume the cron.

## Acceptance details

1. Verify the worktree is clean except the expected untracked `.hermes/` dispatch directory.
2. Read the current `.github/workflows/deploy-pages.yml` and preserve its path-list semantics.
3. Add this concurrency policy, adapting only if the current workflow structure requires an equivalent safe form:

```yaml
concurrency:
  group: pages-deploy
  cancel-in-progress: ${{ github.event_name == 'push' && !contains(github.event.head_commit.message, '[skip deploy]') }}
```

This must keep push-deploys from queueing up while preserving `[skip deploy]` health-timer pushes in their own group or pass-through path. Verify the behavior against release-please commit `aa729327`.

4. Prune the path list only if the audit proves that it is the queue cause. If pruning is justified, dashboard-rendering paths may include: `docs/**`, `health/**`, `datapulse.json`, `agent.json`, `mcp.json`, `catalog-snapshot.json`, `attestations/**`, `.attestations/**`, `badges/**`, `samples/**`, `data/**`, `llms.txt`, `robots.txt`, `sitemap.xml`, `feed.xml`, and `changelog.json`. Do not prune `mcp/server.py` or `mcp/requirements.txt` without stating the agent-discovery consequence.
5. Create a test branch, not a direct main push. Run `gh workflow run deploy-pages.yml --ref <branch>` only if safe and permitted by the workflow; otherwise document the limitation and validate YAML/concurrency semantics locally.
6. Open or prepare a PR for operator review; do not merge or push directly to `origin/main`.
7. Identify in-flight stuck runs and report their IDs. Do not cancel them without operator approval.
8. After the PR is merged, the operator will remove `a369885b3a4c`; Codex must not remove the cron during this dispatch.
9. Report exact files changed, tests run, branch/PR handle if created, and any operator follow-up.

## Constraints

- Do not push directly to `origin/main`.
- Do not merge the PR.
- Do not cancel in-flight runs without operator approval.
- Do not remove or resume the cron before the workflow fix is merged.

