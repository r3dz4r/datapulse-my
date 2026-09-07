#!/usr/bin/env python3
"""Generate signed daily probe attestations and unsigned trust scores."""
from __future__ import annotations
import argparse, base64, hashlib, json, shutil, subprocess, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ZERO = "0" * 64
ATTESTATION_MAX_AGE_SECONDS = 36 * 60 * 60
def canonical(value: object) -> bytes: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
def sha(value: bytes) -> str: return hashlib.sha256(value).hexdigest()
def parse_time(value: str) -> datetime: return datetime.fromisoformat(value.replace("Z", "+00:00"))
def load(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8"))
def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def sign(private: Ed25519PrivateKey, payload: dict) -> str: return base64.b64encode(private.sign(canonical(payload))).decode()

def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())

def _fetch_json(url: str) -> dict | None:
    """Fetch one allowlisted Singapore catalog/realtime response."""
    try:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; DataPulseMY/1.0; +https://www.data-pulse.my)",
            },
        )
        response = urllib.request.urlopen(request, timeout=10)
        try:
            if getattr(response, "status", 200) != 200:
                return None
            payload = json.loads(response.read())
        finally:
            response.close()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None

def enrich_sg_metadata(manifest: list[dict], probe_policy: dict) -> list[dict]:
    """Fill Singapore manifest metadata from catalog APIs or policy fallbacks."""
    static = probe_policy.get("sg_static_metadata", {})
    if not isinstance(static, dict):
        static = {}
    api_count = 0
    static_count = 0
    metadata_cache: dict[str, dict | None] = {}
    for entry in manifest:
        dataset_id = entry.get("id")
        url = entry.get("url")
        if not isinstance(dataset_id, str) or not dataset_id.startswith("sg_"):
            continue
        source: dict[str, object] | None = None
        from_api = False
        if isinstance(url, str) and url.startswith("https://api-production.data.gov.sg/v2/public/api/datasets/"):
            metadata_url = url.rsplit("/", 1)[0] + "/metadata"
            if metadata_url not in metadata_cache:
                metadata_cache[metadata_url] = _fetch_json(metadata_url)
            payload = metadata_cache[metadata_url]
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, dict):
                source = {
                    "title": data.get("name"),
                    "description": data.get("description"),
                    "publisher": data.get("managedBy"),
                    "last_updated_at": data.get("lastUpdatedAt"),
                    "frequency": entry.get("frequency") or entry.get("refresh_frequency"),
                }
                from_api = True
        elif isinstance(url, str) and url.startswith("https://api.data.gov.sg/v1/environment/"):
            payload = _fetch_json(url)
            items = payload.get("items") if isinstance(payload, dict) else None
            timestamp = items[0].get("timestamp") if isinstance(items, list) and items and isinstance(items[0], dict) else None
            source = {"last_updated_at": timestamp, "frequency": "realtime"}
        elif isinstance(url, str) and url.startswith("https://api.data.gov.sg/v1/transport/"):
            source = {"last_updated_at": "realtime (no static updated_at)", "frequency": "realtime"}
        else:
            source = {}
        fallback = static.get(dataset_id)
        if not isinstance(fallback, dict):
            fallback = {}
        if source is None or not any(_nonempty(source.get(field)) for field in ("title", "description", "publisher")):
            source = {**fallback, **(source or {})}
            if dataset_id == "sg_datagov_coe_bidding":
                source["last_updated_at"] = "not provided by catalog API"
        else:
            for field, value in fallback.items():
                source.setdefault(field, value)
        if from_api:
            api_count += 1
        else:
            static_count += 1
        for field in ("title", "description", "publisher", "last_updated_at", "frequency"):
            if not _nonempty(entry.get(field)) and source.get(field) is not None:
                entry[field] = source[field]
    print(f"enriched {api_count + static_count} sg_ datasets ({api_count} from API, {static_count} from static map)")
    return manifest

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

