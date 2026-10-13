import asyncio
import logging
import os
import tempfile
from typing import Any

from core.artifacts import (
    Artifact,
    GalleryArtifact,
    ImageArtifact,
    TEMP_DIR_PREFIX,
    TextArtifact,
    VideoArtifact,
    remove_temp_dir,
)
from providers.instagram.cookies import guarded_cookies
from providers.instagram.detector import canonical_url

logger = logging.getLogger(__name__)

MAX_VIDEO_ITEMS = 3


class InstagramResolver:
    def __init__(
        self,
        max_duration_sec: int,
        max_filesize_bytes: int,
        cookies_file: str | None = None,
    ) -> None:
        self.max_duration_sec = max_duration_sec
        self.max_filesize_bytes = max_filesize_bytes
        self.cookies_file = cookies_file

    async def resolve(self, url: str) -> list[Artifact]:
        post_url = canonical_url(url)
        if not post_url:
            return []

        info = await asyncio.to_thread(self._extract_info, post_url)
        if not info:
            return []

        entries = self._entries(info)
        caption = self._caption(info)
        artifacts: list[Artifact] = []
        images: list[ImageArtifact] = []
        rejections: list[str] = []
        videos_taken = 0

        for index, entry in enumerate(entries):
            image_url = self._image_url(entry)
            if not entry.get("formats"):
                if image_url:
                    images.append(ImageArtifact(url=image_url))
                continue

            if videos_taken >= MAX_VIDEO_ITEMS:
                logger.info(
                    "Skipping video %s of carousel url=%s, limit %s reached",
                    index + 1,
                    post_url,
                    MAX_VIDEO_ITEMS,
                )
                continue

            duration = int(entry.get("duration") or 0)
            if duration > self.max_duration_sec:
                rejections.append(self._too_long(duration))
                continue

            video = await self._fetch_video(
                post_url,
                index if len(entries) > 1 else None,
            )
            if isinstance(video, str):
                rejections.append(video)
                continue
            if video:
                artifacts.append(video)
                videos_taken += 1

        artifacts.extend(self._gallery(images))

        if not artifacts:
            if rejections:
                return [
                    TextArtifact(
                        title=caption or "",
                        body=f"Не отправляю видео файлом. {rejections[0]}",
                        post_url=post_url,
                    )
                ]
            logger.info("Instagram post has no media url=%s", post_url)
            return []

        if caption:
            self._set_caption(artifacts[0], caption)
        return artifacts

    async def _fetch_video(
        self,
        post_url: str,
        entry_index: int | None,
    ) -> VideoArtifact | str | None:
        """Download one video; a string means it was rejected with a reason."""

        download_dir = tempfile.mkdtemp(prefix=f"{TEMP_DIR_PREFIX}instagram_")
        try:
            info = await asyncio.to_thread(
                self._download,
                post_url,
                download_dir,
                entry_index,
            )
            file_path = self._downloaded_path(info)
            if not file_path:
                logger.warning(
                    "yt-dlp produced no file for url=%s item=%s",
                    post_url,
                    entry_index,
                )
                remove_temp_dir(download_dir)
                return None

            file_size = os.path.getsize(file_path)
            if file_size > self.max_filesize_bytes:
                logger.warning(
                    "Instagram video too large url=%s size=%s",
                    post_url,
                    file_size,
                )
                remove_temp_dir(download_dir)
                return (
                    f"Файл весит {file_size / (1024 * 1024):.1f} МБ, "
                    f"лимит {self.max_filesize_bytes // (1024 * 1024)} МБ."
                )
        except Exception:
            remove_temp_dir(download_dir)
            raise

        return VideoArtifact(url=post_url, file_path=file_path)

    def _too_long(self, duration: int) -> str:
        return (
            f"Длительность {duration // 60}:{duration % 60:02d}, "
            f"лимит {self.max_duration_sec // 60} мин."
        )

    @staticmethod
    def _entries(info: dict[str, Any]) -> list[dict[str, Any]]:
        if info.get("_type") != "playlist":
            return [info]
        entries = info.get("entries") or []
        return [entry for entry in entries if isinstance(entry, dict)]

    @staticmethod
    def _caption(info: dict[str, Any]) -> str | None:
        description = str(info.get("description") or "").strip()
        if description:
            return description
        return str(info.get("title") or "").strip() or None

    @staticmethod
    def _image_url(entry: dict[str, Any]) -> str | None:
        thumbnails = [
            thumbnail
            for thumbnail in entry.get("thumbnails") or []
            if isinstance(thumbnail, dict) and thumbnail.get("url")
        ]
        if thumbnails:
            return str(thumbnails[-1]["url"])
        return str(entry.get("thumbnail") or "") or None

    @staticmethod
    def _gallery(images: list[ImageArtifact]) -> list[Artifact]:
        if not images:
            return []
        if len(images) == 1:
            return [images[0]]
        return [GalleryArtifact(items=images)]

    @staticmethod
    def _set_caption(artifact: Artifact, caption: str) -> None:
        media_types = (ImageArtifact, GalleryArtifact, VideoArtifact)
        if isinstance(artifact, media_types):
            artifact.caption = caption

    def _ydl_options(
        self,
        download_dir: str | None,
        entry_index: int | None = None,
    ) -> dict[str, Any]:
        max_mb = self.max_filesize_bytes // (1024 * 1024)
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": False,
            "logger": logger,
            "format": (
                f"bv*[filesize_approx<{max_mb}M][vcodec^=avc1]"
                f"+ba[ext=m4a]/"
                f"bv*[filesize_approx<{max_mb}M]+ba/"
                f"b[filesize_approx<{max_mb}M]/"
                f"bv*+ba/b"
            ),
            "merge_output_format": "mp4",
        }
        if download_dir:
            options["paths"] = {"home": download_dir}
            options["outtmpl"] = {"default": "%(id)s.%(ext)s"}
        if entry_index is not None:
            options["playlist_items"] = str(entry_index + 1)
        if self.cookies_file:
            options["cookiefile"] = self.cookies_file
        return options

    def _extract_info(self, url: str) -> dict[str, Any] | None:
        from yt_dlp import YoutubeDL

        with guarded_cookies(self.cookies_file):
            with YoutubeDL(self._ydl_options(None)) as ydl:
                info = ydl.extract_info(url, download=False, process=False)
        if not isinstance(info, dict):
            return None
        return info

    def _download(
        self,
        url: str,
        download_dir: str,
        entry_index: int | None,
    ) -> dict[str, Any]:
        from yt_dlp import YoutubeDL

        with guarded_cookies(self.cookies_file):
            options = self._ydl_options(download_dir, entry_index)
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
        return info if isinstance(info, dict) else {}

    @classmethod
    def _downloaded_path(cls, info: dict[str, Any]) -> str | None:
        downloads = info.get("requested_downloads") or []
        for item in downloads:
            if not isinstance(item, dict):
                continue
            file_path = item.get("filepath")
            if file_path and os.path.exists(str(file_path)):
                return str(file_path)
        for entry in info.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            file_path = cls._downloaded_path(entry)
            if file_path:
                return file_path
        return None
