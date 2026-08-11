import unittest

from scripts.check_url_drift import compare_urls


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


if __name__ == "__main__":
    unittest.main()
