import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_news


class FetchNewsTests(unittest.TestCase):
    def test_old_pinned_items_expire_like_regular_news(self):
        items = [
            {
                "date": "2026-06-29",
                "title": "Old manually selected item",
                "news_source": "Example",
                "url": "https://example.com/old",
                "pinned": True,
            }
        ] + [
            {
                "date": f"2026-08-{day:02d}",
                "title": f"Current data center event {day}",
                "news_source": "Example",
                "url": f"https://example.com/{day}",
            }
            for day in range(1, 4)
        ]

        selected, _ = fetch_news.select_items(items, keep=3)

        self.assertEqual([item["date"] for item in selected], ["2026-08-03", "2026-08-02", "2026-08-01"])
        self.assertTrue(all("pinned" not in item for item in items))


if __name__ == "__main__":
    unittest.main()
