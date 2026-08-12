#!/usr/bin/env python3
"""Fail when deployment cadence facts in docs drift from the canonical timer."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_TIMER = Path("/home/redza/dotfiles/system/datapulse-health.timer")
OLD_FACTS = (
    "every 15 minutes",
    "15-minute cadence",
    "15-minute timer",
    "OnCalendar=*:0/15",
    "*/15",
    "318 datasets",
)


def timer_facts(timer: Path) -> tuple[str, str]:
    text = timer.read_text(encoding="utf-8")
    calendar = re.search(r"^OnCalendar=(.+)$", text, re.MULTILINE)
    description = re.search(r"^Description=(.+)$", text, re.MULTILINE)
    if not calendar or not description:
        raise ValueError(f"timer must contain OnCalendar= and Description=: {timer}")
    return calendar.group(1).strip(), description.group(1).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--timer", type=Path, default=CANONICAL_TIMER)
    args = parser.parse_args()
    timer = args.timer if args.timer.exists() else args.root / "deploy/systemd/datapulse-health.timer"
    try:
        calendar, description = timer_facts(timer)
    except (OSError, ValueError) as exc:
        print(f"cadence lint error: {exc}")
        return 2
    paths = (
        args.root / "docs/operations.md",
        args.root / "README.md",
        args.root / "deploy/systemd/datapulse-health.service",
    )
    findings: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            lowered = line.lower()
            for old in OLD_FACTS:
                if old.lower() in lowered:
                    findings.append(f"{path}:{line_number}: docs say {old!r}, unit says {calendar!r} ({description})")
    print(f"deploy/docs drift summary: timer={timer} OnCalendar={calendar!r} Description={description!r}")
    if findings:
        print(f"found {len(findings)} stale cadence fact(s):")
        print("\n".join(findings))
        return 1
    print("no stale cadence facts found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
