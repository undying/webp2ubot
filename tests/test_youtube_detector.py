import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from providers.youtube.detector import (
    extract_video_id,
    is_shorts_url,
    is_youtube_url,
)


class YoutubeDetectorTests(unittest.TestCase):
    def test_extract_video_id_from_shorts(self) -> None:
        self.assertEqual(
            extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_extract_video_id_from_watch(self) -> None:
        self.assertEqual(
            extract_video_id(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s"
            ),
            "dQw4w9WgXcQ",
        )

    def test_extract_video_id_from_short_host(self) -> None:
        self.assertEqual(
            extract_video_id("https://youtu.be/dQw4w9WgXcQ?si=abc"),
            "dQw4w9WgXcQ",
        )

    def test_extract_video_id_from_embed_and_live(self) -> None:
        self.assertEqual(
            extract_video_id("https://m.youtube.com/embed/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )
        self.assertEqual(
            extract_video_id("https://www.youtube.com/live/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_rejects_non_video_urls(self) -> None:
        self.assertIsNone(extract_video_id("https://www.youtube.com/@channel"))
        self.assertIsNone(extract_video_id("https://example.com/watch?v=abc"))
        self.assertIsNone(extract_video_id("https://www.youtube.com/watch"))
        self.assertIsNone(extract_video_id("https://youtu.be/short"))

    def test_is_youtube_url(self) -> None:
        self.assertTrue(
            is_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ")
        )
        self.assertFalse(is_youtube_url("https://www.youtube.com/feed/trending"))

    def test_is_shorts_url(self) -> None:
        self.assertTrue(
            is_shorts_url("https://www.youtube.com/shorts/dQw4w9WgXcQ")
        )
        self.assertFalse(
            is_shorts_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        )


if __name__ == "__main__":
    unittest.main()
