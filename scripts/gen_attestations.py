#!/usr/bin/env python3
"""Generate signed daily probe attestations and unsigned trust scores."""
from __future__ import annotations
import argparse, base64, hashlib, json, shutil, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ZERO = "0" * 64
def canonical(value: object) -> bytes: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
def sha(value: bytes) -> str: return hashlib.sha256(value).hexdigest()
def parse_time(value: str) -> datetime: return datetime.fromisoformat(value.replace("Z", "+00:00"))
def load(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8"))
def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def sign(private: Ed25519PrivateKey, payload: dict) -> str: return base64.b64encode(private.sign(canonical(payload))).decode()

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

def generate(root: Path, key_path: Path, now: datetime) -> None:
    manifest, health, trends, drift, recon = load_score_inputs(root); key=load(key_path)
    private=Ed25519PrivateKey.from_private_bytes(base64.b64decode(key["private_key_base64"])); public=base64.b64decode(key["public_key_base64"])
    if private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)!=public: raise ValueError("private and public key do not match")
    registry=load(root/"docs/.well-known/datapulse-probe-keys.json"); row=next((r for r in registry["keys"] if r["key_id"]==key["key_id"]),None)
    if row is None or row.get("status")!="active" or not(parse_time(row["not_before"])<=now<=parse_time(row["not_after"])): raise ValueError("signing key is not active")
    day=now.date().isoformat(); base=root/"attestations"; dated=base/day; latest=base/"latest"; previous=load(latest/"chain_head.json")["chain_head"] if (latest/"chain_head.json").exists() else ZERO
    hp=root/"health/history.jsonl"; history=[json.loads(line) for line in hp.read_text(encoding="utf-8").splitlines() if line.strip()] if hp.exists() else []; health_by={r["dataset_id"]:r for r in health["datasets"]}; links=[]; refs={}
    for entry in sorted(manifest["datasets"],key=lambda r:r["id"]):
        did=entry["id"]; h=health_by.get(did,{}); observed=h.get("last_checked") or health["checked_at"]; cutoff14=now-timedelta(days=14); cutoff1=now-timedelta(days=1); times=[parse_time(r["observed_at"]) for r in history if r.get("dataset_id")==did and r.get("observed_at")]; fp=h.get("first_row_hash"); browser=h.get("access_dependency")=="browser"
        payload={"schema":"datapulse/v1/probe-attestation","date":day,"observed_at":observed,"dataset_id":did,"source_url":entry["url"],"observed_request_url":h.get("request_url"),"access_dependency":h.get("access_dependency","direct"),"probe_count_14d":sum(t>=cutoff14 for t in times),"probe_count_24h":sum(t>=cutoff1 for t in times),"last_status":h.get("status"),"last_staleness_days":h.get("staleness_days"),"content_fingerprint":{"scheme":"shape-v1:sha256","scope":"first-row-or-headers","value":fp} if fp else None,"browser_receipt":{"available":False,"reason":"probe runner emitted no signed receipt" if browser else None},"previous_chain_head":previous,"key_id":key["key_id"],"signer_pubkey_base64":key["public_key_base64"]}
        link=sha(bytes.fromhex(previous)+canonical(payload)); ref=f"attestations/{day}/{did}.json"; envelope={"schema":"datapulse/v1/probe-attestation-envelope","payload":payload,"signature_base64":sign(private,payload),"chain_link":link,"verification_level":"L1-capable"}; Ed25519PublicKey.from_public_bytes(public).verify(base64.b64decode(envelope["signature_base64"]),canonical(payload)); dump(root/ref,envelope); links.append({"dataset_id":did,"chain_link":link}); refs[did]=ref
    head_payload={"schema":"datapulse/v1/daily-chain-head","date":day,"previous_chain_head":previous,"dataset_count":len(links),"dataset_links_sha256":sha(canonical(links)),"key_id":key["key_id"]}; chain_head=sha(bytes.fromhex(previous)+canonical(head_payload)); head={"schema":"datapulse/v1/daily-chain-head-envelope","payload":head_payload,"signature_base64":sign(private,head_payload),"chain_head":chain_head,"dataset_links":links,"anchor":{"tag":None,"commit":None,"anchored":False}}; dump(dated/"chain_head.json",head)
    chain_index=load(base/"chain-index.json") if (base/"chain-index.json").exists() else {"schema":"datapulse/v1/chain-index","heads":{},"anchors":{}}; chain_index["heads"][chain_head]=f"attestations/{day}/chain_head.json"; chain_index["anchors"].update(discover_git_anchors(root)); dump(base/"chain-index.json",chain_index); generated_at=now.replace(microsecond=0).isoformat().replace("+00:00","Z"); dump(dated/"index.json",{"schema":"datapulse/v1/attestation-index","date":day,"chain_head_ref":f"attestations/{day}/chain_head.json","attestations":refs}); dump(dated/"scores.json",score_rows(manifest,health,trends,drift,recon,generated_at))
    if latest.exists(): shutil.rmtree(latest)
    latest.mkdir(parents=True)
    for filename in ("chain_head.json","index.json","scores.json"): shutil.copy2(dated/filename,latest/filename)
    for entry in manifest["datasets"]: entry["attestation_ref"]=refs[entry["id"]]; entry["methodology_version"]=3
    dump(root/"datapulse.json",manifest)

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parent.parent); parser.add_argument("--private-key",type=Path,required=True); parser.add_argument("--now"); args=parser.parse_args(); generate(args.root,args.private_key,parse_time(args.now) if args.now else datetime.now(timezone.utc)); return 0
if __name__=="__main__": raise SystemExit(main())
