#!/usr/bin/env python3
"""Check source-observation claims against each page's recorded check date."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATED_CLAIM = re.compile(r"Latest source observation: (\d{4}-\d{2}-\d{2})\b")


def test_source_observation_claims_do_not_postdate_last_checked() -> None:
    examined = 0
    violations: list[str] = []

    for page in sorted((ROOT / "data").glob("*.md")):
        text = page.read_text(encoding="utf-8")
        claims = DATED_CLAIM.findall(text)
        if not claims:
            continue

        relative = page.relative_to(ROOT)
        front_matter = re.match(r"\A---\n(.*?)\n---(?:\n|\Z)", text, re.DOTALL)
        assert front_matter is not None, f"{relative}: missing YAML front matter"
        checked = re.search(
            r"(?m)^last_checked:[ \t]*[\"']?(\d{4}-\d{2}-\d{2})(?=T|[\"']?[ \t]*$)",
            front_matter.group(1),
        )
        assert checked is not None, f"{relative}: missing dated last_checked"
        checked_date = date.fromisoformat(checked.group(1))
        examined += 1

        for claim in claims:
            if date.fromisoformat(claim) > checked_date:
                violations.append(
                    f"{relative}: Latest source observation: {claim} "
                    f"is later than last_checked: {checked_date.isoformat()}"
                )

    print(f"Examined {examined} pages carrying dated source-observation claims")
    assert examined >= 30, f"Examined {examined} dated-claim pages; expected at least 30"
    assert not violations, "Source-observation claims postdate last_checked:\n" + "\n".join(
        violations
    )
