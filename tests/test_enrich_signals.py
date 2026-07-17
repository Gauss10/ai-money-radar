import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "enrich_signals_from_digests", ROOT / "scripts" / "enrich_signals_from_digests.py"
)
enrich = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(enrich)


class EnrichSignalsTests(unittest.TestCase):
    def test_youtube_video_id_is_preserved(self):
        url = "https://www.youtube.com/watch?v=abc123&utm_source=test"
        self.assertEqual(enrich.normalize_url(url), "https://www.youtube.com/watch?v=abc123")

    def test_tracking_query_is_removed_from_regular_url(self):
        url = "https://x.com/example/status/1?s=20&utm_source=test"
        self.assertEqual(enrich.normalize_url(url), "https://x.com/example/status/1")

    def test_intro_is_removed_and_h2_stops_entry(self):
        digest = """# 日报

### P1｜测试栏目

栏目：这是重复的栏目介绍。
这里是需要保留的中文摘要。
[原文](https://example.com/item)

## 近期论文

不应进入上一条。
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-07-17-ai-signal.md"
            path.write_text(digest, encoding="utf-8")
            sections = enrich.parse_digest(path)
        self.assertEqual(len(sections), 1)
        self.assertNotIn("栏目：", sections[0]["body"])
        self.assertNotIn("近期论文", sections[0]["body"])
        self.assertIn("这里是需要保留的中文摘要。", sections[0]["body"])


if __name__ == "__main__":
    unittest.main()
