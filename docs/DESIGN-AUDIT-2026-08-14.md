# DataPulse MY design audit — 2026-08-14

**Status:** Audit only. No design changes were made. Empirical evidence in `~/dotfiles/notes/audit-2026-08-14-screenshots/`.

## Method

- Sol-tier brief (`/tmp/design_audit_brief.md`) inspected DOM, CSS, and live HTML.
- Operator verified empirically with camofox at 1440×900: dashboard hero, MCP section, mid-page (mechanism + waffle), comparison table, Probe/Measure/Classify/Publish steps, and dataset cards. Landing hero, mid-section (waffle + all-caps H2), and full-page.
- 9 PNGs preserved in `~/dotfiles/notes/audit-2026-08-14-screenshots/` (1.7 MB total; not in the repo — binary asset, off-band).

## Live fetches

| URL | Title | Description | HTML size |
|---|---|---|---|
| `https://data-pulse.my/` | "DataPulse MY — Malaysian public data health" | "Live health for 385 Malaysian public datasets tracked by DataPulse MY." | 1,017,113 bytes |
| `https://data-pulse.my/landing` | "DataPulse MY — A trust layer for Malaysian public datasets" | "DataPulse MY is a trust layer for Malaysian public datasets, with health, provenance, and programmatic access." | 30,182 bytes |

Both fetches returned HTTP 200 on 14 August 2026.

## Empirical findings (visual confirmation of sol brief)

| Sol brief claim | Empirical confirmation |
|---|---|
| Landing is more polished than the dashboard | ✅ Confirmed — landing has a clear reading path; the dashboard buries the catalogue after a full marketing sequence. |
| Three all-caps H2s on landing (lines 102, 135, 174) | ✅ **Confirmed visually** in the waffle / dashboard-uptime section. The H2 `THE DASHBOARD RIGHT NOW` is the loudest text on the page by far, character-overflowing into the calendar grid behind it. |
| Status tokens incomplete in shared CSS | Not visually verified; corroborated by CSS inspection. |
| Site chrome differs (4-link landing nav vs 3-link dashboard nav) | ✅ Confirmed visually. Dashboard has **no link to /landing** — only the brand-mark click returns there. |
| Health evidence repeats | ✅ Confirmed visually — landing has hero counter + waffle + surface table; dashboard has stat strip + status legend + waffle + changelog + comparison table. |

## New findings (visual only, not in sol brief)

### Probe/Measure/Classify/Publish — circle-icon heading overlap
On the dashboard around y=4500, the four workflow-step headings (`Probe`, `Measure`, `Classify`, `Publish`) have a thin horizontal line cutting through each word. The cause is **the circle icons overlapping the heading text** — the icons are positioned at a y-coordinate that intersects the heading baseline. This bug is not in Sol's text-based brief and would not have been caught without rendering.

Evidence: `audit-2026-08-14-screenshots/shot_dashboard_cards.png` and `shot_dashboard_cards2.png`.

### Mobile-only stat strip behavior not validated
Camera at 1440×900 desktop only. The brief's claims about mobile responsive behavior are derived from CSS only.

### Plausible presence vs. "no analytics" copy
Visual side-by-side of the two pages confirms the contradiction: dashboard emits the Plausible script (visible in DOM); landing footer claims "No tracking. No analytics. No cookies. No accounts." Both pages share the same custom-domain trust model, so one of those statements is wrong by design. Sol brief flagged this in §8.

## Screenshots inventory

| File | Page | Section | Resolution |
|---|---|---|---|
| `shot_landing.png` | `/landing` | Hero (above the fold) | 1440×900 |
| `shot_landing_full.png` | `/landing` | Full page | 1536×4155 |
| `shot_landing_mid.png` | `/landing` | Mid-section ("THE DASHBOARD RIGHT NOW" H2) | 1440×900 |
| `shot_dashboard.png` | `/` | Hero + stat strip | 1440×900 |
| `shot_dashboard_y900.png` | `/` | MCP terminal section | 1440×900 |
| `shot_dashboard_mid.png` | `/` | Mechanism / waffle / status legend | 1440×900 |
| `shot_dashboard_cards.png` | `/` | Comparison table (BNM) | 1440×900 |
| `shot_dashboard_cards2.png` | `/` | Probe/Measure/Classify/Publish (overlap bug visible) | 1440×900 |

Files live in `/home/redza/dotfiles/notes/audit-2026-08-14-screenshots/` (operator-side; not in the repo).

## Roster

| Asset | URL | Independence from page swap |
|---|---|---|
| `mcp.json` | `/mcp.json` | Yes — path-only, content unchanged by swap |
| `datapulse.json` | `/datapulse.json` | Yes — data manifest unaffected |
| `health/latest.json` | `/health/latest.json` | Yes — JSON output unaffected |
| `llms.txt` | `/llms.txt` | Yes — content unaffected |
| `data/<id>.md` | `/data/<id>.md` | Yes |
| `badges/<id>.svg` | `/badges/<id>.svg` | Yes |
| MCP endpoint | `mcp.data-pulse.my/mcp` | Yes (subdomain) |
| Glama, M8ven | n/a | Yes — they scrape `mcp.json` + GitHub source; **neither care about the `/` rendered page** |

## Sol brief summary recommendations

1. Finish Phase 5 nav integration (needs planning).
2. Choose one primary health summary per page (needs planning).
3. Normalize three all-caps landing H2s — ≤30 min.
4. Run a dashboard card legibility pass — ≤30 min for CSS only.
5. Reconcile shared status tokens and privacy copy — ≤30 min.

## Additional (visual-confirmed) recommendations

6. **Fix the `Probe / Measure / Classify / Publish` heading overlap** — investigate CSS positioning of the circle icons vs the heading baseline. Confirmed visually on the rendered page; not in Sol's CSS-only audit.
7. **Verify mobile rendering** with at least a 375×667 and a 768×1024 camofox capture before claiming a responsive fix lands.
8. **Reconcile dashboard Plausible script presence with landing "No tracking" copy** — one of these statements is dishonest on its current day. Decide whether the dashboard really needs analytics or the landing really needs to admit it.

## Phase plan coverage

- Phase 1 (CSS extraction) — SHIPPED in commit `17042f0`
- Phase 2 (dashboard on shared CSS, B1) — SHIPPED in commit `8f8a848`
- Phase 3 (NPRA page) — PENDING
- Phase 4 (generator durability test) — SHIPPED in commit `2aa99f7`
- Phase 5 (nav integration sitewide) — PENDING; this audit's items 1, 3, 6 are also Phase 5 scope