def reuse_existing_day(root: Path, day: str) -> bool:
    """Verify an immutable dated set before refreshing the derived latest view."""
    dated = root / "attestations" / day
    if not dated.exists():
        return False
    if not dated.is_dir():
        raise ValueError("same-day attestation is corrupt or inconsistent: dated set is not a directory")
    required = ("binding.json", "chain_head.json", "index.json", "scores.json")
    present = [name for name in required if (dated / name).is_file()]
    if not present:
        # Fresh-day Sigstore preparation may already have written its Rekor
        # inputs below this directory; it has not created a dated set yet.
        return False
    if len(present) != len(required):
        raise ValueError("same-day attestation is corrupt or inconsistent: dated set is incomplete")
    try:
        from scripts.verify_attestation_binding import ContractError, _load, _verify_legacy_plane, _verify_signature, verify_rekor_evidence
    except ModuleNotFoundError:
        from verify_attestation_binding import ContractError, _load, _verify_legacy_plane, _verify_signature, verify_rekor_evidence
    try:
        binding = _load(dated / "binding.json", "same-day binding")
        index = _load(dated / "index.json", "same-day attestation index")
        head = _load(dated / "chain_head.json", "same-day chain head")
        _load(dated / "scores.json", "same-day trust scores")
        payload = binding.get("payload")
        if (
            binding.get("schema") != "datapulse/v1/attestation-binding-envelope"
            or not isinstance(payload, dict)
            or payload.get("schema") != "datapulse/v1/attestation-binding"
            or payload.get("date") != day
            or payload.get("ed25519", {}).get("chain_head") != head.get("chain_head")
            or payload.get("ed25519", {}).get("chain_head_ref") != f"attestations/{day}/chain_head.json"
        ):
            raise ContractError("same-day binding does not match its dated chain head")
        registry = _load(root / "docs/.well-known/datapulse-probe-keys.json", "probe key registry")
        key_id = payload.get("ed25519", {}).get("key_id")
        matches = [row for row in registry.get("keys", []) if isinstance(row, dict) and row.get("key_id") == key_id]
        if len(matches) != 1:
            raise ContractError("same-day attestation key is missing or ambiguous")
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(matches[0]["public_key_base64"], validate=True))
        _verify_signature(public, payload, binding.get("signature_base64"), "same-day binding")
        rekor = binding.get("rekor")
        claims = {"artifact_signed": rekor is not None, "rekor_witnessed": rekor is not None, "source_truth_verified": False}
        if binding.get("claims") != claims:
            raise ContractError("same-day binding claims do not match its evidence")
        if rekor is not None:
            health = payload.get("health")
            if not isinstance(health, dict) or not isinstance(health.get("artifact_sha256"), str):
                raise ContractError("same-day binding health claim is invalid")
            verify_rekor_evidence(root, rekor, health["artifact_sha256"])
        _verify_legacy_plane(root, index, head, public, matches[0])
        chain_index = _load(root / "attestations/chain-index.json", "chain index")
        refs = [ref for ref in chain_index.get("heads", {}).values() if isinstance(ref, str) and ref.startswith(f"attestations/{day}/")]
        if refs != [f"attestations/{day}/chain_head.json"]:
            raise ContractError("duplicate-date attestation ambiguity detected")
    except (ContractError, KeyError, TypeError, ValueError) as error:
        raise ValueError(f"same-day attestation is corrupt or inconsistent: {error}") from error
    latest = root / "attestations" / "latest"
    if latest.exists(): shutil.rmtree(latest)
    latest.mkdir(parents=True)
    for filename in ("chain_head.json", "index.json", "scores.json", "binding.json"):
        shutil.copy2(dated / filename, latest / filename)
    return True

