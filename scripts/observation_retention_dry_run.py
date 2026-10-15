#!/usr/bin/env python3
"""Read-only, envelope-authoritative retention measurements for an observation store.

The newest filed observation is the deterministic as-of instant. A cutoff retains
observations at or after that instant minus the requested calendar months.
No object is removed by this command, including objects with no references.
"""
from __future__ import annotations

import argparse
import calendar
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from observation_store import (
    DIGEST_PATTERN,
    ObservationStoreError,
    _load_policy_config,
    archiving_mode,
    blob_path,
    global_limits,
    normalized_path,
    resolve_root,
)

logger = logging.getLogger(__name__)
PROJECTION_DIGEST = re.compile(r"(?:^|; )projection_digest (sha256:[^\s;]+)(?:$|;)")
INVARIANT = (
    "A blob may never be removed while any surviving envelope still cites its digest."
)
REPLAY_STATES = frozenset({
    "replayable", "metadata_only", "partial", "incomparable", "not_replayable", "unknown",
})


def _months_before(moment: datetime, months: int) -> datetime:
    year, month = divmod(moment.year * 12 + moment.month - 1 - months, 12)
    return moment.replace(year=year, month=month + 1, day=min(
        moment.day, calendar.monthrange(year, month + 1)[1]
    ))


def _instant(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("observed_at must be an ISO-8601 string with a timezone")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"invalid observed_at {value!r}") from error
    if moment.tzinfo is None:
        raise ValueError(f"observed_at {value!r} has no timezone")
    return moment.astimezone(timezone.utc)


def _digest(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or DIGEST_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} {value!r} is not sha256:<64 lowercase hex>")
    return value


def _projection_digest(envelope: dict[str, Any]) -> tuple[str | None, bool]:
    projection = envelope.get("normalized_projection")
    if not isinstance(projection, dict):
        raise ValueError("normalized_projection is not an object")
    if projection.get("state") not in {"retained", "not_retained", "unknown"}:
        raise ValueError("normalized_projection has an invalid state")
    if projection.get("state") != "retained":
        return None, False
    provenance = envelope.get("field_provenance")
    detail = provenance.get("normalized_projection") if isinstance(provenance, dict) else None
    transform = detail.get("transform") if isinstance(detail, dict) else None
    match = PROJECTION_DIGEST.search(transform) if isinstance(transform, str) else None
    if match is None:
        return None, True
    return _digest(match.group(1), "projection_digest"), False


