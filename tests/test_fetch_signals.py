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
    def test_youtube_video_id_is_preserved_for_deep_reads(self):
        url = "https://www.youtube.com/watch?v=abc123&utm_source=test"
        self.assertEqual(
            fetch_signals.normalize_signal_url(url),
            "https://www.youtube.com/watch?v=abc123",
        )

    def test_tracking_query_is_removed_from_regular_url(self):
        url = "https://x.com/example/status/1?s=20&utm_source=test"
        self.assertEqual(
            fetch_signals.normalize_signal_url(url),
            "https://x.com/example/status/1",
        )

    def test_deep_read_removes_source_intro_and_timeline(self):
        value = """栏目：重复的栏目介绍。
核心事实第一段。
00:00 节目介绍
判断：需要继续跟踪真实采用。"""
        cleaned = fetch_signals.clean_deep_detail(value)
        self.assertNotIn("栏目：", cleaned)
        self.assertNotIn("00:00", cleaned)
        self.assertIn("核心事实第一段。", cleaned)
        self.assertIn("判断：", cleaned)

    def test_model_json_accepts_fenced_output(self):
        value = '```json\n{"title":"标题","bio":"简介","detail":"判断：内容"}\n```'
        self.assertEqual(fetch_signals.parse_model_json(value)["title"], "标题")

    def test_thin_source_does_not_generate_a_deep_read(self):
        item = {"detail": "只有一句简短宣传。", "take": "通用判断"}
        self.assertIsNone(fetch_signals.generate_deep_read(item, "unused-key"))

    def test_generated_summary_removes_timeline_and_promotion(self):
        raw = """摘要：核心结论是模型训练成本下降。
时间轴：
00:00 节目介绍
03:22 训练数据
订阅频道获取更多内容。
#AI #datacenter"""
        self.assertEqual(
            fetch_signals.clean_generated_summary(raw),
            "核心结论是模型训练成本下降。",
        )

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

    def test_display_removes_identical_take_across_authors(self):
        entries = [
            {"date": "2026-07-10", "who": "A", "url": "a", "take": "same", "_raw": "first item"},
            {"date": "2026-07-10", "who": "B", "url": "b", "take": "same", "_raw": "second item"},
        ]
        self.assertEqual(len(fetch_signals.dedupe(entries, unique_take=True)), 1)

    def test_display_pool_uses_latest_three_days(self):
        entries = [
            {"date": "2026-07-12", "who": "A", "url": "a", "take": "one", "_raw": "a", "_score": 8},
            {"date": "2026-07-11", "who": "B", "url": "b", "take": "two", "_raw": "b", "_score": 9},
            {"date": "2026-07-10", "who": "C", "url": "c", "take": "three", "_raw": "c", "_score": 10},
            {"date": "2026-07-09", "who": "D", "url": "d", "take": "four", "_raw": "d", "_score": 99},
        ]
        pool = fetch_signals.recent_display_pool(entries)
        self.assertEqual([item["date"] for item in pool], ["2026-07-12", "2026-07-11", "2026-07-10"])

    def test_display_backfills_from_recent_archive_after_take_dedupe(self):
        current = [
            {"date": "2026-07-12", "who": "A", "url": "a", "take": "one", "_raw": "a", "_score": 10},
            {"date": "2026-07-12", "who": "B", "url": "b", "take": "one", "_raw": "b", "_score": 9},
            {"date": "2026-07-12", "who": "C", "url": "c", "take": "two", "_raw": "c", "_score": 8},
        ]
        archive = [
            {"date": "2026-07-10", "who": "D", "url": "d", "take": "three"},
            {"date": "2026-07-10", "who": "E", "url": "e", "take": "four"},
            {"date": "2026-07-09", "who": "F", "url": "f", "take": "five"},
        ]
        display = fetch_signals.select_display(current, archive)
        self.assertEqual([(item["date"], item["take"]) for item in display], [
            ("2026-07-12", "one"),
            ("2026-07-12", "two"),
            ("2026-07-10", "three"),
            ("2026-07-10", "four"),
        ])


if __name__ == "__main__":
    unittest.main()
