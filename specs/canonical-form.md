# Canonical JSON form

**Status:** normative specification
**Applies to:** every payload signed or digested by this repository
**Reference implementation:** `canonical()` in `scripts/gen_attestations.py` (line 12)
**Test vectors:** `scripts/tests/fixtures/canonical_vectors.json`
**Enforcement:** `scripts/tests/test_canonical_vectors.py`

This document pins the bytes that a signature covers. It is descriptive of the
implementation that already exists: it does not change `scripts/gen_attestations.py`
and does not change the live chain.

## Why this exists

Two implementations can serialise the same logical payload differently — a
different key order, a different whitespace convention, an escaped or unescaped
non-ASCII character — and still both verify, because the signature is checked
against each implementation's own bytes. The digests then differ while every
signature remains valid, so the binding between the signed payload and the
artifact it is supposed to cover fails silently. A canonicalisation rule plus
positive, negative, and canonical-form vectors makes that failure mode
impossible to miss.

## Scope: the bytes a signature covers

The canonical form of a value is exactly the reference implementation:

```python
json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
```

which is returned as the bytes `canonical(value)`. A signature covers
`canonical(payload)` and nothing else.

For the daily probe attestation, the signed value is the `payload` object, not
the envelope that transports it. The envelope fields — `schema`,
`signature_base64`, `chain_link`, `verification_level`, `chain_head`,
`dataset_links`, `anchor`, `claims`, `rekor`, and the pretty-printed formatting
on disk — are not covered. A verifier must extract `payload`, canonicalise it,
and verify the signature over those bytes. Re-serialising the whole envelope, or
canonicalising it as written on disk, produces different bytes and must fail.

The same rule covers every derived digest in the chain:

```text
chain_link              = sha256(previous_chain_head_bytes || canonical(payload))
dataset_links_sha256    = sha256(canonical(links))
chain_head              = sha256(previous_chain_head_bytes || canonical(head_payload))
```

where `previous_chain_head_bytes` is the 32 raw bytes decoded from the
64-character hex head, not the hex text.

## Normative rules

A producer that signs, and a verifier that checks, MUST apply all of the
following.

1. **UTF-8 without a BOM.** The canonical bytes are the UTF-8 encoding of the
   JSON text. No byte-order mark (`EF BB BF`) may precede them. A BOM changes
   the first byte of the signed input and therefore the digest.
2. **No insignificant whitespace.** Separators are exactly `,` and `:` with no
   spaces, newlines, or indentation. `indent` must never be used for signed
   material; pretty-printing is for human-readable files only.
3. **Keys sorted.** Object keys are sorted with `sort_keys=True`, which is
   Python's ascending Unicode code-point order. Two objects with the same
   members in different insertion orders canonicalise identically.
4. **No trailing newline.** A trailing `\n` is not part of the canonical bytes.
   The newline that `dump()` appends when writing an envelope to disk is
   formatting, not signed material.
5. **Unicode preserved as UTF-8, not escaped.** `ensure_ascii=False` means a
   non-ASCII character is emitted as its UTF-8 octets and never rewritten as a
   `\uXXXX` escape. An escaped rendering is a different byte string with a
   different digest even though it parses to the same string.
6. **Integers exact.** JSON integers round-trip exactly, including values
   outside the binary64 exactly-representable range (for example
   `9007199254740993`). The signer must not coerce an integer through a float.
7. **No NaN or Infinity.** `NaN`, `Infinity`, and `-Infinity` are not valid
   JSON under RFC 8259. They must never appear in signed material. A
   non-conformant serialiser can emit them (Python's `json.dumps` does by
   default), so a verifier must reject them explicitly rather than parse them
   leniently.
8. **Duplicate keys rejected.** A JSON object may not repeat a member name. The
   canonical form has no way to express a duplicate key, so a parser that keeps
   "last value wins" silently discards evidence. Parsing for signed material
   must use an `object_pairs_hook` that raises on a repeated key.
9. **Decoded data model in, bytes out.** `canonical()` takes the already-decoded
   Python value (`dict`, `list`, `str`, `int`, `bool`, `None`) and returns
   `bytes`. It does not parse text; parsing and duplicate/BOM/non-finite
   rejection happen before it.
