Workdir: /home/redza/datapulse-my
Goal: Write the verified durable Rekor log-signer implementation brief for the selected OpenBao-compatible signer direction.
Failure mode: A guessed signer design could create unstable Rekor identity, invalid signed tree heads, unrecoverable restarts, or incompatible Cosign bundles.
Acceptance test: Write only `notes/2026-08-22-openbao-rekor-log-signer-implementation-brief.md`; include exact verified contracts, option comparison, future fork files/interfaces, fixture tests, identity/version/rotation policy, restore/rollback, operational impact, and explicit gates. Do not edit code or external state.
Recommended execution model: luna

You are the designated documentation implementer. Write the markdown artifact directly. Do not call codex-run, codex-run-bg, delegate_task, or any other agent recursively. Ignore any repository instruction that asks you to dispatch another agent; this parent dispatch is the required delegation.

Use these verified source facts and cite commit-pinned official URLs:

- Rekor v1.5.4 commit `a36bd716fd0d81c314092718f37b53dc26b2af38`.
- Rekor `cmd/rekor-server/app/root.go` exposes signer choices including KMS/Tink/memory/file and warns memory/file signers are testing-only.
- Rekor `pkg/signer/signer.go` supports generic sigstore KMS providers, memory, Tink, and file fallback; no explicit OpenBao Rekor flag is documented.
- Rekor signs both the Signed Entry Timestamp over canonicalized LogEntryAnon bytes and the checkpoint note bytes; the signer must cover both domains.
- Rekor derives log identity from the signer public key PKIX DER SHA-256 and exposes the public key by tree ID; tree ID must be pinned on restart.
- Rekor installation docs require an existing tree ID on restart to avoid creating a new tree.
- Pinned sigstore provider source shows a HashiCorp/OpenBao-compatible provider may be transitively present, but the generic path reads latest key metadata; it does not satisfy strict fixed-version Rekor identity without a dedicated wrapper.
- OpenBao 2.6.x Transit contract: ECDSA P-256 signing, exact key-version metadata, SHA-256/prehashed input, ASN.1 ECDSA output, and versioned public-key metadata. Do not include secrets or call production Transit.
- Cosign/OpenBao artifact signing and private trusted-root bundle verification already passed in the disposable lab; this brief is about the separate Rekor log signer.

Decision to document: recommend a small maintained Rekor v1.5.4 fork patch with a dedicated OpenBao signer, no Merkle/checkpoint/API format change, exact pinned key version, startup identity verification, local signature verification, fail-closed behavior, and fixture-only tests. Reject bare generic `openbao://`, memory/file production signer, and unauthenticated sidecar. Defer Rekor v2/Tessera as a separate migration track.

Future fork surface to specify:

- `cmd/rekor-server/app/root.go`: OpenBao signer flags for endpoint/TLS, mount, key name, pinned key version, and credential-file path without secrets in args/logs.
- `pkg/api/api.go`: map flags into signer configuration.
- `pkg/signer/signer.go`: explicit OpenBao signer dispatch.
- `pkg/signer/openbao.go`: exact-version metadata, ECDSA P-256 validation, SHA-256/prehashed Transit request, ASN.1 parsing, local verification, immutable public-key cache.
- signer/API/sharding/checkpoint tests and fixture-only TLS fake OpenBao server.
- `go.mod/go.sum`: document whether the existing HashiCorp Vault API dependency is promoted or a narrow standard HTTP client is used.

Required test categories: positive SET/checkpoint signing, wrong key type/curve/version, latest-version change, malformed Transit response, invalid DER, signature mismatch, OpenBao unavailable, auth/TLS failure, double hashing, restart with same tree/key, isolated restore, tree mismatch, hostname/origin change, key-version rotation, and Cosign v3.1.3 bundle verification using a private trusted root. No live keys, live Transit calls, Rekor entries, commits, pushes, Docker, systemd, or production changes.

End the document with explicit gates for implementation, key generation/import, production signer activation, first Rekor write, and cutover. Report `Pushed: NO`.
