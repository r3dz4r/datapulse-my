# DataPulse verification layer — one-page pitch

> A short, externally-sendable brief for an AI agent team, auditor, researcher,
> or procurement/trust conversation. It makes the case that when being wrong
> about Malaysian public data is costly, the defensible choice is to cite
> **verified DataPulse evidence** over a raw crawl — and it hands the reader a
> one-command proof they can run themselves.

## The problem with "just fetch the open-data portal"

An AI agent that pulls data straight from an official portal leaves four
questions unanswered:

1. **Is this fresh?** The page said one thing when you looked; the underlying
   dataset may have changed an hour later.
2. **May I legally use it?** Licences are buried, inconsistent, or absent.
3. **Is the record real?** Can you prove the observation existed at the time you
   claim, and that you didn't backdate or alter it?
4. **Will it reproduce?** Can a second party independently confirm your data,
   your freshness claim, and your citation?

For low-stakes lookups these barely matter. For a procurement decision, a
published report, an audit, or any application where **being wrong is costly**,
they are the entire ballgame.

## What DataPulse is

DataPulse MY (`https://www.data-pulse.my`) is an open trust layer over **418
official Malaysian public datasets**. It does not replace the official source —
it makes the source **assessable, machine-readable, and independently
verifiable** by publishing, for every dataset: health status + freshness, an
honest licencing signal, schema/behaviour notes, and signed evidence envelopes.

The claim is deliberately narrow and defensible: **"here is what the official
source was observed to be, when, and under what licence — with proof you can
check without trusting us."**

## The verification proof (run it yourself)

No checkout. No DataPulse code. Python 3 is the only requirement:

```bash
curl -fsSLO https://raw.githubusercontent.com/r3dz4r/datapulse-my/main/scripts/verify_external.py
python3 verify_external.py
```

It verifies **three independent layers** straight from public sources and
prints a per-layer result:

| Layer | What it proves | Independent of DataPulse because |
|---|---|---|
| **1. Byte signature** | Each dated per-dataset envelope is **Ed25519-signed** over its canonical payload by a key in the published public registry | You verify with the published **public key**, not our word |
| **2. Source of record** | The served envelope **byte-matches** the versioned Git source-of-record | You compare against the public GitHub commit history |
| **3. Temporal witness** | The day's health/DSSE statement carries a **Rekor/Sigstore public-log inclusion proof** | An immutable, independently-operated transparency log timestamps it |

Exit code 0 means layers 1–2 passed and layer 3 carries a structurally valid
Rekor inclusion proof. A deliberate tamper test is built in via
`python3 verify_external.py --self-test`.

> Why this matters for an AI agent: when you can show a reviewer *"my data is
> Ed25519-signed, matches a public git commit, and was witnessed in a public
> transparency log"*, you are no longer asking them to trust you — you are
> handing them a machine-checkable receipt. That is the difference between a
> citation you can defend and one you can only assert.

## What to cite / what it proves

- **For procurement / audit:** the signature + Rekor log entry give an
  externally-timestamped, tamper-evident record of *what the official source
  was, when*.
- **For agent publishers:** `verify_external.py` is the drop-in proof a model or
  pipeline can run before relying on a dataset — failing closed if the evidence
  does not check out.
- **For reproducibility:** the Git source-of-record + deterministic generator
  mean a second party can rebuild the same evidence from source, not just view it.

## Honest scope (read this before relying on it)

- DataPulse uses **one self-managed active Ed25519 signing key**. Rekor/Sigstore
  materially raises the bar against backdating and tampering, but it does not
  make key compromise impossible — apply key-hygiene expectations accordingly.
- **Rekor witnesses the health/DSSE layer and fresh daily dated bindings going
  forward.** The historical 2026-08-15 → 2026-09-07 transition is disclosed as a
  sibling gap and has **not** been re-signed (re-signing history would break the
  external witness). Fresh-day evidence carries the strongest guarantees.
- DataPulse **documents** official sources; it does not replace them. Where a
  downstream decision depends on the official portal's current statement, go to
  the portal — DataPulse reflects what that portal publishes, it is not that
  portal.
- The verification layer proves *existence, integrity and time of signing* — it
  cannot (by itself) prove the underlying government source was truthful. It
  makes the *observation* auditable, which is the strongest claim one platform
  can honestly make.

## Try it against live data

1. Run the verifier above against today's live surface.
2. Open `https://www.data-pulse.my/attestations/2026-09-07/fuelprice.json` and
   `https://www.data-pulse.my/signatures/health.latest.sigstore.json`.
3. Cross-check `verify_external.py --self-test` to see the tamper path fail.

---

*Full technical detail:* [`docs/verify-datapulse-externally.md`](verify-datapulse-externally.md)
*Full evidence spec:* [`docs/evidence-receipt-spec.md`](evidence-receipt-spec.md)