10. **Array order is significant and preserved.** JSON arrays are ordered.
    Canonicalisation never sorts an array; only object members are sorted.
11. **No Unicode normalisation.** `canonical()` does not apply NFC, NFD, NFKC,
    or any other normalisation. Two visually similar strings that differ in
    normal form are different values with different canonical bytes. A producer
    that wants normalised text must normalise the value before signing and must
    record that choice in the schema.
12. **No floats in signed payloads.** See the dedicated section below. This is a
    producer-and-verifier contract obligation, not something `canonical()`
    enforces by itself.

### What the reference implementation does and does not enforce

`canonical()` faithfully applies rules 1–6, 9, 10, and 11 for the values it is
given. It cannot enforce the input restrictions on its own:

- Python's `json.dumps` allows `NaN`/`Infinity` by default, so `canonical()`
  will happily return `b'{"value":NaN}'`. The spec forbids that value; the
  rejection belongs at parse/validation time.
- `canonical()` receives a decoded `dict`, so duplicate keys have already been
  collapsed by a lenient parser. The rejection belongs at parse time, before
  `canonical()` is called.

Producers MUST validate the data model before signing, and verifiers MUST reject
non-finite numbers and duplicate keys before trusting a digest. The negative
vectors in `scripts/tests/fixtures/canonical_vectors.json` assert exactly these
cross-checks.

## Integers, floats, and portability

Signed payloads MUST use integers, booleans, strings, null, arrays, and objects.
They MUST NOT contain JSON numbers with a fractional part or an exponent. A
conceptually fractional quantity must be encoded as an integer with a declared
scale, as a pair of integers, or as a decimal string with the scale fixed by the
schema.

The reason is portability, not aesthetics. JSON does not define one
representation for a non-integer number. Different languages and JSON libraries
choose different shortest round-trip spellings (`100.0`, `1e2`, `1.0E+2`), and
binary64 cannot represent every integer (`9007199254740993` becomes
`9007199254740992`). The same logical value can therefore produce different
canonical bytes and different digests depending on which language serialised
it — the exact silent binding failure this specification exists to prevent.
Integers avoid the problem because their JSON syntax has one representation and
can be carried exactly.

## Relationship to RFC 8785 (JCS)

This form overlaps with the JSON Canonicalization Scheme (RFC 8785) on object
key sorting, no insignificant whitespace, no trailing newline, and UTF-8
encoding, and it agrees with JCS for the ASCII-keyed, integer-valued payloads
this repository signs today. It is a narrower profile, not a JCS
implementation:

- JCS defines a number format that includes non-integers; this form prohibits
  non-integers in signed payloads instead.
- JCS sorts keys by UTF-16 code units; Python's `sort_keys=True` sorts by
  Unicode code point. The two orderings agree for all Basic Multilingual Plane
  keys and can disagree when a key contains a character outside the BMP (an
  astral-plane character, represented in UTF-16 as a surrogate pair). No current
  signed payload uses such a key. A future payload that does MUST pin the
  intended ordering explicitly rather than assume the two rules agree.
- JCS does not forbid duplicate keys at the serialiser; this form does.

Do not claim RFC 8785 conformance for `canonical()`.

## What breaks historical verification of `.attestations/chain_head.json`

`.attestations/chain_head.json` and the dated heads under `attestations/` are
the published outputs of the chain rule in "Scope" above. Because every link and
every head is `sha256(previous_chain_head_bytes || canonical(...))`, any change
to the canonical bytes changes every derived digest. Historical signatures
still present on disk will no longer verify against a re-derived payload, and
the published chain heads will no longer reproduce.

The changes that break verification are, at minimum:

- appending a trailing newline to the signed bytes;
- prefixing a UTF-8 BOM;
- switching to `ensure_ascii=True`;
- switching separators to the `json.dumps` defaults `(", ", ": ")`, to any
  other whitespace-bearing separators, or to a different character pair;
- adding `indent`;
- dropping or changing `sort_keys=True`;
- sorting keys by locale, by UTF-16, or by any rule other than Python code
  point;
- serialising with a different library that formats integers or strings
  differently;
