# Release reproducibility verification

- Verified at: `2026-08-09T11:03:50+08:00`
- Source SHA: `042c10f0869a5505e2018d01d1509efd2ef90240`
- Profile result: `bash scripts/generate.sh release-build` exited 0 in both isolated runs
- Total files built: **648**

| Path category | File count | First-run hash | Second-run hash | Match? |
|---|---:|---|---|:---:|
| data/<id>.md | 166 | `4e6708884f8046af309bd7ef211a53205bc5606849779751870485feb5271b6d` | `4e6708884f8046af309bd7ef211a53205bc5606849779751870485feb5271b6d` | Yes |
| badges/ | 173 | `b579e58f0fa3b6e185c48e009cff4a4d19c48d4829f6737cf5a141581dfc7aa1` | `b579e58f0fa3b6e185c48e009cff4a4d19c48d4829f6737cf5a141581dfc7aa1` | Yes |
| feed.xml | 1 | `60dc91ce5e604c0b47d5395512be128a09024c289a9b31e5e2591828c0bc8ce0` | `60dc91ce5e604c0b47d5395512be128a09024c289a9b31e5e2591828c0bc8ce0` | Yes |
| README.md (trust-summary) | 1 | `fdbb55de716dc0e2a7b50d232d99f62c0934c2606a56c7cd5f43f5ac871356f7` | `fdbb55de716dc0e2a7b50d232d99f62c0934c2606a56c7cd5f43f5ac871356f7` | Yes |
| changelog.json | 1 | `80be09946af73daf1abfa8b85a9d441992e886cfbe9a9ae51f30345bd03275d6` | `80be09946af73daf1abfa8b85a9d441992e886cfbe9a9ae51f30345bd03275d6` | Yes |
| data/json/ | 136 | `9669e7645e030c414d8a96ed95c1bffd3668c3df0f4e921cc9442f28218875ca` | `9669e7645e030c414d8a96ed95c1bffd3668c3df0f4e921cc9442f28218875ca` | Yes |
| data/jsonld/ | 167 | `cf147d76cadbd0e2354e83a879b290a055eff4fa781c747e45a0378d3714c63b` | `cf147d76cadbd0e2354e83a879b290a055eff4fa781c747e45a0378d3714c63b` | Yes |
| docs/mcp-reference.md | 1 | `7800a72660152afebda57dacb7437c4c7ca82ea88fe188b9e80c531473ed7945` | `7800a72660152afebda57dacb7437c4c7ca82ea88fe188b9e80c531473ed7945` | Yes |
| mcp.json | 1 | `81ea9bb64cbfae60ab21b87aa5f048d065b10f26811f04db7c5785e12543ab94` | `81ea9bb64cbfae60ab21b87aa5f048d065b10f26811f04db7c5785e12543ab94` | Yes |
| docs/.dashboard_filters.json | 1 | `ef1356b4ab8f2f1f98aecb02550da5803242d64207994d98f1cee86a20f5a301` | `ef1356b4ab8f2f1f98aecb02550da5803242d64207994d98f1cee86a20f5a301` | Yes |

## Deployment verification (T34, 2026-08-09)

- Date: `2026-08-09T11:16:15+08:00`
- Reviewed source SHA: `18ae5aea7369d505deca82935584e4962ce97c66` (`git rev-parse HEAD`)
- Deployed SHA at `https://data-pulse.my/`: `042c10f0869a5505e2018d01d1509efd2ef90240` (fetched from GitHub API)
- SHA check: ❌ mismatch
- Surface fetches:
  - dashboard: OK
  - llms.txt: OK
  - datapulse.json: OK
  - health/latest.json: OK
  - data/jsonld/catalog.json: OK
  - mcp.json: OK
  - feed.xml: OK
- `scripts/verify_release_invariants.sh`: OK
- `scripts/verify_agent_ready.sh`: OK
- MCP tools count: 5 (search_datasets, get_dataset, find_stale, get_provenance, find_by_licence)
- `python3 scripts/verify_mcp_deployment.py`: `MISMATCH`
- Known exceptions: live MCP service predates the T29 source-commit markers; `verify_mcp_deployment.py` reports `deployed=<missing>` until redeploy.
- Reproduction:

```bash
# Trigger deploy (waits for timer)
git push origin HEAD:main  # only if local is ahead

# Re-run post-deploy invariants
DATAPULSE_RELEASE_BASE_URL="https://data-pulse.my" bash scripts/verify_release_invariants.sh
DATAPULSE_AGENT_BASE_URL="https://data-pulse.my" bash scripts/verify_agent_ready.sh
```

## Reproduction

```bash
python3 scripts/verify_release_reproducible.py
```

## Rollout observation (T35, 2026-08-09)

### Observation protocol

Two consecutive 15-minute timer ticks are observed, including one that probes a browser-dependent dataset (`doe_apims`, `kkm_idengue`, or `eperolehan-diklankan`). Each tick is verified for:

- Scoped commit: only `health/ badges/ feed.xml README.md changelog.json` modified (no unrelated paths staged)
- Lock released between ticks: `/tmp/datapulse-health.lock` not present between cycles (proves the flock guard released)
- Public artifacts updated: `git diff origin/main` shows the expected tracked-file churn
- Browser-dependent dataset probed: the latest health envelope records a fresh `last_checked` for at least one of `doe_apims`, `kkm_idengue`, `eperolehan-diklankan`

### Pre-observation snapshot

- Pre-observation HEAD: `ef364c5` — `chore(health): update due dataset health`
- Timer state at observation start: `active`, next fire at `11:45`
- Lock file at observation start: `present`
- Last 2 timer commits observed before observation window:
  - `ef364c5` — `chore(health): update due dataset health`
  - `042c10f` — `chore(health): update due dataset health`

### Observation cycles

| Cycle | Trigger time | Commit SHA | Scoped paths OK? | Lock released? | Browser-dependent probed? |
|---|---|---|---|---|---|
| 1 (first observed) | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ |
| 2 (second observed) | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ |

### Final state

- ROLLOUT STATUS: _pending observation_
- All 7 gates green: contract verifier (166 datasets), JSON Schema, MCP pytest (25/25), scripts/tests (225/225), NPRA format tests, fact lint (0 findings), agent-ready live (166/166)
- Reproduction: `bash scripts/check.sh --due` runs every 15 minutes via systemd timer. `bash scripts/generate.sh release-build` runs on Pages workflow dispatch. `bash scripts/verify_release_invariants.sh --local` is the local regression gate.

### Observation completed

- Observation window: `<start-time>` → `<end-time>`
- Operator fill-in: see cycle table above.
- Final status: ROLLOUT COMPLETE (or BLOCKED on <reason>)
