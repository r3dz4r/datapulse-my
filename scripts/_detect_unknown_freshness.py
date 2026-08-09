#!/usr/bin/env python3
"""Detect ISO date fields for datasets currently missing freshness signals."""

import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parent.parent
DETECTION_PATH = Path("/tmp/_uf_detection.json")
UNDETECTABLE_PATH = Path("/tmp/_uf_undetectable.json")
DATE_FIELD_RE = re.compile(
    r"^date$|^date_|^_date$|.*_date$|.*_at$|^year$|^month$|^quarter$|^period$"
)
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def write_json_atomic(path, value):
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")
        temporary_path = Path(handle.name)
    temporary_path.replace(path)


def sample_url(url):
    return f"{url}{'&' if '?' in url else '?'}limit=1"


def slug_from_url(url):
    values = parse_qs(urlsplit(url).query).get("id", [])
    return values[0] if len(values) == 1 and values[0] else None


def fetch_sample(url):
    with tempfile.TemporaryFile("w+b") as response:
        subprocess.run(
            [
                "curl",
                "--location",
                "--max-time",
                "10",
                "--silent",
                "--fail",
                sample_url(url),
            ],
            check=True,
            stdout=response,
        )
        response.seek(0)
        return json.load(response)


def detect_date_field(rows):
    if not isinstance(rows, list) or not rows or not all(
        isinstance(row, dict) for row in rows
    ):
        return None

    best_field = None
    best_cardinality = -1
    for field in rows[0]:
        if not DATE_FIELD_RE.search(field):
            continue
        values = [row.get(field) for row in rows]
        if not values or not all(
            isinstance(value, str) and ISO_DATE_RE.fullmatch(value) for value in values
        ):
            continue
        cardinality = len(set(values))
        if cardinality > best_cardinality:
            best_field = field
            best_cardinality = cardinality
    return best_field


def extract_max_date(rows, field):
    values = [row.get(field) for row in rows if row.get(field) is not None]
    return max(values, default=None)


def main():
    health = json.loads((ROOT / "health/latest.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "datapulse.json").read_text(encoding="utf-8"))
    policy = json.loads(
        (ROOT / "scripts/probe-policy.json").read_text(encoding="utf-8")
    )

    unknown_ids = {
        row["dataset_id"]
        for row in health["datasets"]
        if row.get("status") == "unknown-freshness"
    }
    manifest_by_id = {row["id"]: row for row in manifest["datasets"]}
    existing_keys = set(policy["datasets"])
    detected = {}
    undetectable = {}
    samples = {}

    for dataset_id in sorted(unknown_ids):
        entry = manifest_by_id.get(dataset_id)
        if entry is None:
            undetectable[dataset_id] = {"reason": "missing manifest entry"}
            continue
        url = entry["url"]
        slug = slug_from_url(url)
        if slug is None:
            undetectable[dataset_id] = {
                "reason": "URL has no single non-empty id query parameter",
                "url": url,
            }
            continue
        if slug in existing_keys:
            undetectable[slug] = {"reason": "existing probe-policy key", "url": url}
            continue
        if slug in detected or slug in undetectable:
            raise RuntimeError(f"duplicate slug among unknown datasets: {slug}")
        try:
            rows = fetch_sample(url)
        except (subprocess.CalledProcessError, json.JSONDecodeError, UnicodeDecodeError) as error:
            undetectable[slug] = {
                "reason": f"sample fetch or JSON parse failed: {type(error).__name__}",
                "url": url,
            }
            continue
        field = detect_date_field(rows)
        if field is None:
            undetectable[slug] = {
                "reason": "response is not a non-empty list of dicts with an ISO date field",
                "url": url,
            }
            continue
        extracted = extract_max_date(rows, field)
        if not isinstance(extracted, str) or not ISO_DATE_RE.fullmatch(extracted):
            undetectable[slug] = {
                "reason": "max-date sanity check failed",
                "url": url,
            }
            continue
        detected[slug] = {"date_field": field, "extraction_mode": "max"}
        samples[slug] = extracted

    write_json_atomic(DETECTION_PATH, detected)
    write_json_atomic(UNDETECTABLE_PATH, undetectable)

    collisions = sorted(existing_keys.intersection(detected))
    print(f"unknown={len(unknown_ids)} detected={len(detected)} undetectable={len(undetectable)}")
    print(f"existing_key_collisions={len(collisions)} duplicate_slugs=0")
    print("sample_detected:")
    for slug in list(detected)[:5]:
        print(f"  {slug}: {detected[slug]['date_field']} -> {samples[slug]}")


if __name__ == "__main__":
    main()
