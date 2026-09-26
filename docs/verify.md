---
audience: auditor, governance reviewer, procurement, agent builder
canonical: true
volatility: contract
owner: operator
review_trigger: when the signing chain, the probe key registry, the verifier, or the receipt format changes
last_verified: 2026-09-26
---

# Verify a DataPulse claim

This page is the front door for independent verification. A second party with nothing but a shell should be able to reproduce what DataPulse asserts, see what a pass does and does not establish, and recognise the failure states.

Every command and every output below was run against the live estate on **2026-09-26**. Output is quoted verbatim, including the parts that are not flattering.

## Path A — reproduce the whole published chain, with no DataPulse installation

The verifier is a single Python file that needs only Python 3. It performs three independent checks over public HTTPS and prints one result line per layer.

```bash
curl -fsSLO https://raw.githubusercontent.com/r3dz4r/datapulse-my/main/scripts/verify_external.py
```

```bash
python3 verify_external.py
```

Observed output on 2026-09-26:

```text
LAYER 1 PASS: Ed25519 canonical-payload signature for 2026-09-26/air_pollution using ed25519-a829715828ba0f88
LAYER 2 PASS: served envelope matches GitHub main; latest chain head equals 2026-09-26 dated head
LAYER 3 PASS (importable evidence present; Rekor not independently refetched: Rekor public log: could not fetch valid JSON (HTTP Error 404: Not Found))
```

The command exits zero only when the first two layers pass and the third contains a structurally valid inclusion proof. Note the layer 3 wording: when the public log cannot be re-queried, the output says so rather than claiming a re-fetch that did not happen. That honesty is the point of the layer, not a defect in it.

The verifier can also prove its own failure path offline, against a known-good fixture and a deliberately tampered one:

```bash
python3 verify_external.py --self-test
```

Observed output on 2026-09-26:

```text
SELF-TEST PASS: known signature verified and deliberately tampered payload failed
```

### What each layer establishes

| Layer | Establishes | Source of truth |
|---|---|---|
| 1 — Signature | The dated dataset envelope was signed by a key in the published registry, over those exact bytes | the probe key registry at `/.well-known/datapulse-probe-keys.json` |
| 2 — Source of record | The served envelope byte-matches the versioned Git record, and the `latest` chain head equals the dated head | the public repository on the main branch |
| 3 — Temporal witness | The health statement carries a transparency-log entry with an inclusion proof whose Merkle root reconstructs | the Rekor public log |

## Path B — verify one dataset's evidence receipt

Every dataset publishes a signed evidence receipt. The MCP server returns the verification command as structured data rather than prose, so a caller never has to transcribe it by hand. For the dataset with id `air_pollution`, the served `verification_hint` is:

```text
(
  tmpdir=$(mktemp -d) || exit 1
  trap 'rm -rf "$tmpdir"' EXIT
  curl --fail --location --proto '=https' --proto-redir '=https' --silent --show-error --output "$tmpdir/receipt.sigstore.json" https://data-pulse.my/data/air_pollution.receipt.sigstore.json && \
  curl --fail --location --proto '=https' --proto-redir '=https' --silent --show-error --output "$tmpdir/receipt.evidence.json" https://data-pulse.my/data/air_pollution.receipt.evidence.json && \
  cosign verify-blob-attestation --bundle "$tmpdir/receipt.sigstore.json" --certificate-identity https://github.com/r3dz4r/datapulse-my/.github/workflows/deploy-cloudflare-pages.yml@refs/heads/main --certificate-oidc-issuer https://token.actions.githubusercontent.com --type https://www.data-pulse.my/predicates/per-dataset-evidence/v1 "$tmpdir/receipt.evidence.json"
)
```

Run that snippet as-is; it exits zero only on a verified receipt. Observed output on 2026-09-26:

```text
Verified OK
```

The certificate identity matters and is not guessable: the receipt is signed by the repository's deploy workflow through GitHub's OIDC issuer, not by a hand-run job, and `cosign` fails closed when the identity or issuer does not match. Guessing the identity produces this, which is a useful control in its own right:

```text
Error: failed to verify certificate identity: no matching CertificateIdentity found
```

### The failure states, verbatim

A tampered payload — one byte appended to the evidence file — under an otherwise valid signature:

```text
Error: failed to verify signature: provided artifact digests do not match digests in statement
```

A receipt that does not exist returns **HTTP 404** from both the evidence path and the bundle path after redirect resolution. There is no soft failure and no fallback that quietly substitutes an older receipt.

An unknown dataset id asked over MCP returns a structured tool error rather than an empty result:

```text
Error calling tool 'verify_dataset': Unknown dataset id: not_a_real_dataset
```

## Trust anchors

| Anchor | Where | Why it matters |
|---|---|---|
| Probe key registry | `/.well-known/datapulse-probe-keys.json` | Carries the key id, algorithm, validity window, a `status` that includes `superseded`, the key it `supersedes`, and `compromised_at`. A key with no rotation semantics is a liability rather than an anchor |
| Attestation chain head | `/observation-receipts/chain_head.json` and the dated head under `attestations/` | A published head makes omission and reordering of observations detectable, not merely a failed signature |
| Signature identity | `https://github.com/r3dz4r/datapulse-my/.github/workflows/deploy-cloudflare-pages.yml@refs/heads/main` | Pins verification to the project's own deploy workflow through GitHub's OIDC issuer |
| Public log | the Rekor transparency entry on the health statement | An independent temporal witness outside DataPulse's own infrastructure |

## What a pass does not prove

Verification here establishes **integrity, provenance of the observation, and timing**. It does not establish that an upstream publisher's figures are true, complete, or suitable for your purpose. In particular:

- a valid signature proves who signed and that the bytes did not change, not that the underlying government figure is correct;
- a fresh status means the content is within the source's declared cadence window, not that it is suitable for every use;
- a receipt shows what DataPulse observed at a time, not an independent re-observation of the publisher;
- the historical window from 2026-08-15 to 2026-09-07 is disclosed as a sibling gap and has not been retrospectively re-signed.

Non-coverage is stated rather than implied: DataPulse does not certify truth, does not replace the official source, and does not write to it. That boundary is owned by [Trust contract](trust-contract.md).

## Go deeper

- [Verify DataPulse externally](verify-datapulse-externally.md) — the verifier's three layers in implementation detail
- [Evidence receipt specification](evidence-receipt-spec.md) — the receipt's structure and interpretation
- [Reproducibility](reproducibility.md) — release, observation and claim reproducibility
- [Release verification](release-verification.md) — the current release's proof of provenance
- [Trust contract](trust-contract.md) — what the product does and does not assert
