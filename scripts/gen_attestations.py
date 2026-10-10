#!/usr/bin/env python3
"""Generate signed daily probe attestations and unsigned trust scores."""
from __future__ import annotations
import argparse, base64, hashlib, json, shutil, subprocess, tempfile, os, fcntl, sys
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.verify_attestation_binding import ContractError
from scripts.attestation_sets import discovery, verify_set, descriptor, validate_discovery, correction_record, set_directory, FILES, append_content_digest, rekor_content

ZERO = "0" * 64
ATTESTATION_MAX_AGE_SECONDS = 36 * 60 * 60
ATTESTATION_KEY_PURPOSE = "attestation-chain-signing"
PROBE_COUNTS_SCHEMA = "datapulse/v1/probe-counts"
PROBE_COUNTS_MAX_AGE_SECONDS = 48 * 60 * 60
def canonical(value: object) -> bytes: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
def sha(value: bytes) -> str: return hashlib.sha256(value).hexdigest()
def parse_time(value: str) -> datetime: return datetime.fromisoformat(value.replace("Z", "+00:00"))
def load(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8"))
def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def sign(private: Ed25519PrivateKey, payload: dict) -> str: return base64.b64encode(private.sign(canonical(payload))).decode()

def health_binding(root: Path, health: dict) -> dict:
    datasets = health.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ValueError("health datasets must be a non-empty array")
    dataset_ids = [row.get("dataset_id") for row in datasets if isinstance(row, dict)]
    if len(dataset_ids) != len(datasets) or any(not isinstance(item, str) or not item for item in dataset_ids) or len(dataset_ids) != len(set(dataset_ids)):
        raise ValueError("health dataset ids must be unique non-empty strings")
    checked_at = health.get("checked_at")
    if not isinstance(checked_at, str):
        raise ValueError("health checked_at must be an ISO-8601 string")
    parse_time(checked_at)
    return {
        "artifact_ref":"health/latest.json",
        "artifact_sha256":sha((root/"health/latest.json").read_bytes()),
        "dataset_count":len(dataset_ids),
        "dataset_ids_sha256":sha(canonical(sorted(dataset_ids))),
        "observed_at":checked_at,
    }

def binding_envelope(private: Ed25519PrivateKey, day: str, generated_at: str, health_claim: dict, head: dict, key_id: str, rekor: dict | None = None) -> dict:
    payload={
        "schema":"datapulse/v1/attestation-binding",
        "date":day,
        "published_at":generated_at,
        "freshness":{"max_age_seconds":ATTESTATION_MAX_AGE_SECONDS},
        "health":health_claim,
        "ed25519":{"chain_head_ref":f"attestations/{day}/chain_head.json","chain_head":head["chain_head"],"key_id":key_id,"key_status":"active"},
    }
    return {
        "schema":"datapulse/v1/attestation-binding-envelope",
        "payload":payload,
        "signature_base64":sign(private,payload),
        "claims":{"artifact_signed":rekor is not None,"rekor_witnessed":rekor is not None,"source_truth_verified":False},
        "rekor":rekor,
    }

def rekor_binding(root: Path, reference: Path | None, expected_digest: str) -> dict | None:
    if reference is None:
        return None
    try:
        reference_ref=reference.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise ValueError("Rekor reference must be inside the repository") from error
    document=load(reference)
    bundle=document.get("bundle")
    if not isinstance(bundle,str):
        raise ValueError("Rekor reference is missing its bundle reference")
    bundle_path=Path(bundle)
    if bundle_path.is_absolute():
        try: bundle_ref=bundle_path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError as error: raise ValueError("Rekor bundle must be inside the repository") from error
    else:
        try: bundle_ref=(reference.parent/bundle_path).resolve().relative_to(root.resolve()).as_posix()
        except ValueError as error: raise ValueError("Rekor bundle must be inside the repository") from error
    if not (root/bundle_ref).is_file():
        raise ValueError("Rekor bundle reference does not exist")
    metadata={"reference_ref":reference_ref,"bundle_ref":bundle_ref}
    try:
        from scripts.verify_attestation_binding import verify_rekor_evidence
    except ModuleNotFoundError:
        from verify_attestation_binding import verify_rekor_evidence
    verify_rekor_evidence(root,metadata,expected_digest)
    return metadata

def discover_git_anchors(root: Path) -> dict[str, dict[str, str]]:
    if not (root / ".git").exists():
        return {}
    anchors = {}; result = subprocess.run(["git", "tag", "--list", "v[0-9]*"], cwd=root, text=True, capture_output=True)
    if result.returncode: return anchors
    for tag in result.stdout.splitlines():
        shown = subprocess.run(["git", "show", f"{tag}:.attestations/chain_head.json"], cwd=root, text=True, capture_output=True)
        if shown.returncode: continue
        try: head = json.loads(shown.stdout)["chain_head"]
        except (json.JSONDecodeError, KeyError, TypeError): continue
        commit = subprocess.run(["git", "rev-list", "-n", "1", tag], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
        if len(head) == 64 and len(commit) == 40: anchors[head] = {"tag":tag, "commit":commit}
    return anchors

STATUS_SCORE = {"fresh":100,"reference":90,"aging":65,"stale":20,"degraded":10,"unreachable":0,"discontinued":0,"browser-dependent":50,"unknown":50,"unknown-freshness":50}
TREND_SCORE = {"recovering":100,"stable":75,"deteriorating":25,"insufficient_data":50}
DRIFT_SCORE = {"stable":100,"record_count_drift":40,"drift_detected":0,"insufficient_data":50}
RECON_SCORE = {"agree":100,"different_granularity":50,"discrepancy":0,"insufficient_data":50,"single_source":50}

# methodology_version 3 separates component availability from numeric values.
# A score has a 25-point floor, while datasets stale for at least a year are capped at 30:
# a lone observed component must not produce an absolute-zero verdict or mask confirmed staleness.
SCORE_WEIGHTS = {"freshness":.30,"reliability":.30,"trend":.20,"drift":.10,"cross_source_agreement":.10}
CLASSIFIED_FRESHNESS_STATUSES = {"browser-dependent", "unknown", "unknown-freshness", "reference", "discontinued"}
AVAILABILITY_REASONS = {"measured", "classified", "insufficient_history", "not_applicable", "missing_record", "unknown_status"}

def _availability(available: bool, reason: str) -> dict:
    assert reason in AVAILABILITY_REASONS
    return {"available": available, "reason": reason}

def component_values_and_availability(did: str, h: dict | None, t: dict | None, d: dict | None, reconciliation_verdict: str | None) -> tuple[dict, dict]:
    h_status = h.get("status") if h else None
    trend = t.get("trend") if t else None
    drift_verdict = d.get("verdict") if d else None
    reliability = t.get("publish_on_time_pct") if t else None
    numeric_reliability = isinstance(reliability, (int, float)) and not isinstance(reliability, bool)
    components = {"freshness": STATUS_SCORE.get(h_status, 50), "reliability": reliability if numeric_reliability else 50, "trend": TREND_SCORE.get(trend, 50), "drift": DRIFT_SCORE.get(drift_verdict, 50), "cross_source_agreement": RECON_SCORE.get(reconciliation_verdict or "single_source", 50)}
    availability = {
        "freshness": _availability(False, "missing_record") if h is None else _availability(True, "classified") if h_status in CLASSIFIED_FRESHNESS_STATUSES else _availability(True, "measured") if h_status in STATUS_SCORE else _availability(False, "unknown_status"),
        "reliability": _availability(True, "measured") if numeric_reliability else _availability(False, "missing_record") if t is None or reliability is None else _availability(False, "unknown_status"),
        "trend": _availability(False, "missing_record") if t is None else _availability(False, "insufficient_history") if trend == "insufficient_data" else _availability(True, "measured") if trend in TREND_SCORE else _availability(False, "unknown_status"),
        "drift": _availability(False, "missing_record") if d is None else _availability(False, "insufficient_history") if drift_verdict == "insufficient_data" else _availability(True, "measured") if drift_verdict in DRIFT_SCORE else _availability(False, "unknown_status"),
        "cross_source_agreement": _availability(False, "not_applicable") if reconciliation_verdict is None else _availability(False, "insufficient_history") if reconciliation_verdict == "insufficient_data" else _availability(True, "measured") if reconciliation_verdict in RECON_SCORE else _availability(False, "unknown_status"),
    }
    assert components.keys() == availability.keys()
    return components, availability

def load_score_inputs(root: Path) -> tuple[dict, dict, dict, dict, dict]:
    return tuple(load(root / path) for path in ("datapulse.json", "health/latest.json", "health/trends.json", "health/drift.json", "health/reconciliation.json"))

def score_rows(manifest: dict, health: dict, trends: dict, drift: dict, recon: dict, generated_at: str) -> dict:
    hs={r["dataset_id"]:r for r in health["datasets"]}; ts={r["dataset_id"]:r for r in trends["datasets"]}; ds={r["dataset_id"]:r for r in drift["datasets"]}; rs={m["id"]:g["verdict"] for g in recon["groups"] for m in g["members"]}; rows=[]
    for entry in manifest["datasets"]:
        did=entry["id"]; h=hs.get(did); t=ts.get(did); d=ds.get(did)
        components, component_availability = component_values_and_availability(did, h, t, d, rs.get(did))
        present_components={name:value for name,value in components.items() if component_availability[name]["available"]}
        present_weight_sum=sum(SCORE_WEIGHTS[name] for name in present_components)
        value=round(sum(SCORE_WEIGHTS[name]/present_weight_sum*value for name,value in present_components.items()),1) if present_weight_sum else 50.0
        value=max(value,25.0)
        if h and h.get("status")=="stale" and (h.get("staleness_days") or 0)>=365: value=min(value,30.0)
        rows.append({"dataset_id":did,"methodology_version":3,"score":value,"components":components,"component_availability":component_availability,"observed_at":h.get("last_checked") if h else None})
    return {"schema":"datapulse/v1/trust-scores","generated_at":generated_at,"methodology_version":3,"datasets":rows}

def refresh_manifest_refs(root: Path, directory: str) -> None:
    """Derive mutable manifest references from the selected immutable index."""
    index = load(root / directory / "index.json")
    original_index = root / "attestations" / index["date"] / "index.json"
    if original_index.is_file():
        original = load(original_index)
        if load(root / original["chain_head_ref"])["chain_head"] == load(root / index["chain_head_ref"])["chain_head"]:
            index = original
    refs = index["attestations"]
    manifest = load(root / "datapulse.json")
    for entry in manifest["datasets"]:
        entry["attestation_ref"] = refs[entry["id"]]
        entry["methodology_version"] = 3
    dump(root / "datapulse.json", manifest)


def promote(root: Path, directory: str) -> None:
    """Refresh only the named mutable projections from verified immutable bytes."""
    latest = root / "attestations/latest"
    latest.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        shutil.copy2(root / directory / filename, latest / filename)
    mirror = root / ".attestations/chain_head.json"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / directory / "chain_head.json", mirror)
    refresh_manifest_refs(root, directory)


def agrees(root: Path, directory: str, manifest: dict, health_claim: dict, registry: dict, rekor: dict | None) -> bool:
    """Ignore generated refs and execution time when comparing accepted inputs."""
    binding = load(root / directory / "binding.json")
    index = load(root / directory / "index.json")
    if (binding["payload"]["health"] != health_claim
            or binding["payload"]["ed25519"]["key_id"] != registry.get("current_key_id")
            or set(index["attestations"]) != {r["id"] for r in manifest["datasets"]}
            or (rekor is not None and rekor_content(root, binding.get("rekor")) != rekor_content(root, rekor))):
        return False
    return all(load(root / index["attestations"][r["id"]])["payload"]["source_url"] == r["url"] for r in manifest["datasets"])


def load_probe_counts(root: Path, now: datetime) -> dict | None:
    """Return a fresh, schema-valid count map, or None when unusable.

    The absent artefact is the honest-unknown case; a present-but-stale or
    malformed artefact is rejected outright so its plausible numbers never
    stand in for an observation the run cannot actually confirm.
    """
    try:
        document = load(root / "health/probe_counts.json")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(document, dict) or document.get("schema") != PROBE_COUNTS_SCHEMA:
        return None
    generated_at = document.get("generated_at")
    if not isinstance(generated_at, str):
        return None
    try:
        generated = parse_time(generated_at)
    except ValueError:
        return None
    if generated.tzinfo is None:
        return None
    if now - generated > timedelta(seconds=PROBE_COUNTS_MAX_AGE_SECONDS):
        return None
    counts = document.get("counts")
    return counts if isinstance(counts, dict) else None

def probe_counts_for_dataset(counts: dict, dataset_id: str) -> tuple[int | None, int | None]:
    """Map one dataset's artifact entry to (14d, 24h); absence is null, never zero."""
    record = counts.get(dataset_id)
    if not isinstance(record, dict):
        return (None, None)
    d14, d1 = record.get("d14"), record.get("d1")
    if not isinstance(d14, int) or isinstance(d14, bool) or not isinstance(d1, int) or isinstance(d1, bool):
        return (None, None)
    return (d14, d1)

def _generate(root: Path, key_path: Path, now: datetime, rekor_reference: Path | None = None, force_append: bool = False) -> None:
    day=now.date().isoformat()
    latest = root / "attestations" / "latest"
    latest_date=load(latest/"index.json").get("date") if (latest/"index.json").exists() else None
    if isinstance(latest_date,str) and latest_date>day:
        raise ValueError("older dated attestation cannot supersede latest")
    manifest, health, trends, drift, recon = load_score_inputs(root)
    ids = [r["id"] for r in manifest["datasets"]]
    if len(ids) != len(set(ids)) or set(ids) != {r["dataset_id"] for r in health["datasets"]}:
        raise ValueError("catalogue and health dataset IDs disagree")
    chain_index = discovery(root)
    previous = chain_index["current_head"] or ZERO
    if previous != ZERO and load(root / chain_index["heads"][previous])["payload"]["date"] > day:
        raise ValueError("older dated attestation cannot supersede latest")
    health_claim = health_binding(root, health)
    registry = load(root / "docs/.well-known/datapulse-probe-keys.json")
    rekor = rekor_binding(root, rekor_reference, health_claim["artifact_sha256"])
    if previous != ZERO:
        directory = chain_index["heads"][previous].rsplit("/", 1)[0]
        verify_set(root, chain_index["heads"][previous])
        if not force_append and load(root / chain_index["heads"][previous])["payload"]["date"] == day and agrees(root, directory, manifest, health_claim, registry, rekor):
            from scripts.verify_attestation_binding import _registry_key, _parse_time
            _registry_key(registry, registry.get("current_key_id"), _parse_time(load(root / directory / "binding.json")["payload"]["published_at"], "published"), now)
            observed = parse_time(health_claim["observed_at"])
            published = parse_time(load(root / directory / "binding.json")["payload"]["published_at"])
            if now < observed or now < published or max((now-observed).total_seconds(), (now-published).total_seconds()) > ATTESTATION_MAX_AGE_SECONDS:
                raise ValueError("served attestation is stale or in the future")
            revision = root / directory / "revisions" / previous
            promote(root, revision.relative_to(root).as_posix() if revision.is_dir() else directory)
            dump(root / "attestations/chain-index.json", chain_index)
            return
    key=load(key_path)
    private=Ed25519PrivateKey.from_private_bytes(base64.b64decode(key["private_key_base64"])); public=base64.b64decode(key["public_key_base64"])
    if private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)!=public: raise ValueError("private and public key do not match")
    registry=load(root/"docs/.well-known/datapulse-probe-keys.json"); row=next((r for r in registry["keys"] if r["key_id"]==key["key_id"]),None)
    if row is None or registry.get("schema") != "datapulse/v2/probe-key-registry" or registry.get("current_key_id")!=key["key_id"] or row.get("purpose") != ATTESTATION_KEY_PURPOSE or row.get("public_key_base64") != key["public_key_base64"] or row.get("status")!="active" or not(parse_time(row["not_before"])<=now<=parse_time(row["not_after"])): raise ValueError("signing key is not active")
    generated_at=now.replace(microsecond=0).isoformat().replace("+00:00","Z"); base=root/"attestations"; dated=base/day; health_claim=health_binding(root,health); rekor=rekor_binding(root,rekor_reference,health_claim["artifact_sha256"])
    pc_path=root/"health/probe_counts.json"; pc_present=pc_path.exists() and pc_path.stat().st_size>0; probe_artifact=load_probe_counts(root,now) if pc_present else None
    hp=root/"health/history.jsonl"; history_available=hp.exists() and hp.stat().st_size>0; use_history=history_available and not pc_present; history=[json.loads(line) for line in hp.read_text(encoding="utf-8").splitlines() if line.strip()] if use_history else []; health_by={r["dataset_id"]:r for r in health["datasets"]}; links=[]; refs={}
    envelopes = {}
    for entry in sorted(manifest["datasets"],key=lambda r:r["id"]):
        did=entry["id"]; h=health_by.get(did,{}); observed=h.get("last_checked") or health["checked_at"]; cutoff14=now-timedelta(days=14); cutoff1=now-timedelta(days=1); times=[parse_time(r["observed_at"]) for r in history if r.get("dataset_id")==did and r.get("observed_at")]; probe_counts=probe_counts_for_dataset(probe_artifact,did) if probe_artifact is not None else ((sum(t>=cutoff14 for t in times),sum(t>=cutoff1 for t in times)) if use_history else (None,None)); fp=h.get("first_row_hash"); browser=h.get("access_dependency")=="browser"
        payload={"schema":"datapulse/v1/probe-attestation","date":day,"observed_at":observed,"dataset_id":did,"source_url":entry["url"],"observed_request_url":h.get("request_url"),"access_dependency":h.get("access_dependency","direct"),"probe_count_14d":probe_counts[0],"probe_count_24h":probe_counts[1],"last_status":h.get("status"),"last_staleness_days":h.get("staleness_days"),"content_fingerprint":{"scheme":"shape-v1:sha256","scope":"first-row-or-headers","value":fp} if fp else None,"browser_receipt":{"available":False,"reason":"probe runner emitted no signed receipt" if browser else None},"previous_chain_head":previous,"key_id":key["key_id"],"signer_pubkey_base64":key["public_key_base64"]}
        link=sha(bytes.fromhex(previous)+canonical(payload)); ref=f"attestations/{day}/{did}.json"; envelope={"schema":"datapulse/v1/probe-attestation-envelope","payload":payload,"signature_base64":sign(private,payload),"chain_link":link,"verification_level":"L1-capable"}; Ed25519PublicKey.from_public_bytes(public).verify(base64.b64decode(envelope["signature_base64"]),canonical(payload)); envelopes[did] = envelope; links.append({"dataset_id":did,"chain_link":link}); refs[did]=ref
    run = chain_index["days"].get(day, [])
    correction = None
    if run:
        predecessor = run[-1]
        if predecessor != previous:
            raise ValueError("same-day correction predecessor disagrees with discovery")
        prior_binding = load(root / set_directory(chain_index["heads"][predecessor]) / "binding.json")
        correction = correction_record(day, run[0], predecessor, prior_binding["payload"]["health"]["artifact_sha256"], health_claim["artifact_sha256"])
        if (root / correction["health_snapshot_ref"]).exists():
            raise ValueError("correction revision already exists but is not indexed")
    head_payload={"schema":"datapulse/v1/daily-chain-head","date":day,"previous_chain_head":previous,"dataset_count":len(links),"dataset_links_sha256":sha(canonical(links)),"key_id":key["key_id"]}
    if correction is not None:
        head_payload["correction"] = correction
    scores = score_rows(manifest,health,trends,drift,recon,generated_at)
    binding = binding_envelope(private,day,generated_at,health_claim,{"chain_head": ZERO},key["key_id"],rekor)
    if correction is not None:
        binding["payload"]["correction"] = correction
    witness = rekor_content(root, rekor)
    head_payload["append_content_sha256"] = append_content_digest(
        head_payload, envelopes, scores, binding["payload"], witness)
    chain_head=sha(bytes.fromhex(previous)+canonical(head_payload)); head={"schema":"datapulse/v1/daily-chain-head-envelope","payload":head_payload,"signature_base64":sign(private,head_payload),"chain_head":chain_head,"dataset_links":links,"anchor":{"tag":None,"commit":None,"anchored":False}}
    directory = f"attestations/{day}/revisions/{chain_head}"
    dated = root / directory
    if dated.exists() and any((dated / name).exists() for name in FILES):
        raise ValueError("same-day attestation is corrupt or inconsistent: destination already exists")
    refs = {did: f"{directory}/{did}.json" for did in envelopes}
    for did, envelope in envelopes.items():
        dump(root / refs[did], envelope)
        # The first daily envelope remains a served legacy URL. Corrections
        # only append revision paths and must never replace that day's alias.
        if not run:
            legacy = base / day / f"{did}.json"
            if legacy.exists():
                if load(legacy) != envelope:
                    raise ValueError("legacy dataset attestation cannot be overwritten")
            else:
                dump(legacy, envelope)
    dump(dated / "chain_head.json", head)
    dump(dated / "index.json", {"schema": "datapulse/v1/attestation-index", "date": day,
        "chain_head_ref": directory + "/chain_head.json", "binding_ref": directory + "/binding.json", "attestations": refs})
    dump(dated / "scores.json", scores)
    binding["payload"]["ed25519"]["chain_head"] = chain_head
    binding["payload"]["ed25519"]["chain_head_ref"] = directory + "/chain_head.json"
    if witness is not None:
        dump(dated / "rekor-reference.json", witness["reference"])
        dump(dated / "rekor-bundle.json", witness["bundle"])
        use_served_rekor = rekor["reference_ref"].startswith(f"attestations/rekor/{day}/")
        binding["rekor"] = {"reference_ref": rekor["reference_ref"] if use_served_rekor else directory + "/rekor-reference.json",
                            "bundle_ref": rekor["bundle_ref"] if use_served_rekor else directory + "/rekor-bundle.json"}
        # The served-plane fetch follows binding proof references. Retain the
        # producer's dated Rekor URLs alongside the immutable revision copies.
        if rekor["reference_ref"].startswith(f"attestations/rekor/{day}/"):
            binding["rekor"].update({"historical_reference_ref": rekor["reference_ref"],
                                     "historical_bundle_ref": rekor["bundle_ref"]})
            if not run:
                binding["rekor"].update({f"dataset_{did}_ref": f"attestations/{day}/{did}.json"
                                         for did in envelopes})
    binding["signature_base64"] = sign(private, binding["payload"])
    dump(dated / "binding.json", binding)
    # Preserve the exact raw health input beside the signed set so a same-day
    # correction can be verified against its recorded bytes, not the mutable
    # health alias. A correction also pins its new input in the content-addressed
    # snapshot named by its signed record.
    health_bytes = (root / "health/latest.json").read_bytes()
    (dated / "health.json").write_bytes(health_bytes)
    chain_head_ref = directory + "/chain_head.json"
    if not run:
        # Keep the original day's historical verification plane while the
        # append set itself remains isolated by its content-addressed path.
        original = base / day
        if any((original / name).exists() for name in FILES):
            raise ValueError("original daily attestation already exists but is not indexed")
        for name in ("chain_head.json", "scores.json"):
            shutil.copy2(dated / name, original / name)
        original_index = load(dated / "index.json")
        original_index["chain_head_ref"] = f"attestations/{day}/chain_head.json"
        original_index["binding_ref"] = f"attestations/{day}/binding.json"
        original_index["attestations"] = {did: f"attestations/{day}/{did}.json" for did in envelopes}
        dump(original / "index.json", original_index)
        dump(original / "binding.json", binding_envelope(
            private, day, generated_at, health_claim, head, key["key_id"], rekor))
        (original / "health.json").write_bytes(health_bytes)
        chain_head_ref = original_index["chain_head_ref"]
    if correction is not None:
        correction_snapshot = root / correction["health_snapshot_ref"]
        correction_snapshot.parent.mkdir(parents=True, exist_ok=True)
        correction_snapshot.write_bytes(health_bytes)
    verify_set(root, directory + "/chain_head.json")
    if not run:
        verify_set(root, chain_head_ref)
    chain_index["heads"][chain_head] = chain_head_ref
    chain_index["envelopes"][chain_head] = descriptor(head, chain_head_ref, len(run) + 1)
    chain_index["days"].setdefault(day, []).append(chain_head)
    chain_index["current_head"] = chain_head
    for digest, anchor in discover_git_anchors(root).items():
        if digest in chain_index["anchors"] and chain_index["anchors"][digest] != anchor:
            raise ValueError("existing anchor cannot be replaced")
        chain_index["anchors"].setdefault(digest, anchor)
    validate_discovery(root, chain_index)
    dump(base / "chain-index.json", chain_index)
    promote(root, directory)


