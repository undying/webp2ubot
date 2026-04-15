import unittest
import sys
import importlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

telegram_error = importlib.import_module("telegram.error")
BadRequest = telegram_error.BadRequest

reddit_artifacts = importlib.import_module("reddit_artifacts")
GalleryArtifact = reddit_artifacts.GalleryArtifact
ImageArtifact = reddit_artifacts.ImageArtifact
TextArtifact = reddit_artifacts.TextArtifact
VideoArtifact = reddit_artifacts.VideoArtifact
reddit_sender = importlib.import_module("reddit_sender")
MAX_GALLERY_ITEMS = reddit_sender.MAX_GALLERY_ITEMS
MAX_MEDIA_CAPTION_LENGTH = reddit_sender.MAX_MEDIA_CAPTION_LENGTH
RedditSender = reddit_sender.RedditSender


class RedditSenderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.sender = RedditSender()
        self.message = AsyncMock()
        self.message.message_id = 777

    async def test_send_text(self) -> None:
        artifact = TextArtifact(
            title="Title",
            body="Body",
            post_url="https://reddit.com/post",
        )
        await self.sender.send(self.message, [artifact])
        self.message.reply_text.assert_awaited_once()
        _, kwargs = self.message.reply_text.await_args
        self.assertEqual(kwargs["reply_to_message_id"], 777)

    async def test_send_gallery_uses_media_group(self) -> None:
        items = [
            ImageArtifact(url=f"https://i.redd.it/{index}.jpg")
            for index in range(MAX_GALLERY_ITEMS + 2)
        ]
        artifact = GalleryArtifact(items=items, caption="caption")
        self.sender._download_content = AsyncMock(return_value=b"img")

        await self.sender.send(self.message, [artifact])

        self.message.reply_media_group.assert_awaited_once()
        _, kwargs = self.message.reply_media_group.await_args
        self.assertEqual(len(kwargs["media"]), MAX_GALLERY_ITEMS)
        self.assertEqual(kwargs["reply_to_message_id"], 777)

    async def test_send_video_fallback_to_conversion(self) -> None:
        artifact = VideoArtifact(
            url="https://v.redd.it/test.mp4",
            caption="video",
        )
        self.sender._download_content = AsyncMock(return_value=b"video-bytes")
        self.message.reply_video = AsyncMock(
            side_effect=[BadRequest("bad format"), None]
        )

        with patch.object(
            self.sender,
            "_convert_video_bytes_to_mp4",
            return_value=b"mp4-bytes",
        ):
            await self.sender.send(self.message, [artifact])

        self.assertEqual(self.message.reply_video.await_count, 2)
        for _, kwargs in self.message.reply_video.await_args_list:
            self.assertEqual(kwargs["reply_to_message_id"], 777)

    async def test_send_video_uses_dash_mux_when_available(self) -> None:
        artifact = VideoArtifact(
            url="https://v.redd.it/test.mp4",
            caption="video",
            dash_url="https://v.redd.it/test/DASHPlaylist.mpd",
        )
        self.message.reply_video = AsyncMock(return_value=None)
        self.sender._download_content = AsyncMock(return_value=b"downloaded")

        with patch.object(
            self.sender,
            "_mux_dash_to_mp4_bytes",
            return_value=b"muxed",
        ) as dash_mux:
            await self.sender.send(self.message, [artifact])

        dash_mux.assert_called_once_with(
            "https://v.redd.it/test/DASHPlaylist.mpd"
        )
        self.sender._download_content.assert_not_called()
        self.message.reply_video.assert_awaited_once()

    async def test_send_merges_selftext_into_media_caption_when_fits(
        self,
    ) -> None:
        image_artifact = ImageArtifact(
            url="https://i.redd.it/test.jpg",
            caption="Title",
        )
        text_artifact = TextArtifact(
            title="Title",
            body="Short body",
            post_url="https://reddit.com/post",
        )
        self.sender._download_content = AsyncMock(return_value=b"img")

        await self.sender.send(self.message, [image_artifact, text_artifact])

        self.message.reply_photo.assert_awaited_once()
        self.message.reply_text.assert_not_called()
        _, kwargs = self.message.reply_photo.await_args
        self.assertEqual(kwargs["caption"], "Title\n\nShort body")

    async def test_send_keeps_separate_text_when_selftext_too_long(
        self,
    ) -> None:
        image_artifact = ImageArtifact(
            url="https://i.redd.it/test.jpg",
            caption="Title",
        )
        long_body = "x" * (MAX_MEDIA_CAPTION_LENGTH + 10)
        text_artifact = TextArtifact(
            title="Title",
            body=long_body,
            post_url="https://reddit.com/post",
        )
        self.sender._download_content = AsyncMock(return_value=b"img")

        await self.sender.send(self.message, [image_artifact, text_artifact])

        self.message.reply_photo.assert_awaited_once()
        self.message.reply_text.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
