import unittest
import sys
import importlib
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

reddit_client = importlib.import_module("reddit_client")
PublicRedditClient = reddit_client.PublicRedditClient
RedditClient = reddit_client.RedditClient
build_reddit_client = reddit_client.build_reddit_client


class RedditClientFactoryTests(unittest.TestCase):
    def test_build_reddit_client_uses_oauth_when_env_present(self) -> None:
        env = {
            "REDDIT_CLIENT_ID": "client-id",
            "REDDIT_CLIENT_SECRET": "client-secret",
            "REDDIT_USER_AGENT": "webp2u-test/1.0 by u/test",
        }
        with patch.dict("os.environ", env, clear=True):
            client, mode = build_reddit_client()
        self.assertIsInstance(client, RedditClient)
        self.assertEqual(mode, "oauth")

    def test_build_reddit_client_fallbacks_to_public_json(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            client, mode = build_reddit_client()
        self.assertIsInstance(client, PublicRedditClient)
        self.assertEqual(mode, "public_json")

    def test_public_json_url_builder(self) -> None:
        post_url = "https://redd.it/abc123"
        actual = PublicRedditClient._post_json_url(post_url)
        self.assertEqual(actual, "https://www.reddit.com/abc123.json")


if __name__ == "__main__":
    unittest.main()
