# DataPulse CI and OpenWiki integration audit — 2026-08-27

## User requirement

- No deterministic-safety-net bypasses.
- CI must be fail-closed, canonical, streamlined, and self-healing.
- OpenWiki must automatically generate DataPulse documentation from canonical repository inputs.
- `https://www.data-pulse.my` must be the canonical human-facing site; the apex must redirect to `www`.

## Current evidence

### CI

- Nine workflows exist: `ci.yml`, `deploy-pages.yml`, `deploy-cloudflare-pages.yml`, `release-please.yml`, `anchor-release-attestation.yml`, `pipeline-freshness.yml`, `pipeline-audit.yml`, `publish-mcp.yml`, and `openwiki-update.yml`.
- `ci.yml` runs on every push, pull request, and manual dispatch, with job name `deterministic-safety-net`.
- Ruleset `20884049` is active on `main`, requires `deterministic-safety-net`, and also has a repository-role bypass actor with `bypass_mode=always`.
- Direct pushes are accepted with GitHub reporting the required check as `expected`; this is not true gating.
- The health producer creates direct `[skip deploy]` commits on `main`; removing the bypass without redesigning that producer would stop health publication.
- The landing-page commit exposed 12 CI failures: isolated release fixtures did not stage `scripts/gen_landing_page.py`, and two invariant tests were coupled to an old fetch block.
- GitHub Pages failed on the same release-build staging defect; Cloudflare Pages succeeded.
- `deploy-pages.yml` contains `continue-on-error` on deployment attempts and `|| true` on `.attestations` copying. These are not equivalent to bypassing the deterministic safety net, but each requires explicit failure semantics review.
- Workflow actions use mutable major tags (`actions/checkout@v4`, setup/actions v4/v5, Cloudflare Wrangler v3, release-please v4); there is no repository-wide SHA pinning policy.
- `release-please.yml` has useful concurrency protection and no direct bypass, but `contents: write`/`pull-requests: write` are expected for its role.
- `anchor-release-attestation.yml` has write permissions and pushes to a PR branch; it must remain isolated from ordinary CI and be tested as a bot-authored PR-head workflow.

### Public host/routing

- `config/public-surfaces.json` and schema currently declare `https://data-pulse.my` as the website origin.
- Cloudflare and GitHub Pages verifiers derive/assume the apex origin.
- Current HTTP behavior redirects `www.data-pulse.my` to the apex, opposite to the requested canonical direction.
- The new landing page is available at `/landing` and `/landing.html` redirect behavior, but the canonical site decision must be encoded in config and every workflow/verifier.
- Cloudflare deployment workflow's own served verification passed against the configured origin; that proves the current configured route, not the desired `www` policy.

### OpenWiki

- Tracked generated files: `openwiki/quickstart.md`, `openwiki/datasets.md`, `openwiki/mcp.md`, `openwiki/operations.md`, and `openwiki/.last-update.json`.
- Current generated docs are stale: they describe 122 datasets, obsolete MCP/tool counts, old workflow behavior, and old pipeline assumptions. Canonical DataPulse state is 389 datasets and 16 MCP tools.
- `openwiki/.last-update.json` is dated `2026-08-06` and records `openwiki` model metadata from that run.
- Actual workflow currently uses Node 20, unpinned global `npm install -g openwiki`, writes provider credentials into `~/.openwiki/.env`, invokes `openwiki code --update --print`, and directly pushes generated changes to `main`.
- `openwiki/operations.md` contradicts the actual workflow by describing a PR-based workflow, a daily schedule, and inline env configuration that are not present in the current workflow file.
- Local global install is `openwiki@0.3.2` and crashes before execution due to a LangChain export mismatch.
- Isolated `openwiki@0.4.3` works with Node 22; npm metadata declares Node `>=22`. A project-local lockfile is required because the package uses wide dependency ranges.
- OpenWiki v0.4.3 documents code-mode output under `openwiki/`, supports `--update --print`, and treats `openwiki/INSTRUCTIONS.md` as user-authored control metadata.

## Required target architecture

```text
canonical DataPulse inputs
  + openwiki/INSTRUCTIONS.md (human-authored policy)
→ project-local Node 22 + locked OpenWiki 0.4.3
→ generated openwiki/* only
→ generated-doc verifier / fact lint / link checks
→ PR branch, never direct main push
→ deterministic-safety-net on PR
→ human merge
→ normal deployment
```

### OpenWiki ownership rules

- `openwiki/INSTRUCTIONS.md` is the only hand-authored OpenWiki control file.
- OpenWiki may modify only generated files under `openwiki/`; it must not modify `.github/workflows`, `AGENTS.md`, `CLAUDE.md`, source scripts, manifests, or public HTML.
- Generated OpenWiki pages are derivatives, not canonical sources.
- The verifier must fail on stale current-state claims, old domains, unsupported workflow claims, missing current links, secret/config leakage, and out-of-scope file changes.
- Historical audit documents remain immutable and are excluded from current-fact linting.

### CI rules

- No `continue-on-error` for required validation or publication success.
- No `|| true` on required artifact copies or verification commands.
- Every failure must be visible with a non-zero exit or an explicit, tested non-fatal classification.
- OpenWiki PRs must run the normal deterministic safety net; no special bypass label, actor, or workflow condition.
- The direct health producer/main bypass must be redesigned separately before removing the ruleset bypass actor.

### Canonical host rules

- Change the public-surface website origin to `https://www.data-pulse.my`.
- Derive all generated links and workflow/verifier base URLs from that config.
- Configure Cloudflare edge behavior so apex redirects to `www` and `www` serves the canonical Pages artifact.
- Validate both hosts, redirect status/location, certificate, canonical link, and served landing content after deployment.

## Next implementation gates

1. Codex implementation of the OpenWiki project-local locked PR workflow, `INSTRUCTIONS.md`, generated-doc verifier, and CI integration.
2. Codex implementation of canonical `www` origin propagation through repo/workflow/verifier sources.
3. Separate explicit permission/ruleset and health-producer redesign to eliminate the current main-branch bypass without stopping the producer.
4. Cloudflare edge/DNS redirect change and post-deploy served-state verification.
