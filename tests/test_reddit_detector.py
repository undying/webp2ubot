import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from providers.reddit.detector import is_reddit_url, normalize_reddit_url


class RedditDetectorTests(unittest.TestCase):
    def test_is_reddit_url_positive(self) -> None:
        self.assertTrue(is_reddit_url("https://www.reddit.com/r/python/comments/abc/test"))
        self.assertTrue(is_reddit_url("https://old.reddit.com/r/python/comments/abc/test"))
        self.assertTrue(is_reddit_url("https://redd.it/abc123"))

    def test_is_reddit_url_negative(self) -> None:
        self.assertFalse(is_reddit_url("https://example.com/post"))

    def test_normalize_reddit_url(self) -> None:
        actual = normalize_reddit_url("http://WWW.Reddit.com/r/python/comments/abc/test?x=1#fragment")
        self.assertEqual(actual, "http://www.reddit.com/r/python/comments/abc/test?x=1")


if __name__ == "__main__":
    unittest.main()
