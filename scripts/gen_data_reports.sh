#!/usr/bin/env bash
set -u

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
health_file="${1:-$repo_root/health/latest.json}"

python3 - "$repo_root" "$health_file" <<'PY'
import json
import re
import sys
from pathlib import Path


ROOT = Path(sys.argv[1])
HEALTH_PATH = Path(sys.argv[2])
DATA_DIR = ROOT / "data"
AUTO_SECTIONS = {"Status", "Last checked", "File size"}


def yaml_scalar(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def freshness_delta(row):
    value = row.get("freshness_delta")
    if value is not None:
        return str(value)
    days = row.get("staleness_days")
    return "unknown" if days is None else f"{days} days"


def health_file_size(row):
    value = row.get("file_size_bytes")
    return row.get("content_length") if value is None else value


def split_frontmatter(text, dataset_id, row):
    match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if match:
        return match.group(1), text[match.end():]

    # One legacy report predates front matter. Give it the same known field
    # vocabulary as the other reports, without inventing dataset measurements.
    if dataset_id == "eperolehan-diklankan":
        frontmatter = "\n".join(
            [
                f"dataset_id: {dataset_id}",
                f"last_checked: {row['last_checked']}",
                f"status: {row['status']}",
                f"freshness_delta: {freshness_delta(row)}",
                "next_expected_update: unknown",
                "file_size_bytes: null",
                "file_count: null",
                "schema_version: unknown",
                "schema_drift: none",
                "known_quirks: []",
                "breaking_changes: []",
                "licence: Open Government Licence (Malaysia)",
                "attribution: MOF ePerolehan",
            ]
        )
        return frontmatter, text

    raise ValueError("missing YAML front matter")


def update_frontmatter(frontmatter, row):
    replacements = {
        "last_checked": row.get("last_checked"),
        "status": row.get("status"),
        "freshness_delta": freshness_delta(row),
        "file_count": row.get("file_count"),
        "file_size_bytes": health_file_size(row),
        "last_observed": row.get("content_freshness_date"),
        "last_modified": row.get("last_modified"),
        "record_count": row.get("record_count"),
        "column_count": row.get("column_count"),
    }
    nullable_measurements = {
        "last_observed",
        "last_modified",
        "record_count",
        "column_count",
    }
    lines = frontmatter.splitlines()
    seen = set()
    for index, line in enumerate(lines):
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$", line)
        if not match:
            continue
        key = match.group(1)
        if key in replacements and (
            replacements[key] is not None or key in nullable_measurements
        ):
            lines[index] = f"{key}: {yaml_scalar(replacements[key])}"
            seen.add(key)

    required = ("last_checked", "status", "freshness_delta")
    missing = [key for key in required if key not in seen]
    for key in missing:
        key_index = required.index(key)
        predecessors = ("dataset_id",) + required[:key_index]
        insert_at = 0
        for index, line in enumerate(lines):
            if any(line.startswith(f"{predecessor}:") for predecessor in predecessors):
                insert_at = index + 1
        lines.insert(insert_at, f"{key}: {yaml_scalar(replacements[key])}")
    return "\n".join(lines)


def display_status(value):
    return str(value).replace("-", " ").capitalize()


def format_checked(value):
    match = re.fullmatch(
        r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?Z",
        str(value),
    )
    if not match:
        return str(value)
    year, month, day, hour, minute, second = match.groups()
    return f"{year}-{month}-{day} at {hour}:{minute}:{second} UTC."


def generated_sections(row):
    freshness = freshness_delta(row)
    message = str(row.get("message") or "No health-check message was recorded.").strip()
    size = health_file_size(row)
    count = row.get("file_count")

    status = (
        "## Status\n\n"
        f"**Status:** {display_status(row['status'])}\n\n"
        f"**Freshness:** {freshness}\n\n"
        f"{message}\n\n"
    )
    checked = f"## Last checked\n\n{format_checked(row['last_checked'])}\n\n"
    if size is None:
        size_text = "The health snapshot did not report a file size."
    else:
        size_text = f"The checked resource is {int(size):,} bytes."
    if count is not None:
        size_text += f" The snapshot reports {count} file(s)."
    file_size = f"## File size\n\n{size_text}\n\n"
    return status + checked + file_size


def refresh_body(body, row):
    sections = list(re.finditer(r"(?m)^## ([^\n]+)\n", body))
    first_section_start = sections[0].start() if sections else len(body)
    title = re.search(r"(?m)^# .+$", body[:first_section_start])
    if not title:
        raise ValueError("missing level-one title")

    prefix = body[title.start():title.end()] + "\n\n"
    preamble = body[title.end():first_section_start]
    preamble_lines = [
        line
        for line in preamble.splitlines()
        if not re.match(
            r"^\*\*(?:Dataset ID|Status|Freshness|Last checked|File size|Row count|Schema):\*\*",
            line,
        )
    ]
    preserved_preamble = "\n".join(preamble_lines).strip()
    if preserved_preamble:
        preserved_preamble += "\n\n"

    preserved_sections = []
    for index, section in enumerate(sections):
        end = sections[index + 1].start() if index + 1 < len(sections) else len(body)
        if section.group(1).strip() not in AUTO_SECTIONS:
            preserved_sections.append(body[section.start():end].rstrip("\n") + "\n\n")

    return prefix + generated_sections(row) + preserved_preamble + "".join(preserved_sections)


def refresh_report(row):
    dataset_id = row.get("dataset_id")
    if not isinstance(dataset_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", dataset_id):
        raise ValueError(f"invalid dataset_id: {dataset_id!r}")
    path = DATA_DIR / f"{dataset_id}.md"
    if not path.exists():
        return False

    original = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(original, dataset_id, row)
    updated = (
        "---\n"
        + update_frontmatter(frontmatter, row)
        + "\n---\n\n"
        + refresh_body(body, row).rstrip("\n")
        + "\n"
    )
    temporary = path.with_suffix(".md.tmp")
    temporary.write_text(updated, encoding="utf-8", newline="\n")
    temporary.replace(path)
    return True


try:
    health = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    datasets = health["datasets"]
    if not isinstance(datasets, list):
        raise TypeError("health.datasets must be an array")
except Exception as error:
    print(f"gen_data_reports: unable to read {HEALTH_PATH}: {error}", file=sys.stderr)
    raise SystemExit(1)

refreshed = 0
skipped = 0
failed = 0
for row in datasets:
    dataset_id = row.get("dataset_id", "<unknown>") if isinstance(row, dict) else "<invalid>"
    try:
        if refresh_report(row):
            refreshed += 1
        else:
            skipped += 1
    except Exception as error:
        failed += 1
        print(f"gen_data_reports: {dataset_id}: {error}", file=sys.stderr)

print(f"Regenerated {refreshed} dataset reports; skipped {skipped}; failed {failed}.")
PY
