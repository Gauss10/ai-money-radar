import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("fetch_signals", ROOT / "scripts" / "fetch_signals.py")
fetch_signals = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_signals)


class FetchSignalsTests(unittest.TestCase):
    def test_compute_does_not_match_computer_science(self):
        score, rule = fetch_signals.classify("How Bitcoin rewired a classic computer science problem")
        self.assertFalse(rule and rule["name"] == "compute / GPU financing")
        self.assertLess(score, 8)

    def test_long_podcast_description_is_not_penalized_for_thanks(self):
        text = "Datacenters bigger than cities. " + ("AI buildout and power. " * 20) + "Thanks to our partners."
        score, rule = fetch_signals.classify(text)
        self.assertEqual(rule["name"], "compute / GPU financing")
        self.assertGreaterEqual(score, 8)

    def test_browser_posts_from_same_person_are_one_event(self):
        left = {
            "date": "2026-07-10",
            "who": "Cat Wu",
            "_raw": "Claude Code on desktop now has an in-app browser.",
        }
        right = {
            "date": "2026-07-10",
            "who": "Cat Wu",
            "_raw": "Claude Code can now open any website inside the desktop app.",
        }
        self.assertTrue(fetch_signals.same_event(left, right))

    def test_different_events_survive_identical_take(self):
        entries = [
            {"date": "2026-07-10", "who": "A", "url": "a", "take": "same", "_raw": "first item"},
            {"date": "2026-07-10", "who": "B", "url": "b", "take": "same", "_raw": "second item"},
        ]
        self.assertEqual(len(fetch_signals.dedupe(entries)), 2)


if __name__ == "__main__":
    unittest.main()
