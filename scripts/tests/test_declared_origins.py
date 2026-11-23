#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def _declarations() -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    contract = json.loads((ROOT / "config/public-surfaces.json").read_text(encoding="utf-8"))
    served = json.loads((ROOT / "config/served-origins.json").read_text(encoding="utf-8"))
    return contract["origins"], served["origins"]


class DeclaredOriginsTests(unittest.TestCase):
    def test_contract_origins_have_served_entries(self) -> None:
        contract_origins, served_origins = _declarations()
        unserved = sorted(contract_origins.keys() - served_origins.keys())
        self.assertFalse(
            unserved,
            f"contract origins have no served-origins entry: {', '.join(unserved)}",
        )

    def test_served_origin_implementation_paths_exist(self) -> None:
        _, served_origins = _declarations()
        missing = sorted(
            entry["path"]
            for entry in served_origins.values()
            if not (ROOT / entry["path"]).exists()
        )
        self.assertFalse(
            missing,
            f"served-origin implementation paths do not exist: {', '.join(missing)}",
        )

    def test_served_origins_are_declared_in_contract(self) -> None:
        contract_origins, served_origins = _declarations()
        undeclared = sorted(served_origins.keys() - contract_origins.keys())
        self.assertFalse(
            undeclared,
            f"served origins are missing from public-surface contract: {', '.join(undeclared)}",
        )


if __name__ == "__main__":
    unittest.main()