def _envelopes(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    defects: list[str] = []
    for path in sorted((root / "envelopes").rglob("*.json")):
        relative = path.relative_to(root).as_posix()
        parts = path.relative_to(root / "envelopes").parts
        try:
            if len(parts) != 4 or not parts[1].isdigit() or not parts[2].isdigit():
                raise ValueError("file is outside envelopes/<dataset>/<YYYY>/<MM>/*.json")
            if len(parts[1]) != 4 or len(parts[2]) != 2 or not 1 <= int(parts[2]) <= 12:
                raise ValueError("file has an invalid YYYY/MM directory")
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(envelope, dict):
                raise ValueError("envelope is not a JSON object")
            if envelope.get("observation_id") != path.stem:
                raise ValueError("missing or mismatched observation_id")
            if envelope.get("dataset_id") != parts[0]:
                raise ValueError("dataset_id differs from its directory")
            moment = _instant(envelope.get("observed_at"))
            if (f"{moment:%Y}", f"{moment:%m}") != (parts[1], parts[2]):
                raise ValueError("observed_at differs from its YYYY/MM directory")
            source = _digest(envelope.get("source_digest"), "source_digest")
            normalized, projection_unknown = _projection_digest(envelope)
            if envelope.get("replay_state") not in REPLAY_STATES:
                raise ValueError("replay_state is missing or invalid")
            rows.append({
                "path": relative,
                "dataset_id": parts[0],
                "observation_id": path.stem,
                "observed_at": moment,
                "source_digest": source,
                "normalized_digest": normalized,
                "normalized_digest_unknown": projection_unknown,
                "replay_state": envelope.get("replay_state"),
            })
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            defects.append(f"{relative}: {error}")
    return rows, defects


def _objects(root: Path, directory: str, suffix: str) -> dict[str, int]:
    objects: dict[str, int] = {}
    for path in sorted((root / directory / "sha256").rglob(f"*.{suffix}")):
        digest = "sha256:" + path.stem
        if DIGEST_PATTERN.fullmatch(digest) and path.parent.name == path.stem[:2]:
            objects[digest] = path.stat().st_size
    return objects


def _dataset_policy(config: dict[str, Any], dataset_id: str) -> dict[str, Any]:
    entries = config.get("datasets")
    entry = entries.get(dataset_id) if isinstance(entries, dict) else None
    mode = archiving_mode(dataset_id)
    if mode is None or not isinstance(entry, dict):
        return {"status": "no policy — not permitted to archive", "mode": None,
                "retention_months": None, "capture_raw_bytes": None,
                "raw_bytes_expire_days": None}
    return {"status": "configured", "mode": mode,
            "retention_months": entry.get("retention_months"),
            "capture_raw_bytes": entry.get("capture_raw_bytes"),
            "raw_bytes_expire_days": entry.get("raw_bytes_expire_days")}


def _measure(
    rows: list[dict[str, Any]], months: int, as_of: datetime | None,
    raw_sizes: dict[str, int], normalized_sizes: dict[str, int],
    config: dict[str, Any], defects: list[str],
) -> dict[str, Any]:
    threshold = _months_before(as_of, months) if as_of is not None else None
    pruned = [row for row in rows if threshold is not None and row["observed_at"] < threshold]
    retained = [row for row in rows if row not in pruned]
    normalized_reference_unknown = any(row["normalized_digest_unknown"] for row in rows)
    raw_owners: dict[str, set[str]] = defaultdict(set)
    normalized_owners: dict[str, set[str]] = defaultdict(set)
    for row in pruned:
        if row["source_digest"]:
            raw_owners[row["source_digest"]].add(row["dataset_id"])
        if row["normalized_digest"]:
            normalized_owners[row["normalized_digest"]].add(row["dataset_id"])
    datasets: dict[str, Any] = {}
    for dataset_id in sorted({row["dataset_id"] for row in rows}):
        policy = _dataset_policy(config, dataset_id)
        gone = [row for row in pruned if row["dataset_id"] == dataset_id]
        kept = [row for row in retained if row["dataset_id"] == dataset_id]
        gone_raw = {row["source_digest"] for row in gone if row["source_digest"]}
        kept_raw = {row["source_digest"] for row in retained if row["source_digest"]}
        gone_normalized = {row["normalized_digest"] for row in gone
                           if row["normalized_digest"]}
        kept_normalized = {row["normalized_digest"] for row in retained
                           if row["normalized_digest"]}
        raw_expiry = policy["raw_bytes_expire_days"]
        expired_kept = sum(
            1 for row in kept if row["source_digest"] and as_of is not None
            and isinstance(raw_expiry, int)
            and row["observed_at"] < as_of - timedelta(days=raw_expiry)
        )
        datasets[dataset_id] = {
            "policy": policy,
            "candidate_shorter_than_policy": (
                months < policy["retention_months"]
                if isinstance(policy["retention_months"], int) else None
            ),
            "vintages_pruned": len(gone),
            "vintages_retained": len(kept),
            "pruned_observation_ids": [
                row["observation_id"] for row in sorted(
                    gone, key=lambda item: (item["observed_at"], item["observation_id"])
                )
            ],
            "retained_observation_ids": [
                row["observation_id"] for row in sorted(
                    kept, key=lambda item: (item["observed_at"], item["observation_id"])
                )
            ],
            "envelopes_left": len(kept),
            "replay_states_pruned": {
                str(state): sum(row["replay_state"] == state for row in gone)
                for state in sorted({row["replay_state"] for row in gone}, key=str)
            },
            "replay_states_retained": {
                str(state): sum(row["replay_state"] == state for row in kept)
                for state in sorted({row["replay_state"] for row in kept}, key=str)
            },
            "oldest_pruned_observed_at": min(
                (row["observed_at"] for row in gone), default=None
            ),
            "newest_retained_observed_at": max(
                (row["observed_at"] for row in kept), default=None
            ),
            "raw_bytes_freed": (
                None if defects or policy["capture_raw_bytes"] is False else
                sum(raw_sizes.get(digest, 0) for digest in gone_raw - kept_raw
                    if raw_owners[digest] == {dataset_id})
            ),
            "normalized_bytes_freed": (
                None if defects or normalized_reference_unknown else sum(
                    normalized_sizes.get(digest, 0)
                    for digest in gone_normalized - kept_normalized
                    if normalized_owners[digest] == {dataset_id}
                )
            ),
            "normalized_bytes_unknown": normalized_reference_unknown,
            "retained_raw_refs_past_policy_expiry": expired_kept,
            "raw_expiry_conflicts_with_invariant": expired_kept > 0,
        }
    gone_raw_all = {row["source_digest"] for row in pruned if row["source_digest"]}
    kept_raw_all = {row["source_digest"] for row in retained if row["source_digest"]}
    gone_normalized_all = {row["normalized_digest"] for row in pruned
                           if row["normalized_digest"]}
    kept_normalized_all = {row["normalized_digest"] for row in retained
                           if row["normalized_digest"]}
    return {
        "months": months,
        "cutoff_observed_at": threshold,
        "datasets": datasets,
        "newly_unreferenced_raw_digests": (
            sorted(gone_raw_all - kept_raw_all) if not defects else []
        ),
        "never_prunable_shared_raw_digests": sorted(gone_raw_all & kept_raw_all),
        "raw_bytes_freed_all_datasets": (
            sum(raw_sizes.get(digest, 0) for digest in gone_raw_all - kept_raw_all)
            if not defects else None
        ),
        "newly_unreferenced_normalized_digests": (
            sorted(gone_normalized_all - kept_normalized_all)
            if not defects and not normalized_reference_unknown else []
        ),
        "never_prunable_shared_normalized_digests": sorted(
            gone_normalized_all & kept_normalized_all
        ),
        "normalized_bytes_freed_all_datasets": (
            None if defects or normalized_reference_unknown
            else sum(normalized_sizes.get(digest, 0)
                     for digest in gone_normalized_all - kept_normalized_all)
        ),
        "safe_to_consider_removal": not defects and not normalized_reference_unknown,
    }


def build_report(root: Path, cutoffs: list[int]) -> dict[str, Any]:
    """Measure candidate retention cutoffs without writing to the store."""
    config = _load_policy_config()
    rows, defects = _envelopes(root)
    envelopes_scanned = len(rows) + len(defects)
    raw_sizes = _objects(root, "blobs", "raw")
    normalized_sizes = _objects(root, "normalized", "json")
    for row in rows:
        for label, sizes in (("source_digest", raw_sizes),
                             ("normalized_digest", normalized_sizes)):
            digest = row[label]
            if digest is not None and digest not in sizes:
                defects.append(f"{row['path']}: {label} {digest} has no stored object")
    referenced_raw = {row["source_digest"] for row in rows if row["source_digest"]}
    referenced_normalized = {row["normalized_digest"] for row in rows
                             if row["normalized_digest"]}
    normalized_reference_unknown = sum(row["normalized_digest_unknown"] for row in rows)
    as_of = max((row["observed_at"] for row in rows), default=None)
    report = {
        "store_root": str(root),
        "as_of_observed_at": as_of,
        "as_of_basis": "newest valid envelope observed_at",
        "policy_default_retention_months": global_limits()["retention_months"],
        "envelopes_scanned": envelopes_scanned,
        "valid_envelopes": len(rows),
        "integrity_defect_count": len(defects),
        "integrity_defects": sorted(defects),
        "normalized_reference_unknown_count": normalized_reference_unknown,
        "orphan_raw_digests": sorted(set(raw_sizes) - referenced_raw) if not defects else [],
        "orphan_normalized_digests": (
            sorted(set(normalized_sizes) - referenced_normalized)
            if not defects and not normalized_reference_unknown else []
        ),
        "orphans_are_never_proposed_for_removal": True,
        "safety_invariant": INVARIANT,
        "normalized_digest_source": (
            "field_provenance.normalized_projection.transform; the schema's "
            "normalized_projection has no digest field"
        ),
        "candidates": [
            _measure(rows, months, as_of, raw_sizes, normalized_sizes, config, defects)
            for months in cutoffs
        ],
    }
    return report


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _text_report(report: dict[str, Any]) -> str:
    lines = [
        f"Store: {report['store_root']}",
        f"As of: {report['as_of_observed_at']} ({report['as_of_basis']})",
        f"Valid envelopes: {report['valid_envelopes']}",
        f"Integrity defects: {report['integrity_defect_count']}",
        f"Unknown normalized references: {report['normalized_reference_unknown_count']}",
        f"Safety invariant: {INVARIANT}",
        f"Orphan raw digests (never proposed for removal): {report['orphan_raw_digests']}",
        f"Orphan normalized digests (never proposed): {report['orphan_normalized_digests']}",
        f"Normalized digest source: {report['normalized_digest_source']}",
    ]
    lines.extend(f"Defect: {item}" for item in report["integrity_defects"])
    for candidate in report["candidates"]:
        lines.append(f"Cutoff {candidate['months']} months: {candidate['cutoff_observed_at']}")
        for name, data in candidate["datasets"].items():
            lines.append(
                f"  {name}: policy={data['policy']}; retained={data['vintages_retained']}; "
                f"pruned={data['vintages_pruned']}; envelopes left={data['envelopes_left']}; "
                f"shorter than policy={data['candidate_shorter_than_policy']}; "
                f"oldest pruned={data['oldest_pruned_observed_at']}; "
                f"newest retained={data['newest_retained_observed_at']}; "
                f"raw bytes freed={data['raw_bytes_freed']}; "
                f"normalized bytes freed={data['normalized_bytes_freed']}; "
                f"replay states retained={data['replay_states_retained']}; "
                f"replay states pruned={data['replay_states_pruned']}; "
                f"retained raw refs past policy expiry="
                f"{data['retained_raw_refs_past_policy_expiry']}; "
                f"raw expiry conflicts with invariant="
                f"{data['raw_expiry_conflicts_with_invariant']}"
            )
        lines.append("  Newly unreferenced raw digests: " +
                     str(candidate["newly_unreferenced_raw_digests"]))
        lines.append("  Shared raw digests, never prunable: " +
                     str(candidate["never_prunable_shared_raw_digests"]))
        lines.append("  Raw bytes freed across all datasets: " +
                     str(candidate["raw_bytes_freed_all_datasets"]))
        lines.append("  Newly unreferenced normalized digests: " +
                     str(candidate["newly_unreferenced_normalized_digests"]))
        lines.append("  Shared normalized digests, never prunable: " +
                     str(candidate["never_prunable_shared_normalized_digests"]))
        lines.append("  Normalized bytes freed across all datasets: " +
                     str(candidate["normalized_bytes_freed_all_datasets"]))
        lines.append(f"  Safe to consider removal: {candidate['safe_to_consider_removal']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the read-only report CLI and return 0, 2 (refusal), or 3 (defect)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store", required=True, type=Path, help="absolute observation store root"
    )
    parser.add_argument("--cutoffs", help="comma-separated positive calendar months")
    parser.add_argument("--json", action="store_true", help="emit deterministic JSON")
    args = parser.parse_args(argv)
    try:
        root = resolve_root(args.store)
        if not root.is_dir():
            raise ValueError(f"store root does not exist or is not a directory: {root}")
        if not (root / "envelopes").is_dir():
            raise ValueError(f"store root has no envelopes/ directory: {root}")
        default = global_limits()["retention_months"]
        raw_cutoffs = args.cutoffs.split(",") if args.cutoffs is not None else [
            str(default), "12", "6", "3"
        ]
        if any(not item.strip().isdigit() or int(item.strip()) <= 0 for item in raw_cutoffs):
            raise ValueError("cutoffs must be comma-separated positive integer months")
        cutoffs = sorted({int(item.strip()) for item in raw_cutoffs}, reverse=True)
        report = _json_ready(build_report(root, cutoffs))
    except (OSError, ObservationStoreError, ValueError) as error:
        logger.error("retention dry-run refused: %s", error)
        return 2
    if args.json:
        sys.stdout.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    else:
        sys.stdout.write(_text_report(report) + "\n")
    return 3 if report["integrity_defect_count"] else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR, format="%(message)s")
    sys.exit(main())
