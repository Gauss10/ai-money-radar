import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "fetch_codex_adoption", ROOT / "scripts" / "fetch_codex_adoption.py"
)
fetch_codex_adoption = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_codex_adoption)


def article(text):
    return {
        "date": "2026-07-21",
        "title": "Official adoption update",
        "url": "https://openai.com/index/official-adoption-update",
        "text": text,
    }


class FetchCodexAdoptionTests(unittest.TestCase):
    def test_extracts_standalone_codex_weekly_users(self):
        points = fetch_codex_adoption.extract_points(article(
            "Codex now has more than 5 million weekly active users, up more than 6x since February."
        ))
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["value_m"], 5)
        self.assertEqual(points[0]["label"], ">5M")
        self.assertEqual(points[0]["metric_key"], "codex_wau")

    def test_extracts_developers_using_codex_every_week(self):
        points = fetch_codex_adoption.extract_points(article(
            "More than 4 million developers were using Codex every week."
        ))
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["value_m"], 4)
        self.assertEqual(points[0]["metric_key"], "codex_wau")

    def test_extracts_growth_to_format(self):
        points = fetch_codex_adoption.extract_points(article(
            "Weekly Codex users have more than tripled since the start of the year to 1.6M."
        ))
        self.assertEqual(points[0]["value_m"], 1.6)

    def test_later_current_value_replaces_prior_value_in_same_article(self):
        points = fetch_codex_adoption.extract_points(article(
            "More than 3 million developers were using Codex every week. "
            "Just two weeks later, that number has grown to more than 4 million."
        ))
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["value_m"], 4)
        self.assertEqual(points[0]["label"], ">4M")

    def test_combined_scope_stays_separate(self):
        points = fetch_codex_adoption.extract_points(article(
            "ChatGPT and Codex together now serve over 8 million weekly active users."
        ))
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["value_m"], 8)
        self.assertEqual(points[0]["metric_key"], "codex_chatgpt_combined_wau")

    def test_monthly_metric_stays_separate(self):
        points = fetch_codex_adoption.extract_points(article(
            "Codex now serves approximately 12 million monthly active users."
        ))
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["metric_key"], "codex_mau")
        self.assertEqual(points[0]["label"], "~12M")

    def test_non_usage_number_is_ignored(self):
        points = fetch_codex_adoption.extract_points(article(
            "Codex usage grew 6x after the launch, with strong enterprise adoption."
        ))
        self.assertEqual(points, [])

    def test_chatgpt_metric_is_not_assigned_to_codex(self):
        points = fetch_codex_adoption.extract_points(article(
            "Codex is growing quickly. ChatGPT now has 900 million weekly active users."
        ))
        self.assertEqual(points, [])


if __name__ == "__main__":
    unittest.main()
