import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from providers.instagram.detector import (
    canonical_url,
    extract_media,
    is_instagram_url,
)


class InstagramDetectorTests(unittest.TestCase):
    def test_extract_media_from_reel(self) -> None:
        self.assertEqual(
            extract_media("https://www.instagram.com/reel/C9aBcDeFgHi/"),
            ("reel", "C9aBcDeFgHi"),
        )

    def test_extract_media_from_reels_with_query(self) -> None:
        self.assertEqual(
            extract_media(
                "https://www.instagram.com/reels/C9aBcDeFgHi/?igsh=abc"
            ),
            ("reel", "C9aBcDeFgHi"),
        )

    def test_extract_media_from_user_prefixed_reel(self) -> None:
        self.assertEqual(
            extract_media("https://instagram.com/someuser/reel/C9aBcDeFgHi/"),
            ("reel", "C9aBcDeFgHi"),
        )

    def test_extract_media_from_post_and_tv(self) -> None:
        self.assertEqual(
            extract_media("https://m.instagram.com/p/C9aBcDeFgHi/"),
            ("p", "C9aBcDeFgHi"),
        )
        self.assertEqual(
            extract_media("https://www.instagram.com/tv/C9aBcDeFgHi/"),
            ("tv", "C9aBcDeFgHi"),
        )

    def test_rejects_non_media_urls(self) -> None:
        self.assertIsNone(extract_media("https://www.instagram.com/someuser/"))
        self.assertIsNone(
            extract_media("https://www.instagram.com/stories/user/123/")
        )
        self.assertIsNone(
            extract_media("https://www.instagram.com/share/C9aBcDeFgHi/")
        )
        self.assertIsNone(extract_media("https://example.com/reel/C9aBcDeFg/"))
        self.assertIsNone(extract_media("https://www.instagram.com/reel/ab/"))

    def test_is_instagram_url(self) -> None:
        self.assertTrue(
            is_instagram_url("https://www.instagram.com/reel/C9aBcDeFgHi/")
        )
        self.assertFalse(
            is_instagram_url("https://www.instagram.com/explore/")
        )

    def test_canonical_url(self) -> None:
        self.assertEqual(
            canonical_url("https://instagram.com/someuser/reels/C9aBcDeFgHi"),
            "https://www.instagram.com/reel/C9aBcDeFgHi/",
        )
        self.assertIsNone(canonical_url("https://www.instagram.com/someuser/"))


if __name__ == "__main__":
    unittest.main()
