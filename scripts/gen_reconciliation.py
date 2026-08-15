#!/usr/bin/env python3
"""Generate conservative cross-source dataset reconciliation evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime
from itertools import combinations
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "datapulse.json"
DEFAULT_HEALTH = ROOT / "health/latest.json"
DEFAULT_SEEDS = ROOT / "reconciliation_groups.json"
DEFAULT_OUTPUT = ROOT / "health/reconciliation.json"
SCHEMA = "datapulse/v1/dataset-reconciliation"
SEED_SCHEMA = "datapulse/v1/reconciliation-groups"
VERDICTS = ("agree", "discrepancy", "different_granularity", "insufficient_data")
PUBLISHER_PREFIX = re.compile(r"^(?:data\.gov\.my|opendosm|dosm)\s*[:\-–—]?\s*", re.I)
GRANULARITY_TERMS = (
    "national", "malaysia", "state", "district", "dun", "parlimen", "parliament",
    "constituency", "division", "class", "subclass", "sector", "age", "sex",
    "ethnic", "strata", "monthly", "quarterly", "annual", "daily", "hourly",
)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def normalise_words(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def semantic_title(value: Any) -> str:
    return normalise_words(PUBLISHER_PREFIX.sub("", str(value or "")).strip())


def canonical_url(value: Any) -> str:
    try:
        parsed = urlsplit(str(value))
    except ValueError:
        return ""
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunsplit((
        parsed.scheme.casefold(), parsed.netloc.casefold(), parsed.path.rstrip("/") or "/",
        urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True))), "",
    ))


def endpoint_channel(value: Any) -> str:
    try:
        return urlsplit(str(value)).netloc.casefold()
    except ValueError:
        return ""


def granularity_signature(entry: dict[str, Any]) -> tuple[str, ...]:
    words = set(normalise_words(f"{entry.get('id', '')} {entry.get('name', '')}").split())
    return tuple(term for term in GRANULARITY_TERMS if term in words)


def parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None


def availability_class(status: Any) -> str:
    value = str(status or "").casefold()
    if value in {"fresh", "aging", "stale", "unknown-freshness", "reference"}:
        return "available"
    if value in {"degraded", "unavailable", "discontinued"}:
        return "failed"
    return "unknown"


def validate_seeds(seeds: dict[str, Any], manifest_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if seeds.get("schema") != SEED_SCHEMA or not isinstance(seeds.get("groups"), list):
        raise ValueError(f"reconciliation seed file must use {SEED_SCHEMA}")
    keys: set[str] = set()
    claimed: set[str] = set()
    validated: list[dict[str, Any]] = []
    for group in seeds["groups"]:
        if not isinstance(group, dict) or not isinstance(group.get("key"), str):
            raise ValueError("every reconciliation seed group requires a string key")
        key = group["key"]
        members = group.get("members")
        relationship = group.get("relationship")
        comparison = group.get("comparison")
        if key in keys or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", key):
            raise ValueError(f"duplicate or invalid reconciliation seed key: {key}")
        if not isinstance(members, list) or len(members) < 2 or len(set(members)) != len(members):
            raise ValueError(f"seed group {key} requires at least two unique members")
        missing = sorted(set(members) - manifest_by_id.keys())
        overlap = sorted(set(members) & claimed)
        if missing or overlap:
            raise ValueError(f"seed group {key} has missing={missing} overlapping={overlap}")
        if relationship not in {"equivalent", "different_granularity"}:
            raise ValueError(f"seed group {key} has unsupported relationship")
        if not isinstance(comparison, dict) or comparison.get("record_count_policy") not in {"strict", "context_only"}:
            raise ValueError(f"seed group {key} requires a record_count_policy")
        keys.add(key)
        claimed.update(members)
        validated.append(group)
    return sorted(validated, key=lambda row: row["key"])


def discover_groups(manifest: dict[str, Any], seeds: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [row for row in manifest.get("datasets", []) if isinstance(row, dict) and isinstance(row.get("id"), str)]
    by_id = {row["id"]: row for row in entries}
    seed_groups = validate_seeds(seeds, by_id)
    claimed = {dataset_id for group in seed_groups for dataset_id in group["members"]}
    groups: list[dict[str, Any]] = [
        {
            "group_key": f"seed:{group['key']}", "logical_name": group["logical_name"],
            "grouping_method": "seed", "relationship": group["relationship"],
            "confidence": "reviewed", "member_ids": sorted(group["members"]),
            "record_count_policy": group["comparison"]["record_count_policy"],
            "record_count_tolerance_pct": float(group["comparison"].get("record_count_tolerance_pct", 5.0)),
            "content_date_tolerance_days": int(group["comparison"].get("content_date_tolerance_days", 2)),
            "rationale": group["rationale"],
        }
        for group in seed_groups
    ]
    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        if entry["id"] not in claimed and (url := canonical_url(entry.get("url"))):
            by_url[url].append(entry)
    for url, members in sorted(by_url.items()):
        if len(members) < 2:
            continue
        member_ids = sorted(row["id"] for row in members)
        claimed.update(member_ids)
        groups.append({
            "group_key": f"url:{hashlib.sha256(url.encode()).hexdigest()[:16]}",
            "logical_name": min(members, key=lambda row: row["id"])["name"],
            "grouping_method": "exact_url", "relationship": "equivalent",
            "confidence": "high", "member_ids": member_ids,
            "record_count_policy": "strict", "record_count_tolerance_pct": 0.0,
            "content_date_tolerance_days": 0,
            "rationale": f"members publish the same canonical URL: {url}",
        })
    by_name: dict[tuple[str, str, str, tuple[str, ...]], list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        if entry["id"] in claimed:
            continue
        key = (
            normalise_words(entry.get("custodian")), semantic_title(entry.get("name")),
            normalise_words(entry.get("refresh_frequency")), granularity_signature(entry),
        )
        if all(key[:3]):
            by_name[key].append(entry)
    for key, members in sorted(by_name.items()):
        channels = {endpoint_channel(row.get("url")) for row in members}
        if len(members) < 2 or len(channels - {""}) < 2:
            continue
        member_ids = sorted(row["id"] for row in members)
        slug = "-".join(key[1].split())
        identity = json.dumps(key, ensure_ascii=True, separators=(",", ":"))
        identity_digest = hashlib.sha256(identity.encode()).hexdigest()[:12]
        groups.append({
            "group_key": f"name:{key[0].replace(' ', '-')}:{slug}:{identity_digest}",
            "logical_name": min(members, key=lambda row: row["id"])["name"],
            "grouping_method": "semantic_title", "relationship": "equivalent",
            "confidence": "moderate", "member_ids": member_ids,
            "record_count_policy": "context_only", "record_count_tolerance_pct": 5.0,
            "content_date_tolerance_days": 2,
            "rationale": "exact semantic title, custodian, cadence, and granularity match across endpoint channels",
        })
        claimed.update(member_ids)
    return sorted(groups, key=lambda row: row["group_key"])


def member_row(entry: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    count = health.get("record_count")
    content_date = health.get("content_freshness_date")
    return {
        "id": entry["id"], "name": entry.get("name"), "source": entry.get("source"),
        "source_family": normalise_words(entry.get("custodian")), "url": entry.get("url"),
        "status": health.get("status", "unknown"),
        "availability_class": availability_class(health.get("status")),
        "record_count": count if is_number(count) else None,
        "record_count_estimated": health.get("record_count_estimated") is True,
        "content_date": content_date if parse_date(content_date) else None,
        "content_date_source": health.get("freshness_signal_source"),
    }


def compare_members(left: dict[str, Any], right: dict[str, Any], group: dict[str, Any]) -> dict[str, Any]:
    left_count, right_count = left["record_count"], right["record_count"]
    count_delta = count_delta_pct = count_within = None
    if is_number(left_count) and is_number(right_count):
        count_delta = right_count - left_count
        denominator = max(abs(left_count), abs(right_count))
        count_delta_pct = 0.0 if denominator == 0 else round(100 * abs(count_delta) / denominator, 3)
        if group["record_count_policy"] == "strict" and not (left["record_count_estimated"] or right["record_count_estimated"]):
            allowed = max(1.0, denominator * group["record_count_tolerance_pct"] / 100)
            if group["record_count_tolerance_pct"] == 0:
                allowed = 0.0
            count_within = abs(count_delta) <= allowed
    left_date, right_date = parse_date(left["content_date"]), parse_date(right["content_date"])
    date_delta = None if left_date is None or right_date is None else abs((right_date - left_date).days)
    date_within = None if date_delta is None else date_delta <= group["content_date_tolerance_days"]
    left_availability, right_availability = left["availability_class"], right["availability_class"]
    availability_match = None
    if left_availability != "unknown" and right_availability != "unknown":
        availability_match = left_availability == right_availability
    return {
        "left_id": left["id"], "right_id": right["id"],
        "record_count_delta": count_delta, "record_count_delta_pct": count_delta_pct,
        "record_count_within_tolerance": count_within,
        "content_date_delta_days": date_delta, "content_date_within_tolerance": date_within,
        "availability_match": availability_match,
    }


def materialise_group(group: dict[str, Any], by_id: dict[str, dict[str, Any]], health_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    members = [member_row(by_id[dataset_id], health_by_id.get(dataset_id, {})) for dataset_id in group["member_ids"]]
    comparisons = [compare_members(left, right, group) for left, right in combinations(members, 2)]
    evaluated = [value for comparison in comparisons for key, value in comparison.items() if key in {"record_count_within_tolerance", "content_date_within_tolerance", "availability_match"} and value is not None]
    agreement_evidence = [value for comparison in comparisons for key, value in comparison.items() if key in {"record_count_within_tolerance", "content_date_within_tolerance"} and value is not None]
    if group["relationship"] == "different_granularity":
        verdict = "different_granularity"
        reason = "reviewed relationship: members describe different geographic or dimensional granularity"
    elif any(value is False for value in evaluated):
        verdict = "discrepancy"
        reason = "one or more comparable publication signals exceed the declared tolerance"
    elif agreement_evidence:
        verdict = "agree"
        reason = "all evaluable publication signals are within the declared tolerance"
    else:
        verdict = "insufficient_data"
        reason = "no pair has an evaluable strict count, content-date, or availability comparison"
    return {
        "group_key": group["group_key"], "logical_name": group["logical_name"],
        "grouping_method": group["grouping_method"], "relationship": group["relationship"],
        "confidence": group["confidence"], "verdict": verdict,
        "requires_human_review": verdict == "discrepancy",
        "reason": reason, "rationale": group["rationale"],
        "tolerances": {"record_count_policy": group["record_count_policy"], "record_count_tolerance_pct": group["record_count_tolerance_pct"], "content_date_tolerance_days": group["content_date_tolerance_days"]},
        "members": members, "comparisons": comparisons,
    }


def generate(manifest: dict[str, Any], health: dict[str, Any], seeds: dict[str, Any]) -> dict[str, Any]:
    generated_at = health.get("checked_at")
    if not isinstance(generated_at, str) or parse_date(generated_at) is None:
        raise ValueError("health snapshot has no valid checked_at timestamp")
    entries = [row for row in manifest.get("datasets", []) if isinstance(row, dict) and isinstance(row.get("id"), str)]
    by_id = {row["id"]: row for row in entries}
    health_by_id = {row["dataset_id"]: row for row in health.get("datasets", []) if isinstance(row, dict) and isinstance(row.get("dataset_id"), str)}
    groups = [materialise_group(group, by_id, health_by_id) for group in discover_groups(manifest, seeds)]
    counts = Counter(group["verdict"] for group in groups)
    grouped_ids = {member["id"] for group in groups for member in group["members"]}
    return {
        "schema": SCHEMA, "generated_at": generated_at, "window_days": 0,
        "methodology": {
            "identity_precedence": ["seed_override", "exact_canonical_url", "exact_semantic_title_guarded"],
            "semantic_title_guards": ["same_custodian", "same_refresh_frequency", "same_granularity_signature", "different_endpoint_channel"],
            "semantic_title_stop_words": [], "automatic_name_record_count_policy": "context_only",
            "default_record_count_tolerance_pct": 5.0, "default_content_date_tolerance_days": 2,
            "disclaimer": "A discrepancy is a publication difference requiring review, not proof that either source is wrong.",
        },
        "summary": {
            "datasets_total": len(entries), "groups_total": len(groups), "datasets_grouped": len(grouped_ids), "datasets_single_source": len(entries) - len(grouped_ids),
            "by_verdict": {name: counts[name] for name in VERDICTS},
        },
        "groups": groups,
    }


def write_atomic(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(document, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--health", type=Path, default=DEFAULT_HEALTH)
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    write_atomic(args.output, generate(json.loads(args.manifest.read_text(encoding="utf-8")), json.loads(args.health.read_text(encoding="utf-8")), json.loads(args.seeds.read_text(encoding="utf-8"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
