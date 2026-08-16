#!/usr/bin/env python3
"""Extract code-derived sections for the health methodology document."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs/.health-methodology/extracted.md"
DEFAULT_TIMER = Path("/etc/systemd/system/datapulse-health.timer")
STATUS_MEANINGS = {
    "fresh": "Reachable, structurally usable, and within the freshness window.",
    "aging": "Freshness age is over 1.5× baseline and at most 3× baseline.",
    "stale": "Freshness age is over 3× baseline.",
    "discontinued": "The publisher has stopped updating the dataset; the last known content is retained.",
    "degraded": "Reachable, but probe, schema, shape, or record-count checks failed.",
    "browser-dependent": "Assessment requires rendered browser state.",
    "unreachable": "The source request failed or returned a non-2xx response.",
    "unknown": "No reliable classification is available.",
    "unknown-freshness": "Reachable and structurally usable, but no freshness evidence exists.",
    "reference": "Versioned reference data is reachable; date-based freshness does not apply.",
}


def assignment_values(path: Path) -> dict[str, object]:
    """Read module-level literal assignments without importing production code."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                values[node.targets[0].id] = literal_value(node.value)
            except (TypeError, ValueError):
                continue
    return values


def literal_value(node: ast.AST) -> object:
    """Evaluate the literal arithmetic used by policy constants."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        values = [literal_value(item) for item in node.elts]
        return tuple(values) if isinstance(node, ast.Tuple) else values
    if isinstance(node, ast.Dict):
        return {literal_value(key): literal_value(value) for key, value in zip(node.keys, node.values, strict=True)}
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Div)):
        left, right = literal_value(node.left), literal_value(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        return left / right
    raise ValueError("not a literal expression")


def required(values: dict[str, object], name: str) -> object:
    value = values.get(name)
    if value is None:
        raise ValueError(f"could not extract {name}")
    return value


def section(name: str, body: str) -> str:
    return f"<!-- BEGIN EXTRACTED: {name} -->\n{body.rstrip()}\n<!-- END EXTRACTED: {name} -->"


def schema_version(check_source: str) -> str:
    match = re.search(r'--arg schema "([^"]+)"', check_source)
    if match is None:
        raise ValueError("could not extract health snapshot schema from scripts/check.sh")
    return section("schema-version", f"The current health snapshot schema is `{match.group(1)}`.")


def due_policy(check_source: str, timer: Path) -> str:
    # CI / non-systemd environments: the timer file isn't mounted. Fall back
    # to the known production cadence (5 minutes, OnCalendar=*:0/5).
    try:
        timer_text = timer.read_text(encoding="utf-8") if timer.is_file() else None
    except OSError:
        timer_text = None
    calendar_match = re.search(r"^OnCalendar=(.+)$", timer_text, re.MULTILINE) if timer_text is not None else None
    calendar_value = calendar_match.group(1) if calendar_match is not None else None
    cadence_match = re.fullmatch(r"\*:(\d+)/(\d+)", calendar_value) if calendar_value is not None else None
    if cadence_match is not None:
        cadence_minutes = int(cadence_match.group(2))
        cadence = f"{cadence_minutes} {'minute' if cadence_minutes == 1 else 'minutes'}"
        calendar_note = f"(systemd `OnCalendar={calendar_value}`)"
    else:
        cadence = "5 minutes"
        if timer_text is None:
            calendar_note = "(fallback: timer file not available in this environment)"
        else:
            calendar_note = "(fallback: timer cadence could not be parsed in this environment)"
    clauses = re.findall(r'(?:if|elif) (.+?) then \["([^"]+)", (\d+)\]', check_source)
    if not clauses:
        raise ValueError("could not extract due-policy tiers from scripts/check.sh")
    labels = (
        "30 seconds; hourly",
        "daily (weekdays…)",
        "daily",
        "weekly; monthly; quarterly",
        "annual; survey-year; as-required",
    )
    rows = "\n".join(
        f"| {labels[index] if index < len(labels) else condition} | `{tier}` | {minutes} |"
        for index, (condition, tier, minutes) in enumerate(clauses)
    )
    return section(
        "probe-cadence",
        f"The probe timer fires every **{cadence}** {calendar_note}.\n\n"
        "The due policy in `scripts/check.sh` uses these cadence thresholds:\n\n"
        "| Frequency | Tier | Due after (minutes) |\n| --- | --- | ---: |\n" + rows,
    )


def retention_and_archives(history: dict[str, object], history_source: str) -> str:
    days = required(history, "DEFAULT_RETENTION_DAYS")
    archive_match = re.search(r'DEFAULT_ARCHIVES_DIR\s*=\s*Path\.home\(\)\s*/\s*"([^"]+)"', history_source)
    if archive_match is None:
        raise ValueError("could not extract DEFAULT_ARCHIVES_DIR")
    archives = f"~/{archive_match.group(1)}"
    return section(
        "retention-and-archives",
        f"Raw observations are kept in `health/history.jsonl` for **{days} days**.\n"
        "On expiry, observations are compacted into `health/history_daily.json`\n"
        "(per-dataset, per-day aggregates: counts, status distribution, availability\n"
        "percentage, min/mean/max record counts, mean latency). Observations that\n"
        "fall outside the retention window are also archived to "
        f"`{archives}/health-YYYY-MM.jsonl.gz`\n"
        "(monthly gzip files, append-only).",
    )


def history_schema(history: dict[str, object]) -> str:
    fields = required(history, "HISTORY_FIELDS")
    if not isinstance(fields, tuple):
        raise ValueError("HISTORY_FIELDS is not a tuple")
    daily_schema = required(history, "DAILY_SCHEMA")
    return section(
        "history-schema",
        "Each `health/history.jsonl` row contains:\n\n"
        f"  {', '.join(f'`{field}`' for field in fields)}\n\n"
        "`probe_outcome` is one of `success`, `error`, `timeout`. The optional\n"
        "fields `name`, `url`, `shape_hash`, `column_count`, and `anomaly_detected`\n"
        "are written only when the corresponding source data is available.\n\n"
        f"The compact daily aggregate schema is `{daily_schema}`.",
    )


def status_taxonomy(history: dict[str, object]) -> str:
    statuses = required(history, "STATUSES")
    if not isinstance(statuses, tuple):
        raise ValueError("STATUSES is not a tuple")
    rows = "\n".join(
        f"| `{status}` | {STATUS_MEANINGS.get(status, status.replace('-', ' ').capitalize() + '.')} |"
        for status in statuses
    )
    return section("status-taxonomy", "| Status | Meaning |\n| --- | --- |\n" + rows)


def probe_outcomes(history: dict[str, object]) -> str:
    outcomes = required(history, "PROBE_OUTCOMES")
    if not isinstance(outcomes, tuple):
        raise ValueError("PROBE_OUTCOMES is not a tuple")
    return section("probe-outcomes", f"The probe classifies every observation as one of {', '.join(f'`{outcome}`' for outcome in outcomes)}.")


def anomaly_mode(anomaly: dict[str, object]) -> str:
    window = required(anomaly, "WINDOW_DAYS")
    if not isinstance(window, int):
        raise ValueError("WINDOW_DAYS is not an integer")
    return section(
        "anomaly-mode",
        "During warm-up, a freshness delta is anomalous if strictly greater than three\n"
        f"times the declared cadence. With at least {window - 2} distinct successful prior UTC-day observations in the {window}-day window, a delta is strictly greater\n"
        "than the population mean plus two population standard deviations.\n"
        "The current observation is excluded from the baseline.",
    )


def freshness_baselines(policy: dict[str, object]) -> str:
    baselines = required(policy, "FRESHNESS_BASELINE_SECONDS")
    if not isinstance(baselines, dict):
        raise ValueError("FRESHNESS_BASELINE_SECONDS is not a dictionary")
    rows = []
    for frequency, seconds in baselines.items():
        if not isinstance(seconds, int):
            raise ValueError(f"invalid baseline for {frequency}")
        baseline = ("1 day" if seconds == 86400 else f"{seconds / 86400:g} days") if seconds >= 86400 else ("1 hour" if seconds == 3600 else "30 seconds")
        rows.append(f"| `{frequency}` | {baseline} | ≤1.5× / >1.5×–≤3× / >3× |")
    return section(
        "freshness-baselines",
        "Reachability is not freshness. The probe chooses the newest defensible signal\n"
        "from an HTTP `Last-Modified` header or parsed content date.\n\n"
        "| Frequency | Baseline | Fresh / aging / stale |\n| --- | --- | --- |\n"
        + "\n".join(rows)
        + "\n\nWeekday-daily frequencies use the daily baseline. Survey-year verification uses 45-day and 90-day boundaries; as-required datasets do not infer a freshness window.",
    )


def generate(timer: Path) -> str:
    history_path = ROOT / "scripts/gen_health_history.py"
    history_source = history_path.read_text(encoding="utf-8")
    history = assignment_values(history_path)
    anomaly = assignment_values(ROOT / "scripts/gen_anomaly.py")
    policy = assignment_values(ROOT / "scripts/health_policy.py")
    check_source = (ROOT / "scripts/check.sh").read_text(encoding="utf-8")
    return "\n\n".join((schema_version(check_source), history_schema(history), retention_and_archives(history, history_source), probe_outcomes(history), due_policy(check_source, timer), status_taxonomy(history), anomaly_mode(anomaly), freshness_baselines(policy))) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timer", type=Path, default=DEFAULT_TIMER)
    args = parser.parse_args()
    try:
        content = generate(args.timer)
    except (OSError, SyntaxError, ValueError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"Extracted health methodology content to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
