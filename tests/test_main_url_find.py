import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from main import url_find


class _Entity:
    def __init__(self, url: str | None = None) -> None:
        self.url = url


class _Message:
    def __init__(self) -> None:
        self.text = "https://a.com/test https://reddit.com/r/x/comments/abc/title"

    def parse_entities(self, _types):
        return {
            _Entity(url="https://reddit.com/r/x/comments/abc/title"): "reddit",
            _Entity(url=None): "https://a.com/test",
        }


class UrlFindTests(unittest.TestCase):
    def test_url_find_deduplicates(self) -> None:
        urls = url_find(_Message())
        self.assertEqual(
            urls,
            [
                "https://reddit.com/r/x/comments/abc/title",
                "https://a.com/test",
            ],
        )


if __name__ == "__main__":
    unittest.main()
