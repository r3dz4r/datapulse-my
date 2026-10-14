#!/usr/bin/env python3
"""Fail when live prose counts disagree with their canonical sources."""
from __future__ import annotations

import argparse
import fnmatch
import json
import logging
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)


def verify_doc_claims(root: Path) -> list[str]:
    """Return all live-document disagreements with their path and line."""
    manifest = json.loads((root / "scripts/doc_claims.json").read_text(encoding="utf-8"))
    documents = sorted({path.relative_to(root).as_posix()
                        for glob in manifest["live_documents"] for path in root.glob(glob)
                        if path.is_file()})
    documents = [path for path in documents if not any(
        fnmatch.fnmatchcase(path, exemption) for exemption in manifest["dated_exemptions"])]
    failures: list[str] = []
    for claim in manifest["claims"]:
        command = claim["derive"]
        result = subprocess.run(["bash", "-o", "pipefail", "-c", command], cwd=root,
                                text=True, capture_output=True, timeout=10, check=False)
        if result.returncode or not result.stdout.strip():
            raise ValueError(f"{claim['source']}: derivation failed: {command}: {result.stderr.strip()}")
        if "list_pattern" in claim:
            expected_list = result.stdout.splitlines()
            expected_count = len(expected_list)
        else:
            expected_list = None
            expected_count = int(result.stdout.strip())
        pattern = re.compile(claim["pattern"])
        list_pattern = re.compile(claim["list_pattern"]) if expected_list is not None else None
        for document in documents:
            for line_number, line in enumerate((root / document).read_text(encoding="utf-8").splitlines(), 1):
                for match in pattern.finditer(line):
                    count = int(match.group("count").replace(",", ""))
                    if count != expected_count:
                        failures.append(f"{document}:{line_number} claims {match.group(0).strip()}, "
                                        f"{claim['source']} holds {expected_count}")
                if list_pattern is not None and expected_list is not None:
                    for match in list_pattern.finditer(line):
                        items = [item.strip() for item in match.group("items").split("|")]
                        if items != expected_list:
                            failures.append(f"{document}:{line_number} claims [{', '.join(items)}], "
                                            f"{claim['source']} holds [{', '.join(expected_list)}]")
    return failures


def main() -> int:
    """Check the current tree without modifying generated artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        failures = verify_doc_claims(args.root)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        LOGGER.error("doc claims: %s", error)
        return 1
    for failure in failures:
        LOGGER.error("%s", failure)
    if not failures:
        LOGGER.info("doc claims: all live counts match canonical sources")
    return int(bool(failures))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
