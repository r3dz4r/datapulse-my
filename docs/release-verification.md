# Release reproducibility verification

- Verified at: `2026-08-09T09:52:49+08:00`
- Source SHA: `7aed3bd45e100e96ccc77fdeceba0f4c35d80de5`
- Profile result: `bash scripts/generate.sh release-build` exited 0 in both isolated runs
- Total files built: **648**

| Path category | File count | First-run hash | Second-run hash | Match? |
|---|---:|---|---|:---:|
| data/<id>.md | 166 | `731684950dfe41eab19d8e7300fa4a8313e1ac45d101a882ae9ad8deb5df75a8` | `731684950dfe41eab19d8e7300fa4a8313e1ac45d101a882ae9ad8deb5df75a8` | Yes |
| badges/ | 173 | `b579e58f0fa3b6e185c48e009cff4a4d19c48d4829f6737cf5a141581dfc7aa1` | `b579e58f0fa3b6e185c48e009cff4a4d19c48d4829f6737cf5a141581dfc7aa1` | Yes |
| feed.xml | 1 | `374d9eaa3fabca9d095b2af18df7afba0eef554a9e3fba0ca5ec58b7ea8e1848` | `374d9eaa3fabca9d095b2af18df7afba0eef554a9e3fba0ca5ec58b7ea8e1848` | Yes |
| README.md (trust-summary) | 1 | `fdbb55de716dc0e2a7b50d232d99f62c0934c2606a56c7cd5f43f5ac871356f7` | `fdbb55de716dc0e2a7b50d232d99f62c0934c2606a56c7cd5f43f5ac871356f7` | Yes |
| changelog.json | 1 | `4f49ee07121916cae1b533bd2ef0342b34bbf588ed9024402ad97843d51bc00a` | `4f49ee07121916cae1b533bd2ef0342b34bbf588ed9024402ad97843d51bc00a` | Yes |
| data/json/ | 136 | `905794c3532d90711fd6a6fa05780c60bb117bb10e51684d7c97ba20aefbb29f` | `905794c3532d90711fd6a6fa05780c60bb117bb10e51684d7c97ba20aefbb29f` | Yes |
| data/jsonld/ | 167 | `25a4b97a8efe62383385eb1f10e48f2569446d65e514757c554febcabb99d31b` | `25a4b97a8efe62383385eb1f10e48f2569446d65e514757c554febcabb99d31b` | Yes |
| docs/mcp-reference.md | 1 | `7800a72660152afebda57dacb7437c4c7ca82ea88fe188b9e80c531473ed7945` | `7800a72660152afebda57dacb7437c4c7ca82ea88fe188b9e80c531473ed7945` | Yes |
| mcp.json | 1 | `cba94c282d35b19fe73fb84ad5991d1e0b6fa88e68cab3195b9deae70c3d832e` | `cba94c282d35b19fe73fb84ad5991d1e0b6fa88e68cab3195b9deae70c3d832e` | Yes |
| docs/.dashboard_filters.json | 1 | `ef1356b4ab8f2f1f98aecb02550da5803242d64207994d98f1cee86a20f5a301` | `ef1356b4ab8f2f1f98aecb02550da5803242d64207994d98f1cee86a20f5a301` | Yes |

## Reproduction

```bash
python3 scripts/verify_release_reproducible.py
```