@contextmanager
def writer_lock(directory: Path):
    """Lock the evidence directory without adding a tracked lock file."""
    fd = os.open(directory, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def generate(root: Path, key_path: Path, now: datetime, rekor_reference: Path | None = None, force_append: bool = False) -> None:
    """Prepare and validate privately, then accept under a repository writer lock."""
    root = root.resolve()
    key_path = key_path.resolve()
    now = now.astimezone(timezone.utc)
    base = root / ".attestations"
    base.mkdir(parents=True, exist_ok=True)
    with writer_lock(base):
        paths = ["datapulse.json", "health/latest.json", "health/trends.json", "health/drift.json", "health/reconciliation.json", "health/history.jsonl", "health/probe_counts.json", "docs/.well-known/datapulse-probe-keys.json"]
        snapshots = {p: (root / p).read_bytes() for p in paths if (root / p).is_file()}
        index_path = root / "attestations/chain-index.json"
        original_index = index_path.read_bytes() if index_path.exists() else None
        source = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True).stdout
        with tempfile.TemporaryDirectory(prefix="candidate-", dir=base) as temporary:
            staging = Path(temporary)
            for path, data in snapshots.items():
                target = staging / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            if (root / "attestations").exists():
                shutil.copytree(root / "attestations", staging / "attestations")
            if (base / "chain_head.json").exists():
                (staging / ".attestations").mkdir()
                shutil.copy2(base / "chain_head.json", staging / ".attestations/chain_head.json")
            reference = staging / rekor_reference.resolve().relative_to(root) if rekor_reference else None
            try:
                _generate(staging, key_path, now, reference, force_append)
            except (ValueError, KeyError, TypeError, OSError) as error:
                error_type = ContractError if isinstance(error, ContractError) else ValueError
                raise error_type(f"same-day attestation is corrupt or inconsistent: {error}") from error
            if (source != subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True).stdout
                    or original_index != (index_path.read_bytes() if index_path.exists() else None)
                    or any((root / p).read_bytes() != data for p, data in snapshots.items())):
                raise ValueError("accepted source/head or canonical inputs changed during preparation")
            # Frozen --now fixtures need no wall-clock check; live callers check midnight.
            candidate = load(staging / "attestations/chain-index.json")
            directory = candidate["heads"][candidate["current_head"]].rsplit("/", 1)[0]
            revision = staging / directory / "revisions" / candidate["current_head"]
            if revision.is_dir():
                directory = revision.relative_to(staging).as_posix()
            destination = root / directory
            immutable_index = load(staging / directory / "index.json")
            day = immutable_index["date"]
            candidate_correction = load(staging / directory / "binding.json").get("payload", {}).get("correction")
            snapshot_directory = candidate_correction["health_snapshot_ref"].rsplit("/", 1)[0] if isinstance(candidate_correction, dict) else None
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.rename(staging / directory, destination)
            elif any((destination / name).read_bytes() != (staging / directory / name).read_bytes() for name in FILES):
                raise ValueError("immutable destination cannot be overwritten")
            if len(candidate["days"][day]) == 1:
                for name in (*FILES, "health.json"):
                    source_alias = staging / "attestations" / day / name
                    alias = root / "attestations" / day / name
                    if alias.exists():
                        if alias.read_bytes() != source_alias.read_bytes():
                            raise ValueError("original daily attestation cannot be overwritten")
                    else:
                        os.rename(source_alias, alias)
                for reference in immutable_index["attestations"].values():
                    name = Path(reference).name
                    source_alias = staging / "attestations" / day / name
                    alias = root / "attestations" / day / name
                    if alias.exists():
                        if alias.read_bytes() != source_alias.read_bytes():
                            raise ValueError("legacy dataset attestation cannot be overwritten")
                    else:
                        alias.parent.mkdir(parents=True, exist_ok=True)
                        os.rename(source_alias, alias)
            if snapshot_directory is not None:
                snapshot_destination = root / snapshot_directory
                if not snapshot_destination.exists():
                    snapshot_destination.parent.mkdir(parents=True, exist_ok=True)
                    os.rename(staging / snapshot_directory, snapshot_destination)
                elif (snapshot_destination / "health.json").read_bytes() != (staging / snapshot_directory / "health.json").read_bytes():
                    raise ValueError("immutable correction snapshot cannot be overwritten")
            mutable = ["attestations/chain-index.json", "datapulse.json", ".attestations/chain_head.json"] + ["attestations/latest/" + n for n in FILES]
            backup = {p: (root / p).read_bytes() if (root / p).exists() else None for p in mutable}
            try:
                for path in mutable:
                    target = root / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    pending = target.with_name(target.name + ".tmp")
                    pending.write_bytes((staging / path).read_bytes())
                    os.replace(pending, target)
            except BaseException:
                for path, data in backup.items():
                    target = root / path
                    if data is None:
                        target.unlink(missing_ok=True)
                    else:
                        target.write_bytes(data)
                raise


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parent.parent); parser.add_argument("--private-key",type=Path,required=True); parser.add_argument("--now"); parser.add_argument("--rekor-reference",type=Path); parser.add_argument("--force-append", action="store_true"); args=parser.parse_args(); generate(args.root,args.private_key,parse_time(args.now) if args.now else datetime.now(timezone.utc),args.rekor_reference, args.force_append); return 0
if __name__=="__main__": raise SystemExit(main())
