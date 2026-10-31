from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.check_url_drift import audit, compare_urls
from scripts.gen_dynamic_manifest_urls import ROOT, stale_surfaces, sync_urls
from scripts.gen_json_envelope import generate as generate_envelopes


class CheckUrlDriftTests(unittest.TestCase):
    def run_audit(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/check_url_drift.py"), "--root", str(root)],
            capture_output=True, text=True, timeout=10, check=False,
        )

    def matching_dynamic_fixture(self, root: Path) -> None:
        self.dynamic_fixture(root)
        health_path = root / "health/latest.json"
        health = json.loads(health_path.read_text())
        manifest_url = json.loads((root / "datapulse.json").read_text())["datasets"][0]["url"]
        health["datasets"][0].update(url=manifest_url, request_url=manifest_url)
        health_path.write_text(json.dumps(health), encoding="utf-8")

    def add_fixture_dataset(
        self, root: Path, dataset_id: str, status: int, *, dynamic: bool = True,
    ) -> None:
        for name in ("datapulse.json", "health/latest.json", "scripts/probe-policy.json"):
            path = root / name
            document = json.loads(path.read_text())
            if name.endswith("probe-policy.json"):
                if dynamic:
                    document["datasets"][dataset_id] = document["datasets"]["pricecatcher"]
            else:
                row = dict(document["datasets"][0])
                row["dataset_id" if name.startswith("health") else "id"] = dataset_id
                if name.startswith("health"):
                    row["http_status"] = status
                document["datasets"].append(row)
            path.write_text(json.dumps(document), encoding="utf-8")
        for folder, key in (("json", "id"), ("jsonld", "identifier")):
            row = json.loads((root / f"data/{folder}/pricecatcher.json").read_text())
            row[key] = dataset_id
            (root / f"data/{folder}/{dataset_id}.json").write_text(json.dumps(row), encoding="utf-8")

    def test_availability_alone_does_not_fail_the_build(self) -> None:
        for status in (None, 404, "200", True):
            with self.subTest(status=status), TemporaryDirectory() as directory:
                root = Path(directory)
                self.matching_dynamic_fixture(root)
                # Keep one confirmed dynamic dataset so this is upstream availability,
                # rather than a total failure of the probe/network.
                self.add_fixture_dataset(root, "available", 206)
                health_path = root / "health/latest.json"
                health = json.loads(health_path.read_text())
                health["datasets"][0].update(http_status=status, status="unreachable")
                health_path.write_text(json.dumps(health), encoding="utf-8")

                result = self.run_audit(root)

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Availability: 1", result.stderr)
                self.assertIn("pricecatcher: observed URL has no confirmed HTTP 2xx", result.stderr)

    def test_drift_still_fails_the_build(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.dynamic_fixture(root)
            result = self.run_audit(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("pricecatcher: URL mismatch", result.stdout)

    def test_all_dynamic_unavailable_fails_as_probe_broken(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.matching_dynamic_fixture(root)
            self.add_fixture_dataset(root, "unavailable", 404)
            self.add_fixture_dataset(root, "static_available", 200, dynamic=False)
            health_path = root / "health/latest.json"
            health = json.loads(health_path.read_text())
            health["datasets"][0].update(http_status=None, status="unreachable")
            health_path.write_text(json.dumps(health), encoding="utf-8")
            result = self.run_audit(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("probe found no confirmed HTTP 2xx anywhere", result.stdout + result.stderr)
            self.assertIn("our probe or our network is broken", result.stdout + result.stderr)
            self.assertIn("Availability: 2", result.stderr)

    def test_no_dynamic_datasets_does_not_claim_probe_broken(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.matching_dynamic_fixture(root)
            (root / "scripts/probe-policy.json").write_text(json.dumps({"datasets": {}}))
            result = self.run_audit(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Availability: 0", result.stderr)

    def dynamic_fixture(self, root: Path) -> None:
        (root / "scripts").mkdir()
        (root / "health").mkdir()
        (root / "docs").mkdir()
        (root / "data/json").mkdir(parents=True)
        (root / "data/jsonld").mkdir(parents=True)
        monthly = "https://storage.data.gov.my/pricecatcher/pricecatcher_2026-09.parquet"
        observed = monthly.replace("2026-09", "2026-10")
        policy = {"datasets": {"pricecatcher": {"dynamic-url": {"template": "https://storage.data.gov.my/pricecatcher/pricecatcher_{YYYY-MM}.parquet"}}}}
        (root / "scripts/probe-policy.json").write_text(json.dumps(policy), encoding="utf-8")
        (root / "datapulse.json").write_text(json.dumps({"datasets": [{"id": "pricecatcher", "url": monthly, "refresh_frequency": "monthly"}]}), encoding="utf-8")
        (root / "health/latest.json").write_text(json.dumps({"datasets": [{"dataset_id": "pricecatcher", "url": observed, "request_url": observed, "http_status": 200}]}), encoding="utf-8")
        (root / "data/json/pricecatcher.json").write_text(json.dumps({"id": "pricecatcher", "reproducibility": {"url": monthly}}), encoding="utf-8")
        (root / "data/jsonld/pricecatcher.json").write_text(json.dumps({"identifier": "pricecatcher", "sameAs": monthly}), encoding="utf-8")
        (root / "docs/index.html").write_text('dataset.refresh_frequency ? `On its ${dataset.refresh_frequency} cadence`', encoding="utf-8")

    def test_matching_sources_are_clean(self):
        url = "https://example.test/data.csv"
        self.assertEqual(compare_urls({"alpha": {"manifest": url, "health": url, "dashboard": url}}), [])

    def test_mismatch_reports_dataset_and_values(self):
        result = compare_urls({"alpha": {"manifest": "a", "health": "b"}})
        self.assertEqual(len(result), 1)
        self.assertIn("alpha", result[0])
        self.assertIn("manifest=a", result[0])

    def test_empty_url_is_reported_missing(self):
        result = compare_urls({"alpha": {"manifest": "a", "health": None}})
        self.assertEqual(result, ["alpha: missing health"])

    def test_missing_dataset_surface_is_reported(self):
        result = compare_urls({"alpha": {"manifest": "a", "dashboard": None}})
        self.assertEqual(result, ["alpha: missing dashboard"])

    def test_audit_uses_every_manifest_row_without_an_embedded_payload(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "scripts").mkdir()
            (root / "scripts/probe-policy.json").write_text(
                json.dumps({"datasets": {}}), encoding="utf-8"
            )
            (root / "data/json").mkdir(parents=True)
            (root / "data/jsonld").mkdir(parents=True)
            datasets = [
                {
                    "id": "alpha",
                    "url": "https://example.test/alpha",
                    "refresh_frequency": "daily",
                },
                {
                    "id": "beta",
                    "url": "https://example.test/beta",
                    "refresh_frequency": "daily",
                },
            ]
            (root / "datapulse.json").write_text(
                json.dumps({"datasets": datasets}), encoding="utf-8"
            )
            (root / "health/latest.json").parent.mkdir(parents=True)
            (root / "health/latest.json").write_text(
                json.dumps(
                    {"datasets": [{"dataset_id": "alpha", "url": datasets[0]["url"]}]}
                ),
                encoding="utf-8",
            )
            for dataset in datasets:
                (root / "data/json" / f'{dataset["id"]}.json').write_text(
                    json.dumps(
                        {
                            "id": dataset["id"],
                            "reproducibility": {"url": dataset["url"]},
                        }
                    ),
                    encoding="utf-8",
                )
                (root / "data/jsonld" / f'{dataset["id"]}.json').write_text(
                    json.dumps({"identifier": dataset["id"], "sameAs": dataset["url"]}),
                    encoding="utf-8",
                )
            (root / "docs/index.html").write_text(
                'dataset.refresh_frequency ? `On its ${dataset.refresh_frequency} cadence`',
                encoding="utf-8",
            )

            discrepancies, cadence, availability = audit(root)

        self.assertEqual(discrepancies, ["beta: missing health"])
        self.assertEqual(cadence, [])
        self.assertEqual(availability, [])

    def test_monthly_roll_uses_confirmed_probe_url_and_is_idempotent(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.dynamic_fixture(root)
            (root / "datapulse.json").chmod(0o664)
            self.assertEqual(sync_urls(root), ["pricecatcher"])
            serialized = (root / "datapulse.json").read_bytes()
            self.assertIn("pricecatcher_2026-10.parquet", serialized.decode())
            self.assertEqual((root / "datapulse.json").stat().st_mode & 0o777, 0o664)
            self.assertEqual(stale_surfaces(root), ["pricecatcher"])
            self.assertEqual(sync_urls(root), [])
            self.assertEqual((root / "datapulse.json").read_bytes(), serialized)
            health_path = root / "health/latest.json"
            health = json.loads(health_path.read_text())
            next_month = "https://storage.data.gov.my/pricecatcher/pricecatcher_2026-11.parquet"
            health["datasets"][0].update(url=next_month, request_url=next_month)
            health_path.write_text(json.dumps(health), encoding="utf-8")
            self.assertEqual(sync_urls(root), ["pricecatcher"])
            self.assertEqual(json.loads((root / "datapulse.json").read_text())["datasets"][0]["url"], next_month)

    def test_annual_template_rolls_from_observed_year(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.dynamic_fixture(root)
            policy_path = root / "scripts/probe-policy.json"
            policy = json.loads(policy_path.read_text())
            policy["datasets"]["annual"] = {"dynamic-url": {"template": "https://storage.data.gov.my/transportation/vehicles_{YYYY}.csv"}}
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            manifest_path = root / "datapulse.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["datasets"].append({"id": "annual", "url": "https://storage.data.gov.my/transportation/vehicles_2026.csv"})
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            health_path = root / "health/latest.json"
            health = json.loads(health_path.read_text())
            observed = "https://storage.data.gov.my/transportation/vehicles_2027.csv"
            health["datasets"].append({"dataset_id": "annual", "url": observed, "request_url": observed, "http_status": 206})
            health_path.write_text(json.dumps(health), encoding="utf-8")
            self.assertEqual(sync_urls(root), ["annual", "pricecatcher"])
            self.assertEqual(json.loads(manifest_path.read_text())["datasets"][1]["url"], observed)

    def test_unconfirmed_or_wrong_observation_cannot_change_manifest(self):
        for field, value in (
            ("http_status", 404),
            ("request_url", "https://example.test/wrong.csv"),
            ("request_url", "https://storage.data.gov.my/pricecatcher/pricecatcher_2026-09.parquet"),
        ):
            with self.subTest(field=field), TemporaryDirectory() as directory:
                root = Path(directory)
                self.dynamic_fixture(root)
                health_path = root / "health/latest.json"
                health = json.loads(health_path.read_text())
                health["datasets"][0][field] = value
                health_path.write_text(json.dumps(health), encoding="utf-8")
                before = (root / "datapulse.json").read_bytes()
                self.assertEqual(sync_urls(root), [])
                self.assertEqual((root / "datapulse.json").read_bytes(), before)

    def test_stale_manifest_and_missing_surface_still_fail_with_404(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.dynamic_fixture(root)
            discrepancies, _, _ = audit(root)
            self.assertTrue(any("pricecatcher: URL mismatch" in item for item in discrepancies))
            (root / "data/json/pricecatcher.json").unlink()
            discrepancies, _, _ = audit(root)
            self.assertIn("pricecatcher: missing json envelope", discrepancies)
            health_path = root / "health/latest.json"
            health = json.loads(health_path.read_text())
            health["datasets"][0]["http_status"] = 404
            health_path.write_text(json.dumps(health), encoding="utf-8")
            discrepancies, _, availability = audit(root)
            self.assertIn("pricecatcher: missing json envelope", discrepancies)
            self.assertTrue(any("pricecatcher: URL mismatch" in item for item in discrepancies))
            self.assertTrue(any("status=404" in item for item in availability))

    def test_scoped_envelope_regeneration_uses_manifest_url(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.dynamic_fixture(root)
            sync_urls(root)
            with patch("scripts.gen_json_envelope.infer_fields", return_value=[]):
                self.assertEqual(generate_envelopes(root, dry_run=False, force=True, target_dataset_id="pricecatcher"), 1)
            envelope = json.loads((root / "data/json/pricecatcher.json").read_text())
            self.assertEqual(envelope["reproducibility"]["url"], "https://storage.data.gov.my/pricecatcher/pricecatcher_2026-10.parquet")

    def test_every_dynamic_dataset_matches_its_observation_and_surfaces(self):
        policy = json.loads((ROOT / "scripts/probe-policy.json").read_text())["datasets"]
        manifest = {row["id"]: row for row in json.loads((ROOT / "datapulse.json").read_text())["datasets"]}
        health = {row["dataset_id"]: row for row in json.loads((ROOT / "health/latest.json").read_text())["datasets"]}
        dynamic = [dataset_id for dataset_id, settings in policy.items() if "dynamic-url" in settings]
        self.assertEqual(len(dynamic), 11)
        for dataset_id in dynamic:
            with self.subTest(dataset_id=dataset_id):
                expected = health[dataset_id]["request_url"]
                self.assertEqual(manifest[dataset_id]["url"], expected)
                self.assertEqual(health[dataset_id]["url"], expected)
                self.assertEqual(json.loads((ROOT / "data/json" / f"{dataset_id}.json").read_text())["reproducibility"]["url"], expected)
                self.assertEqual(json.loads((ROOT / "data/jsonld" / f"{dataset_id}.json").read_text())["sameAs"], expected)
        self.assertEqual(stale_surfaces(ROOT), [])
        with patch("socket.socket", side_effect=AssertionError("audit attempted network access")):
            self.assertEqual(audit(ROOT)[0], [])


if __name__ == "__main__":
    unittest.main()
