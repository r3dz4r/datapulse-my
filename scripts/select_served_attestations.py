"""Select the attestation history reachable from a Cloudflare Pages artifact."""

from __future__ import annotations

import argparse
import itertools
import json
import re
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable


SITE_DIRECTORIES = (
    "functions", "health", "deltas", "record-evidence", "badges", "samples",
    "data", "observation-receipts", ".attestations",
)
SITE_ROOT_FILES = (
    "llms.txt", "robots.txt", "sitemap.xml", "feed.xml", "datapulse.json",
    "datapulse_summary.json", "custodians.json", "datapulse.schema.json",
    "health.schema.json", "agent.schema.json", "mcp.schema.json",
    "record-evidence.schema.json", "agent.json", "mcp.json",
    "catalog-snapshot.json", "catalog-graph.json", "changelog.json",
)
DATED_REF = re.compile(
    r"attestations/\d{4}-\d{2}-\d{2}/"
    r"(?:revisions/[0-9a-f]{64}/)?[A-Za-z0-9_.-]+\.json\Z"
)
HEAD_REF = re.compile(
    r"attestations/\d{4}-\d{2}-\d{2}/"
    r"(?:revisions/[0-9a-f]{64}/)?chain_head\.json\Z"
)
PUBLIC_REF = re.compile(
    rb"attestations/\d{4}-\d{2}-\d{2}/"
    rb"(?:revisions/[0-9a-f]{64}/)?[A-Za-z0-9_.-]+\.json(?:\.gz)?"
)
SAFE_REF = re.compile(r"attestations/[A-Za-z0-9_./-]+\.json(?:\.gz)?\Z")
SIGNED_METADATA = ("index.json", "binding.json", "scores.json", "health.json", "health.json.gz")
RETENTION_FILE = "served-retention.json"


def projected_site_files(root: Path) -> dict[Path, Path]:
    """Map source files to the names used by the two Pages assembly steps."""
    files = {path.relative_to(root / "docs"): path
             for path in (root / "docs").rglob("*") if path.is_file()}
    for name in SITE_DIRECTORIES:
        directory = root / name
        if directory.exists():
            files.update((path.relative_to(root), path)
                         for path in directory.rglob("*") if path.is_file())
    for name in SITE_ROOT_FILES:
        path = root / name
        if path.is_file():
            files[Path(name)] = path
    return files


def full_revision_directories(chain: dict, cutoff: date, depth: int) -> set[str]:
    """Select newest accepted sets by discovery sequence, never hash or mtime."""
    days: dict[str, list[tuple[int, str]]] = {}
    for digest in chain.get("envelopes", chain["heads"]):
        reference = chain["heads"][digest]
        if not HEAD_REF.fullmatch(reference):
            raise ValueError(f"unsafe chain head reference: {reference!r}")
        day = reference.split("/")[1]
        if date.fromisoformat(day) < cutoff:
            continue
        sequence = chain.get("envelopes", {}).get(digest, {}).get("sequence", 1)
        if not isinstance(sequence, int) or sequence < 1:
            raise ValueError(f"invalid attestation sequence: {digest}")
        days.setdefault(day, []).append((sequence, reference.rsplit("/", 1)[0]))
    return {directory for revisions in days.values()
            for _, directory in sorted(revisions)[-depth:]}


def select_attestations(
    plane: Path, public_files: Iterable[Path], full_revisions_per_day: int = 1,
) -> set[Path]:
    """Return source paths required by signed heads, current refs, and pages."""
    chain = json.loads((plane / "chain-index.json").read_text())
    latest = json.loads((plane / "latest/index.json").read_text())
    # Workflow parity is the published-window contract; the artifact guard keeps it under the ceiling.
    cutoff = date.fromisoformat(latest["date"]) - timedelta(days=6)
    full_directories = full_revision_directories(chain, cutoff, full_revisions_per_day)
    keep = {plane / "chain-index.json"}
    keep.update(path for path in (plane / "latest").iterdir() if path.is_file())

    def require(reference: str) -> Path:
        if (not isinstance(reference, str) or not reference.startswith("attestations/")
                or ".." in Path(reference).parts or not SAFE_REF.fullmatch(reference)):
            raise ValueError(f"unsafe attestation reference: {reference!r}")
        path = plane.parent / reference
        if not path.is_file():
            raise FileNotFoundError(f"published attestation reference is missing: {reference}")
        keep.add(path)
        return path

    def binding_references(path: Path) -> None:
        binding = json.loads(path.read_text())
        for reference in (binding.get("rekor") or {}).values():
            require(reference)
        snapshot = binding.get("payload", {}).get("correction", {}).get("health_snapshot_ref")
        if snapshot:
            require(snapshot)

    accepted = set(chain.get("envelopes", chain["heads"]))
    for digest, reference in chain["heads"].items():
        if not HEAD_REF.fullmatch(reference):
            raise ValueError(f"unsafe chain head reference: {reference!r}")
        directory = require(reference).parent
        # Migration anchors promise only a head, not an accepted signed set.
        if digest not in accepted:
            continue
        for name in SIGNED_METADATA:
            path = directory / name
            if path.is_file():
                keep.add(path)
            elif name not in ("health.json", "health.json.gz"):
                raise FileNotFoundError(f"accepted attestation metadata is missing: {path}")
        binding_path = directory / "binding.json"
        binding_references(binding_path)
        for field, reference in chain.get("envelopes", {}).get(digest, {}).items():
            if field.endswith("_ref"):
                require(reference)
        if directory.relative_to(plane.parent).as_posix() in full_directories:
            keep.update(path for path in directory.iterdir() if path.is_file())
            # Missing evidence in a full set is broken, even if absent from the source tree.
            index = json.loads((directory / "index.json").read_text())
            for reference in index.get("attestations", {}).values():
                require(reference)

    for field in ("chain_head_ref", "binding_ref"):
        if latest.get(field):
            if not DATED_REF.fullmatch(latest[field]):
                raise ValueError(f"unsafe current attestation reference: {latest[field]!r}")
            require(latest[field])
    for reference in latest["attestations"].values():
        if not DATED_REF.fullmatch(reference):
            raise ValueError(f"unsafe current attestation reference: {reference!r}")
        require(reference)
    latest_binding = plane / "latest/binding.json"
    if latest_binding.is_file():
        binding_references(latest_binding)

    for path in public_files:
        for match in PUBLIC_REF.findall(path.read_bytes()):
            require(match.decode("ascii"))
    checked_bindings: set[Path] = set()
    while pending := {path for path in keep if path.name == "binding.json"} - checked_bindings:
        for path in pending:
            binding_references(path)
        checked_bindings.update(pending)
    return keep


