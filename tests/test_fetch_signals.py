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

    def test_generated_summary_rejects_prompt_and_reasoning_leakage(self):
        raw = (
            "We need to produce 2-3 sentences, about 100-220 Chinese characters. "
            "Let's count manually. 最终摘要看起来是正常中文，但前面泄露了推理过程。"
        )
        self.assertEqual(fetch_signals.clean_generated_summary(raw), "")

    def test_generated_summary_rejects_meta_refusal(self):
        raw = "由于您提供的原始内容仅包含标题，我无法从中提取具体事实，请提供完整原文。"
        self.assertEqual(fetch_signals.clean_generated_summary(raw), "")

    def test_title_only_source_is_not_summary_material(self):
        self.assertFalse(fetch_signals.has_summary_material({
            "detail": "Trading Houses For Datacenters",
        }))
        self.assertTrue(fetch_signals.has_summary_material({
            "detail": (
                "If a human-level software engineer could run on an H100 equivalent, "
                "that H100 should rent for over $250k a year, 15x today's spot price."
            ),
        }))

    def test_public_entry_cannot_reintroduce_polluted_summary(self):
        entry = {
            "date": "2026-07-29",
            "who": "Example",
            "detail": "A sufficiently detailed source sentence " * 4,
            "detail_zh": "We need to produce Chinese summary. Let's count characters. 正常结论。",
            "take_zh": "原始内容仅包含标题，我无法从中提取，请提供完整原文。",
        }
        public = fetch_signals.public_entry(entry)
        self.assertEqual(public["detail_zh"], "")
        self.assertEqual(public["take_zh"], "")

    def test_cover_summary_uses_complete_existing_detail(self):
        detail = "本期披露了新的模型使用数据与关键商业进展。"
        self.assertEqual(
            fetch_signals.cover_summary_fallback(detail, "通用主题模板"),
            detail,
        )

    def test_cover_summary_falls_back_instead_of_truncating(self):
        detail = "本期披露了新的模型使用数据与关键商业进展。" * 8
        self.assertEqual(
            fetch_signals.cover_summary_fallback(detail, "通用主题模板"),
            "通用主题模板",
        )

    def test_generated_cover_rejects_ellipsis_and_adds_full_stop(self):
        self.assertEqual(fetch_signals.clean_generated_cover("核心事实" * 9), "核心事实" * 9 + "。")
        self.assertEqual(fetch_signals.clean_generated_cover("核心事实" * 9 + "…"), "")
        self.assertEqual(
            fetch_signals.clean_generated_cover("公司披露关键经营数据，并讨论开放源代码与模型。"),
            "",
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
