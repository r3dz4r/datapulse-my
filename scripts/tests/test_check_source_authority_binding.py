"""Tests for scripts/check_source_authority_binding.py."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.check_source_authority_binding import (
    INTERPRETATION_LABEL,
    MIRROR_LABEL,
    FieldCoverage,
    load_datasets,
    main,
    measure_binding,
    render_report,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_source_authority_binding.py"
LIVE_MANIFEST = REPO_ROOT / "datapulse.json"

FIXTURE_DATASETS = [
    {
        "id": "alpha",
        "url": "https://example.test/alpha.csv",
        "steward": "Agency Alpha",
        "custodian": "agency_alpha",
        "attribution": "Agency Alpha via example.test",
        "licence": "Open Government Licence",
        "canonical_id": "alpha_canonical",
        "expected_record_count": 42,
        "series_code": "series_alpha",
        "schema_id": "schema.alpha",
        "freshness_policy": {"interpretation": "observation_period"},
        "mirror_disqualification_rule": "prefer api.example.test; reject mirrors",
    },
    {
        "id": "beta",
        "url": "https://example.test/beta.csv",
        "steward": "Agency Beta",
        "custodian": "agency_beta",
        "attribution": "Agency Beta",
        "licence": "CC BY 4.0",
        "canonical_id": "",
        "expected_record_count": None,
        "freshness_policy": {"interpretation": "publication_date"},
    },
    {
        "id": "gamma",
        "url": "https://example.test/gamma.csv",
        "steward": "Agency Gamma",
        "custodian": "agency_gamma",
        "attribution": "Agency Gamma",
        "licence": "CC BY 4.0",
    },
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(directory: str, payload: object) -> Path:
    path = Path(directory) / "datapulse.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class FixtureCoverageTests(unittest.TestCase):
    def test_true_coverage_on_small_fixture(self):
        report = measure_binding(FIXTURE_DATASETS)
        coverage = {entry.field: entry.present for entry in report.fields}
        self.assertEqual(report.total, 3)
        self.assertEqual(
            coverage,
            {
                "url": 3,
                "steward": 3,
                "custodian": 3,
                "attribution": 3,
                "licence": 3,
                "canonical_id": 1,
                "expected_record_count": 1,
                "series_code": 1,
                "schema_id": 1,
                INTERPRETATION_LABEL: 2,
                MIRROR_LABEL: 1,
            },
        )

    def test_interpretation_breakdown_counts(self):
        report = measure_binding(FIXTURE_DATASETS)
        self.assertEqual(
            dict(report.interpretation_counts),
            {"observation_period": 1, "publication_date": 1, "missing": 1},
        )

    def test_rendered_lines_show_present_total_and_percentage(self):
        lines = render_report(measure_binding(FIXTURE_DATASETS))
        self.assertIn("url: 3/3 (100.0%)", lines)
        self.assertIn("canonical_id: 1/3 (33.3%)", lines)
        self.assertIn(f"{MIRROR_LABEL}: 1/3 (33.3%)", lines)
        self.assertIn("  observation_period: 1", lines)
        self.assertIn("  publication_date: 1", lines)
        self.assertIn("  missing: 1", lines)
        self.assertEqual(lines[-1], "Datasets measured: 3")

    def test_load_datasets_reads_fixture(self):
        with TemporaryDirectory() as directory:
            path = _write_manifest(directory, {"$schema": "x", "datasets": FIXTURE_DATASETS})
            rows = load_datasets(path)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["id"], "alpha")

    def test_nested_mirror_alias_is_detected(self):
        row = dict(FIXTURE_DATASETS[2])
        row["freshness_policy"] = {"mirror_disqualification": True}
        report = measure_binding([row])
        self.assertEqual(report.field(MIRROR_LABEL).present, 1)

    def test_field_coverage_percentage_guards_zero_total(self):
        self.assertEqual(FieldCoverage("url", 0, 0).percentage, 0.0)


class MeasurementFailureTests(unittest.TestCase):
    def _run(self, path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--manifest", str(path)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )

    def test_malformed_manifest_exits_nonzero(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "datapulse.json"
            path.write_text("{ this is not valid json", encoding="utf-8")
            completed = self._run(path)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("error", completed.stderr.lower())

    def test_dataset_less_manifest_exits_nonzero(self):
        for payload in ({"$schema": "x"}, {"$schema": "x", "datasets": []}, {"datasets": {}}):
            with self.subTest(payload=payload):
                with TemporaryDirectory() as directory:
                    path = _write_manifest(directory, payload)
                    completed = self._run(path)
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(completed.stdout, "")
                self.assertIn("datasets", completed.stderr.lower())

    def test_missing_manifest_exits_nonzero(self):
        with TemporaryDirectory() as directory:
            completed = self._run(Path(directory) / "absent.json")
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")

    def test_main_returns_nonzero_instead_of_raising(self):
        with TemporaryDirectory() as directory:
            path = _write_manifest(directory, {"datasets": []})
            self.assertNotEqual(main(["--manifest", str(path)]), 0)


class ReadOnlyProofTests(unittest.TestCase):
    def test_live_manifest_sha256_unchanged_after_run(self):
        before = _sha256(LIVE_MANIFEST)
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(_sha256(LIVE_MANIFEST), before)

        expected_total = len(
            json.loads(LIVE_MANIFEST.read_text(encoding="utf-8"))["datasets"]
        )
        self.assertIn(f"Datasets measured: {expected_total}", completed.stdout)
        self.assertIn("url: ", completed.stdout)


if __name__ == "__main__":
    unittest.main()
