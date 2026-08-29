Workdir: /home/redza/datapulse-my
Goal: Align the root public dashboard page with the approved government-friendly positioning by revising its visible landing/problem/comparison copy while preserving dashboard behavior and generated data integrity.
Failure mode: The root URL `/` still presents Malaysian public data as “silently breaking”, labels sources “stale by default” and “licences unclear”, and frames DataPulse against official sources and resellers. That undermines the collaborative source-of-record positioning already applied to `/landing` and `/npra.html`.
Acceptance test: `docs/index.html` contains collaborative source-of-record language, no retired adversarial phrases or stale tool-count demo text, the dashboard’s embedded data and JavaScript behavior remain intact, and repository/page tests pass.
Recommended execution model: terra

Implementation authority: You are the designated Codex implementer for this dispatch. The repository rule requiring Hermes to dispatch Codex has already been fulfilled; it does not prohibit you from editing the explicitly scoped file below. Edit the scoped file directly. Do not call codex-run, codex-run-bg, delegate_task, or any other agent recursively.

## Scope

Modify only visible copy in `docs/index.html`, plus run the existing deterministic generator if required to refresh its embedded data block. Do not change:

- dashboard JavaScript behavior, filters, status taxonomy, health methodology, or embedded data values;
- CSS, layout, icons, URLs, navigation, or assets;
- `mcp/server.py`, workflows, health artifacts, or other pages;
- any credentials, API paths, or service configuration.

## Copy direction

Reframe the root page as a public-service companion layer:

1. Replace the current problem heading and paragraph with language such as “Making published data easier to review and reuse”. Acknowledge that Malaysian agencies and public institutions publish data for public use; explain that DataPulse adds independent, read-only observations of availability, freshness signals, provenance, and licence/reuse context. State that official publishers remain the source of record.
2. Replace the three adversarial pain-card labels/copy with neutral operational descriptions:
   - publication timing can be hard to see;
   - freshness signals vary by source;
   - reuse context should travel with the data.
   Explain the observable limitation without implying agency negligence.
3. Rename “The mechanism” to “How DataPulse supports review” and describe the same inspectable pipeline as a support for review and documentation. Keep the four existing technical steps and their factual meaning; avoid broad “safe to use” or institutional-performance claims.
4. Replace “The honest difference” and the current direct comparison table with a constructive “A complementary layer around official data” framing. Keep the official publisher as source of record and explain what DataPulse adds: observed timestamps/signals, explicit evidence gaps, machine-readable provenance/licence context, read-only agent access, and published structural observations. Do not describe official sources or resellers as opaque, deficient, or inferior.
5. Replace the stale MCP demo line `11 read-only tools over 389 licence-declared datasets` with neutral non-counted copy such as “Read-only catalogue context with provenance and publication signals.”
6. Preserve the existing legal section, public-source restrictions, rate limits, robots.txt statement, source-maintainer correction path, dashboard links, and all data-driven status rendering.

Do not add unsupported government endorsements, rankings, guarantees, certification claims, or claims that DataPulse validates the correctness of the underlying data.

## Verification

Run:

```bash
python3 scripts/embed_dashboard_data.py --html docs/index.html
python3 scripts/check.py
python3 scripts/verify_repository_contract.py
python3 scripts/gen_site_nav.py --check
python3 -m pytest scripts/tests/test_embed_dashboard_data_shell.py scripts/tests/test_site_nav.py -q
git diff --check
```

Perform a copy audit confirming these are absent from `docs/index.html`:

- `Malaysian open data is silently breaking`
- `Stale by default`
- `No freshness signal`
- `Licences unclear`
- `The honest difference`
- `World-class supply`
- `11 read-only tools over`

Confirm these remain present:

- source-of-record language;
- read-only/public-source/legal boundaries;
- dashboard and methodology links;
- maintainer correction path;
- embedded data marker and client-side health rendering.

Do not commit or push. Return exact changed files, copy audit, tests, and `Pushed: NO`.
