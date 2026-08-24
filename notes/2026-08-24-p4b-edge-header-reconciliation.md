# P4B edge-header reconciliation — 2026-08-24

## Live evidence

- `https://data-pulse.my/` and `/health/latest.json` return HTTP 200 from `Server: GitHub.com` via Varnish.
- `Strict-Transport-Security`, `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy` are absent.
- Apex DNS resolves directly to the four GitHub Pages IPs; `www` resolves to `r3dz4r.github.io`.
- The zone uses Cloudflare nameservers, but the website traffic is not currently proxied through Cloudflare; no `cf-ray` header is present.
- No repository `_headers`, Netlify, Wrangler, or equivalent response-header configuration exists.
- A Cloudflare dashboard token exists with Account Cloudflare Tunnel:Edit, Zone:Edit, and DNS:Edit, but its token value is not available to the VPS runtime under the checked environment/config sources. Its explicit Transform Rules and Account Rulesets permissions are not yet verified.

## Reconciliation

- **Shipped:** P4A evidence-coverage artifact and pipeline wiring are committed, pushed, CI-verified, Pages-deployed, and served.
- **Main lane:** P4B browser security headers.
- **Blocked dependency:** GitHub Pages direct hosting does not expose a normal repository-controlled response-header surface. Cloudflare Response Header Transform Rules are viable only after the website DNS records are deliberately proxied through Cloudflare.
- **Deferred:** P4C performance and all P5–P8 lanes.

## Safety boundary

P4B does **not** require migrating away from GitHub Pages. The intended minimal path is edge layering: keep GitHub Pages as the origin and proxy the existing apex/www DNS records through Cloudflare, then apply scoped response-header transforms at the Cloudflare edge. GitHub Actions, Pages deployment, origin content, and the existing GitHub Pages custom-domain setup remain unchanged.

Do not change DNS proxy state, HSTS, CSP enforcement, or Cloudflare rules without an explicit reversible rollout plan. Begin CSP in report-only mode and verify before enforcement; this still requires Cloudflare credentials or dashboard action.

**Next gate:** choose the serving-edge path and approve the exact header/DNS change set before mutation.

## Attempt and rollback

- Cloudflare token verification passed: active; zone/DNS/response-ruleset read access passed.
- Created a scoped response-header ruleset and proxied only the five existing apex/www GitHub Pages records.
- Headers appeared at Cloudflare, but the proxied GitHub Pages origin returned `301 Location: https://r3dz4r.github.io/datapulse-my`, changing the public canonical URL. This is unacceptable for DataPulse.
- Rolled back all five DNS records to `proxied=false` and removed the P4B ruleset; API readback passed.
- Authoritative/public DNS now returns GitHub Pages IPs again, and direct origin verification with the custom Host returns HTTP 200.

**P4B status:** blocked on a safe GitHub Pages origin-compatibility design. The edge layering attempt must not be retried without a canary that proves custom-domain redirects remain on `data-pulse.my`.
