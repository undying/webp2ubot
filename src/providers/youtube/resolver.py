import asyncio
import logging
import os
import tempfile
from typing import Any

from core.artifacts import (
    Artifact,
    TEMP_DIR_PREFIX,
    TextArtifact,
    VideoArtifact,
    remove_temp_dir,
)
from providers.youtube.cookies import guarded_cookies
from providers.youtube.detector import extract_video_id

logger = logging.getLogger(__name__)


class YoutubeResolver:
    def __init__(
        self,
        max_duration_sec: int,
        max_filesize_bytes: int,
        cookies_file: str | None = None,
        remote_components: list[str] | None = None,
    ) -> None:
        self.max_duration_sec = max_duration_sec
        self.max_filesize_bytes = max_filesize_bytes
        self.cookies_file = cookies_file
        self.remote_components = remote_components or []

    async def resolve(self, url: str) -> list[Artifact]:
        video_id = extract_video_id(url)
        if not video_id:
            return []
        canonical_url = f"https://www.youtube.com/watch?v={video_id}"

        info = await asyncio.to_thread(self._extract_info, canonical_url)
        if not info:
            return []

        duration = int(info.get("duration") or 0)
        if duration > self.max_duration_sec:
            return self._reject(info, canonical_url, self._too_long(duration))

        download_dir = tempfile.mkdtemp(prefix=f"{TEMP_DIR_PREFIX}youtube_")
        try:
            info = await asyncio.to_thread(
                self._download,
                canonical_url,
                download_dir,
            )
            file_path = self._downloaded_path(info)
            if not file_path:
                logger.warning(
                    "yt-dlp produced no file for url=%s",
                    canonical_url,
                )
                remove_temp_dir(download_dir)
                return []

            file_size = os.path.getsize(file_path)
            if file_size > self.max_filesize_bytes:
                logger.warning(
                    "YouTube video too large url=%s size=%s",
                    canonical_url,
                    file_size,
                )
                remove_temp_dir(download_dir)
                return self._reject(
                    info,
                    canonical_url,
                    f"Файл весит {file_size / (1024 * 1024):.1f} МБ, "
                    f"лимит {self.max_filesize_bytes // (1024 * 1024)} МБ.",
                )
        except Exception:
            remove_temp_dir(download_dir)
            raise

        return [
            VideoArtifact(
                url=canonical_url,
                caption=str(info.get("title") or "").strip() or None,
                file_path=file_path,
            )
        ]

    def _too_long(self, duration: int) -> str:
        return (
            f"Длительность {duration // 60}:{duration % 60:02d}, "
            f"лимит {self.max_duration_sec // 60} мин."
        )

    @staticmethod
    def _reject(
        info: dict[str, Any],
        url: str,
        reason: str,
    ) -> list[Artifact]:
        title = str(info.get("title") or "").strip()
        body = f"Не отправляю видео файлом. {reason}"
        return [TextArtifact(title=title, body=body, post_url=url)]

    def _ydl_options(self, download_dir: str | None) -> dict[str, Any]:
        max_mb = self.max_filesize_bytes // (1024 * 1024)
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "logger": logger,
            "format": (
                f"bv*[filesize_approx<{max_mb}M][vcodec^=avc1]"
                f"+ba[ext=m4a]/"
                f"b[filesize_approx<{max_mb}M][ext=mp4]/"
                f"b[ext=mp4]/b"
            ),
            "merge_output_format": "mp4",
        }
        if download_dir:
            options["paths"] = {"home": download_dir}
            options["outtmpl"] = {"default": "%(id)s.%(ext)s"}
        if self.cookies_file:
            options["cookiefile"] = self.cookies_file
        if self.remote_components:
            options["remote_components"] = self.remote_components
        return options

    def _extract_info(self, url: str) -> dict[str, Any] | None:
        from yt_dlp import YoutubeDL

        with guarded_cookies(self.cookies_file):
            with YoutubeDL(self._ydl_options(None)) as ydl:
                info = ydl.extract_info(url, download=False)
        if not isinstance(info, dict):
            return None
        return info

    def _download(self, url: str, download_dir: str) -> dict[str, Any]:
        from yt_dlp import YoutubeDL

        with guarded_cookies(self.cookies_file):
            with YoutubeDL(self._ydl_options(download_dir)) as ydl:
                info = ydl.extract_info(url, download=True)
        return info if isinstance(info, dict) else {}

    @staticmethod
    def _downloaded_path(info: dict[str, Any]) -> str | None:
        downloads = info.get("requested_downloads") or []
        for item in downloads:
            if not isinstance(item, dict):
                continue
            file_path = item.get("filepath")
            if file_path and os.path.exists(str(file_path)):
                return str(file_path)
        return None
