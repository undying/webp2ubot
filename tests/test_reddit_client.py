import unittest
import sys
import importlib
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

reddit_client = importlib.import_module("providers.reddit.client")
PublicRedditClient = reddit_client.PublicRedditClient
RedditClient = reddit_client.RedditClient
build_reddit_client = reddit_client.build_reddit_client
REDDIT_DEFAULT_USER_AGENT = reddit_client.get_reddit_user_agent()


class RedditClientFactoryTests(unittest.TestCase):
    def test_build_reddit_client_uses_oauth_when_env_present(self) -> None:
        env = {
            "REDDIT_CLIENT_ID": "client-id",
            "REDDIT_CLIENT_SECRET": "client-secret",
        }
        with patch.dict("os.environ", env, clear=True):
            client, mode = build_reddit_client()
        self.assertIsInstance(client, RedditClient)
        self.assertEqual(mode, "oauth")
        self.assertEqual(client.user_agent, REDDIT_DEFAULT_USER_AGENT)

    def test_build_client_fallbacks_to_public_json_anonymous(
        self,
    ) -> None:
        with patch.dict("os.environ", {}, clear=True):
            client, mode = build_reddit_client()
        self.assertIsInstance(client, PublicRedditClient)
        self.assertEqual(mode, "public_json_anonymous")
        self.assertIsNone(client.cookie)

    def test_build_reddit_client_uses_public_cookie_when_present(self) -> None:
        with patch.dict(
            "os.environ",
            {"REDDIT_PUBLIC_COOKIE": "reddit_session=abc; token_v2=def"},
            clear=True,
        ):
            client, mode = build_reddit_client()
        self.assertIsInstance(client, PublicRedditClient)
        self.assertEqual(mode, "public_json_cookie")
        self.assertEqual(client.cookie, "reddit_session=abc; token_v2=def")

    def test_public_json_url_builder(self) -> None:
        post_url = "https://redd.it/abc123"
        actual = PublicRedditClient._post_json_url(post_url)
        self.assertEqual(actual, "https://www.reddit.com/abc123.json")

    def test_share_url_resolution_detection(self) -> None:
        self.assertTrue(
            PublicRedditClient._requires_share_resolution(
                "https://www.reddit.com/r/Catswithjobs/s/wASl5QzV9k"
            )
        )
        self.assertFalse(
            PublicRedditClient._requires_share_resolution(
                "https://www.reddit.com/r/Catswithjobs/comments/1sm8d2o/post/"
            )
        )

    def test_public_headers_include_cookie_and_referer(self) -> None:
        client = PublicRedditClient(
            user_agent="UA",
            cookie="reddit_session=abc",
            referer="https://www.reddit.com/",
        )
        headers = client._build_headers()
        self.assertEqual(headers["User-Agent"], "UA")
        self.assertEqual(headers["Cookie"], "reddit_session=abc")
        self.assertEqual(headers["Referer"], "https://www.reddit.com/")


if __name__ == "__main__":
    unittest.main()
