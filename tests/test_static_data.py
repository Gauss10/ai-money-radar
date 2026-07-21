import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "data"


class StaticDataTest(unittest.TestCase):
    def test_codex_milestones_are_unique_and_ordered(self):
        payload = json.loads((DATA / "codex_wau.json").read_text(encoding="utf-8"))
        points = payload["points"]
        keys = [(point["date"], point.get("metric_key", "codex_wau")) for point in points]
        self.assertEqual(keys, sorted(set(keys)))
        self.assertTrue(all(point["value_m"] > 0 for point in points))
        self.assertTrue(all(point["url"].startswith("https://") for point in points))
        self.assertTrue(all(point.get("metric_key") for point in points))
        self.assertTrue(all(point.get("period") in {"weekly_active_users", "monthly_active_users"} for point in points))

    def test_compute_deals_have_explicit_aggregation_rules(self):
        payload = json.loads((DATA / "compute_deals.json").read_text(encoding="utf-8"))
        deals = payload["deals"]
        ids = [deal["id"] for deal in deals]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(deal["layer"] in {"cloud_site", "chip_system"} for deal in deals))
        self.assertTrue(all(isinstance(deal["capacity_counted"], bool) for deal in deals))
        self.assertTrue(all(deal["url"].startswith("https://") for deal in deals))
        self.assertTrue(all(deal["gw"] is not None for deal in deals if deal["capacity_counted"]))

        totals = {
            (company, layer): round(sum(
                deal["gw"] for deal in deals
                if deal["capacity_counted"]
                and deal["company"] == company
                and deal["layer"] == layer
            ), 2)
            for company in ("OpenAI", "Anthropic")
            for layer in ("cloud_site", "chip_system")
        }
        self.assertEqual(totals[("OpenAI", "cloud_site")], 8.45)
        self.assertEqual(totals[("OpenAI", "chip_system")], 11.0)
        self.assertEqual(totals[("Anthropic", "cloud_site")], 6.3)
        self.assertEqual(totals[("Anthropic", "chip_system")], 5.0)


if __name__ == "__main__":
    unittest.main()
