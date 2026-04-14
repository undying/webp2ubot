import unittest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telegram.error import BadRequest

from reddit_artifacts import GalleryArtifact, ImageArtifact, TextArtifact, VideoArtifact
from reddit_sender import MAX_GALLERY_ITEMS, RedditSender


class RedditSenderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.sender = RedditSender()
        self.message = AsyncMock()

    async def test_send_text(self) -> None:
        artifact = TextArtifact(title="Title", body="Body", post_url="https://reddit.com/post")
        await self.sender.send(self.message, [artifact])
        self.message.reply_text.assert_awaited_once()

    async def test_send_gallery_uses_media_group(self) -> None:
        items = [ImageArtifact(url=f"https://i.redd.it/{index}.jpg") for index in range(MAX_GALLERY_ITEMS + 2)]
        artifact = GalleryArtifact(items=items, caption="caption")
        self.sender._download_content = AsyncMock(return_value=b"img")

        await self.sender.send(self.message, [artifact])

        self.message.reply_media_group.assert_awaited_once()
        _, kwargs = self.message.reply_media_group.await_args
        self.assertEqual(len(kwargs["media"]), MAX_GALLERY_ITEMS)

    async def test_send_video_fallback_to_conversion(self) -> None:
        artifact = VideoArtifact(url="https://v.redd.it/test.mp4", caption="video")
        self.sender._download_content = AsyncMock(return_value=b"video-bytes")
        self.message.reply_video = AsyncMock(side_effect=[BadRequest("bad format"), None])

        with patch.object(self.sender, "_convert_video_bytes_to_mp4", return_value=b"mp4-bytes"):
            await self.sender.send(self.message, [artifact])

        self.assertEqual(self.message.reply_video.await_count, 2)


if __name__ == "__main__":
    unittest.main()
