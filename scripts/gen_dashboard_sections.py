#!/usr/bin/env python3
"""Generate README-ordered dashboard sections and a popularity hero section."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Iterable


METRICS_URL = "https://api.data.gov.my/data-catalogue?id=metrics_dataset_cumul"
CACHE_TTL = dt.timedelta(hours=1)
USER_AGENT = "Mozilla/5.0 (compatible; DataPulseMY/1.0)"
README_CATEGORIES = (
    ("Bank Negara Malaysia (BNM)", "bnm"),
    ("MET Malaysia", "met"),
    ("Department of Environment (DOE)", "doe"),
    ("KKM (Ministry of Health)", "kkm"),
    ("OpenDOSM (DOSM open data portal)", "opendosm"),
    ("data.gov.my", "data_gov_my"),
)
HANSARD_IDS = (
    "hansard_sittings",
    "hansard_parliamentary_terms",
    "hansard_mps",
)
HEADING_PATTERN = re.compile(r"^#### (.+)$")
DATASET_BULLET_PATTERN = re.compile(r"^- \[[^]]+\]\(data/([^)]+)\.md\)")


class GenerationError(RuntimeError):
    """Raised when dashboard section inputs do not satisfy the contract."""


def parse_readme_categories(readme: str) -> dict[str, list[str]]:
    """Extract dataset IDs belonging to each README level-four heading."""
    categories: dict[str, list[str]] = {}
    current: str | None = None
    for line in readme.splitlines():
        heading = HEADING_PATTERN.match(line)
        if heading:
            current = heading.group(1).strip()
            categories[current] = []
            continue
        if line.startswith("### "):
            current = None
            continue
        if current is None:
            continue
        dataset = DATASET_BULLET_PATTERN.match(line)
        if dataset:
            categories[current].append(dataset.group(1))
    return categories


def _number(value: object) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def select_popular_ids(
    metrics: Iterable[dict], manifest_ids: set[str], *, limit: int = 12
) -> list[str]:
    """Rank tracked datasets by views plus CSV and Parquet downloads."""
    ranked: list[tuple[int, str]] = []
    for row in metrics:
        dataset_id = row.get("id")
        if not isinstance(dataset_id, str) or dataset_id not in manifest_ids:
            continue
        engagement = sum(
            _number(row.get(field))
            for field in ("views", "download_csv", "download_parquet")
        )
        ranked.append((engagement, dataset_id))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [dataset_id for _, dataset_id in ranked[:limit]]


def _parse_timestamp(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def _read_cache(cache_path: Path) -> tuple[list[dict], str, dt.datetime] | None:
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    fetched_at = cached.get("fetched_at") if isinstance(cached, dict) else None
    datasets = cached.get("datasets") if isinstance(cached, dict) else None
    parsed_at = _parse_timestamp(fetched_at)
    if not isinstance(fetched_at, str) or not isinstance(datasets, list) or parsed_at is None:
        return None
    if not all(isinstance(row, dict) for row in datasets):
        return None
    return datasets, fetched_at, parsed_at


def _format_timestamp(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_metrics(
    cache_path: Path,
    *,
    now: dt.datetime | None = None,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> tuple[list[dict], str]:
    """Load metrics from a one-hour cache, refreshing with stale fallback."""
    now = (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC)
    cached = _read_cache(cache_path)
    if cached and now - cached[2] < CACHE_TTL:
        return cached[0], cached[1]

    request = urllib.request.Request(METRICS_URL, headers={"User-Agent": USER_AGENT})
    try:
        with opener(request, timeout=30) as response:  # type: ignore[attr-defined]
            metrics = json.load(response)
        if not isinstance(metrics, list) or not all(isinstance(row, dict) for row in metrics):
            raise GenerationError("metrics_dataset_cumul response must be an array of objects")
        fetched_at = _format_timestamp(now)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"fetched_at": fetched_at, "datasets": metrics}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        return metrics, fetched_at
    except (OSError, urllib.error.URLError, UnicodeError, json.JSONDecodeError) as error:
        if cached:
            print(
                f"gen_dashboard_sections.py: metrics refresh failed; using cache from {cached[1]}: {error}",
                file=sys.stderr,
            )
            return cached[0], cached[1]
        raise GenerationError(f"cannot load {METRICS_URL}: {error}") from error


def _section(name: str, key: str, datasets: Iterable[str], *, kind: str = "category") -> dict:
    return {
        "name": name,
        "key": key,
        "type": kind,
        "datasets": list(datasets),
    }


def build_sections(
    manifest: dict, parsed_categories: dict[str, list[str]], popular_ids: list[str]
) -> list[dict]:
    """Build canonical, exhaustive category sections plus the popularity hero."""
    rows = manifest.get("datasets") if isinstance(manifest, dict) else None
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise GenerationError("datapulse.json: 'datasets' must be an array of objects")
    identifiers = [row.get("id") for row in rows]
    if not all(isinstance(dataset_id, str) for dataset_id in identifiers):
        raise GenerationError("datapulse.json: every dataset must have a string id")
    if len(identifiers) != len(set(identifiers)):
        raise GenerationError("datapulse.json: dataset ids must be unique")

    ordered_ids = list(identifiers)
    manifest_ids = set(ordered_ids)
    references = {
        row["id"] for row in rows if row.get("data_type") == "reference"
    }
    hansard = set(HANSARD_IDS) & manifest_ids
    gtfs = {dataset_id for dataset_id in ordered_ids if dataset_id.startswith("gtfs_")}
    reserved = references | hansard | gtfs
    assigned: set[str] = set()

    result = [
        _section(
            "Most-Consumed Malaysian Data",
            "top_visited",
            popular_ids,
            kind="popular",
        )
    ]
    for name, key in README_CATEGORIES:
        category_ids = [
            dataset_id
            for dataset_id in parsed_categories.get(name, [])
            if dataset_id in manifest_ids
            and dataset_id not in reserved
            and dataset_id not in assigned
        ]
        assigned.update(category_ids)
        result.append(_section(name, key, category_ids))

    gtfs_ids = [dataset_id for dataset_id in ordered_ids if dataset_id in gtfs]
    assigned.update(gtfs_ids)
    result.append(_section("GTFS transit feeds", "gtfs", gtfs_ids))

    hansard_ids = [dataset_id for dataset_id in HANSARD_IDS if dataset_id in hansard]
    assigned.update(hansard_ids)
    result.append(_section("Hansard & parliamentary", "hansard", hansard_ids))

    reference_ids = [dataset_id for dataset_id in ordered_ids if dataset_id in references]
    assigned.update(reference_ids)
    result.append(_section("Reference tables", "reference", reference_ids))

    other_ids = [dataset_id for dataset_id in ordered_ids if dataset_id not in assigned]
    result.append(
        _section(
            "Other government open data",
            "other_government_open_data",
            other_ids,
        )
    )
    return result


def generate(
    readme_path: Path,
    manifest_path: Path,
    output_path: Path,
    cache_path: Path,
) -> dict:
    try:
        readme = readme_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GenerationError(f"cannot read dashboard section input: {error}") from error

    metrics, fetched_at = load_metrics(cache_path)
    rows = manifest.get("datasets", []) if isinstance(manifest, dict) else []
    manifest_ids = {
        row.get("id") for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    popular_ids = select_popular_ids(metrics, manifest_ids, limit=12)
    document = {
        "generated_at": fetched_at,
        "sections": build_sections(
            manifest, parse_readme_categories(readme), popular_ids
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return document


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", type=Path, default=root / "README.md")
    parser.add_argument("--manifest", type=Path, default=root / "datapulse.json")
    parser.add_argument(
        "--output", type=Path, default=root / "docs/.dashboard_sections.json"
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=root / ".cache/datapulse/metrics_dataset_cumul.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        generate(args.readme, args.manifest, args.output, args.cache)
    except GenerationError as error:
        print(f"gen_dashboard_sections.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
