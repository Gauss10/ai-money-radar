import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("fetch_vercel", ROOT / "scripts" / "fetch_vercel.py")
fetch_vercel = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_vercel)


class FetchVercelTests(unittest.TestCase):
    def test_model_rows_keep_legacy_metrics(self):
        rows = [
            {"date": "2026-07-15", "name": "Model A", "metric": "tokens", "share_percent": 30.04},
            {"date": "2026-07-15", "name": "Model B", "metric": "tokens", "share_percent": 40.02},
            {"date": "2026-07-15", "name": "Model A", "metric": "spend", "share_percent": 55.0},
            {"date": "2026-07-15", "name": "Model A", "metric": "requests", "share_percent": 20.0},
            {"date": "2026-07-15", "name": "Image A", "metric": "imageCount", "share_percent": 90.0},
        ]

        table = fetch_vercel.model_rows_to_table(rows)

        self.assertEqual(table["tokens"]["2026-07-15"][0], ["Model B", 40.02])
        self.assertEqual(table["cost"]["2026-07-15"], [["Model A", 55.0]])
        self.assertEqual(table["requests"]["2026-07-15"], [["Model A", 20.0]])
        self.assertNotIn("imageCount", table)

    def test_lab_spend_history_uses_official_lab_rows(self):
        rows = [
            {"date": "2026-07-14", "name": "anthropic", "metric": "spend", "share_percent": 45.25},
            {"date": "2026-07-14", "name": "openai", "metric": "spend", "share_percent": 20.0},
            {"date": "2026-07-14", "name": "google", "metric": "spend", "share_percent": 10.0},
            {"date": "2026-07-14", "name": "zai", "metric": "spend", "share_percent": 8.0},
            {"date": "2026-07-15", "name": "anthropic", "metric": "spend", "share_percent": 44.0},
            {"date": "2026-07-15", "name": "openai", "metric": "tokens", "share_percent": 15.0},
        ]

        history = fetch_vercel.build_lab_spend_history(rows)

        self.assertEqual(history["days"], ["2026-07-14", "2026-07-15"])
        self.assertEqual(history["series"]["Anthropic"], [45.25, 44.0])
        self.assertEqual(history["series"]["OpenAI"], [20.0, 0.0])
        self.assertEqual(history["series"]["Gemini"], [10.0, 0.0])
        self.assertEqual(history["series"]["Z.ai"], [8.0, 0.0])

    def test_weekly_average_uses_selected_dates_and_rebuilds_other(self):
        table = {
            "tokens": {
                "2026-07-04": [["Old Leader", 90.0]],
                "2026-07-05": [["Model A", 40.0], ["Model B", 20.0]],
                "2026-07-06": [["Model A", 30.0], ["Model B", 30.0]],
            }
        }

        rows = fetch_vercel.weekly_average(
            table, ["2026-07-05", "2026-07-06"], "tokens"
        )

        self.assertEqual(rows[:2], [["Model A", 35.0], ["Model B", 25.0]])
        self.assertEqual(rows[-1], ["Other", 40.0])
        self.assertNotIn("Old Leader", [name for name, _ in rows])

    def test_model_history_is_rebuilt_from_api_table_only(self):
        table = {
            "tokens": {
                "2026-05-16": [["Claude Test", 12.0], ["Model A", 20.0]],
                "2026-05-17": [["Claude Test", 15.0]],
            },
            "cost": {
                "2026-05-16": [["Claude Test", 30.0]],
                "2026-05-17": [["Model A", 25.0]],
            },
        }

        history = fetch_vercel.build_model_history(table)

        self.assertEqual(
            history["tokens"]["days"], ["2026-05-16", "2026-05-17"]
        )
        self.assertEqual(
            history["tokens"]["series"]["Claude (family)"], [12.0, 15.0]
        )
        self.assertNotIn("2026-05-15", history["tokens"]["days"])

    def test_snapshots_use_common_api_dates_and_rebuild_other(self):
        table = {
            "tokens": {
                "2026-07-14": [["Model A", 60.04]],
                "2026-07-15": [["Model A", 40.04], ["Model B", 20.04]],
            },
            "cost": {
                "2026-07-15": [["Model A", 55.04]],
            },
            "requests": {
                "2026-07-15": [["Model A", 50.04]],
            },
        }

        snapshots = fetch_vercel.build_snapshots(table)

        self.assertEqual([row["date"] for row in snapshots], ["2026-07-15"])
        self.assertEqual(
            snapshots[0]["token_share"],
            [["Model A", 40.0], ["Model B", 20.0], ["Other", 40.0]],
        )


if __name__ == "__main__":
    unittest.main()
