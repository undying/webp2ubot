import unittest
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reddit_artifacts import GalleryArtifact, ImageArtifact, TextArtifact, VideoArtifact
from reddit_resolver import RedditResolver


class RedditResolverTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = AsyncMock()
        self.resolver = RedditResolver(self.client)

    async def test_resolve_single_image(self) -> None:
        self.client.fetch_post_data.return_value = {
            "title": "Image post",
            "url_overridden_by_dest": "https://i.redd.it/test.jpg",
        }
        artifacts = await self.resolver.resolve("https://reddit.com/test")
        self.assertEqual(len(artifacts), 1)
        self.assertIsInstance(artifacts[0], ImageArtifact)

    async def test_resolve_gallery(self) -> None:
        self.client.fetch_post_data.return_value = {
            "title": "Gallery post",
            "is_gallery": True,
            "gallery_data": {"items": [{"media_id": "m1"}, {"media_id": "m2"}]},
            "media_metadata": {
                "m1": {"s": {"u": "https://i.redd.it/1.jpg"}},
                "m2": {"s": {"u": "https://i.redd.it/2.jpg"}},
            },
        }
        artifacts = await self.resolver.resolve("https://reddit.com/test")
        self.assertEqual(len(artifacts), 1)
        self.assertIsInstance(artifacts[0], GalleryArtifact)
        self.assertEqual(len(artifacts[0].items), 2)

    async def test_resolve_text_post(self) -> None:
        self.client.fetch_post_data.return_value = {
            "title": "Text post",
            "is_self": True,
            "selftext": "Body",
            "permalink": "/r/python/comments/abc/post",
        }
        artifacts = await self.resolver.resolve("https://reddit.com/test")
        self.assertEqual(len(artifacts), 1)
        self.assertIsInstance(artifacts[0], TextArtifact)

    async def test_resolve_video_and_gif(self) -> None:
        self.client.fetch_post_data.return_value = {
            "title": "Video post",
            "media": {"reddit_video": {"fallback_url": "https://v.redd.it/abc/DASH_720.mp4"}},
        }
        artifacts = await self.resolver.resolve("https://reddit.com/test")
        self.assertEqual(len(artifacts), 1)
        self.assertIsInstance(artifacts[0], VideoArtifact)

        self.client.fetch_post_data.return_value = {
            "title": "Gif post",
            "url_overridden_by_dest": "https://i.redd.it/test.gif",
        }
        artifacts = await self.resolver.resolve("https://reddit.com/test2")
        self.assertEqual(len(artifacts), 1)
        self.assertIsInstance(artifacts[0], VideoArtifact)


if __name__ == "__main__":
    unittest.main()
