import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.check_url_drift import audit, compare_urls


class CheckUrlDriftTests(unittest.TestCase):
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

            discrepancies, cadence = audit(root)

        self.assertEqual(discrepancies, ["beta: missing health"])
        self.assertEqual(cadence, [])


if __name__ == "__main__":
    unittest.main()