def generate(root: Path, key_path: Path, now: datetime, rekor_reference: Path | None = None) -> None:
    day=now.date().isoformat()
    manifest_path = root / "datapulse.json"
    manifest = load(manifest_path)
    policy_path = root / "scripts/probe-policy.json"
    if policy_path.is_file():
        enrich_sg_metadata(manifest.get("datasets", []), load(policy_path))
        dump(manifest_path, manifest)
    latest = root / "attestations" / "latest"
    latest_date=load(latest/"index.json").get("date") if (latest/"index.json").exists() else None
    if isinstance(latest_date,str) and latest_date>day:
        raise ValueError("older dated attestation cannot supersede latest")
    if reuse_existing_day(root, day):
        return
    manifest, health, trends, drift, recon = load_score_inputs(root); key=load(key_path)
    private=Ed25519PrivateKey.from_private_bytes(base64.b64decode(key["private_key_base64"])); public=base64.b64decode(key["public_key_base64"])
    if private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)!=public: raise ValueError("private and public key do not match")
    registry=load(root/"docs/.well-known/datapulse-probe-keys.json"); row=next((r for r in registry["keys"] if r["key_id"]==key["key_id"]),None)
    if row is None or registry.get("current_key_id")!=key["key_id"] or row.get("status")!="active" or not(parse_time(row["not_before"])<=now<=parse_time(row["not_after"])): raise ValueError("signing key is not active")
    generated_at=now.replace(microsecond=0).isoformat().replace("+00:00","Z"); base=root/"attestations"; dated=base/day; health_claim=health_binding(root,health); rekor=rekor_binding(root,rekor_reference,health_claim["artifact_sha256"])
    previous=load(latest/"chain_head.json")["chain_head"] if (latest/"chain_head.json").exists() else ZERO
    hp=root/"health/history.jsonl"; history=[json.loads(line) for line in hp.read_text(encoding="utf-8").splitlines() if line.strip()] if hp.exists() else []; health_by={r["dataset_id"]:r for r in health["datasets"]}; links=[]; refs={}
    for entry in sorted(manifest["datasets"],key=lambda r:r["id"]):
        did=entry["id"]; h=health_by.get(did,{}); observed=h.get("last_checked") or health["checked_at"]; cutoff14=now-timedelta(days=14); cutoff1=now-timedelta(days=1); times=[parse_time(r["observed_at"]) for r in history if r.get("dataset_id")==did and r.get("observed_at")]; fp=h.get("first_row_hash"); browser=h.get("access_dependency")=="browser"
        payload={"schema":"datapulse/v1/probe-attestation","date":day,"observed_at":observed,"dataset_id":did,"source_url":entry["url"],"observed_request_url":h.get("request_url"),"access_dependency":h.get("access_dependency","direct"),"probe_count_14d":sum(t>=cutoff14 for t in times),"probe_count_24h":sum(t>=cutoff1 for t in times),"last_status":h.get("status"),"last_staleness_days":h.get("staleness_days"),"content_fingerprint":{"scheme":"shape-v1:sha256","scope":"first-row-or-headers","value":fp} if fp else None,"browser_receipt":{"available":False,"reason":"probe runner emitted no signed receipt" if browser else None},"previous_chain_head":previous,"key_id":key["key_id"],"signer_pubkey_base64":key["public_key_base64"]}
        link=sha(bytes.fromhex(previous)+canonical(payload)); ref=f"attestations/{day}/{did}.json"; envelope={"schema":"datapulse/v1/probe-attestation-envelope","payload":payload,"signature_base64":sign(private,payload),"chain_link":link,"verification_level":"L1-capable"}; Ed25519PublicKey.from_public_bytes(public).verify(base64.b64decode(envelope["signature_base64"]),canonical(payload)); dump(root/ref,envelope); links.append({"dataset_id":did,"chain_link":link}); refs[did]=ref
    head_payload={"schema":"datapulse/v1/daily-chain-head","date":day,"previous_chain_head":previous,"dataset_count":len(links),"dataset_links_sha256":sha(canonical(links)),"key_id":key["key_id"]}; chain_head=sha(bytes.fromhex(previous)+canonical(head_payload)); head={"schema":"datapulse/v1/daily-chain-head-envelope","payload":head_payload,"signature_base64":sign(private,head_payload),"chain_head":chain_head,"dataset_links":links,"anchor":{"tag":None,"commit":None,"anchored":False}}; dump(dated/"chain_head.json",head)
    chain_index=load(base/"chain-index.json") if (base/"chain-index.json").exists() else {"schema":"datapulse/v1/chain-index","heads":{},"anchors":{}}
    if any(isinstance(ref,str) and ref.startswith(f"attestations/{day}/") for ref in chain_index.get("heads",{}).values()): raise ValueError("duplicate-date attestation already exists in chain index")
    chain_index["heads"][chain_head]=f"attestations/{day}/chain_head.json"; chain_index["anchors"].update(discover_git_anchors(root)); dump(base/"chain-index.json",chain_index); dump(dated/"index.json",{"schema":"datapulse/v1/attestation-index","date":day,"chain_head_ref":f"attestations/{day}/chain_head.json","binding_ref":f"attestations/{day}/binding.json","attestations":refs}); dump(dated/"scores.json",score_rows(manifest,health,trends,drift,recon,generated_at)); binding=binding_envelope(private,day,generated_at,health_claim,head,key["key_id"],rekor); Ed25519PublicKey.from_public_bytes(public).verify(base64.b64decode(binding["signature_base64"]),canonical(binding["payload"])); dump(dated/"binding.json",binding)
    if latest.exists(): shutil.rmtree(latest)
    latest.mkdir(parents=True)
    for filename in ("chain_head.json","index.json","scores.json","binding.json"): shutil.copy2(dated/filename,latest/filename)
    for entry in manifest["datasets"]: entry["attestation_ref"]=refs[entry["id"]]; entry["methodology_version"]=3
    dump(root/"datapulse.json",manifest)

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parent.parent); parser.add_argument("--private-key",type=Path,required=True); parser.add_argument("--now"); parser.add_argument("--rekor-reference",type=Path); args=parser.parse_args(); generate(args.root,args.private_key,parse_time(args.now) if args.now else datetime.now(timezone.utc),args.rekor_reference); return 0
if __name__=="__main__": raise SystemExit(main())
