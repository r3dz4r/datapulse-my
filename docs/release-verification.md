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

## Reproduction

```bash
python3 scripts/verify_release_reproducible.py
```
