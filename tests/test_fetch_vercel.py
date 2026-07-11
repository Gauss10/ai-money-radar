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


if __name__ == "__main__":
    unittest.main()