- normalising Unicode before serialisation;
- changing the covered subtree, for example signing the whole envelope instead
  of `payload`;
- encoding the text as anything other than UTF-8.

**None of these may land without an explicit migration**: a new canonical
version identifier, a documented re-signing or dual-verification plan, and a
verifier that keeps accepting the historical form for the dates that used it.
Until such a migration is approved, `canonical()` is frozen and is verified
byte-for-byte by the vectors in this specification.

## Proposed evidence receipt fields that still need a canonical rule

The evidence receipt described in `docs/evidence-receipt-spec.md` and the
`trust-stack/v1.0.0` companions reference several values that are not yet
governed by the rule above. Until each has its own pinned rule, a signature over
the receipt MUST NOT assume that the generic `canonical(payload)` rule settles
these fields.

- **`returned_payload_hash`.** Ambiguous in four ways. (a) Does it cover the raw
  wire bytes of the response, the transport-decoded bytes (after gzip, Brotli,
  or chunked transfer), or the decoded character bytes? (b) Does it cover the
  exact retrieved octets, including any BOM, trailing newline, or trailing
  whitespace, or the canonical form of a parsed JSON value? (c) What charset
  decoding is applied before hashing, and what happens on invalid UTF-8?
  (d) Are response headers, status line, or redirects included? These choices
  produce different digests for the same logical response. The rule must say
  which one `returned_payload_hash` means and must state whether it is a
  byte-exact content digest or a canonical-payload digest. The two must not be
  conflated.
- **`transformation_lineage`.** Ambiguous in five ways. (a) Is the lineage an
  ordered array of steps or an unordered map keyed by step ID? (b) If ordered,
  what establishes the order, and is that order signed? (c) Does each step hash
  its input and output, and does a later step's digest chain the earlier step's
  digest, or are the hashes independent? (d) How are an empty lineage, a missing
  step, and an unavailable lineage distinguished from each other in bytes?
  (e) Are the step field names, software identifiers, versions, and parameters
  part of the hashed bytes, and are versions strings or integers? Today the
  dataset passports emit `transformation_lineage` as an `unavailable` object
  with a reason code, so no signed lineage exists yet; the rule must be pinned
  before one does.
- **Other receipt fields with the same gap.** `payload_digest` needs its covered
  subtree named (by analogy to the `payload` rule above). `schema_fingerprint`
  and `content_digest` need their covered bytes named. `provenance_refs`,
  `attestation_refs`, `artifact_ref`, and `artifact_sha256` need to say whether
  the digest is over exact file bytes or over a canonical form.
  `dataset_ids_sha256` is already pinned by `canonical(sorted(dataset_ids))`.
  `conflicts`, `limitations`, and `reason_codes` need a stable ordering rule so
  that two producers with the same set agree byte-for-byte. `created_at`,
  `observed_at`, `retrieved_at`, and the other timestamps need one timestamp
  serialisation (UTC RFC 3339 with `Z`, fixed fractional-second precision)
  pinned before they are signed. `contract_version`, `object_type`, and
  `object_id` need the digest-input fields for each object named.

Where a field already has a rule elsewhere, that rule owns it. Where it does
not, this document is the default only for values that are plain JSON objects,
arrays, strings, integers, booleans, and null.

## Enforcement

`scripts/tests/fixtures/canonical_vectors.json` contains three classes of
literal vector:

- **positive** — a logical payload, its exact canonical byte string, and the
  sha256 of those bytes;
- **negative** — a payload and a near-miss rendering that MUST NOT match the
  canonical bytes, with the reason it is wrong;
- **canonical-form** — two independently constructed representations of the
  same logical value that MUST produce identical bytes and digest.

`scripts/tests/test_canonical_vectors.py` imports `canonical` from
`scripts.gen_attestations` and asserts every vector. It does not reimplement
canonicalisation; the fixture is the contract.

## Non-goals

- This specification does not modify `scripts/gen_attestations.py`. The live
  chain depends on `canonical()` as written; this document records and tests it.
- It does not sign anything, generate keys, or read key material.
- It does not define a new canonical version, and it authorises no migration of
  the existing chain.
