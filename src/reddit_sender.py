import io
import tempfile
from html import escape
from typing import Iterable
from urllib.parse import urlparse

import aiohttp
import ffmpeg
from telegram import InputMediaPhoto, Message
from telegram.error import BadRequest

from reddit_artifacts import (
    GalleryArtifact,
    ImageArtifact,
    TextArtifact,
    VideoArtifact,
)


MAX_TEXT_REPLY_LENGTH = 4096
MAX_MEDIA_CAPTION_LENGTH = 1024
MAX_GALLERY_ITEMS = 10
MAX_DOWNLOAD_BYTES = 40 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 4096


class DownloadError(Exception):
    pass


class RedditSender:
    def __init__(
        self,
        request_timeout: int = 12,
        retry_count: int = 2,
    ) -> None:
        self.request_timeout = request_timeout
        self.retry_count = retry_count

    async def send(
        self,
        message: Message,
        artifacts: Iterable[
            ImageArtifact | GalleryArtifact | TextArtifact | VideoArtifact
        ],
    ) -> None:
        artifact_list = list(artifacts)
        index = 0
        while index < len(artifact_list):
            artifact = artifact_list[index]
            next_artifact = (
                artifact_list[index + 1]
                if index + 1 < len(artifact_list)
                else None
            )
            if self._is_media_artifact(artifact) and isinstance(
                next_artifact,
                TextArtifact,
            ):
                merged_caption = self._merge_caption_with_selftext(
                    self._media_caption(artifact),
                    next_artifact.body,
                )
                if merged_caption is not None:
                    self._set_media_caption(artifact, merged_caption)
                    index += 1
            if isinstance(artifact, GalleryArtifact):
                await self._send_gallery(message, artifact)
            elif isinstance(artifact, ImageArtifact):
                await self._send_image(message, artifact)
            elif isinstance(artifact, VideoArtifact):
                await self._send_video(message, artifact)
            elif isinstance(artifact, TextArtifact):
                await self._send_text(message, artifact)
            index += 1

    async def _send_image(
        self,
        message: Message,
        artifact: ImageArtifact,
    ) -> None:
        payload = await self._download_content(artifact.url)
        image_stream = io.BytesIO(payload)
        image_stream.name = self._file_name_from_url(
            artifact.url,
            "reddit.jpg",
        )
        caption = self._truncate_media_caption(artifact.caption)
        await message.reply_photo(
            photo=image_stream,
            caption=caption,
            **self._reply_kwargs(message),
        )

    async def _send_gallery(
        self,
        message: Message,
        artifact: GalleryArtifact,
    ) -> None:
        items = artifact.items[:MAX_GALLERY_ITEMS]
        media_group = []
        buffers: list[io.BytesIO] = []
        for index, item in enumerate(items):
            payload = await self._download_content(item.url)
            image_stream = io.BytesIO(payload)
            image_stream.name = self._file_name_from_url(
                item.url,
                f"gallery_{index}.jpg",
            )
            buffers.append(image_stream)
            image_caption = None
            if index == 0:
                image_caption = self._truncate_media_caption(artifact.caption)
            media_group.append(
                InputMediaPhoto(
                    media=image_stream,
                    caption=image_caption,
                )
            )
        if media_group:
            await message.reply_media_group(
                media=media_group,
                **self._reply_kwargs(message),
            )
        for buffer in buffers:
            buffer.close()

    async def _send_text(
        self,
        message: Message,
        artifact: TextArtifact,
    ) -> None:
        chunks = []
        if artifact.title:
            chunks.append(f"<b>{escape(artifact.title)}</b>")
        if artifact.body:
            chunks.append(escape(artifact.body))
        if artifact.post_url:
            chunks.append(escape(artifact.post_url))
        text = "\n\n".join(chunks)
        if len(text) > MAX_TEXT_REPLY_LENGTH:
            text = text[: MAX_TEXT_REPLY_LENGTH - 1]
        await message.reply_text(
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            **self._reply_kwargs(message),
        )

    async def _send_video(
        self,
        message: Message,
        artifact: VideoArtifact,
    ) -> None:
        payload = await self._download_content(artifact.url)
        video_stream = io.BytesIO(payload)
        video_stream.name = self._file_name_from_url(
            artifact.url,
            "reddit.mp4",
        )
        caption = self._truncate_media_caption(artifact.caption)
        try:
            await message.reply_video(
                video=video_stream,
                caption=caption,
                **self._reply_kwargs(message),
            )
            return
        except BadRequest:
            converted_bytes = self._convert_video_bytes_to_mp4(payload)
            converted_stream = io.BytesIO(converted_bytes)
            converted_stream.name = "reddit.mp4"
            await message.reply_video(
                video=converted_stream,
                caption=caption,
                **self._reply_kwargs(message),
            )
        finally:
            video_stream.close()

    async def _download_content(self, url: str) -> bytes:
        last_exception: Exception | None = None
        headers = {"User-Agent": "webp2u-reddit-sender/1.0"}
        for _ in range(self.retry_count + 1):
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(
                        url,
                        timeout=self.request_timeout,
                    ) as response:
                        response.raise_for_status()
                        parts = []
                        received_bytes = 0
                        async for chunk in response.content.iter_chunked(
                            DOWNLOAD_CHUNK_BYTES
                        ):
                            received_bytes += len(chunk)
                            if received_bytes > MAX_DOWNLOAD_BYTES:
                                raise DownloadError(
                                    "Downloaded file exceeds limit"
                                )
                            parts.append(chunk)
                        return b"".join(parts)
            except Exception as exc:
                last_exception = exc
        if last_exception:
            raise last_exception
        raise DownloadError("Failed to download remote file")

    @staticmethod
    def _truncate_media_caption(caption: str | None) -> str | None:
        if not caption:
            return None
        if len(caption) <= MAX_MEDIA_CAPTION_LENGTH:
            return caption
        return caption[: MAX_MEDIA_CAPTION_LENGTH - 1]

    @staticmethod
    def _file_name_from_url(url: str, fallback: str) -> str:
        parsed = urlparse(url)
        candidate = parsed.path.rsplit("/", maxsplit=1)[-1]
        if not candidate:
            return fallback
        return candidate

    @staticmethod
    def _convert_video_bytes_to_mp4(payload: bytes) -> bytes:
        input_file = tempfile.NamedTemporaryFile(mode="w+b")
        output_file = tempfile.NamedTemporaryFile(mode="w+b")
        try:
            input_file.write(payload)
            input_file.flush()
            (
                ffmpeg
                .input(input_file.name)
                .output(output_file.name, format="mp4", vcodec="libx264")
                .overwrite_output()
                .run()
            )
            output_file.seek(0)
            return output_file.read()
        finally:
            input_file.close()
            output_file.close()

    @staticmethod
    def _reply_kwargs(message: Message) -> dict[str, int]:
        if message.message_id is None:
            return {}
        return {"reply_to_message_id": message.message_id}

    @staticmethod
    def _is_media_artifact(
        artifact: (
            ImageArtifact | GalleryArtifact | TextArtifact | VideoArtifact
        ),
    ) -> bool:
        return isinstance(
            artifact,
            (ImageArtifact, GalleryArtifact, VideoArtifact),
        )

    @staticmethod
    def _media_caption(
        artifact: ImageArtifact | GalleryArtifact | VideoArtifact,
    ) -> str | None:
        return artifact.caption

    @staticmethod
    def _set_media_caption(
        artifact: ImageArtifact | GalleryArtifact | VideoArtifact,
        caption: str,
    ) -> None:
        artifact.caption = caption

    @staticmethod
    def _merge_caption_with_selftext(
        media_caption: str | None,
        selftext: str,
    ) -> str | None:
        body = selftext.strip()
        if not body:
            return media_caption
        caption_parts = []
        if media_caption and media_caption.strip():
            caption_parts.append(media_caption.strip())
        caption_parts.append(body)
        merged = "\n\n".join(caption_parts)
        if len(merged) > MAX_MEDIA_CAPTION_LENGTH:
            return None
        return merged
