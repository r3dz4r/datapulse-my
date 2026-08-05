# Security policy

Report suspected vulnerabilities privately through GitHub Security Advisories
for `r3dz4r/datapulse-my`. Do not open a public issue containing exploit steps,
credentials, private network details, or unredacted logs. For non-sensitive
hardening suggestions, use a normal issue.

## Threat model

DataPulse MY is read-only: Pages serves static artifacts and MCP tools read the
published manifest and health snapshot. The main risks are malicious or
unexpected upstream content, resource exhaustion, stale/misleading generated
state, browser-probe compromise, dependency vulnerabilities, and accidental
secret publication. MCP does not provide repository, filesystem, or upstream
write tools.

Treat all source responses as untrusted. Keep timeouts, response-size limits,
strict JSON parsing, fixed output fields, and reverse-proxy rate limits. Do not
render upstream HTML into privileged pages.

## Secrets

Never commit API keys, tunnel credentials, cookies, TLS private keys, GitHub
tokens, or Camofox session data. GitHub secrets belong in Actions secrets;
Cloudflare credentials and TLS keys belong in root- or user-restricted deployed
paths outside the repository. Samples and logs must be reviewed for personal
data and authentication material before publication.
