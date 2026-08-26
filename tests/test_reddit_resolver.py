import unittest
import sys
import importlib
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

reddit_artifacts = importlib.import_module("reddit_artifacts")
GalleryArtifact = reddit_artifacts.GalleryArtifact
ImageArtifact = reddit_artifacts.ImageArtifact
TextArtifact = reddit_artifacts.TextArtifact
VideoArtifact = reddit_artifacts.VideoArtifact
RedditResolver = importlib.import_module("reddit_resolver").RedditResolver


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
            "gallery_data": {
                "items": [{"media_id": "m1"}, {"media_id": "m2"}],
            },
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
            "media": {
                "reddit_video": {
                    "fallback_url": "https://v.redd.it/abc/DASH_720.mp4",
                    "dash_url": "https://v.redd.it/abc/DASHPlaylist.mpd",
                }
            },
        }
        artifacts = await self.resolver.resolve("https://reddit.com/test")
        self.assertEqual(len(artifacts), 1)
        self.assertIsInstance(artifacts[0], VideoArtifact)
        self.assertEqual(
            artifacts[0].dash_url,
            "https://v.redd.it/abc/DASHPlaylist.mpd",
        )

        self.client.fetch_post_data.return_value = {
            "title": "Gif post",
            "url_overridden_by_dest": "https://i.redd.it/test.gif",
        }
        artifacts = await self.resolver.resolve("https://reddit.com/test2")
        self.assertEqual(len(artifacts), 1)
        self.assertIsInstance(artifacts[0], VideoArtifact)

    async def test_resolve_image_with_text_returns_both_artifacts(
        self,
    ) -> None:
        self.client.fetch_post_data.return_value = {
            "title": "Image and text",
            "selftext": "Post body",
            "permalink": "/r/python/comments/abc/post",
            "url_overridden_by_dest": "https://i.redd.it/test.jpg",
        }
        artifacts = await self.resolver.resolve(
            "https://reddit.com/test-image-text"
        )
        self.assertEqual(len(artifacts), 2)
        self.assertIsInstance(artifacts[0], ImageArtifact)
        self.assertIsInstance(artifacts[1], TextArtifact)

    async def test_resolve_handles_nullable_media_blocks(self) -> None:
        self.client.fetch_post_data.return_value = {
            "title": "Nullable media",
            "media": None,
            "preview": None,
        }
        artifacts = await self.resolver.resolve("https://reddit.com/test3")
        self.assertEqual(artifacts, [])


if __name__ == "__main__":
    unittest.main()
