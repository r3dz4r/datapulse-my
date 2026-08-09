#!/usr/bin/env python3
"""Generate the weekly human- and machine-readable trust snapshot."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any


STATUSES = (
    "fresh",
    "aging",
    "stale",
    "degraded",
    "browser-dependent",
    "unreachable",
    "unknown",
    "unknown-freshness",
)


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip() if result.returncode == 0 else ""


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def git_json(root: Path, commit: str, path: str) -> dict[str, Any] | None:
    content = git(root, "show", f"{commit}:{path}", check=False)
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def baseline_document(
    root: Path, path: str, start: date
) -> tuple[str, dict[str, Any] | None]:
    cutoff = f"{start.isoformat()}T00:00:00Z"
    before = git(root, "rev-list", "-1", f"--before={cutoff}", "HEAD", "--", path)
    commits = ([before] if before else []) + git(
        root,
        "log",
        "--reverse",
        "--format=%H",
        f"--since={cutoff}",
        "HEAD",
        "--",
        path,
    ).splitlines()
    for commit in commits:
        document = git_json(root, commit, path)
        if document and document.get("datasets"):
            return commit, document
    return "", None


def repository_has_week(root: Path, start: date) -> bool:
    timestamps = git(root, "log", "--reverse", "--format=%cI", "HEAD").splitlines()
    if not timestamps:
        return False
    first_commit = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))
    cutoff = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    return first_commit <= cutoff


def rows_by_id(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["dataset_id"]: row for row in document.get("datasets", [])}


def status_change(
    dataset_id: str,
    old: dict[str, Any],
    new: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "old_status": old.get("status"),
        "new_status": new.get("status"),
        "last_checked": new.get("last_checked"),
        "source": source,
    }


def change_summary(
    root: Path,
    current_changelog: dict[str, Any],
    start: date,
) -> tuple[dict[str, list[dict[str, Any]]], str]:
    if not repository_has_week(root, start):
        return {}, "Insufficient history (<7 days); change arrays were not inferred."

    changelog_commit, old_changelog = baseline_document(root, "changelog.json", start)
    health_commit, old_health = baseline_document(root, "health/latest.json", start)
    if old_changelog is None or old_health is None:
        return {}, "Insufficient history (<7 days); change arrays were not inferred."

    old_rows = rows_by_id(old_changelog)
    current_rows = rows_by_id(current_changelog)
    changelog_source = f"changelog.json@{changelog_commit[:12]}..HEAD"
    new_breaks: list[dict[str, Any]] = []
    recovered: list[dict[str, Any]] = []
    for dataset_id in sorted(old_rows.keys() & current_rows.keys()):
        old, new = old_rows[dataset_id], current_rows[dataset_id]
        transition = (old.get("status"), new.get("status"))
        if transition in {("fresh", "stale"), ("stale", "unreachable")}:
            new_breaks.append(status_change(dataset_id, old, new, changelog_source))
        elif old.get("status") != "fresh" and new.get("status") == "fresh":
            recovered.append(status_change(dataset_id, old, new, changelog_source))

    old_health_rows = rows_by_id(old_health)
    current_health_rows = rows_by_id(load_json(root / "health/latest.json"))
    health_source = f"health/latest.json@{health_commit[:12]}..HEAD"
    schema_changes: list[dict[str, Any]] = []
    for dataset_id in sorted(old_health_rows.keys() & current_health_rows.keys()):
        old, new = old_health_rows[dataset_id], current_health_rows[dataset_id]
        record_changed = old.get("record_count") != new.get("record_count")
        shape_changed = (
            old.get("column_count") != new.get("column_count")
            or bool(old.get("content_shape_changed"))
            != bool(new.get("content_shape_changed"))
        )
        if record_changed or shape_changed:
            schema_changes.append(
                {
                    "dataset_id": dataset_id,
                    "old_record_count": old.get("record_count"),
                    "new_record_count": new.get("record_count"),
                    "old_content_shape": {"column_count": old.get("column_count")},
                    "new_content_shape": {"column_count": new.get("column_count")},
                    "last_checked": new.get("last_checked"),
                    "source": health_source,
                }
            )

    added_paths = git(
        root,
        "log",
        f"--since={start.isoformat()}T00:00:00Z",
        "--diff-filter=A",
        "--name-only",
        "--pretty=format:",
        "--",
        "data/*.md",
    ).splitlines()
    added: list[dict[str, Any]] = []
    for dataset_id in sorted({Path(path).stem for path in added_paths if path.strip()}):
        row = current_rows.get(dataset_id)
        if row:
            added.append(
                {
                    "dataset_id": dataset_id,
                    "old_status": None,
                    "new_status": row.get("status"),
                    "last_checked": row.get("last_checked"),
                    "source": f"git history for data/{dataset_id}.md",
                }
            )

    return {
        "new_breaks": new_breaks,
        "recovered": recovered,
        "schema_changes": schema_changes,
        "added": added,
    }, f"Compared with the oldest available snapshots in the seven-day window ({changelog_commit[:12]} / {health_commit[:12]})."


def distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(row.get("status", "unknown")).replace("_", "-") for row in rows)
    total = len(rows)
    result: dict[str, Any] = {status: counts[status] for status in STATUSES}
    percentages = {
        status: round(counts[status] * 100 / total, 1) if total else 0.0
        for status in STATUSES
    }
    if total:
        largest = max(STATUSES, key=lambda status: counts[status])
        percentages[largest] = round(
            percentages[largest] + round(100.0 - sum(percentages.values()), 1), 1
        )
    result["percentages"] = percentages
    result["total"] = total
    return result


def coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    namespaces = Counter(row.get("namespace") or "unknown" for row in rows)
    licences = Counter(row.get("licence") or "unknown" for row in rows)
    return {
        "total_datasets": len(rows),
        "by_namespace": dict(sorted(namespaces.items())),
        "by_licence": dict(sorted(licences.items())),
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return lines


def status_section(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        return lines + ["_None observed in the comparison window._", ""]
    values = [
        [f"`{row['dataset_id']}`", row["old_status"], row["new_status"], row["last_checked"]]
        for row in rows
    ]
    return lines + markdown_table(["Dataset", "Old status", "New status", "Last checked"], values) + [""]


def render_markdown(snapshot: dict[str, Any]) -> str:
    distribution_data = snapshot["status_distribution"]
    coverage_data = snapshot["coverage"]
    changes = snapshot["changes"]
    caveats = snapshot["caveats"]
    unreachable_verb = "is" if caveats["unreachable"] == 1 else "are"
    lines = [
        f"# DataPulse MY Trust Snapshot — Week {snapshot['iso_week'].split('-W')[1]}, {snapshot['iso_week'][:4]}",
        "",
        f"**Dates covered:** {snapshot['date_range']['start']} to {snapshot['date_range']['end']} (UTC)",
        f"**Snapshot date:** {snapshot['week']}",
        f"**Source commit:** `{snapshot['source_commit']}`",
        "",
        "## Status distribution",
        "",
    ]
    lines += markdown_table(
        ["Status", "Count", "Percent"],
        [[f"`{status}`", distribution_data[status], f"{distribution_data['percentages'][status]:.1f}%"] for status in STATUSES]
        + [["**Total**", f"**{distribution_data['total']}**", "**100.0%**"]],
    ) + [""]

    if changes:
        lines += status_section("New breaks", changes["new_breaks"])
        lines += status_section("Recovered", changes["recovered"])
        lines += ["## Schema and record-count changes", ""]
        if changes["schema_changes"]:
            lines += markdown_table(
                ["Dataset", "Old records", "New records", "Old columns", "New columns", "Last checked"],
                [
                    [
                        f"`{row['dataset_id']}`",
                        row["old_record_count"],
                        row["new_record_count"],
                        row["old_content_shape"]["column_count"],
                        row["new_content_shape"]["column_count"],
                        row["last_checked"],
                    ]
                    for row in changes["schema_changes"]
                ],
            ) + [""]
        else:
            lines += ["_None observed in the comparison window._", ""]
        lines += ["## Newly added datasets", ""]
        if changes["added"]:
            lines += [f"- `{row['dataset_id']}` — {row['new_status']}" for row in changes["added"]] + [""]
        else:
            lines += ["_None observed in the comparison window._", ""]
    else:
        lines += [
            "## Changes",
            "",
            "_Insufficient history (<7 days); new breaks, recoveries, schema changes, and additions were not inferred._",
            "",
        ]

    lines += ["## Coverage", "", f"- Total datasets: **{coverage_data['total_datasets']}**", "", "### By namespace", ""]
    lines += markdown_table(["Namespace", "Datasets"], [[f"`{key}`", value] for key, value in coverage_data["by_namespace"].items()]) + [""]
    lines += ["### By licence", ""]
    lines += markdown_table(["Licence", "Datasets"], [[key, value] for key, value in coverage_data["by_licence"].items()]) + [""]
    lines += [
        "## Honest caveats",
        "",
        f"- **{caveats['unknown_freshness']}** datasets have unknown freshness and **{caveats['unreachable']}** {unreachable_verb} unreachable. These are explicit trust gaps, not silent green checks.",
        f"- {caveats['history']}",
        "",
        "## Reproducibility",
        "",
        f"Generated by `bash scripts/gen_trust_snapshot.sh`. License: MIT. Cite: https://data-pulse.my/trust-snapshot-{snapshot['week']}.md",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    root = Path(os.environ.get("DATAPULSE_REPO_ROOT", Path(__file__).parents[1])).resolve()
    snapshot_date = date.fromisoformat(os.environ.get("FAKE_DATE", datetime.now(timezone.utc).date().isoformat()))
    start = snapshot_date - timedelta(days=6)
    changelog = load_json(root / "changelog.json")
    rows = changelog.get("datasets", [])
    status_distribution = distribution(rows)
    changes, history_note = change_summary(root, changelog, start)
    iso_year, iso_week, _ = snapshot_date.isocalendar()
    snapshot = {
        "week": snapshot_date.isoformat(),
        "iso_week": f"{iso_year}-W{iso_week:02d}",
        "generated_at": f"{snapshot_date.isoformat()}T00:00:00Z",
        "source_commit": git(root, "rev-parse", "HEAD"),
        "date_range": {"start": start.isoformat(), "end": snapshot_date.isoformat()},
        "status_distribution": status_distribution,
        "coverage": coverage(rows),
        "changes": changes,
        "caveats": {
            "unknown_freshness": status_distribution["unknown-freshness"],
            "unreachable": status_distribution["unreachable"],
            "history": history_note,
        },
        "reproducibility": {
            "command": "bash scripts/gen_trust_snapshot.sh",
            "license": "MIT",
            "cite": f"https://data-pulse.my/trust-snapshot-{snapshot_date.isoformat()}.md",
        },
    }

    output_base = root / "docs" / f"trust-snapshot-{snapshot_date.isoformat()}"
    output_base.with_suffix(".md").write_text(render_markdown(snapshot), encoding="utf-8", newline="\n")
    output_base.with_suffix(".json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(output_base.with_suffix(".md").relative_to(root))
    print(output_base.with_suffix(".json").relative_to(root))


if __name__ == "__main__":
    main()
