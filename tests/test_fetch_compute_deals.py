import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "fetch_compute_deals", ROOT / "scripts" / "fetch_compute_deals.py"
)
fetch_compute_deals = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_compute_deals)


class FetchComputeDealsTests(unittest.TestCase):
    def test_candidate_requires_infrastructure_and_transaction_terms(self):
        self.assertTrue(fetch_compute_deals.is_candidate({
            "title": "New 2 gigawatt compute partnership",
            "summary": "signed capacity agreement",
            "text": "",
        }))
        self.assertFalse(fetch_compute_deals.is_candidate({
            "title": "New GPU benchmark",
            "summary": "performance results",
            "text": "",
        }))

    def test_fenced_model_json_is_accepted(self):
        result = fetch_compute_deals.parse_model_json(
            '```json\n{"is_deal": false}\n```'
        )
        self.assertEqual(result, {"is_deal": False})

    def test_anthropic_listing_metadata_can_prefilter_without_article_fetch(self):
        page = '''<a href="/news/example-compute" class="item">
          <h2>Anthropic signs 2 gigawatt compute partnership</h2>
          <time>Jul 21, 2026</time><p>New cloud capacity agreement.</p></a>'''
        original = fetch_compute_deals.http_get
        fetch_compute_deals.http_get = lambda _url: page
        try:
            rows = fetch_compute_deals.discover_anthropic()
        finally:
            fetch_compute_deals.http_get = original
        self.assertEqual(rows[0]["date"], "2026-07-21")
        self.assertTrue(fetch_compute_deals.is_candidate(rows[0]))

    def test_auto_deal_never_enters_capacity_chart(self):
        item = {
            "company": "OpenAI",
            "url": "https://openai.com/index/example-compute-deal",
            "date": "2026-07-21",
        }
        result = {
            "is_deal": True,
            "counterparty": "Example Cloud",
            "layer": "cloud_site",
            "status": "signed",
            "gw": 2,
            "gw_label": "2",
            "scope_zh": "2GW 云算力。",
            "scope_en": "2GW of cloud compute.",
            "note_zh": "官方公告。",
            "note_en": "Official announcement.",
        }
        deal = fetch_compute_deals.normalize_deal(item, result)
        self.assertFalse(deal["capacity_counted"])
        self.assertTrue(deal["auto_discovered"])
        self.assertEqual(deal["gw"], 2.0)

    def test_invalid_status_is_rejected(self):
        item = {"company": "Anthropic", "url": "https://anthropic.com/news/test", "date": "2026-07-21"}
        result = {
            "is_deal": True,
            "counterparty": "Example",
            "layer": "cloud_site",
            "status": "rumor",
        }
        self.assertIsNone(fetch_compute_deals.normalize_deal(item, result))


if __name__ == "__main__":
    unittest.main()
