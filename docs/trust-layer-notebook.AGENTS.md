# AGENTS.md — `docs/trust-layer-notebook.ipynb`

Working agreement for AI agents extending, regenerating, or replacing the trust-layer tutorial notebook.

## What this is

`trust-layer-notebook.ipynb` is a 12-cell Jupyter notebook hosted on the public dashboard and surfaced via the **Open in Google Colab** badge in `README.md`. It teaches new users the verification-first pattern: **check health → fetch with confidence → refuse to use unacceptable data**. The "Open in Colab" link goes to `/docs/trust-layer-notebook.ipynb` on the public site.

**Two audiences**: humans learning DataPulse MY (read-only), and AI agents editing it (read-and-modify).

## Hard rules

1. **Read-only notebook.** The notebook itself fetches but never mutates state. Do not add cells that perform writes, deletes, or destructive operations.
2. **Citations must point at live docs.** Every link in markdown cells should be to `https://data-pulse.my/...` (or a known upstream like `data.gov.my`), not to internal paths or `localhost`. Cells that fail-open on URL fetch are acceptable but must say so explicitly.
3. **Status taxonomy is 10-valued.** The taxonomy has been `fresh | aging | stale | discontinued | degraded | browser_dependent | unreachable | unknown | unknown_freshness | reference` since 2026-08-11. The notebook references the taxonomy — if you change the notebook's status enum, update both the markdown and the corresponding code cell in lockstep.
4. **No fabricated dataset IDs.** `fuelprice` and similar examples must reference real datasets. If you change an example dataset, verify it still exists via `curl https://data-pulse.my/datapulse.json | jq '...'` first.
5. **Cell IDs are stable.** Each cell has a stable `id` field (e.g. `load-health-envelope`, `inspect-fresh-evidence`). Don't change IDs without also updating the README badge links and any cross-notebook references.
6. **Keep it under 15 cells.** The current 12-cell structure (Title, Why, Load, Status, Fresh example intro/code, Fetch, Stale example intro/code, Usable, Limitations) is the "right amount" for a tutorial. More cells = higher cognitive load. If you find yourself adding cells, prefer replacing an existing one.

## Style conventions

- **Cell type:** `markdown` for prose + headings, `code` for executable Python. Don't mix prose into code cells.
- **Output:** each code cell should print or display one observable result. Multi-line outputs are fine but should be human-skimmable.
- **Imports:** top of the first code cell only. Use stdlib + `requests` + `pandas` — no exotic deps; the notebook runs in Colab's default environment.
- **No `pip install` cells.** Colab comes with `requests`, `pandas` pre-installed. If a new dep is genuinely needed, write a single `try/except ImportError` block, not a `%pip install` line — Colab cells run on every kernel restart, and pip-install cells trigger re-execution warnings.
- **Magic commands:** avoid `%`, `%%` if possible. Some Colab users run kernels in restricted environments where magic is disabled.
- **Markdown style:** sentence case headings, **bold** for the one thing each cell is teaching, no emoji in markdown prose (colab renders them inconsistently).

## What is NOT in the notebook

- **Deploy-time configuration** — `.github/workflows/health-check.yml`, the timer in `~/.config/systemd/user/datapulse-health.timer`
- **The MCP server code** — `mcp/server.py` and the 16 tools exposed via `mcp.data-pulse.my`
- **Raw health probes** — these run via systemd, not from this notebook
- **The pipeline that GENERATES this notebook** — there is no generator; the notebook is hand-authored and committed

## Out of scope

- Adding **paid-product demos** — the notebook is a free-tier trust layer tutorial, not a sales surface. If you want to demo a paid feature, do it on a different artifact.
- **Embedding authentication or API keys** — the notebook is public; no env-var reads beyond `requests` defaults.
- **Changing the public URL structure** — `docs/trust-layer-notebook.ipynb` is the canonical path; renaming breaks the Colab badge in `README.md`.

## Verification before push

```bash
# 1. Notebook is valid JSON
python3 -c "import json; json.load(open('docs/trust-layer-notebook.ipynb'))"

# 2. Cell count is unchanged (or intentionally changed)
python3 -c "import json; print(len(json.load(open('docs/trust-layer-notebook.ipynb'))['cells']))"

# 3. Every cell has a stable id
python3 -c "
import json
nb = json.load(open('docs/trust-layer-notebook.ipynb'))
ids = [c.get('id') for c in nb['cells']]
print('all ids present:', all(ids), 'unique:', len(set(ids)) == len(ids))
"

# 4. Execute the code cells locally (requires network)
jupyter nbconvert --to notebook --execute docs/trust-layer-notebook.ipynb \
  --output trust-layer-notebook-executed.ipynb
# Then diff to ensure no surprises in cell outputs
```

## Pre-flight checklist (for dispatch briefs)

When writing a codex brief that touches this notebook:

- **Which cell(s) change?** cell index or stable id
- **What status taxonomy does the cell reference?** pin the exact list — 10 values
- **What dataset is used as the example?** verify it exists in `datapulse.json`
- **Why is this read-only?** brief must explicitly state no writes
- **What replaces the old cell?** if replacing, copy the new content into the brief verbatim
- **Workdir:** absolute path to this repo