def retention_inventory(plane: Path, keep: set[Path], depth: int) -> dict:
    """Record only dataset omissions; signed metadata and pinned refs cannot be waived."""
    chain = json.loads((plane / "chain-index.json").read_text())
    not_served = set()
    for digest in chain.get("envelopes", chain["heads"]):
        directory = (plane.parent / chain["heads"][digest]).parent
        index = json.loads((directory / "index.json").read_text())
        for reference in index.get("attestations", {}).values():
            if (not isinstance(reference, str) or not DATED_REF.fullmatch(reference)
                    or Path(reference).parent != directory.relative_to(plane.parent)
                    or Path(reference).name in (*SIGNED_METADATA, "chain_head.json")):
                raise ValueError(f"unsafe dataset attestation reference: {reference!r}")
            if plane.parent / reference not in keep:
                not_served.add(reference)
    return {"schema": "datapulse/v1/served-attestation-retention",
            "full_revisions_per_day": depth, "not_served": sorted(not_served)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--site", type=Path)
    parser.add_argument("--max-files", type=int, default=18000)
    parser.add_argument("--full-revisions-per-day", type=int, default=1,
                        help="newest accepted revisions served in full per day of the seven-day window")
    args = parser.parse_args()
    if args.apply and args.site is None:
        parser.error("--apply requires --site")
    if args.max_files < 1:
        parser.error("--max-files must be positive")
    if args.full_revisions_per_day < 1:
        parser.error("--full-revisions-per-day must be positive")

    root = args.root.resolve()
    site = args.site.resolve() if args.site else None
    if args.plan:
        plane = root / "attestations"
        projected = projected_site_files(root)
        public_files = projected.values()
        other_count = len(projected)
    else:
        assert site is not None
        plane = site / "attestations" if (site / "attestations").is_dir() else root / "attestations"
        public_files = (path for path in site.rglob("*") if path.is_file()
                        and (site / "attestations") not in path.parents)
        if not (site / ".attestations").exists():
            public_files = itertools.chain(
                public_files,
                (path for path in (root / ".attestations").rglob("*") if path.is_file()),
            )
        other_count = sum(1 for path in site.rglob("*") if path.is_file()
                          and (site / "attestations") not in path.parents)
        if not (site / ".attestations").exists():
            other_count += sum(1 for path in (root / ".attestations").rglob("*") if path.is_file())

    keep = select_attestations(plane, public_files, args.full_revisions_per_day)
    inventory = retention_inventory(plane, keep, args.full_revisions_per_day)
    before = sum(1 for path in plane.rglob("*") if path.is_file())
    total = other_count + len(keep) + 1  # The generated retention inventory is served too.
    print(json.dumps({"attestations_before": before, "attestations_retained": len(keep) + 1,
                      "full_revisions_per_day": args.full_revisions_per_day,
                      "max_files": args.max_files, "mode": "plan" if args.plan else "apply",
                      "site_total": total}, sort_keys=True), flush=True)
    if total > args.max_files:
        raise SystemExit(f"Pages artifact has {total} files (guard {args.max_files})")

    if args.apply:
        assert site is not None
        destination = site / "attestations"
        if plane == destination:
            for path in plane.rglob("*"):
                if path.is_file() and path not in keep:
                    path.unlink()
        else:
            for path in keep:
                target = destination / path.relative_to(plane)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        inventory_path = destination / RETENTION_FILE
        temporary = inventory_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(inventory, sort_keys=True) + "\n")
        temporary.replace(inventory_path)
        if not (site / ".attestations").exists() and (root / ".attestations").is_dir():
            shutil.copytree(root / ".attestations", site / ".attestations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
