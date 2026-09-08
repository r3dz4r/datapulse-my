# Additive quality-profile reconciliation

Date: 2026-09-08

## Decision

`scripts/gen_quality_profile.py` derives an additive `quality_profile` for each
row in `health/latest.json`. The profile is a deterministic, machine-readable
metadata/evidence readiness profile. It is not a universal quality score,
semantic-truth claim, certification, safety claim, or admission decision.

The policy is `datapulse-quality-readiness/v1`; the profile version is
`datapulse-quality-profile/v1`. Dimensions are ordered as `fair`, `licensing`,
`provenance`, `governance`, `reproducibility`, and `catalogue_readiness`.

## Evidence mapping and boundaries

| Dimension | Existing inputs | What the check says | Boundary |
| --- | --- | --- | --- |
| fair | manifest identity, URL, licence/attribution; health URL/status and shape metadata | declared catalogue/reuse metadata and one observed access/shape signal | does not establish FAIR compliance, continued access, or semantic interoperability |
| licensing | manifest licence and attribution | declarations are present | no legal interpretation or licence validation |
| provenance | manifest URL, steward/custodian; health request URL and observation time | declared and observed source boundary is recorded | does not establish authority or truth; URL disagreement remains a conflict |
| governance | manifest methodology version and cadence; health status/reason slot | declared method/cadence and status-reason field are present | does not establish institutional governance or publisher compliance |
| reproducibility | health shape, retrieval time and count; manifest attestation reference | recorded probe metadata and reference are present | does not promise response replay, count completeness, or verify the reference |
| catalogue_readiness | manifest ID/name/steward/source/report; paired health ID and input schema validation | this manifest/snapshot pair is structurally sufficient for the named policy | does not validate semantic content or external identity |

Each check carries stable reason codes, source/path evidence references, and a
limitation. `pass` means only the stated bounded check passed. `fail` records a
known observed failure (currently an unreachable or discontinued access
observation). Missing or ambiguous signals are `unknown`, never neutral,
zero, pass, or `not_applicable`. The single explicit `not_applicable` rule is
the declared cadence check for manifest `data_type` `reference` or
`policy-reference`, because these types intentionally have no freshness clock.

Dimension coverage reports applicable, evaluated, pass, fail, unknown, and
not-applicable check counts. A dimension is `fail` if any check fails,
`unknown` if no check fails and any is unknown, `not_applicable` if every
check is explicitly not applicable, and `pass` only when every check is pass
or explicitly not applicable. Overall is `not_ready` if any dimension fails,
`indeterminate` if no dimension fails and any is unknown, and `ready` only
when every dimension is pass or explicitly not applicable; unknown is never
collapsed.

## External producer handoff

The probe/timer that first writes `health/latest.json` is outside this
repository (`datapulse-pipeline.sh` in the operator-managed dotfiles). Do not
modify it from this lane. After its probe output passes runtime validation and
before downstream history, attestation, dashboard, or deployment consumers,
the operator-managed pipeline must run:

```bash
python3 /home/redza/datapulse-my/scripts/gen_quality_profile.py \
  --manifest /home/redza/datapulse-my/datapulse.json \
  --health /home/redza/datapulse-my/health/latest.json
```

The command validates both inputs against the repository schemas, enriches the
health snapshot atomically in place, then validates the enriched output. It
does not use network access, keys, trust roots, services, deployment state, or
upstream calls. If input validation, full manifest/health parity, or output
validation fails, it writes no profile. This is the required external handoff;
the local generator and tests are deliberately the public artifact path in this
repository without editing operator-managed infrastructure.
